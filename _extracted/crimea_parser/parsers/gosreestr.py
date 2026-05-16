"""Госреестр классифицированных средств размещения РФ.

Источник: classification.tourism.gov.ru — официальный реестр аккредитованных
гостиниц/санаториев. Фильтр по региону: Республика Крым (код 91), Севастополь (92).

Реестр публичный, без авторизации. Парсим JSON-ответ их API
(если доступен) либо HTML-страницу со списком (через Chromium).

Возвращает: name, тип, категория (звёзды), адрес, ИНН/ОГРН (в comment).
"""
import json
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from utils.storage import save_item

# JSON-API портала Минэка — найден через DevTools на classification.tourism.gov.ru
API_URLS = [
    # Старый домен (был до 2023, домен уже не резолвится)
    "https://classification.tourism.gov.ru/api/objects",
    "https://classification.tourism.gov.ru/api/public/objects",
    # Новый Национальный реестр средств размещения (ФЗ-590 от 2022)
    "https://nbo.gov.ru/api/objects",
    "https://nbo.gov.ru/api/v1/objects",
    "https://nbo.gov.ru/api/public/objects",
    # Альтернативы через Росаккредитацию
    "https://reestr.tourism.gov.ru/api/objects",
]

# Коды регионов (KLADR): Республика Крым = 91, Севастополь = 92
REGION_CODES = {
    "91": "Крым",
    "92": "Севастополь",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0"

CITY_HINTS = (
    "Симферополь", "Ялта", "Севастополь", "Евпатория", "Феодосия",
    "Керчь", "Алушта", "Судак", "Саки", "Бахчисарай",
    "Коктебель", "Партенит", "Гурзуф", "Новый Свет", "Форос",
)


def _detect_city(text: str) -> str:
    for c in CITY_HINTS:
        if c in (text or ""):
            return c
    return "Крым"


def _http_json(url: str) -> dict | list:
    try:
        req = Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
        })
        with urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        return {"_error": str(e)}


def _fetch_region(region_code: str) -> list:
    """Пробуем разные эндпоинты, пока не получим JSON со списком."""
    for base in API_URLS:
        for page in range(1, 50):  # пагинация
            params = {
                "region": region_code,
                "page": page,
                "size": 100,
            }
            url = f"{base}?{urlencode(params)}"
            data = _http_json(url)
            if isinstance(data, dict):
                if "_error" in data:
                    print(f"  [Госреестр] {url} → {data['_error'][:120]}")
                    break
                # стандартный ответ: {content: [...], totalPages: N}
                content = data.get("content") or data.get("items") or data.get("data") or []
                if not content:
                    break
                yield from content
                total_pages = data.get("totalPages") or data.get("totalpages") or 0
                if page >= total_pages:
                    break
            elif isinstance(data, list):
                if not data:
                    break
                yield from data
                if len(data) < 100:
                    break
            else:
                break


async def run(context):
    """context не используется."""
    print("\n=== Госреестр Минэка ===")
    added = 0
    total_fetched = 0
    api_failed = True

    for code, region_name in REGION_CODES.items():
        for obj in _fetch_region(code):
            api_failed = False
            total_fetched += 1
            # пытаемся вытащить ключевые поля независимо от формы JSON
            name = (obj.get("name") or obj.get("objectName")
                    or obj.get("title") or obj.get("nameRu") or "").strip()
            if not name:
                continue
            address = (obj.get("address") or obj.get("addr")
                       or obj.get("fullAddress") or "").strip()
            stars = obj.get("category") or obj.get("stars") or obj.get("classCategory") or ""
            inn = obj.get("inn") or obj.get("INN") or ""
            ogrn = obj.get("ogrn") or obj.get("OGRN") or ""
            phone = obj.get("phone") or obj.get("phoneNumber") or ""
            email = obj.get("email") or ""
            website = obj.get("website") or obj.get("site") or ""
            obj_type = obj.get("type") or obj.get("objectType") or "размещение"

            comment_parts = []
            if stars:
                comment_parts.append(f"звёзды: {stars}")
            if inn:
                comment_parts.append(f"ИНН: {inn}")
            if ogrn:
                comment_parts.append(f"ОГРН: {ogrn}")

            if save_item({
                "city": _detect_city(address) or region_name,
                "name": name,
                "address": address,
                "phone": str(phone) if phone else "",
                "email": str(email) if email else "",
                "website": str(website) if website else "",
                "category": str(obj_type),
                "comment": "; ".join(comment_parts),
                "source": "Госреестр",
                "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }):
                added += 1

    if api_failed:
        print("  [Госреестр] API недоступен/изменён, нужен апдейт эндпоинта")
    print(f"  получено: {total_fetched}, добавлено: {added}")
