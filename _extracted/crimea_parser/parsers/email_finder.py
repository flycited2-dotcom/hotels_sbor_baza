"""Email/phone/address enrichment by visiting each website.

Логика:
1. На главной — ищем mailto:/tel:/visible-text email и phone.
2. Дополнительно обходим типовые контактные страницы (/contacts, /kontakty, ...).
3. Из найденного текста пробуем выудить адрес (эвристика на «г./пгт./ул./ш./пр.»).
"""
import asyncio
import csv
import os
import random
import re
from datetime import datetime
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from utils.browser import create_browser_context
from utils.storage import CSV_DELIMITER, FIELDS, normalize_phone

OUTPUT_FILE = f"output/result_enriched_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")

ADDRESS_RE = re.compile(
    r"(?:(?:г\.?|город)\s*[А-Яа-яЁё\-]+[,.\s]+)?"
    r"(?:(?:ул\.?|улица|пр-т|проспект|пер\.?|переулок|ш\.?|шоссе|пл\.?|площадь|наб\.?|набережная|пгт\.?|посёлок|поселок)\s*"
    r"[А-Яа-яЁё0-9\s\-\.,]{3,80})",
    re.IGNORECASE,
)

EMAIL_BLOCKLIST = (
    "example.", "@domain", "noreply", "no-reply",
    "@sentry", "@wixpress", "@2x.png", ".png", ".jpg", ".jpeg", ".webp",
    "@react", "@vue", "@babel", "@types", "@material",
    "@yandex-team", "@google-analytics", "@cloudflare",
)

CONTACT_PATHS = [
    "/contacts", "/contact", "/contact-us", "/contact_us",
    "/kontakty", "/kontakt", "/contacts.html", "/contact.html",
    "/o-nas", "/o_nas", "/about", "/about-us", "/about_us",
    "/page/contact", "/page/contacts", "/feedback", "/info",
    "/svyazatsya", "/связаться", "/контакты", "/о-нас",
    "/index.php?route=information/contact",
    "/info/contacts", "/cms/contacts",
]


def _decode_obfuscated_email(text: str) -> str:
    """info[at]hotel[dot]ru → info@hotel.ru."""
    if not text:
        return ""
    candidates = re.findall(
        r"[a-zA-Z0-9._%+\-]+\s*[\[\(]\s*(?:at|собака|@)\s*[\]\)]\s*[a-zA-Z0-9.\-]+\s*[\[\(]\s*(?:dot|точка|\.)\s*[\]\)]\s*[a-zA-Z]{2,}",
        text, re.IGNORECASE,
    )
    for c in candidates:
        decoded = re.sub(r"\s*[\[\(]\s*(?:at|собака|@)\s*[\]\)]\s*", "@", c, flags=re.IGNORECASE)
        decoded = re.sub(r"\s*[\[\(]\s*(?:dot|точка|\.)\s*[\]\)]\s*", ".", decoded, flags=re.IGNORECASE)
        if "@" in decoded and "." in decoded.split("@")[-1]:
            return decoded
    return ""


def pick_email(text: str) -> str:
    if not text:
        return ""
    for e in EMAIL_RE.findall(text):
        low = e.lower()
        if any(b in low for b in EMAIL_BLOCKLIST):
            continue
        if low.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
            continue
        return e
    return ""


def pick_phone(text: str) -> str:
    if not text:
        return ""
    matches = PHONE_RE.findall(text)
    return normalize_phone(matches[0]) if matches else ""


def pick_address(text: str) -> str:
    if not text:
        return ""
    m = ADDRESS_RE.search(text)
    if not m:
        return ""
    addr = re.sub(r"\s{2,}", " ", m.group(0)).strip(" ,.;")
    return addr[:200]


async def _harvest_dom(page) -> tuple[str, str]:
    """mailto: / tel: ссылки в DOM (приоритет)."""
    email = ""
    phone = ""
    try:
        em = await page.query_selector("a[href^='mailto:']")
        if em:
            href = await em.get_attribute("href") or ""
            cand = href.replace("mailto:", "").split("?")[0].strip()
            if cand and "@" in cand:
                email = cand
    except Exception:
        pass
    try:
        tl = await page.query_selector("a[href^='tel:']")
        if tl:
            href = await tl.get_attribute("href") or ""
            cand = href.replace("tel:", "").strip()
            if cand:
                phone = normalize_phone(cand)
    except Exception:
        pass
    return email, phone


async def _scroll_to_bottom(page, n: int = 6):
    """Многие сайты подгружают footer (контакты) только после скролла."""
    for _ in range(n):
        try:
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        except Exception:
            pass
        await page.wait_for_timeout(400)


async def _harvest_page(page) -> tuple[str, str, str]:
    """email/phone/address из текущей страницы с DOM + полный HTML + visible text."""
    email = phone = address = ""
    e, p = await _harvest_dom(page)
    email = email or e
    phone = phone or p
    try:
        html = await page.content()
        if not email:
            email = pick_email(html) or _decode_obfuscated_email(html)
        if not phone:
            phone = pick_phone(html)
    except Exception:
        pass
    try:
        visible = await page.evaluate("document.body && document.body.innerText || ''")
        if not address:
            address = pick_address(visible)
        if not email:
            email = _decode_obfuscated_email(visible)
    except Exception:
        pass
    return email, phone, address


async def enrich_from_website(page, website: str) -> tuple[str, str, str]:
    email = phone = address = ""
    try:
        try:
            await page.goto(website, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"    goto fail: {e}")
            return "", "", ""
        await page.wait_for_timeout(1500)
        await _scroll_to_bottom(page, n=4)
        await page.wait_for_timeout(800)

        e, p, a = await _harvest_page(page)
        email = email or e
        phone = phone or p
        address = address or a

        if not (email and phone and address):
            for path in CONTACT_PATHS:
                if email and phone and address:
                    break
                try:
                    await page.goto(website.rstrip("/") + path,
                                    wait_until="domcontentloaded", timeout=10000)
                    await page.wait_for_timeout(1000)
                    await _scroll_to_bottom(page, n=2)
                    e, p, a = await _harvest_page(page)
                    email = email or e
                    phone = phone or p
                    address = address or a
                except Exception:
                    continue

    except Exception:
        pass

    return email, phone, address


async def run_enrichment(input_csv: str):
    if not os.path.exists(input_csv):
        print(f"Файл не найден: {input_csv}")
        return None

    # читаем CSV — пробуем оба разделителя
    rows = []
    for delim in (";", ","):
        try:
            with open(input_csv, encoding="utf-8-sig") as f:
                sample = f.read(2048)
                f.seek(0)
                if delim in sample:
                    reader = csv.DictReader(f, delimiter=delim)
                    rows = list(reader)
                    if rows and "name" in rows[0]:
                        break
        except Exception:
            continue

    if not rows:
        print(f"Не удалось прочитать CSV: {input_csv}")
        return None

    targets = [r for r in rows if r.get("website") and (not r.get("email") or not r.get("phone") or not r.get("address"))]
    print(f"\n=== Email Finder: {len(targets)}/{len(rows)} объектов на обогащение ===")

    async with async_playwright() as p:
        browser, context = await create_browser_context(p, headless=True)
        page = await context.new_page()

        for i, row in enumerate(rows):
            if not row.get("website"):
                continue
            need_email = not row.get("email")
            need_phone = not row.get("phone")
            need_addr = not row.get("address")
            if not (need_email or need_phone or need_addr):
                continue

            print(f"  [{i + 1}/{len(rows)}] {row.get('name','?')} → {row['website']}")
            try:
                email, phone, address = await enrich_from_website(page, row["website"])
            except Exception as e:
                print(f"    ошибка: {e}")
                email = phone = address = ""

            if need_email and email:
                row["email"] = email
                print(f"    email: {email}")
            if need_phone and phone:
                row["phone"] = phone
                print(f"    phone: {phone}")
            if need_addr and address:
                row["address"] = address
                print(f"    address: {address}")

            await asyncio.sleep(random.uniform(1.2, 2.5))

        await browser.close()

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDS,
            delimiter=CSV_DELIMITER, quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Обогащённый файл: {OUTPUT_FILE}")
    return OUTPUT_FILE
