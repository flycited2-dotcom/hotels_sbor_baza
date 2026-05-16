"""VK API — поиск групп размещения в Крыму.

ENV: VK_TOKEN (user access_token; получить на https://dev.vk.com).
Без токена парсер тихо пропускается.

Метод groups.search:
  q=<запрос>&type=group&country=1&city=<id>&count=1000
Затем groups.getById с extended=1&fields=description,site,contacts,phone,addresses,city.
"""
import json
import os
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from utils.storage import save_item

API = "https://api.vk.com/method"
V = "5.131"

# Крым/Севастополь — id городов VK. Главные:
VK_CITIES = {
    295:    "Симферополь",
    314:    "Ялта",
    298:    "Севастополь",
    363:    "Евпатория",
    288:    "Феодосия",
    309:    "Керчь",
    300:    "Алушта",
    349:    "Судак",
    359:    "Бахчисарай",
    365:    "Саки",
}

QUERIES = [
    "отель", "гостиница", "пансионат", "санаторий",
    "база отдыха", "дом отдыха", "гостевой дом", "эллинг",
    "хостел", "глэмпинг", "апарт-отель",
]


def _api(method: str, params: dict, token: str) -> dict:
    params = dict(params)
    params["access_token"] = token
    params["v"] = V
    url = f"{API}/{method}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        return {"error": {"error_msg": str(e)}}


def _detect_city(addresses, default_city: str) -> str:
    if isinstance(addresses, dict):
        main = addresses.get("main_address") or {}
        city = main.get("title") or main.get("city")
        if isinstance(city, dict):
            city = city.get("title")
        if city:
            return city
    return default_city


async def run(context):
    """context не используется."""
    token = os.getenv("VK_TOKEN", "").strip()
    if not token:
        print("\n=== VK: VK_TOKEN не задан, пропуск ===")
        return

    print("\n=== VK groups.search ===")
    found_group_ids: set[int] = set()

    # 1. Поиск групп по городам × запросам
    for city_id, city_name in VK_CITIES.items():
        for q in QUERIES:
            resp = _api("groups.search", {
                "q": q,
                "type": "group",
                "country_id": 1,
                "city_id": city_id,
                "count": 100,
            }, token)
            if "error" in resp:
                print(f"  [VK] {city_name}/{q} err: {resp['error'].get('error_msg', '?')[:100]}")
                time.sleep(1)
                continue
            items = resp.get("response", {}).get("items", [])
            for it in items:
                gid = it.get("id")
                if gid:
                    found_group_ids.add(gid)
            time.sleep(0.4)  # VK rate-limit ~3 RPS

    if not found_group_ids:
        print("  [VK] ничего не найдено")
        return

    print(f"  найдено уникальных групп: {len(found_group_ids)}")

    # 2. Детали групп пачками по 500
    added = 0
    gids = list(found_group_ids)
    for chunk_start in range(0, len(gids), 500):
        chunk = gids[chunk_start:chunk_start + 500]
        resp = _api("groups.getById", {
            "group_ids": ",".join(map(str, chunk)),
            "fields": "description,site,contacts,phone,addresses,city,activity",
        }, token)
        if "error" in resp:
            print(f"  [VK] getById err: {resp['error'].get('error_msg', '?')[:100]}")
            time.sleep(2)
            continue
        groups = resp.get("response", {}).get("groups") or resp.get("response", [])
        if isinstance(groups, dict):
            groups = groups.get("groups", [])
        for g in groups:
            name = g.get("name", "")
            if not name:
                continue
            phone = g.get("phone", "")
            site = g.get("site", "")
            city = ""
            addr = ""
            city_obj = g.get("city")
            if isinstance(city_obj, dict):
                city = city_obj.get("title", "")
            addresses = g.get("addresses")
            if addresses:
                addr_main = addresses.get("main_address") if isinstance(addresses, dict) else None
                if isinstance(addr_main, dict):
                    addr = addr_main.get("address", "")
                    if not city:
                        city = addr_main.get("city", "") if isinstance(addr_main.get("city"), str) else ""
            screen = g.get("screen_name") or g.get("id")
            social = f"https://vk.com/{screen}"

            if save_item({
                "city": city or "Крым",
                "name": name,
                "address": addr,
                "phone": str(phone),
                "email": "",
                "website": str(site),
                "social": social,
                "category": g.get("activity") or "размещение",
                "source": "VK",
                "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }):
                added += 1
        time.sleep(0.4)

    print(f"\n[VK] добавлено: {added}")
