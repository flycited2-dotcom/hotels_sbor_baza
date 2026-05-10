import asyncio
import random
import re
from utils.storage import save_item
from datetime import datetime

QUERIES = [
    ("гостиница", "Крым"),
    ("отель", "Крым"),
    ("хостел", "Крым"),
    ("эллинг", "Крым"),
    ("глэмпинг", "Крым"),
    ("кемпинг", "Крым"),
    ("база отдыха", "Крым"),
    ("дом отдыха", "Крым"),
    ("пансионат", "Крым"),
    ("гостевой дом", "Крым"),
]

CITIES = [
    "Симферополь","Ялта","Евпатория","Феодосия",
    "Керчь","Алушта","Судак","Севастополь","Саки",
]

def detect_city(text):
    for c in CITIES:
        if c in text:
            return c
    return "Крым"

async def run(context):
    page = await context.new_page()
    print("\n=== Авито ===")

    for keyword, region in QUERIES:
        print(f"\n[Авито] {keyword} / {region}")
        try:
            url = (
                f"https://www.avito.ru/rossiya_krym/"
                f"?q={keyword.replace(' ', '+')}"
                f"&s=104"
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(3000)

            for _ in range(8):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1000)

            links = await page.query_selector_all("a[data-marker='item-title']")
            hrefs = []
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    full = "https://www.avito.ru" + href if href.startswith("/") else href
                    hrefs.append(full)

            print(f"  Объявлений: {len(hrefs)}")

            for href in hrefs[:30]:
                detail_page = None
                try:
                    detail_page = await context.new_page()
                    await detail_page.goto(href, wait_until="networkidle", timeout=30000)
                    await detail_page.wait_for_timeout(2000)

                    name = ""
                    for sel in ["h1[itemprop='name']", "h1.title-info-title", "h1"]:
                        el = detail_page.locator(sel).first
                        if await el.count() > 0:
                            name = (await el.inner_text()).strip()
                            break

                    address = ""
                    for sel in [
                        "[class*='address-georeferences']",
                        "span[class*='geo-address']",
                        "[data-marker='delivery-location-summary/text']",
                    ]:
                        el = detail_page.locator(sel).first
                        if await el.count() > 0:
                            address = (await el.inner_text()).strip()
                            break

                    phone = ""
                    show_btn = detail_page.locator("button:has-text('Показать телефон')")
                    if await show_btn.count() > 0:
                        await show_btn.first.click()
                        await detail_page.wait_for_timeout(1500)
                        tel_el = detail_page.locator("a[href^='tel:']").first
                        if await tel_el.count() > 0:
                            phone = (await tel_el.inner_text()).strip()

                    email = ""
                    mailto = detail_page.locator("a[href^='mailto:']")
                    if await mailto.count() > 0:
                        href_m = await mailto.first.get_attribute("href") or ""
                        email = href_m.replace("mailto:", "").strip()

                    website = ""
                    desc = detail_page.locator("[class*='description']").first
                    if await desc.count() > 0:
                        desc_text = await desc.inner_text()
                        urls = re.findall(r'https?://[^\s,]+', desc_text)
                        if urls:
                            website = urls[0]

                    city = detect_city(address + " " + name)

                    save_item({
                        "city": city,
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": email,
                        "website": website,
                        "category": keyword,
                        "source": "Авито",
                        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

                    await detail_page.close()

                except Exception as e:
                    print(f"  Ошибка объявления: {e}")
                    if detail_page:
                        try:
                            await detail_page.close()
                        except:
                            pass
                    continue

                await asyncio.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"  Ошибка запроса [{keyword}]: {e}")

        await asyncio.sleep(random.uniform(6, 12))

    await page.close()
