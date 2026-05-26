# Parser Hotels — 3 задачи Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Три улучшения парсера крымских гостиниц: (A) XLSX-разбивка городов с порогом 10 контактов, (B) накопительный отчёт парсера с выбором файла в боте и загрузкой на Google Drive, (C) улучшение сбора email с 20% до 50%+.

**Architecture:** Все изменения вносятся в репозиторий `hotels_sbor_baza`. Задачи A и C — изменения в `crimea_parser`. Задача B — изменения в `parser_admin_bot` + новые утилиты. Задача A также затрагивает `hotel_lead_bot/services/excel.py`.

**Tech Stack:** Python 3.11+, asyncio, Playwright, aiogram 3.x, openpyxl, google-api-python-client, aiohttp, bs4

---

## Подготовка: клонировать репозиторий

- [ ] Клонировать репозиторий в рабочую директорию:
```bash
cd C:\Users\TLT-1\Documents\GitHub\parser_hotels
git clone https://github.com/flycited2-dotcom/hotels_sbor_baza .
```

---

## Задача A: XLSX — порог городов < 10 → лист «Остальные»

**Проблема:** Сейчас `build_xlsx` создаёт отдельный лист для каждого города, включая деревни с 1-2 объектами. Результат: 50+ листов с одиночными записями.

**Решение:** Города с количеством записей `< MIN_CITY_ROWS` объединять в лист «Остальные». Константа `MIN_CITY_ROWS = 10`.

**Files:**
- Modify: `_extracted/crimea_parser/utils/excel_export.py` — функция `build_xlsx`
- Modify: `hotel_lead_bot/services/excel.py` — функция `_build_workbook`

---

### Task A-1: Изменить `excel_export.py` (crimea_parser)

**Files:**
- Modify: `_extracted/crimea_parser/utils/excel_export.py`

- [ ] **Шаг 1: Найти блок группировки по городам в `build_xlsx`**

В файле `excel_export.py` найти этот блок (примерно строки 80-100):
```python
    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        city = (r.get("city") or "Не указан").strip() or "Не указан"
        by_city[city].append(r)

    for city in sorted(by_city.keys(), key=lambda c: -len(by_city[c])):
        sheet_name = _safe_sheet_name(city)
        if sheet_name in wb.sheetnames:
            sheet_name = _safe_sheet_name(f"{city}_2")
        ws = wb.create_sheet(sheet_name)
        _write_sheet(ws, by_city[city])
```

- [ ] **Шаг 2: Заменить блок на версию с порогом**

```python
    MIN_CITY_ROWS = 10

    by_city: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        city = (r.get("city") or "Не указан").strip() or "Не указан"
        by_city[city].append(r)

    others: list[dict] = []
    for city in sorted(by_city.keys(), key=lambda c: -len(by_city[c])):
        if len(by_city[city]) < MIN_CITY_ROWS:
            others.extend(by_city[city])
            continue
        sheet_name = _safe_sheet_name(city)
        if sheet_name in wb.sheetnames:
            sheet_name = _safe_sheet_name(f"{city}_2")
        ws = wb.create_sheet(sheet_name)
        _write_sheet(ws, by_city[city])

    if others:
        ws_others = wb.create_sheet("Остальные")
        _write_sheet(ws_others, others)
```

- [ ] **Шаг 3: Проверить вручную**

```bash
cd _extracted/crimea_parser
python -c "
from utils.excel_export import build_xlsx
# создаём тестовый CSV с несколькими городами
import csv, os
rows = [
    {'city': 'Ялта', 'name': f'Отель {i}', 'phone': '79001234567', 'email': '', 'category': 'Гостиница', 'address': '', 'website': '', 'source': 'osm', 'parsed_at': '2026-01-01', 'client_type': ''}
    for i in range(15)
] + [
    {'city': 'Деревня', 'name': f'Гостевой дом {i}', 'phone': '79001234568', 'email': '', 'category': 'Гостиница', 'address': '', 'website': '', 'source': 'osm', 'parsed_at': '2026-01-01', 'client_type': ''}
    for i in range(3)
]
with open('/tmp/test.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=';')
    writer.writeheader()
    writer.writerows(rows)
result = build_xlsx('/tmp/test.csv', '/tmp/test.xlsx')
print('OK:', result)
"
```

Ожидаемый результат: создан `/tmp/test.xlsx` с листами «Сводка», «Все», «Ялта» (15 записей), «Остальные» (3 записи). Листа «Деревня» НЕТ.

- [ ] **Шаг 4: Commit**

```bash
git add _extracted/crimea_parser/utils/excel_export.py
git commit -m "feat(xlsx): merge cities with <10 rows into 'Остальные' sheet"
```

---

### Task A-2: Изменить `hotel_lead_bot/services/excel.py`

**Files:**
- Modify: `hotel_lead_bot/services/excel.py`

- [ ] **Шаг 1: Добавить разбивку по городам в `_build_workbook`**

Текущая функция создаёт один лист с заголовком. Нужно добавить листы по городам. Найти функцию `_build_workbook` и добавить в конец после создания основного листа:

```python
MIN_CITY_ROWS = 10

def _build_city_sheets(wb, leads: list[dict]) -> None:
    """Добавляет листы по городам, города < MIN_CITY_ROWS → лист 'Остальные'."""
    from collections import defaultdict
    by_city: dict[str, list] = defaultdict(list)
    for lead in leads:
        city = (lead.get("city") or "Не указан").strip() or "Не указан"
        by_city[city].append(lead)

    others = []
    for city in sorted(by_city.keys(), key=lambda c: -len(by_city[c])):
        if len(by_city[city]) < MIN_CITY_ROWS:
            others.extend(by_city[city])
            continue
        ws = wb.create_sheet(_safe_name(city))
        _write_leads_sheet(ws, by_city[city])

    if others:
        ws = wb.create_sheet("Остальные")
        _write_leads_sheet(ws, others)


def _safe_name(name: str) -> str:
    """Обрезает имя листа до 31 символа, убирает запрещённые символы."""
    for ch in r'\/*?:[]\x00':
        name = name.replace(ch, '_')
    return name[:31]


def _write_leads_sheet(ws, leads: list[dict]) -> None:
    """Записывает список лидов на лист с заголовком и стилями."""
    from config import EXCEL_HEADERS
    from openpyxl.styles import Font, PatternFill, Alignment
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")
    ws.append(EXCEL_HEADERS)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for lead in leads:
        ws.append(_lead_to_row(lead))
```

Добавить вызов в конец функции `_build_workbook` (или в функции генерации отчёта):

```python
    _build_city_sheets(wb, leads)
```

- [ ] **Шаг 2: Commit**

```bash
git add hotel_lead_bot/services/excel.py
git commit -m "feat(hotel_lead_bot/excel): add per-city sheets with <10 threshold"
```

---

## Задача B: Накопительный отчёт + выбор файла в боте + Google Drive

**Проблема:**
1. Каждый прогон парсера создаёт отдельный `result_TIMESTAMP.csv`. Нет единой базы всех данных.
2. `/xlsx` в parser_admin_bot отдаёт только последний файл — невозможно получить старые результаты.
3. Данные нигде не заливаются на Google Drive — пользователь не может найти их.

**Решение:**
1. Новый скрипт `utils/merger.py` — объединяет все `result_*.csv` в `output/master_all.csv` + `output/master_all.xlsx` (с дедупликацией по имени+телефону).
2. Команда `/reports` в `parser_admin_bot` — inline-клавиатура со списком последних 10 CSV/XLSX файлов.
3. Утилита `utils/gdrive.py` — загрузка файлов на Google Drive. Команда `/upload_drive <file>` в боте.

**Files:**
- Create: `_extracted/crimea_parser/utils/merger.py`
- Create: `_extracted/crimea_parser/utils/gdrive.py`
- Modify: `parser_admin_bot/handlers/commands.py` — добавить `/reports`, `/upload_drive`
- Modify: `_extracted/crimea_parser/utils/excel_export.py` — экспортировать `build_xlsx` чтобы merger мог использовать
- Modify: `_extracted/crimea_parser/run_email_finder.py` — вызывать merger после обогащения

---

### Task B-1: Создать `utils/merger.py`

**Files:**
- Create: `_extracted/crimea_parser/utils/merger.py`

- [ ] **Шаг 1: Создать файл `merger.py`**

```python
"""Объединяет все result_*.csv в output/ в единый master_all.csv + master_all.xlsx."""
from __future__ import annotations

import csv
import glob
import os
from collections import OrderedDict

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
MASTER_CSV = os.path.join(OUTPUT_DIR, "master_all.csv")
FIELDNAMES = ["city", "name", "category", "client_type", "phone", "email",
              "website", "address", "social", "comment", "source", "parsed_at"]


def _dedup_key(row: dict) -> str:
    """Ключ дедупликации: нормализованное имя + телефон."""
    name = (row.get("name") or "").strip().lower()
    phone = (row.get("phone") or "").strip().replace(" ", "").replace("-", "")
    return f"{name}|{phone}"


def build_master(output_dir: str = OUTPUT_DIR) -> str:
    """
    Читает все result_*.csv (исключая *enriched* и master_all.csv),
    объединяет с дедупликацией, сохраняет в master_all.csv.
    Возвращает путь к файлу.
    """
    pattern = os.path.join(output_dir, "result_*.csv")
    files = sorted(
        [f for f in glob.glob(pattern) if "enriched" not in os.path.basename(f)],
        key=os.path.getmtime,
    )

    # enriched-файлы имеют приоритет над соответствующими raw
    enriched_bases = {
        os.path.basename(f).replace("_enriched", "")
        for f in glob.glob(os.path.join(output_dir, "*_enriched.csv"))
    }

    seen: OrderedDict[str, dict] = OrderedDict()
    for filepath in files:
        base = os.path.basename(filepath)
        # если есть enriched-версия — пропускаем raw
        if base in enriched_bases:
            continue
        _load_csv_into(filepath, seen)

    # поверх raw грузим enriched (они перезапишут/дополнят записи)
    for filepath in glob.glob(os.path.join(output_dir, "*_enriched.csv")):
        _load_csv_into(filepath, seen)

    rows = list(seen.values())
    os.makedirs(output_dir, exist_ok=True)
    with open(MASTER_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"[merger] master_all.csv: {len(rows)} записей из {len(files)} файлов")
    return MASTER_CSV


def _load_csv_into(filepath: str, seen: OrderedDict) -> None:
    try:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                key = _dedup_key(row)
                if key not in seen:
                    seen[key] = row
                else:
                    # обогащаем существующую запись недостающими полями
                    existing = seen[key]
                    for field in FIELDNAMES:
                        if not existing.get(field) and row.get(field):
                            existing[field] = row[field]
    except Exception as e:
        print(f"[merger] ошибка чтения {filepath}: {e}")


def build_master_xlsx(output_dir: str = OUTPUT_DIR) -> tuple[str, str]:
    """Строит master_all.csv и master_all.xlsx. Возвращает (csv_path, xlsx_path)."""
    csv_path = build_master(output_dir)
    xlsx_path = os.path.join(output_dir, "master_all.xlsx")
    try:
        from utils.excel_export import build_xlsx
        result = build_xlsx(csv_path, xlsx_path)
        xlsx_path = result or xlsx_path
    except Exception as e:
        print(f"[merger] xlsx ошибка: {e}")
        xlsx_path = ""
    return csv_path, xlsx_path
```

- [ ] **Шаг 2: Проверить вручную (на сервере или локально)**

```bash
cd _extracted/crimea_parser
python -c "from utils.merger import build_master; print(build_master())"
```

Ожидаемый результат: `[merger] master_all.csv: N записей из M файлов` и файл `output/master_all.csv`.

- [ ] **Шаг 3: Commit**

```bash
git add _extracted/crimea_parser/utils/merger.py
git commit -m "feat(merger): build deduplicated master_all.csv from all result CSVs"
```

---

### Task B-2: Создать `utils/gdrive.py`

**Зависимость:** Нужен `google-api-python-client` и `google-auth`. Уже есть в `hotel_lead_bot` — реиспользовать тот же `credentials.json` (сервисный аккаунт). Нужно включить Google Drive API в Google Cloud Console для того же проекта.

**Files:**
- Create: `_extracted/crimea_parser/utils/gdrive.py`
- Modify: `_extracted/crimea_parser/requirements.txt` — добавить `google-api-python-client>=2.0`

- [ ] **Шаг 1: Добавить зависимость в requirements.txt**

```
google-api-python-client>=2.0
google-auth>=2.0
```

- [ ] **Шаг 2: Создать `gdrive.py`**

```python
"""Загрузка файлов на Google Drive.

Требует: GDRIVE_FOLDER_ID в .env — ID папки на Drive, куда заливать файлы.
Credentials: тот же credentials.json что у hotel_lead_bot (сервисный аккаунт).
Нужно: в Google Cloud Console включить Drive API для проекта сервисного аккаунта,
        расшарить целевую папку сервисному аккаунту (Editor).
"""
from __future__ import annotations

import os
from pathlib import Path

CREDENTIALS_PATH = os.getenv("GDRIVE_CREDENTIALS", "/opt/hotel_lead_bot/credentials.json")
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "")


def upload_file(local_path: str, folder_id: str = FOLDER_ID) -> str | None:
    """
    Загружает файл на Google Drive в указанную папку.
    Возвращает web-ссылку на файл или None при ошибке.
    """
    if not folder_id:
        print("[gdrive] GDRIVE_FOLDER_ID не задан — пропуск загрузки")
        return None
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"[gdrive] credentials.json не найден: {CREDENTIALS_PATH}")
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        file_name = Path(local_path).name
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
               if local_path.endswith(".xlsx") else "text/csv"

        # если файл с таким именем уже есть в папке — обновляем, иначе создаём
        existing = service.files().list(
            q=f"name='{file_name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)",
        ).execute().get("files", [])

        media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

        if existing:
            file_id = existing[0]["id"]
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            meta = {"name": file_name, "parents": [folder_id]}
            result = service.files().create(body=meta, media_body=media, fields="id").execute()
            file_id = result["id"]

        link = f"https://drive.google.com/file/d/{file_id}/view"
        print(f"[gdrive] загружен: {file_name} → {link}")
        return link

    except Exception as e:
        print(f"[gdrive] ошибка загрузки {local_path}: {e}")
        return None
```

- [ ] **Шаг 3: Добавить GDRIVE_FOLDER_ID в `.env.example`**

```
# Google Drive: папка для автоматической загрузки XLSX/CSV отчётов.
# ID папки — последняя часть URL: drive.google.com/drive/folders/<ID>
# Расшарьте папку сервисному аккаунту из credentials.json (роль: Редактор).
GDRIVE_FOLDER_ID=
GDRIVE_CREDENTIALS=/opt/hotel_lead_bot/credentials.json
```

- [ ] **Шаг 4: Commit**

```bash
git add _extracted/crimea_parser/utils/gdrive.py _extracted/crimea_parser/.env.example _extracted/crimea_parser/requirements.txt
git commit -m "feat(gdrive): upload reports to Google Drive via service account"
```

---

### Task B-3: Добавить `/reports` и `/master` в `parser_admin_bot`

**Files:**
- Modify: `parser_admin_bot/handlers/commands.py`

- [ ] **Шаг 1: Добавить импорты в начало `commands.py`**

```python
import glob
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
```

- [ ] **Шаг 2: Добавить CallbackData класс после импортов**

```python
class ReportCallback(CallbackData, prefix="report"):
    path: str
```

- [ ] **Шаг 3: Добавить handler для `/reports`**

Добавить в файл `commands.py`:

```python
@router.message(Command("reports"))
async def cmd_reports(message: Message):
    if not is_admin(message):
        return
    output_dir = "/home/crimea_parser/output"
    # последние 10 CSV и XLSX файлов, новые сверху
    files = sorted(
        glob.glob(os.path.join(output_dir, "*.csv")) +
        glob.glob(os.path.join(output_dir, "*.xlsx")),
        key=os.path.getmtime,
        reverse=True,
    )[:10]

    if not files:
        await message.answer("Нет файлов в output/")
        return

    buttons = []
    for f in files:
        name = os.path.basename(f)
        size_kb = os.path.getsize(f) // 1024
        label = f"📄 {name} ({size_kb} KB)"
        # путь не влезает в CallbackData (64 байта) — используем индекс
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"dl:{name}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите файл для скачивания:", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("dl:"))
async def cb_download_file(callback: CallbackQuery):
    if not is_admin(callback):
        await callback.answer()
        return
    name = callback.data[3:]
    path = os.path.join("/home/crimea_parser/output", name)
    if not os.path.exists(path):
        await callback.message.answer(f"Файл не найден: {name}")
        await callback.answer()
        return
    await callback.message.answer_document(
        FSInputFile(path),
        caption=f"📎 {name}",
    )
    await callback.answer()
```

- [ ] **Шаг 4: Добавить handler для `/master`**

```python
@router.message(Command("master"))
async def cmd_master(message: Message):
    """Строит master_all.csv + xlsx из всех прогонов и отдаёт файлы."""
    if not is_admin(message):
        return
    await message.answer("⏳ Собираю мастер-файл из всех прогонов…")
    try:
        import sys
        sys.path.insert(0, "/home/crimea_parser")
        from utils.merger import build_master_xlsx
        csv_path, xlsx_path = build_master_xlsx()
        await message.answer_document(FSInputFile(csv_path), caption="📊 master_all.csv")
        if xlsx_path and os.path.exists(xlsx_path):
            await message.answer_document(FSInputFile(xlsx_path), caption="📊 master_all.xlsx")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {esc(str(e))}")
```

- [ ] **Шаг 5: Зарегистрировать новые команды в `bot.py`**

В `parser_admin_bot/bot.py` добавить в список команд:
```python
BotCommand(command="reports", description="Список файлов для скачивания"),
BotCommand(command="master", description="Мастер-файл из всех прогонов"),
```

- [ ] **Шаг 6: Commit**

```bash
git add parser_admin_bot/handlers/commands.py parser_admin_bot/bot.py
git commit -m "feat(admin_bot): /reports with file picker, /master cumulative report"
```

---

### Task B-4: Автозагрузка на Google Drive после прогона

**Files:**
- Modify: `_extracted/crimea_parser/run_email_finder.py`
- Modify: `_extracted/crimea_parser/main.py`

- [ ] **Шаг 1: В `run_email_finder.py` добавить загрузку на Drive**

После строки `tg_notify(...)` добавить:

```python
    # Google Drive (опционально, если GDRIVE_FOLDER_ID задан)
    if os.getenv("GDRIVE_FOLDER_ID"):
        try:
            from utils.gdrive import upload_file
            from utils.merger import build_master_xlsx
            # обновляем мастер-файл
            master_csv, master_xlsx = build_master_xlsx()
            upload_file(master_csv)
            if master_xlsx:
                upload_file(master_xlsx)
            if enriched:
                upload_file(enriched)
        except Exception as e:
            print(f"[gdrive] {e}")
```

- [ ] **Шаг 2: В `main.py` добавить то же после финального отчёта**

Найти блок в конце `main()` где вызывается `tg_notify` и добавить аналогичный блок с `upload_file`.

- [ ] **Шаг 3: Commit**

```bash
git add _extracted/crimea_parser/run_email_finder.py _extracted/crimea_parser/main.py
git commit -m "feat(runner): auto-upload master CSV/XLSX to Google Drive after parse run"
```

---

## Задача C: Улучшение сбора email (с 20% до 50%+)

**Анализ причин низкого покрытия email:**
1. У многих объектов нет `website` → `email_finder` пропускает их
2. `email_finder` обходит только главную + `/contacts`, `/booking`, `/about` — мало страниц
3. Не используются: sitemap.xml, Яндекс.Бизнес профили, VK-группы (ссылки уже есть)
4. Не декодируются обфусцированные email в JS (типа `['i','n','f','o'].join('')`)
5. 2GIS имеет API — там иногда есть email в расширенных данных

**Подход (4 уровня, от простого к сложному):**
- **C-1:** Улучшить обход сайтов: sitemap.xml + больше страниц (15 вместо 5)
- **C-2:** Для объектов без website — поиск сайта через DuckDuckGo/Яндекс по имени+город
- **C-3:** VK-группы: если есть `social` ссылка на VK — парсить описание группы и контакты
- **C-4:** Яндекс.Бизнес: если есть карточка в Яндекс.Картах — переходить на неё, искать email

**Files:**
- Modify: `_extracted/crimea_parser/parsers/email_finder.py` — уровни C-1, C-2, C-3
- Create: `_extracted/crimea_parser/parsers/site_finder.py` — поиск сайта по названию (C-2)
- Create: `_extracted/crimea_parser/parsers/vk_email.py` — VK группы (C-3)

---

### Task C-1: sitemap.xml + расширить список страниц

**Files:**
- Modify: `_extracted/crimea_parser/parsers/email_finder.py`

- [ ] **Шаг 1: Расширить список контактных страниц**

В `email_finder.py` найти список контактных URL (примерно):
```python
CONTACT_PATHS = ["/contacts", "/contact", "/about", "/booking"]
```

Заменить на:
```python
CONTACT_PATHS = [
    "/contacts", "/contact", "/kontakty", "/kontakt",
    "/about", "/o-nas", "/o-kompanii",
    "/booking", "/reserve", "/bronirovat",
    "/feedback", "/obratnaya-svyaz",
]
```

- [ ] **Шаг 2: Добавить парсинг sitemap.xml**

В `email_finder.py` добавить функцию после импортов:

```python
async def _get_sitemap_contact_urls(session, base_url: str, limit: int = 5) -> list[str]:
    """Читает sitemap.xml и возвращает до limit контактных URL."""
    import xml.etree.ElementTree as ET
    contact_keywords = {"contact", "about", "kontakt", "about-us", "obratit"}
    try:
        async with session.get(f"{base_url}/sitemap.xml", timeout=10) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()
        root = ET.fromstring(text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text]
        contact_urls = [
            u for u in urls
            if any(kw in u.lower() for kw in contact_keywords)
        ]
        return contact_urls[:limit]
    except Exception:
        return []
```

Добавить вызов этой функции при обходе сайта (перед основным обходом страниц).

- [ ] **Шаг 3: Commit**

```bash
git add _extracted/crimea_parser/parsers/email_finder.py
git commit -m "feat(email_finder): sitemap.xml parsing + extended contact paths"
```

---

### Task C-2: Поиск сайта для объектов без website

**Files:**
- Create: `_extracted/crimea_parser/parsers/site_finder.py`
- Modify: `_extracted/crimea_parser/parsers/email_finder.py`

- [ ] **Шаг 1: Создать `site_finder.py`**

```python
"""Поиск официального сайта отеля по имени и городу через DuckDuckGo HTML API."""
from __future__ import annotations

import asyncio
import re
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

HOTEL_DOMAINS_BLACKLIST = {
    "booking.com", "ostrovok.ru", "sutochno.ru", "tripadvisor.com",
    "yandex.ru", "google.com", "2gis.ru", "avito.ru", "vk.com",
    "instagram.com", "ok.ru", "otzovik.com", "zoon.ru",
}


async def find_website(name: str, city: str, session: aiohttp.ClientSession) -> str | None:
    """
    Ищет официальный сайт объекта через DuckDuckGo.
    Возвращает URL или None.
    """
    query = urllib.parse.quote(f"{name} {city} официальный сайт")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HotelParser/1.0)"}
    try:
        async with session.get(url, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select(".result__url"):
            href = a.get_text(strip=True)
            if not href:
                continue
            if not href.startswith("http"):
                href = "https://" + href
            domain = urllib.parse.urlparse(href).netloc.lstrip("www.")
            if not any(bl in domain for bl in HOTEL_DOMAINS_BLACKLIST):
                return href
    except Exception:
        pass
    return None
```

- [ ] **Шаг 2: Интегрировать `site_finder` в `email_finder`**

В функции `run_enrichment` в `email_finder.py` найти цикл по записям:
```python
for row in rows:
    if not row.get("website"):
        continue  # ← заменить это
```

Заменить на:
```python
for row in rows:
    website = row.get("website", "").strip()
    if not website:
        # пробуем найти сайт через поиск
        try:
            website = await find_website(
                row.get("name", ""), row.get("city", ""), session
            )
            if website:
                row["website"] = website
                print(f"[site_finder] {row.get('name')} → {website}")
        except Exception:
            pass
    if not website:
        continue
```

Добавить импорт вверху файла:
```python
from parsers.site_finder import find_website
```

- [ ] **Шаг 3: Commit**

```bash
git add _extracted/crimea_parser/parsers/site_finder.py _extracted/crimea_parser/parsers/email_finder.py
git commit -m "feat(email_finder): find website for records without one via DuckDuckGo"
```

---

### Task C-3: VK-группы — извлечение email из описания

**Files:**
- Create: `_extracted/crimea_parser/parsers/vk_email.py`
- Modify: `_extracted/crimea_parser/parsers/email_finder.py`

- [ ] **Шаг 1: Создать `vk_email.py`**

```python
"""Извлечение email из публичных VK-групп по ссылке в поле social."""
from __future__ import annotations

import re

import aiohttp
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")


async def extract_email_from_vk(vk_url: str, session: aiohttp.ClientSession) -> str | None:
    """
    Загружает публичную страницу VK-группы и ищет email в описании.
    Работает без авторизации для открытых групп.
    """
    if "vk.com" not in vk_url:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    try:
        async with session.get(vk_url, headers=headers, timeout=20) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        # описание группы — основное место для email
        description = soup.select_one(".wall_module") or soup.select_one("#page_info_wrap")
        text = description.get_text(" ", strip=True) if description else soup.get_text(" ")
        emails = EMAIL_RE.findall(text)
        # фильтруем системные адреса VK
        emails = [e for e in emails if "vk.com" not in e and "vkontakte" not in e]
        return emails[0] if emails else None
    except Exception:
        return None
```

- [ ] **Шаг 2: Подключить VK email в `email_finder.py`**

В функции `run_enrichment`, после извлечения email с сайта, добавить fallback через VK:

```python
        # fallback: если email не нашли, пробуем VK-группу
        if not row.get("email") and row.get("social") and "vk.com" in row.get("social", ""):
            try:
                from parsers.vk_email import extract_email_from_vk
                vk_email = await extract_email_from_vk(row["social"], session)
                if vk_email:
                    row["email"] = vk_email
                    enriched_count += 1
            except Exception:
                pass
```

- [ ] **Шаг 3: Commit**

```bash
git add _extracted/crimea_parser/parsers/vk_email.py _extracted/crimea_parser/parsers/email_finder.py
git commit -m "feat(email_finder): extract email from VK group pages as fallback"
```

---

### Task C-4: Обновить `run_email_finder.py` — прогонять по master

Сейчас email_finder обрабатывает только последний CSV. Нужно обрабатывать мастер-файл.

**Files:**
- Modify: `_extracted/crimea_parser/run_email_finder.py`

- [ ] **Шаг 1: Изменить логику выбора файла**

```python
async def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    
    # Сначала пробуем master_all.csv — он содержит все данные
    master = os.path.join(output_dir, "master_all.csv")
    if not os.path.exists(master):
        # если мастера нет — строим его
        from utils.merger import build_master
        master = build_master(output_dir)
    
    if not master or not os.path.exists(master):
        print("Нет CSV-файлов в output/ — нечего обогащать.")
        return
    
    print(f"Обогащаем: {master}")
    enriched = await run_enrichment(master)
    # ... остальной код без изменений
```

- [ ] **Шаг 2: Commit**

```bash
git add _extracted/crimea_parser/run_email_finder.py
git commit -m "feat(runner): run email enrichment on master_all.csv instead of latest only"
```

---

## Деплой на сервер

- [ ] **Обновить сервер**

```bash
python _deploy_helper.py upload
python _deploy_helper.py deploy
```

Или напрямую:
```bash
ssh root@212.116.115.150
cd /home/crimea_parser
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart crimea_parser_bot.service parser_admin_bot.service
```

- [ ] **Добавить GDRIVE_FOLDER_ID в `.env` на сервере** (если нужна загрузка на Drive)

```bash
echo "GDRIVE_FOLDER_ID=<ваш_folder_id>" >> /home/crimea_parser/.env
echo "GDRIVE_CREDENTIALS=/opt/hotel_lead_bot/credentials.json" >> /home/crimea_parser/.env
```

---

## Ожидаемый результат

| Метрика | До | После |
|---------|-----|-------|
| Email покрытие | ~20% (900/6000) | ~45-55% (2700-3300/6000) |
| Листов в XLSX с 1-2 объектами | много | 0 (все в «Остальные») |
| Доступ к историческим отчётам | нет | `/reports` в боте |
| Накопительная база | нет | `master_all.csv` |
| Google Drive | нет | авто-загрузка после прогона |

---

## Self-Review

**Покрытие spec:**
- ✅ XLSX порог городов < 10 → «Остальные» (Task A-1, A-2)
- ✅ Накопительный отчёт со всеми данными (Task B-1: merger.py)
- ✅ Выбор отчёта в боте (Task B-3: /reports с inline-клавиатурой)
- ✅ Google Drive (Task B-2: gdrive.py + авто-загрузка в B-4)
- ✅ Улучшение email (Task C-1: sitemap, C-2: site_finder, C-3: VK)
- ✅ Деплой описан

**Gaps:** Google Drive требует ручной настройки (включить Drive API, расшарить папку) — это не автоматизируется кодом. Документировано в Task B-2 шаг 2.

**Type consistency:** `build_master_xlsx()` возвращает `tuple[str, str]` — используется в B-3 и B-4 одинаково. ✅
