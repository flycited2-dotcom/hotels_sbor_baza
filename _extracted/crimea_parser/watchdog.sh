#!/bin/bash
# Crimea Parser Watchdog. Запускается каждые 10 минут.
# 1. Если парсер active и CSV не менялся > 30 мин → алерт "завис"
# 2. Если парсер active и прошло >= 30 мин с прошлого heartbeat → heartbeat
# 3. Если парсер failed после старта → алерт о падении (1 раз)

set -e
cd /home/crimea_parser
set -a; . ./.env; set +a

STATE_FILE=/tmp/crimea_watchdog_state
mkdir -p $(dirname $STATE_FILE)

NOW=$(date +%s)
STATE=$(systemctl is-active crimea_parser.service 2>/dev/null || echo unknown)

send_tg() {
    local msg="$1"
    curl -sS --max-time 20 -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TG_CHAT_ID}" \
        --data-urlencode "text=${msg}" \
        --data-urlencode "parse_mode=HTML" >/dev/null 2>&1 || true
}

# 1. Если парсер не активен — снимаем флаг alert_sent и выходим
if [ "$STATE" != "active" ] && [ "$STATE" != "activating" ]; then
    # один раз сообщим если парсер недавно был активен и теперь failed
    if [ "$STATE" = "failed" ] && [ ! -f "$STATE_FILE.fail_sent" ]; then
        send_tg "❌ <b>Парсер упал</b> (systemctl: failed). /status для деталей."
        touch "$STATE_FILE.fail_sent"
    fi
    rm -f "$STATE_FILE.hang_sent" "$STATE_FILE.last_heartbeat"
    exit 0
fi

# Парсер живой → сбрасываем флаг fail_sent
rm -f "$STATE_FILE.fail_sent"

LATEST=$(ls -t /home/crimea_parser/output/result_2*.csv 2>/dev/null | grep -v enriched | head -1)

# 2. Зависание: CSV не растёт > 30 мин
if [ -n "$LATEST" ]; then
    MTIME=$(stat -c %Y "$LATEST")
    AGE=$(( NOW - MTIME ))
    if [ $AGE -gt 1800 ] && [ ! -f "$STATE_FILE.hang_sent" ]; then
        # узнаём этап из progress.json
        STAGE="?"
        if [ -f /home/crimea_parser/output/progress.json ]; then
            STAGE=$(python3 -c "import json; d=json.load(open('/home/crimea_parser/output/progress.json')); print(d.get('stage','?'))" 2>/dev/null || echo "?")
        fi
        send_tg "⚠️ <b>Парсер завис?</b> Этап <code>${STAGE}</code>, CSV не растёт $((AGE/60)) мин. /tail 50 для деталей."
        touch "$STATE_FILE.hang_sent"
    fi
    # сбрасываем флаг если CSV снова обновился
    if [ $AGE -lt 600 ]; then
        rm -f "$STATE_FILE.hang_sent"
    fi
fi

# 3. Heartbeat каждые 30 минут пока парсер активен
LAST_HB=$(cat "$STATE_FILE.last_heartbeat" 2>/dev/null || echo 0)
SINCE_HB=$(( NOW - LAST_HB ))
if [ $SINCE_HB -ge 1800 ]; then
    STAGE="?"
    COUNT="?"
    QUERY=""
    if [ -f /home/crimea_parser/output/progress.json ]; then
        EVAL=$(python3 -c "
import json
try:
    d = json.load(open('/home/crimea_parser/output/progress.json'))
    print(d.get('stage','?'))
    print(d.get('current_count',0))
    print(d.get('current_query',''))
    print(','.join(d.get('completed_sources',[])))
except Exception:
    print('?'); print(0); print(''); print('')
" 2>/dev/null)
        STAGE=$(echo "$EVAL" | sed -n '1p')
        COUNT=$(echo "$EVAL" | sed -n '2p')
        QUERY=$(echo "$EVAL" | sed -n '3p')
        DONE=$(echo "$EVAL" | sed -n '4p')
    fi
    MSG="💓 <b>Heartbeat</b>: парсер работает
Этап: <code>${STAGE}</code>
Записей в прогоне: <b>${COUNT}</b>"
    if [ -n "$QUERY" ]; then
        MSG="${MSG}
Текущий запрос: <code>${QUERY}</code>"
    fi
    if [ -n "$DONE" ]; then
        MSG="${MSG}
Готовые источники: ${DONE}"
    fi
    send_tg "$MSG"
    echo "$NOW" > "$STATE_FILE.last_heartbeat"
fi
