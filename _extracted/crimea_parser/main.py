import asyncio
import glob
import os
import sys
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
from utils.browser import create_browser_context
from utils.storage import total, get_output_file
from utils.telegram_notify import notify as tg_notify
from parsers import osm, wikidata, yandex_maps, search_engine
from parsers.email_finder import run_enrichment

async def main():
    print("=" * 60)
    print("  CRIMEA HOTEL PARSER — запуск всех источников")
    print("=" * 60)

    headless_env = os.getenv("HEADLESS", "1").lower()
    headless = headless_env not in ("0", "false", "")

    async with async_playwright() as p:
        browser, context = await create_browser_context(p, headless=headless)
        try:
            # Порядок: быстрые HTTP-API сначала (OSM, Wikidata),
            # потом тяжёлые с Chromium (Я.Карты, поиск).
            for label, runner in [
                ("OSM", osm.run),
                ("Wikidata", wikidata.run),
                ("Я.Карты", yandex_maps.run),
                ("Поиск (Яндекс/Mail/Rambler/Bing)", search_engine.run),
            ]:
                try:
                    await runner(context)
                except Exception as e:
                    print(f"\n[{label}] критическая ошибка: {e}")
                    import traceback
                    traceback.print_exc()
        finally:
            await browser.close()

    print(f"\n✅ Собрано записей: {total()}")

    latest = get_output_file()
    enriched = None
    if os.path.exists(latest):
        print(f"\n🔍 Запускаем Email Finder по: {latest}")
        enriched = await run_enrichment(latest)

    final_csv = enriched or latest
    auto_notify = os.getenv("AUTO_NOTIFY", "1").lower() not in ("0", "false", "")
    if auto_notify and os.path.exists(final_csv):
        try:
            tg_notify(final_csv, source_label="weekly run")
        except Exception as e:
            print(f"[telegram] критическая ошибка отчётности: {e}")
    elif not auto_notify:
        print("[telegram] AUTO_NOTIFY=0, отчёт не отправлен (отдельный планировщик)")

    print("\n🎉 Всё готово! Смотри папку output/")

if __name__ == "__main__":
    asyncio.run(main())
