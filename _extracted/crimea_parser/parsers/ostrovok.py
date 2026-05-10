import asyncio
import random
from utils.storage import save_item
from datetime import datetime

CITIES_OSTROVOK = [
    ("simferopol", "Симферополь"),
    ("yalta",      "Ялта"),
    ("evpatoriya", "Евпатория"),
    ("feodosiya",  "Феодосия"),
    ("kerch",      "Керчь"),
    ("alushta",    "Алушта"),
    ("sudak",      "Судак"),
    ("sevastopol", "Севастополь"),
]

async def run(context):
    page = await context.new_page()
    print("\n=== Ostrovok.ru ===")

    for city_slug, city_name in CITIES_OSTROVOK:
        print(f"\n[Ostrovok] {city_name}")
        try:
            url = f"https://ostrovok.ru/hotel/{city_slug}/"
            await page.goto(url, wait_until="networkidle", timeout=40000)
            await page.wait_for_timeout(3000)

            for _ in range(8):
                await page.keyboard.press("End")
                await page.wait_for_timeout(1000)

            cards = await page.query_selector_all(
                "[class*='hotel-card'], [class*='HotelCard'], [data-testid*='hotel']"
            )
            print(f"  Карточек: {len(cards)}")

            for card in cards:
                try:
                    name = ""
                    for sel in ["[class*='name']", "[class*='title']", "h3", "h2"]:
                        el = await card.query_selector(sel)
                        if el:
                            name = (await el.inner_text()).strip()
                            if name:
                                break

                    if not name:
                        continue

                    address = ""
                    for sel in ["[class*='address']", "[class*='location']"]:
                        el = await card.query_selector(sel)
                        if el:
                            address = (await el.inner_text()).strip()
                            break

                    href = ""
                    a_el = await card.query_selector("a")
                    if a_el:
                        href = await a_el.get_attribute("href") or ""
                        if href.startswith("/"):
                            href = "https://ostrovok.ru" + href

                    save_item({
                        "city": city_name,
                        "name": name,
                        "address": address,
                        "phone": "",
                        "email": "",
                        "website": href,
                        "category": "отель",
                        "source": "Ostrovok",
                        "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })

                except Exception as e:
                    print(f"  Ошибка карточки: {e}")
                    continue

        except Exception as e:
            print(f"  Ошибка города [{city_name}]: {e}")

        await asyncio.sleep(random.uniform(4, 8))

    await page.close()
