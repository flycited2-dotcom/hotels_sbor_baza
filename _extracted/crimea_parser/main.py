import asyncio
import glob
import os
import sys
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
from utils.browser import create_browser_context
from utils.storage import total, get_output_file, cross_source_merge
from utils.telegram_notify import notify as tg_notify
from utils import progress
from parsers import osm, wikidata, yandex_maps, search_engine, avito, sutochno, ostrovok, twogis
from parsers.email_finder import run_enrichment


# (label, runner, key) — key используется в env ONLY_SOURCE для точечного запуска.
RUNNERS = [
    ("OSM",                            osm.run,           "osm"),
    ("Wikidata",                       wikidata.run,      "wikidata"),
    ("Я.Карты",                        yandex_maps.run,   "yandex"),
    ("Поиск (Яндекс/Mail/Rambler/Bing)", search_engine.run, "search"),
    ("2ГИС",                           twogis.run,        "2gis"),
    ("Авито",                          avito.run,         "avito"),
    ("Суточно.ру",                     sutochno.run,      "sutochno"),
    ("Ostrovok",                       ostrovok.run,      "ostrovok"),
]


async def main():
    print("=" * 60)
    print("  CRIMEA HOTEL PARSER — запуск всех источников")
    print("=" * 60)

    headless_env = os.getenv("HEADLESS", "1").lower()
    headless = headless_env not in ("0", "false", "")

    only_source = (os.getenv("ONLY_SOURCE") or "").strip().lower()
    skip_enrichment = os.getenv("SKIP_ENRICHMENT", "0").lower() in ("1", "true", "yes")

    runners = RUNNERS
    if only_source:
        runners = [r for r in RUNNERS if r[2] == only_source]
        if not runners:
            print(f"⚠ ONLY_SOURCE={only_source!r} не совпадает ни с одним источником: "
                  f"{[r[2] for r in RUNNERS]}")
            return

    print(f"Headless: {headless}, ONLY_SOURCE: {only_source or '—'}, "
          f"SKIP_ENRICHMENT: {skip_enrichment}")
    print(f"Источники: {[r[0] for r in runners]}")

    progress.mark_started()

    async with async_playwright() as p:
        browser, context = await create_browser_context(p, headless=headless)
        try:
            for label, runner, _key in runners:
                progress.mark_stage(label)
                try:
                    await runner(context)
                    progress.mark_completed_source(label)
                except Exception as e:
                    print(f"\n[{label}] критическая ошибка: {e}")
                    import traceback
                    traceback.print_exc()
        finally:
            await browser.close()

    progress.mark_stage("cross_source_merge")
    print(f"\n✅ Собрано записей: {total()}")

    # Cross-source merge — подтягиваем недостающие phone/email/website
    # на записи Я.Карты/прочих из совпадающих по имени записей OSM/2ГИС.
    try:
        merged = cross_source_merge()
        if merged:
            print(f"🔗 Cross-source merge: обогащено {merged} ячеек")
    except Exception as e:
        print(f"[merge] ошибка: {e}")

    latest = get_output_file()
    enriched = None
    if not skip_enrichment and os.path.exists(latest):
        print(f"\n🔍 Запускаем Email Finder по: {latest}")
        enriched = await run_enrichment(latest)
    elif skip_enrichment:
        print("[email_finder] SKIP_ENRICHMENT=1 — пропускаем")

    progress.mark_stage("email_finder")
    final_csv = enriched or latest

    progress.mark_stage("xlsx")
    # XLSX-отчёт со вкладками по городам
    xlsx_path = ""
    if os.path.exists(final_csv):
        try:
            from utils.excel_export import build_xlsx
            xlsx_path = build_xlsx(final_csv) or ""
        except Exception as e:
            print(f"[xlsx] ошибка: {e}")

    auto_notify = os.getenv("AUTO_NOTIFY", "1").lower() not in ("0", "false", "")
    if auto_notify and os.path.exists(final_csv):
        try:
            tg_notify(final_csv, source_label="weekly run", xlsx_path=xlsx_path)
        except Exception as e:
            print(f"[telegram] критическая ошибка отчётности: {e}")
    elif not auto_notify:
        print("[telegram] AUTO_NOTIFY=0, отчёт не отправлен (отдельный планировщик)")

    progress.mark_finished("ok")
    print("\n🎉 Всё готово! Смотри папку output/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        progress.mark_failed("KeyboardInterrupt")
        raise
    except Exception as e:
        progress.mark_failed(str(e))
        raise
