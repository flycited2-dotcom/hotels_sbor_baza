#!/bin/bash
# Crimea Parser Watchdog. Запускается каждые 10 минут через systemd timer.
# Если парсер active, но output/*.csv не менялся > 30 минут — алерт в TG.

set -e
cd /home/crimea_parser
set -a; . ./.env; set +a

STATE=$(systemctl is-active crimea_parser.service 2>/dev/null || echo unknown)
if [ "$STATE" != "active" ] && [ "$STATE" != "activating" ]; then
    exit 0
fi

LATEST=$(ls -t /home/crimea_parser/output/result_2*.csv 2>/dev/null | grep -v enriched | head -1)
if [ -z "$LATEST" ]; then
    # активен, но ни одного CSV ещё нет (только что стартовал) — норм
    exit 0
fi

NOW=$(date +%s)
MTIME=$(stat -c %Y "$LATEST")
AGE=$(( NOW - MTIME ))

if [ $AGE -gt 1800 ]; then
    MSG="⚠️ <b>Watchdog</b>: парсер active, но <code>$(basename $LATEST)</code> не обновлялся $((AGE/60)) мин. Возможно завис."
    curl -sS -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TG_CHAT_ID}" \
        --data-urlencode "text=${MSG}" \
        --data-urlencode "parse_mode=HTML" >/dev/null 2>&1 || true
fi
