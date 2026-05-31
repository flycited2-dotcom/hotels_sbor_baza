# Crimea Hotel Parser — Onboarding & Handoff

> ⚠️ **Актуальный handoff: [docs/HANDOFF_2026-05-31.md](docs/HANDOFF_2026-05-31.md)**.
> Этот ONBOARDING — общая историческая справка, читать его **после** свежего HANDOFF.

Парсер базы средств размещения по Крыму (отели, гостиницы, санатории, пансионаты,
базы отдыха, эллинги, кемпинги, глэмпинги, гостевые дома, хостелы). Работает по
расписанию, складывает CSV/XLSX, шлёт отчёты в Telegram, выгружает в Google Drive,
управляется двумя ботами.

> Последнее обновление: 2026-05-29. Текущая база: **11 993 записи**, email **2 019**, phone **3 218**.

---

## TL;DR

| Файл / каталог | За что отвечает |
|---|---|
| `_extracted/crimea_parser/main.py` | Оркестратор: список `RUNNERS` (12 источников), enrichment, merge, xlsx, gdrive, отчёт |
| `_extracted/crimea_parser/parsers/` | 12 источников данных (таблица ниже) |
| `_extracted/crimea_parser/utils/` | storage (CSV+dedup), merger (master_all), gdrive, excel_export, telegram_notify, progress, geo_city, categories |
| `_extracted/crimea_parser/bot/` | Бот №1 «Hotel_Lead2_Bot» (stdlib long-poll) |
| `parser_admin_bot/` | Бот №2 «АдминБотHotels» (aiogram) |
| `_extracted/crimea_parser/run_email_finder.py` | Добор контактов по master_all без полного парсинга |
| `_extracted/crimea_parser/run_vk.py` | Отдельный VK-добор (HTTP-only, без Chromium) |

**Прод-сервер:** `root@212.116.115.150` (sprinthost, СПб, Ubuntu 24.04, **RAM 5.8 ГБ — мало!**).
Файлы парсера: `/home/crimea_parser/`. Бот №2: `/opt/parser_admin_bot/` (ExecStart указывает сюда; `/root/parser_admin_bot/` — устаревшая копия, не используется). Секреты: `.env` (chmod 600).

> ⚠️ **RAM 5.8 ГБ** — нельзя запускать два Chromium одновременно (основной прогон + email_finder = OOM). VK-добор (HTTP) можно параллельно.

---

## Источники данных (12)

Порядок в `main.py` — быстрые HTTP-API сначала, тяжёлый Chromium потом, Crawler последним:

| # | Источник | Тип | Файл | Статус |
|---|---|---|---|---|
| 1 | OSM Overpass | HTTP/JSON | `parsers/osm.py` | ✅ ~3760, phone/email/website из тегов, города по bbox (`utils/geo_city.py`) |
| 2 | Wikidata SPARQL | HTTP/JSON | `parsers/wikidata.py` | ✅ ~10 (часто 429 — у Wikidata аварийный rate-limit) |
| 3 | Wikipedia | HTTP/JSON | `parsers/wikipedia.py` | ✅ ~73 |
| 4 | Госреестр Минэка | HTTP/JSON | `parsers/gosreestr.py` | ⏸ stub — endpoint не найден (домены NXDOMAIN после реформы 2022) |
| 5 | **VK Groups** | HTTP/JSON | `parsers/vk_groups.py` | ✅ **~6245** — главный источник email! Нужен `VK_TOKEN` |
| 6 | Я.Карты | Chromium | `parsers/yandex_maps.py` | ✅ ~1751 (имя+адрес+сайт; phone в headless не отдаётся) |
| 7 | Поиск (Я/Mail/Rambler/Bing) | Chromium | `parsers/search_engine.py` | ✅ ~147 |
| 8 | 2ГИС | Chromium | `parsers/twogis.py` | ⛔ блокирует Крым (403 → /museum) |
| 9 | Авито | Chromium | `parsers/avito.py` | ⛔ HTTP 429 «IP в бане» с DC-IP |
| 10 | Суточно.ру | Chromium | `parsers/sutochno.py` | селекторы устаревали |
| 11 | Ostrovok | Chromium | `parsers/ostrovok.py` | карточек 0 — не отдаёт |
| 12 | Crawler | aiohttp | `parsers/crawler.py` | ✅ обход website из master + sitemap |

**Добор контактов:** `parsers/email_finder.py` — заходит на website (mailto/JSON-LD/контактные страницы/обфускация),
`parsers/site_finder.py` (ищет сайт через DuckDuckGo для записей без сайта — работает),
`parsers/vk_email.py` (email с публичной VK-страницы).

**Постобработка:** `utils/merger.py` собирает `output/master_all.csv` (все прогоны, дедуп) →
`utils/excel_export.py` строит XLSX со вкладками по городам → `utils/gdrive.py` грузит в Google Drive.

---

## Боты Telegram

Группа отчётов: «База_Отель_Сбор» (`-1003781591836`). Админ: `user_id=1264067528`.

### Бот №1 — `@Hotel_Lead2_Bot` (`crimea_bot.service`, stdlib)
Команды: `/status`, `/sources`, `/db`, `/last_report`, `/tail [N]`, `/help`, и для админа `/run`, `/stop`, `/run_source <key>`.
Код: `_extracted/crimea_parser/bot/`. В `/run` уже стоит `--no-block` (корректно).

### Бот №2 — «АдминБотHotels» (`parser_admin_bot.service`, aiogram)
Команды: `/run`, `/run_emails`, `/run_source`, `/status`, `/tail`, `/stop`, `/schedule`, `/last_report`.
Код: `/opt/parser_admin_bot/` (в репо — `parser_admin_bot/`).

> ⚠️ **БАГ (фикс в репо, деплой ожидается):** `/run`, `/run_emails`, `/run_source` вызывали
> `systemctl start` oneshot-юнита, который блокируется на часы → обёртка ловила timeout 30с →
> ложная ошибка `❌ systemctl start: rc=124`. Сервис при этом РЕАЛЬНО стартовал.
> **Фикс:** `services/systemd.py` + `handlers/commands.py` — добавлен `--no-block`.
> **Задеплоено 2026-05-29** в `/opt/parser_admin_bot/` (services/systemd.py + handlers/commands.py), бот перезапущен. Ложная ошибка `rc=124` устранена.

---

## Сервер: подключение и команды

```bash
ssh root@212.116.115.150   # пароль — приватно, хранится у владельца (НЕ в репозитории)
```

| systemd-юнит | Назначение |
|---|---|
| `crimea_parser.service` | полный прогон (12 источников), oneshot, `TimeoutStartSec=12h`, `MemoryMax=3G` |
| `crimea_parser.timer` | автозапуск вс 03:00 MSK |
| `crimea_email_finder.service` | добор по master_all (`run_email_finder.py`) |
| `crimea_bot.service` | бот №1 (Restart=always) |
| `parser_admin_bot.service` | бот №2 |
| `crimea_watchdog.timer` | каждые 10 мин: алерт зависания/падения, heartbeat 30 мин |
| `crimea_vk.service` | transient (через `systemd-run`) — VK-добор |

```bash
# Запуск (всегда с --no-block для oneshot!)
systemctl start --no-block crimea_parser.service
# VK-добор отдельно (HTTP, можно параллельно):
systemd-run --unit=crimea_vk --property=WorkingDirectory=/home/crimea_parser \
  --setenv=PYTHONUNBUFFERED=1 /home/crimea_parser/venv/bin/python /home/crimea_parser/run_vk.py
# Только добор контактов по всей базе:
systemctl start --no-block crimea_email_finder.service
# Прогресс / логи
cat /home/crimea_parser/output/progress.json
tail -f /home/crimea_parser/parser.log
```

`.env` ключи: `TG_BOT_TOKEN`, `TG_CHAT_ID`, `VK_TOKEN` (бессрочный, scope groups),
`GDRIVE_FOLDER_ID`, `GDRIVE_CREDENTIALS`, `HEADLESS`, `AUTO_NOTIFY`, `ENRICH_LATEST`.

Деплой кода: `python _deploy_helper.py upload` + распаковка, либо точечно через paramiko
(см. историю). `_deploy_helper.py` — paramiko-helper (логин/пароль внутри).

---

## Известные проблемы

| Проблема | Статус |
|---|---|
| 2ГИС блокирует крымский регион (403) | не решается без РФ-прокси из РФ-датацентра |
| Авито 429 «проблема с IP» | нужен residential RU-прокси (~$5-15/мес) |
| Я.Карты не отдают phone в headless | phone берём из email_finder по website |
| Госреестр endpoint NXDOMAIN | искать живой адрес Нац.реестра средств размещения |
| **VK-шум**: по «база отдыха/вилла/апартаменты» цепляет турфирмы, чаты, частников (напр. «ТЕНТ-МАСТЕР») | нужна фильтрация по типу/ключевым словам — НЕ сделано |
| Город «Крым» (не уточнён) у ~2000 OSM-записей | bbox `geo_city.py` покрывает не все посёлки |
| email_finder `pick_address` хватает мусор (меню/текст вместо адреса) | низкий приоритет |

### Решено
OOM → MemoryMax=3G+OOMPolicy=stop · таймаут 4h→12h · DNS-сбой ронял отчёт → 5 ретраев в telegram_notify ·
CSV в Excel «одной колонкой» → разделитель `;`+QUOTE_ALL · дубли между прогонами → SQLite `dedup.db` ·
тихое зависание → watchdog+heartbeat · VK `_clean_site` `Invalid IPv6 URL` → try/except.

---

## Что делать дальше (приоритет)

1. **Задеплоить фикс бота №2** (`--no-block`) — убрать ложную ошибку `rc=124`. Файлы готовы в репо.
2. **Почистить VK-шум** — пометить нерелевантные VK-группы (нет отельных слов в названии/activity) как `needs_review`, не мешать чистым.
3. **email_finder по новым VK-записям** — у многих VK-групп есть `site` без email в контактах → добор с сайта. Ещё +500-800 email. (`systemctl start --no-block crimea_email_finder.service`, RAM — только когда основной прогон не идёт.)
4. **Прокси-слой** (task #5) — разблокировать Авито/2ГИС. Нужны креды прокси.
5. **DaData по ИНН** (task #6) — нужен живой Госреестр + платный API.

---

## История фаз (git)

| Фаза | Что |
|---|---|
| 1 | Базовый парсер из ТЗ |
| 2-3 | parser_admin_bot (aiogram) + XLSX |
| 4 | Бот №1 (stdlib) + crash-resistance |
| 5 | Crawler + bbox-города + чекпоинты + heartbeat |
| 6 | Wikipedia + Госреестр stub + VK Groups (заготовка) |
| 7 (29.05) | VK заработал (×2.8 email), фикс бота №2 (--no-block), синхронизация репо с сервером |

## Контакты
Заказчик: Alex (RitualB2B / ritualb2b.ru) · Группа: «База_Отель_Сбор» (`-1003781591836`) ·
Боты: `@Hotel_Lead2_Bot`, «АдминБотHotels» · Сервер: root@212.116.115.150 (sprinthost).
