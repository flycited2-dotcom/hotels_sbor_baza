"""Доделывает поле `city` в существующем CSV через Nominatim reverse geocoding.

CSV хранит уже без координат, поэтому реверс-геокодинг невозможен post-factum.
Этот скрипт делает другое: повторно опрашивает Overpass с координатами,
сопоставляет с записями в CSV по name+approximate_address и проставляет
city из новой логики geo_city.

Использование:
    python backfill_cities.py output/result_enriched_xxx.csv
Записывает рядом result_..._backfilled.csv
"""
import csv
import json
import os
import sys

from utils.geo_city import detect_city_by_coords
from utils.storage import CSV_DELIMITER, FIELDS
from parsers.osm import _fetch_overpass, _detect_city


def main(in_path: str) -> str:
    # читаем CSV
    with open(in_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    print(f"CSV: {in_path}, всего записей: {len(rows)}")
    targets = [r for r in rows if (r.get("city") or "").strip() in ("", "Крым") and r.get("source") == "OSM"]
    print(f"Кандидатов на бэкфилл (OSM с city=Крым): {len(targets)}")
    if not targets:
        return in_path

    # тянем свежий OSM с координатами
    print("Запрос Overpass…")
    elements = _fetch_overpass()
    print(f"  объектов: {len(elements)}")

    # строим индекс name → (lat, lon, tags)
    by_name: dict[str, tuple[float, float, dict]] = {}
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or tags.get("name:ru") or tags.get("operator") or "").strip().lower()
        if not name:
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None and "center" in el:
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")
        if lat is None or lon is None:
            continue
        if name not in by_name:
            by_name[name] = (lat, lon, tags)

    print(f"  индекс name → coords: {len(by_name)}")

    updated = 0
    for r in rows:
        if r.get("source") != "OSM":
            continue
        cur_city = (r.get("city") or "").strip()
        if cur_city and cur_city != "Крым":
            continue
        name = (r.get("name") or "").strip().lower()
        if name not in by_name:
            continue
        lat, lon, tags = by_name[name]
        new_city = _detect_city(tags, lat, lon)
        if new_city and new_city != "Крым":
            r["city"] = new_city
            updated += 1

    print(f"Обновлено: {updated}")

    out_path = in_path.replace(".csv", "_backfilled.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        # пишем по тем же полям что были в исходнике, не наш FIELDS
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Сохранён: {out_path}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backfill_cities.py <csv-path>")
        sys.exit(1)
    main(sys.argv[1])
