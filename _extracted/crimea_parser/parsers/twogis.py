"""2ГИС — структурированный поиск по Крыму.

URL вида: https://2gis.ru/search/<query>?m=<lon>%2C<lat>%2F<zoom>
Используем общий фильтр по Республике Крым/Севастополю.
В карточке организации видны телефон и сайт без дополнительных кликов.
"""
import asyncio
import random
import re
from datetime import datetime
from urllib.parse import quote_plus, urlparse

from utils.storage import save_item

CATEGORIES = [
    "гостиница", "отель", "пансионат", "дом отдыха",
    "база отдыха", "эллинг", "глэмпинг", "кемпинг",
    "гостевой дом", "хостел", "санаторий", "апарт-отель",
]

REGIONS = [
    ("Крым", "https://2gis.ru/crimea/search/"),
    ("Севастополь", "https://2gis.ru/sevastopol/search/"),
]

CITIES = [
    "Симферополь", "Ялта", "Севастополь", "Евпатория", "Феодосия",
    "Керчь", "Алушта", "Судак", "Саки", "Бахчисарай",
    "Коктебель", "Партенит", "Гурзуф",
]


def detect_city(text: str) -> str:
    if not text:
        return "Крым"
    for c in CITIES:
        if c in text:
            return c
    return "Крым"


async def collect_card_links(page) -> list:
    """Собирает href карточек со списка результатов левой панели."""
    hrefs = []
    # Скроллим левую панель, чтобы подгрузить больше результатов
    panel_sel = "div._1mbvbu1, div[class*='miniCard'], div[class*='_z3wsf']"
    for _ in range(8):
        try:
            await page.evaluate(
                """() => {
                    const sel = ['._1mbvbu1', '[class*=\"miniCard\"]', '[class*=\"_z3wsf\"]', '[class*=\"_1f88dgz\"]'];
                    for (const s of sel) {
                        const el = document.querySelector(s);
                        if (el) { el.scrollTop += 1500; return; }
                    }
                    window.scrollBy(0, 1500);
                }"""
            )
        except Exception:
            pass
        await page.wait_for_timeout(800)

    links = await page.query_selector_all("a[href*='/firm/']")
    for link in links:
        href = await link.get_attribute("href") or ""
        if "/firm/" in href:
            full = href if href.startswith("http") else "https://2gis.ru" + href
            hrefs.append(full.split("?")[0])
    return list(dict.fromkeys(hrefs))


async def parse_firm(context, url: str, category: str, region_label: str) -> bool:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(random.randint(2000, 3500))

        # Имя
        name = ""
        for sel in ["h1", "[itemprop='name']", "[class*='Title']"]:
            el = await page.query_selector(sel)
            if el:
                txt = (await el.inner_text()).strip()
                if txt and len(txt) < 250:
                    name = txt
                    break
        if not name:
            return False

        # Адрес
        address = ""
        for sel in ["[itemprop='address']", "a[href*='geo']", "[class*='_address'], [class*='Address']"]:
            el = await page.query_selector(sel)
            if el:
                a_txt = (await el.inner_text()).strip()
                if a_txt and len(a_txt) < 300:
                    address = a_txt
                    break

        # Телефон — на 2ГИС часто скрыт за «Показать»
        phone = ""
        try:
            show_btn = await page.query_selector("button:has-text('Показать'), [class*='_phone'] button")
            if show_btn:
                await show_btn.click()
                await page.wait_for_timeout(800)
        except Exception:
            pass

        for sel in ["a[href^='tel:']", "[itemprop='telephone']"]:
            el = await page.query_selector(sel)
            if el:
                if sel.startswith("a"):
                    href = await el.get_attribute("href") or ""
                    phone = href.replace("tel:", "").strip()
                else:
                    phone = (await el.inner_text()).strip()
                if phone:
                    break

        # Сайт
        website = ""
        site_links = await page.query_selector_all("a[href^='http']")
        for sl in site_links:
            try:
                href = await sl.get_attribute("href") or ""
                host = urlparse(href).netloc.lower()
                if host and "2gis" not in host and "yandex" not in host and \
                   "google" not in host and "vk.com" not in host and \
                   "instagram" not in host and "facebook" not in host and \
                   "t.me" not in host and "youtube" not in host:
                    website = href
                    break
            except Exception:
                continue

        # E-mail
        email = ""
        try:
            html = await page.content()
            m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html)
            if m:
                email = m.group(0)
        except Exception:
            pass

        city = detect_city(address) or detect_city(name) or region_label or "Крым"

        return save_item({
            "city": city,
            "name": name,
            "address": address,
            "phone": phone,
            "email": email,
            "website": website,
            "category": category,
            "source": "2ГИС",
            "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    except Exception as e:
        print(f"  ошибка карточки: {e}")
        return False
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def run(context):
    print("\n=== 2ГИС ===")
    page = await context.new_page()
    seen_firms = set()

    for region_label, base_url in REGIONS:
        for cat in CATEGORIES:
            search_url = base_url + quote_plus(cat)
            print(f"\n[2ГИС] {region_label} / {cat}")
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(random.randint(2500, 4500))
                links = await collect_card_links(page)
                print(f"  карточек найдено: {len(links)}")
            except Exception as e:
                print(f"  ошибка поиска: {e}")
                links = []

            added = 0
            for href in links[:25]:
                if href in seen_firms:
                    continue
                seen_firms.add(href)
                ok = await parse_firm(context, href, cat, region_label)
                if ok:
                    added += 1
                await asyncio.sleep(random.uniform(1.5, 3.0))

            print(f"  добавлено: {added}")
            await asyncio.sleep(random.uniform(3.0, 6.0))

    await page.close()
