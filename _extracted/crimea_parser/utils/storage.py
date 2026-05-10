import csv
import os
import re
from datetime import datetime

FIELDS = ["city", "name", "address", "phone", "email", "website", "category", "source", "parsed_at"]

OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"result_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")

# Разделитель `;` — RU Excel читает столбцы из коробки.
CSV_DELIMITER = ";"

_seen = set()
_rows = []


def normalize_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    else:
        return (raw or "").strip()
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def _clean(value: str) -> str:
    """Убираем переносы и табуляции — иначе Excel ломает строку."""
    if not value:
        return ""
    s = str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _key(item):
    return f"{item.get('name','').lower().strip()}|{item.get('city','').lower().strip()}"


def save_item(item):
    global _rows
    k = _key(item)
    if k in _seen or not item.get("name"):
        return False
    _seen.add(k)

    cleaned = {k_: _clean(item.get(k_, "")) for k_ in FIELDS}
    if cleaned.get("phone"):
        cleaned["phone"] = normalize_phone(cleaned["phone"])

    _rows.append(cleaned)
    _flush()
    print(f"  ✓ [{cleaned['source']}] {cleaned['city']} | {cleaned['name']} | "
          f"{cleaned.get('phone') or '—'} | {cleaned.get('email') or '—'}")
    return True


def _flush():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDS,
            delimiter=CSV_DELIMITER, quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(_rows)


def total():
    return len(_rows)


def get_output_file():
    return OUTPUT_FILE
