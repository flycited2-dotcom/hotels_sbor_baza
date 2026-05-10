"""Все команды бота. По 5-15 строк на хендлер — компактно и читаемо."""
import logging
import os
import re

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from services.auth import is_admin
from services.csv_finder import (csv_summary, latest_csv, latest_enriched,
                                  latest_xlsx)
from services.systemd import (EMAILS_UNIT, PARSER_TIMER, PARSER_UNIT, _run,
                               health, is_active, journal_tail, systemctl)

log = logging.getLogger(__name__)
router = Router()

VALID_SOURCES = ("osm", "wikidata", "yandex", "search", "2gis", "avito",
                 "sutochno", "ostrovok")


@router.message(F.func(lambda m: not is_admin(m.chat.id)))
async def _block_strangers(message: Message) -> None:
    """Чужой chat_id — молчим, чтобы не светить наличие бота."""
    log.info("denied chat_id=%s text=%r", message.chat.id, (message.text or "")[:80])


@router.message(Command("start", "help"))
async def cmd_help(m: Message) -> None:
    text = (
        "<b>Управление парсером Crimea Hotels</b>\n\n"
        "<b>Запуск</b>\n"
        "/run — полный прогон\n"
        "/run_emails — только email_finder на последнем CSV\n"
        "/run_source <name> — один источник "
        f"({', '.join(VALID_SOURCES)})\n"
        "/stop — остановить текущий прогон\n\n"
        "<b>Информация</b>\n"
        "/status — стадия + последний CSV\n"
        "/logs [N] — N последних строк journalctl (по умолчанию 50)\n"
        "/health — uptime, диск, память\n\n"
        "<b>Файлы</b>\n"
        "/csv — последний result_*.csv\n"
        "/csv_enriched — последний result_enriched_*.csv\n"
        "/xlsx — последний result_*.xlsx\n\n"
        "<b>Расписание</b>\n"
        "/timer_on — включить еженедельный запуск\n"
        "/timer_off — отключить\n"
        "/schedule — текущее расписание"
    )
    await m.answer(text, parse_mode="HTML")


@router.message(Command("run"))
async def cmd_run(m: Message) -> None:
    if await is_active(PARSER_UNIT):
        await m.answer(f"⚠ {PARSER_UNIT} уже работает. /stop для остановки.")
        return
    code, out = await systemctl("start", PARSER_UNIT)
    if code == 0:
        await m.answer(f"✅ {PARSER_UNIT} запущен (TimeoutStartSec=12h, fire-and-forget)\n"
                       f"Прогресс: /status. Финальный отчёт придёт автоматически.")
    else:
        await m.answer(f"❌ systemctl start: rc={code}\n<pre>{out}</pre>", parse_mode="HTML")


@router.message(Command("run_emails"))
async def cmd_run_emails(m: Message) -> None:
    if await is_active(EMAILS_UNIT):
        await m.answer(f"⚠ {EMAILS_UNIT} уже работает.")
        return
    code, out = await systemctl("start", EMAILS_UNIT)
    if code == 0:
        await m.answer(f"✅ {EMAILS_UNIT} запущен — обогащает последний CSV.")
    else:
        await m.answer(f"❌ systemctl start: rc={code}\n<pre>{out}</pre>", parse_mode="HTML")


@router.message(Command("run_source"))
async def cmd_run_source(m: Message, command: CommandObject) -> None:
    name = (command.args or "").strip().lower()
    if name not in VALID_SOURCES:
        await m.answer(f"Источник: {', '.join(VALID_SOURCES)}")
        return
    unit = f"crimea_parser_source@{name}.service"
    code, out = await _run("sudo", "-n", "systemctl", "start", unit)
    if code == 0:
        await m.answer(f"✅ {unit} запущен (ONLY_SOURCE={name}, без email_finder).")
    else:
        await m.answer(f"❌ rc={code}\n<pre>{out[:1000]}</pre>", parse_mode="HTML")


@router.message(Command("stop"))
async def cmd_stop(m: Message) -> None:
    code, out = await systemctl("stop", PARSER_UNIT)
    if code == 0:
        await m.answer(f"🛑 {PARSER_UNIT} остановлен.")
    else:
        await m.answer(f"❌ systemctl stop: rc={code}\n<pre>{out}</pre>", parse_mode="HTML")


_STAGE_RE = re.compile(r"===\s*([^=]+?)\s*===")


@router.message(Command("status"))
async def cmd_status(m: Message) -> None:
    parser_active = await is_active(PARSER_UNIT)
    emails_active = await is_active(EMAILS_UNIT)

    stage = "—"
    log_path = os.path.join(os.getenv("PARSER_DIR", "/home/crimea_parser"),
                             "parser.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-200:]
            for line in reversed(tail):
                m_ = _STAGE_RE.search(line)
                if m_:
                    stage = m_.group(1).strip()
                    break
        except Exception:
            pass

    csv_info = csv_summary(latest_csv() or "")
    parts = [
        f"📊 <b>Статус</b>",
        f"{PARSER_UNIT}: {'🟢 active' if parser_active else '⚪ inactive'}",
        f"{EMAILS_UNIT}: {'🟢 active' if emails_active else '⚪ inactive'}",
        f"Стадия: <b>{stage}</b>",
        "",
        f"<b>Последний CSV</b>",
        f"<pre>{csv_info}</pre>",
    ]
    await m.answer("\n".join(parts), parse_mode="HTML")


@router.message(Command("logs"))
async def cmd_logs(m: Message, command: CommandObject) -> None:
    n = 50
    arg = (command.args or "").strip()
    if arg.isdigit():
        n = max(1, min(int(arg), 500))
    out = await journal_tail(PARSER_UNIT, n=n)
    if len(out) > 3500:
        out = out[-3500:]
    await m.answer(f"<pre>{out or 'пусто'}</pre>", parse_mode="HTML")


@router.message(Command("health"))
async def cmd_health(m: Message) -> None:
    out = await health()
    await m.answer(f"<pre>{out}</pre>", parse_mode="HTML")


async def _send_file(m: Message, path: str | None, label: str) -> None:
    if not path or not os.path.exists(path):
        await m.answer(f"⚠ {label}: файлов нет в output/")
        return
    await m.answer_document(FSInputFile(path), caption=csv_summary(path))


@router.message(Command("csv"))
async def cmd_csv(m: Message) -> None:
    await _send_file(m, latest_csv(), "result_*.csv")


@router.message(Command("csv_enriched"))
async def cmd_csv_enriched(m: Message) -> None:
    await _send_file(m, latest_enriched(), "result_enriched_*.csv")


@router.message(Command("xlsx"))
async def cmd_xlsx(m: Message) -> None:
    await _send_file(m, latest_xlsx(), "result_*.xlsx")


@router.message(Command("timer_on"))
async def cmd_timer_on(m: Message) -> None:
    code, out = await systemctl("enable", PARSER_TIMER)
    code2, out2 = await systemctl("start", PARSER_TIMER)
    if code == 0 and code2 == 0:
        await m.answer(f"✅ {PARSER_TIMER}: enabled+started (вс 03:00)")
    else:
        await m.answer(f"<pre>enable: rc={code}\n{out}\nstart: rc={code2}\n{out2}</pre>",
                       parse_mode="HTML")


@router.message(Command("timer_off"))
async def cmd_timer_off(m: Message) -> None:
    code, out = await systemctl("stop", PARSER_TIMER)
    code2, out2 = await systemctl("disable", PARSER_TIMER)
    if code == 0 and code2 == 0:
        await m.answer(f"🛑 {PARSER_TIMER}: остановлен и отключён")
    else:
        await m.answer(f"<pre>stop: rc={code}\n{out}\ndisable: rc={code2}\n{out2}</pre>",
                       parse_mode="HTML")


@router.message(Command("schedule"))
async def cmd_schedule(m: Message) -> None:
    code, out = await _run("systemctl", "list-timers", "--all", PARSER_TIMER)
    if code != 0:
        await m.answer(f"<pre>rc={code}\n{out}</pre>", parse_mode="HTML")
        return
    await m.answer(f"<pre>{out}</pre>", parse_mode="HTML")
