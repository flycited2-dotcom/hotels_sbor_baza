"""Обработчики команд Telegram-бота."""
import html
import os

from utils.telegram_notify import send_message, send_document
from bot import state

ADMIN_USER_IDS = {1264067528}


def _e(s: str) -> str:
    return html.escape(s or "", quote=False)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def cmd_help(token: str, chat_id: int, user_id: int, args: str) -> None:
    text = (
        "<b>Crimea Hotel Parser — бот</b>\n\n"
        "Для всех:\n"
        "  /status — текущее состояние парсера\n"
        "  /sources — записи по источникам в текущем CSV\n"
        "  /db — статистика накопленной базы (всех времён)\n"
        "  /last_report — прислать свежий CSV + сводку\n"
        "  /tail [N] — последние N строк лога (по умолчанию 30)\n"
        "  /help — это сообщение\n\n"
        "Только для админа:\n"
        "  /run — запустить полный прогон\n"
        "  /stop — остановить текущий прогон\n"
        "  /run_source &lt;ключ&gt; — точечный запуск (osm/wikidata/yandex/search/2gis/avito/sutochno/ostrovok/crawler)\n"
    )
    send_message(token, str(chat_id), text)


def cmd_status(token: str, chat_id: int, user_id: int, args: str) -> None:
    sysstate = state.parser_systemd_state()
    snap = state.progress_snapshot()
    uptime = state.parser_uptime_seconds()

    lines = [f"<b>Статус парсера</b>: <code>{_e(sysstate)}</code>"]
    if uptime is not None:
        lines.append(f"Uptime сервиса: {_e(state.format_uptime(uptime))}")

    if snap:
        if snap.get("status"):
            lines.append(f"State: <b>{_e(snap['status'])}</b>")
        if snap.get("stage"):
            lines.append(f"Этап: <code>{_e(snap['stage'])}</code>")
        if snap.get("current_query"):
            lines.append(f"Запрос: <code>{_e(snap['current_query'])}</code>")
        if snap.get("current_count") is not None:
            lines.append(f"Записей в прогоне: <b>{snap['current_count']}</b>")
        if snap.get("completed_sources"):
            lines.append("Готово: " + ", ".join(_e(s) for s in snap['completed_sources']))
        if snap.get("started_at"):
            lines.append(f"Старт: <code>{_e(snap['started_at'])}</code>")
        if snap.get("last_update"):
            lines.append(f"Последнее обновление: <code>{_e(snap['last_update'])}</code>")
        if snap.get("error"):
            lines.append(f"❌ Ошибка: <code>{_e(snap['error'][:200])}</code>")
    else:
        lines.append("<i>progress.json не найден (парсер ещё не запускался с новой логикой)</i>")

    latest = state.latest_csv()
    if latest:
        st = state.csv_stats(latest)
        lines.append("")
        lines.append(f"<b>Свежий CSV</b>: <code>{_e(os.path.basename(latest))}</code> ({_e(st.get('mtime', ''))})")
        total = st["total"] or 1
        lines.append(f"  всего: <b>{st['total']}</b>")
        lines.append(f"  с тел: <b>{st['phone']}</b> ({100*st['phone']//total}%)")
        lines.append(f"  с email: <b>{st['email']}</b> ({100*st['email']//total}%)")
        lines.append(f"  с адресом: <b>{st['address']}</b> ({100*st['address']//total}%)")

    send_message(token, str(chat_id), "\n".join(lines))


def cmd_sources(token: str, chat_id: int, user_id: int, args: str) -> None:
    latest = state.latest_csv()
    if not latest:
        send_message(token, str(chat_id), "Нет CSV в output/.")
        return
    st = state.csv_stats(latest)
    lines = [f"<b>По источникам</b> в <code>{_e(os.path.basename(latest))}</code>:"]
    for src, n in sorted(st["sources"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {_e(src)}: <b>{n}</b>")
    lines.append(f"\nИтого: <b>{st['total']}</b>")
    send_message(token, str(chat_id), "\n".join(lines))


def cmd_db(token: str, chat_id: int, user_id: int, args: str) -> None:
    try:
        from utils import dedup
        total = dedup.total()
        by_src = dedup.stats_by_source()
    except Exception as e:
        send_message(token, str(chat_id), f"Ошибка чтения dedup.db: {_e(str(e))}")
        return
    lines = [f"<b>База за все прогоны (dedup.db)</b>",
             f"Уникальных записей: <b>{total}</b>",
             "",
             "<b>По источникам</b>:"]
    for s, n in sorted(by_src.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {_e(s)}: <b>{n}</b>")
    send_message(token, str(chat_id), "\n".join(lines))


def cmd_last_report(token: str, chat_id: int, user_id: int, args: str) -> None:
    latest = state.latest_csv()
    if not latest:
        send_message(token, str(chat_id), "Нет CSV в output/.")
        return
    from utils.telegram_notify import notify
    notify(latest, source_label="по запросу /last_report")


def cmd_tail(token: str, chat_id: int, user_id: int, args: str) -> None:
    n = 30
    if args.strip().isdigit():
        n = max(1, min(200, int(args.strip())))
    text = state.log_tail(n)
    if len(text) > 3800:
        text = "…" + text[-3800:]
    send_message(token, str(chat_id), f"<b>Лог (последние {n} строк):</b>\n<pre>{_e(text)}</pre>")


def cmd_run(token: str, chat_id: int, user_id: int, args: str) -> None:
    if not _is_admin(user_id):
        send_message(token, str(chat_id), "⛔ Только для админа.")
        return
    sysstate = state.parser_systemd_state()
    if sysstate in ("active", "activating"):
        send_message(token, str(chat_id), f"Парсер уже идёт: <code>{_e(sysstate)}</code>. /stop сначала.")
        return
    rc, out = state.systemctl("reset-failed", "crimea_parser.service")
    rc, out = state.systemctl("start", "crimea_parser.service", "--no-block")
    if rc == 0:
        send_message(token, str(chat_id), "🟢 Парсер запущен. /status для контроля.")
    else:
        send_message(token, str(chat_id), f"Ошибка запуска: <pre>{_e(out)}</pre>")


def cmd_run_source(token: str, chat_id: int, user_id: int, args: str) -> None:
    if not _is_admin(user_id):
        send_message(token, str(chat_id), "⛔ Только для админа.")
        return
    key = args.strip().lower()
    allowed = {"osm", "wikidata", "yandex", "search", "2gis", "avito", "sutochno", "ostrovok", "crawler"}
    if key not in allowed:
        send_message(token, str(chat_id), f"Неизвестный источник. Доступно: {', '.join(sorted(allowed))}.")
        return
    sysstate = state.parser_systemd_state()
    if sysstate in ("active", "activating"):
        send_message(token, str(chat_id), f"Парсер уже идёт: <code>{_e(sysstate)}</code>.")
        return
    # transient unit с конкретным ONLY_SOURCE
    rc, out = state.systemctl(
        "reset-failed", f"crimea_run_{key}.service",
    )
    import subprocess
    try:
        cmd = [
            "systemd-run",
            f"--unit=crimea_run_{key}",
            f"--description=Crimea parser ({key} only)",
            "--property=TimeoutStartSec=12h",
            "--setenv", f"ONLY_SOURCE={key}",
            "--setenv", "AUTO_NOTIFY=1",
            "--setenv", "HEADLESS=1",
            "/home/crimea_parser/venv/bin/python",
            "/home/crimea_parser/main.py",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            send_message(token, str(chat_id), f"🟢 Запущен точечный прогон <b>{_e(key)}</b>.")
        else:
            send_message(token, str(chat_id), f"Ошибка: <pre>{_e(r.stderr + r.stdout)}</pre>")
    except Exception as e:
        send_message(token, str(chat_id), f"Ошибка: <code>{_e(str(e))}</code>")


def cmd_stop(token: str, chat_id: int, user_id: int, args: str) -> None:
    if not _is_admin(user_id):
        send_message(token, str(chat_id), "⛔ Только для админа.")
        return
    rc, out = state.systemctl("stop", "crimea_parser.service")
    # также гасим transient прогоны
    import subprocess
    try:
        subprocess.run(
            "for u in $(systemctl list-units --no-legend 'crimea_run_*.service' | awk '{print $1}'); "
            "do systemctl stop \"$u\" || true; done",
            shell=True, capture_output=True, timeout=20,
        )
    except Exception:
        pass
    send_message(token, str(chat_id), "🛑 Парсер и точечные прогоны остановлены.")


COMMANDS = {
    "/start": cmd_help,
    "/help": cmd_help,
    "/status": cmd_status,
    "/sources": cmd_sources,
    "/db": cmd_db,
    "/last_report": cmd_last_report,
    "/tail": cmd_tail,
    "/run": cmd_run,
    "/run_source": cmd_run_source,
    "/stop": cmd_stop,
}


def dispatch(token: str, chat_id: int, user_id: int, text: str) -> None:
    """text — полное сообщение от пользователя."""
    text = (text or "").strip()
    if not text.startswith("/"):
        return
    # отделяем команду от аргументов; срезаем @BotName если есть
    first, _, rest = text.partition(" ")
    cmd, _, _bot = first.partition("@")
    cmd = cmd.lower()
    handler = COMMANDS.get(cmd)
    if not handler:
        return
    try:
        handler(token, chat_id, user_id, rest)
    except Exception as e:
        send_message(token, str(chat_id), f"⚠ Ошибка обработчика: <code>{_e(str(e))}</code>")
