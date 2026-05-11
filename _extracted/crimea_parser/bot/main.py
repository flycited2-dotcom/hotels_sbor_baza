"""Telegram long-poll бот. Запускается отдельным systemd-сервисом с Restart=always."""
import json
import os
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# чтобы импорты utils/bot работали при ExecStart=.../bot/main.py
sys.path.insert(0, "/home/crimea_parser")

from dotenv import load_dotenv
load_dotenv("/home/crimea_parser/.env")

from bot.handlers import dispatch


def _get_updates(token: str, offset: int, timeout: int = 30) -> list:
    params = {"timeout": timeout, "allowed_updates": '["message"]'}
    if offset:
        params["offset"] = offset
    url = f"https://api.telegram.org/bot{token}/getUpdates?{urlencode(params)}"
    try:
        with urlopen(url, timeout=timeout + 10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        print(f"[bot] HTTP {e.code}: {body[:200]!r}", flush=True)
        return []
    except URLError as e:
        print(f"[bot] URLError: {e}", flush=True)
        time.sleep(5)
        return []
    except Exception as e:
        print(f"[bot] error: {e}", flush=True)
        time.sleep(5)
        return []
    if not data.get("ok"):
        print(f"[bot] not ok: {data!r}", flush=True)
        return []
    return data.get("result", [])


def main() -> None:
    token = os.getenv("TG_BOT_TOKEN", "").strip()
    if not token:
        print("[bot] TG_BOT_TOKEN не задан, выход", flush=True)
        sys.exit(1)

    print("[bot] long-poll started", flush=True)
    offset = 0
    while True:
        try:
            updates = _get_updates(token, offset, timeout=30)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                text = msg.get("text") or ""
                chat = msg.get("chat") or {}
                frm = msg.get("from") or {}
                chat_id = chat.get("id")
                user_id = frm.get("id")
                if not chat_id or not user_id:
                    continue
                if not text.startswith("/"):
                    continue
                username = frm.get("username", "?")
                print(f"[bot] {username}({user_id}) in {chat_id}: {text[:120]}", flush=True)
                dispatch(token, int(chat_id), int(user_id), text)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[bot] loop error: {e}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
