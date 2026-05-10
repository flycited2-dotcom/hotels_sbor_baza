import asyncio
import random
from utils.storage import save_item
from datetime import datetime

CITIES_SUTOCHNO = [
    ("simferopol", "Симферополь"),
    ("yalta", "Ялта"),
    ("evpatoriya", "Евпатория"),
    ("feodosiya", "Феодосия"),
    ("kerch", "Керчь"),
    ("alushta", "Алушта"),
    ("sudak", "Судак"),
    ("sevastopol", "Севастополь"),
]

async def run(context):
    page = await context.new_page()
    print("\n=== Суточно.ру ===")

    for city_slug, city_name in CITIES_SUTOCHNO:
        print(f"\n[Суточно] {city_name}")
        try:
            url = f"https://sutochno.ru/{city_slug}/vse-obekty"
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await page.wait_for_timeout(3000)

            for _ in range(10):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1200)

            cards = await page.query_selector_all("[class*='object-card'], [class*='ObjectCard']")
            links = []
            for card in cards:
                a = await card.query_selector("a")
                if a:
                    href = await a.get_attribute("href")
                    if href:
                        links.append("https://sutochno.ru" + href if href.startswith("/") else href)

            print(f"  Объектов: {len(links)}")

            for href in links[:25]:
                det = None
                try:
                    det = await context.new_page()
                    await det.goto(href, wait_until="networkidle", timeout=30000)
                    await det.wait_for_timeout(2000)

                    name = ""
                    for sel in ["h1[class*='title']", "h1"]:
                        el = det.locator(sel).first
                        if await el.count() > 0:
                            name = (await el.inner_text()).strip()
                            break

                    if not name:
                        await det.close()
                        continue

                    address = ""
                    for sel in ["[class*='address']", "[class*='location']"]:
                        el = det.locator(sel).first
                        if await el.count() > 0:
                            address = (await el.inner_text()).strip()
                            break

                    phone = ""
                    show_phone = det.locator("button:has-text('телефон'), button:has-text('Позвонить')")
                    if await show_phone.count() > 0:
                        await show_phone.first.click()
                        await det.wait_for_timeout(1200)

                    tel_el = det.locator("a[href^='tel:']").first
                    if await tel_el.count() > 0:
                        phone = (await tel_el.inner_text()).strip()

                    save_item({
                        "city": city_name,
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "email": "",
                        "website": href,
                        "category": "аренда",
                        "source": "Суточно.ру",
                        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

                    await det.close()

                except Exception as e:
                    print(f"  Ошибка объекта: {e}")
                    if det:
                        try:
                            await det.close()
                        except:
                            pass

                await asyncio.sleep(random.uniform(2, 3.5))

        except Exception as e:
            print(f"  Ошибка города [{city_name}]: {e}")

        await asyncio.sleep(random.uniform(5, 8))

    await page.close()
