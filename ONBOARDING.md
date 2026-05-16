# Crimea Hotel Parser — Onboarding & Handoff

Парсер базы средств размещения по Крыму (отели, гостиницы, санатории, пансионаты,
базы отдыха, эллинги, кемпинги, глэмпинги, гостевые дома, хостелы). Работает по
расписанию, складывает CSV/XLSX, шлёт отчёты в Telegram, управляется ботом.

---

## TL;DR

**Куда смотреть в первую очередь:**

| Файл / каталог | За что отвечает |
|---|---|
| `_extracted/crimea_parser/main.py` | Оркестратор — список `RUNNERS`, порядок источников, email_finder, отчёт |
| `_extracted/crimea_parser/parsers/` | 12 источников данных (см. таблицу ниже) |
| `_extracted/crimea_parser/bot/` | Telegram-бот (long-poll, команды управления) |
| `_extracted/crimea_parser/utils/` | storage (CSV+dedup), progress, telegram_notify, browser, geo_city, excel_export |
| `_extracted/crimea_parser/deploy.sh` | One-click деплой: venv, Chromium, systemd-юниты, watchdog, бот |
| `_extracted/crimea_parser/watchdog.sh` | Алерты «завис»/«упал», heartbeat каждые 30 мин |

**Прод-сервер:** `root@212.116.115.150` (sprinthost, СПб, Ubuntu 24.04).
Все файлы парсера — в `/home/crimea_parser/`. Креды — в `/home/crimea_parser/.env`.

---

## Архитектура

```
┌──────────────────────┐    ┌─────────────────────────┐
│ crimea_bot.service   │←──→│ crimea_parser.service   │
│ long-poll Telegram   │    │ oneshot, 12 источников  │
│ /run /stop /status   │    │ TimeoutStartSec=12h     │
│ /sources /db /tail   │    │ MemoryMax=3G            │
└──────────────────────┘    └─────────────────────────┘
        │                              │
        └─── читает state ─────────────┤
                                       ▼
            ┌────────────────────────────────────┐
            │ /home/crimea_parser/output/        │
            │   progress.json — текущее состоние │
            │   dedup.db — SQLite UNIQUE base    │
            │   result_*.csv / *_enriched_*.csv  │
            └────────────────────────────────────┘
                                       │
                ┌──────────────────────┘
                ▼
        ┌──────────────────────┐
        │ crimea_watchdog.timer│  каждые 10 мин:
        │ (системный таймер)   │  — алерт если CSV не растёт > 30 мин
        │                      │  — heartbeat каждые 30 мин
        │                      │  — алерт при failed
        └──────────────────────┘
```

Расписание: `crimea_parser.timer` срабатывает каждое **воскресенье 03:00 MSK**.

---

## Источники данных (12 штук)

Порядок в `main.py` (быстрые HTTP-API сначала, тяжёлый Chromium потом):

| # | Источник | Тип | Файл | Статус |
|---|---|---|---|---|
| 1 | OSM Overpass | HTTP/JSON | `parsers/osm.py` | ✅ ~3600 объектов, реальные phone/email/website |
| 2 | Wikidata SPARQL | HTTP/JSON | `parsers/wikidata.py` | ✅ ~10-15 крупных объектов |
| 3 | Wikipedia (ru) | HTTP/JSON | `parsers/wikipedia.py` | ✅ ~80 объектов с infobox |
| 4 | Госреестр Минэка | HTTP/JSON | `parsers/gosreestr.py` | ⏸ stub, нужен живой endpoint |
| 5 | VK Groups | HTTP/JSON | `parsers/vk_groups.py` | ⏸ нужен `VK_TOKEN` в .env |
| 6 | Я.Карты | Chromium | `parsers/yandex_maps.py` | ✅ ~1300 (с адресами, без phone) |
| 7 | Поиск (Я/Mail/Rambler/Bing) | Chromium | `parsers/search_engine.py` | ✅ цепочка fallback, ~100-200 |
| 8 | 2ГИС | Chromium | `parsers/twogis.py` | ⛔ блокирует Крым на 403 → /museum |
| 9 | Авито | Chromium | `parsers/avito.py` | ⛔ HTTP 429 «IP в бане» с DC-IP |
| 10 | Суточно.ру | Chromium | `parsers/sutochno.py` | селекторы устаревали, проверить |
| 11 | Ostrovok | Chromium | `parsers/ostrovok.py` | селекторы устаревали, проверить |
| 12 | Crawler | aiohttp | `parsers/crawler.py` | ✅ обходит website из CSV, sitemap + ссылки |

После всех — `parsers/email_finder.py` обогащает контактами по website.
Затем `utils/excel_export.py` строит XLSX со вкладками по городам.
Затем `utils/telegram_notify.py` шлёт отчёт в группу.

---

## Telegram бот

**Бот:** `@Hotel_Lead2_Bot` (токен в `.env` на сервере).
**Группа:** «База_Отель_Сбор» (`-1003781591836`).
**Админ:** `user_id=1264067528` — только он может `/run` `/stop` `/run_source`.

### Команды

| Команда | Кто может | Что делает |
|---|---|---|
| `/status` | все | этап + счётчик + время |
| `/sources` | все | разбивка по источникам в текущем CSV |
| `/db` | все | накопленная база (SQLite) |
| `/last_report` | все | прислать свежий CSV |
| `/tail [N]` | все | последние N строк parser.log |
| `/help` | все | список команд |
| `/run` | только админ | стартовать полный прогон |
| `/stop` | только админ | остановить прогон |
| `/run_source <key>` | только админ | точечный прогон (см. ключи ниже) |

**Ключи `/run_source`:** `osm`, `wikidata`, `wikipedia`, `gosreestr`, `vk`,
`yandex`, `search`, `2gis`, `avito`, `sutochno`, `ostrovok`, `crawler`.

---

## Подключение к серверу

```bash
ssh root@212.116.115.150
# пароль: tRu741mAz
```

### Где что лежит на сервере

| Путь | Что |
|---|---|
| `/home/crimea_parser/` | основная директория парсера |
| `/home/crimea_parser/venv/` | Python venv (3.12) |
| `/home/crimea_parser/.env` | TG_BOT_TOKEN, TG_CHAT_ID, HEADLESS, AUTO_NOTIFY, VK_TOKEN |
| `/home/crimea_parser/output/` | CSV/XLSX-отчёты, progress.json, dedup.db |
| `/home/crimea_parser/parser.log` | stdout прогона |
| `/home/crimea_parser/parser_error.log` | stderr Playwright/Chromium |
| `/home/crimea_parser/bot.log` | лог Telegram-бота |
| `/etc/systemd/system/crimea_parser.service` | основной юнит парсера |
| `/etc/systemd/system/crimea_parser.timer` | вс 03:00 MSK |
| `/etc/systemd/system/crimea_bot.service` | бот (Restart=always) |
| `/etc/systemd/system/crimea_watchdog.timer` | каждые 10 мин |

### Полезные команды

```bash
# Статус всех юнитов
systemctl status crimea_parser.service crimea_bot.service crimea_watchdog.timer

# Прогресс
tail -f /home/crimea_parser/parser.log
cat /home/crimea_parser/output/progress.json

# Что в свежем CSV
wc -l /home/crimea_parser/output/result_*.csv | tail -5

# Перезапустить бот после изменения кода
systemctl restart crimea_bot.service

# Ручной запуск (быстрый smoke)
cd /home/crimea_parser && ./venv/bin/python main.py
```

---

## Деплой нового кода

С локальной машины (Windows + Git Bash):

```bash
# 1. правки в _extracted/crimea_parser/...
tar -czf crimea_parser.tar.gz -C _extracted crimea_parser
python _deploy_helper.py upload
python _deploy_helper.py exec "cd /root && rm -rf crimea_parser && tar -xzf crimea_parser.tar.gz && rsync -av --exclude=venv --exclude=output --exclude='*.log' /root/crimea_parser/ /home/crimea_parser/ | tail -8; find /home/crimea_parser -name __pycache__ -exec rm -rf {} + 2>/dev/null; systemctl restart crimea_bot.service"
```

Полный re-deploy с пересборкой venv/Chromium: `bash deploy.sh` на сервере.

`_deploy_helper.py` — простой Python-helper на paramiko (логин/пароль захардкожены).

---

## Известные проблемы и узкие места

### Критичные
1. **2ГИС блокирует Крым** на уровне сервиса (geo-restriction). Web-парсинг невозможен.
2. **Авито HTTP 429** с DC-IP sprinthost. Нужен residential proxy.
3. **Я.Карты в headless не отдают телефон** из правой панели/org-страницы (WebGL-зависимая отрисовка). Адреса + сайты — есть.
4. **Госреестр** — все известные домены `*.tourism.gov.ru` сейчас NXDOMAIN. Нужно найти живой endpoint после реформы 2022.

### Решённые (как сделано)
- ✅ **OOM при ~5000 объектах** → `MemoryMax=3G` + `OOMPolicy=stop`
- ✅ **Таймаут systemd 4h** → `TimeoutStartSec=12h`
- ✅ **DNS-сбой ронял отчёт** → 5 ретраев с экспоненциальным backoff в `telegram_notify`
- ✅ **CSV в Excel «в одну колонку»** → разделитель `;` + `QUOTE_ALL` + чистка `\n\r\t`
- ✅ **66% записей с городом «Крым»** → bbox-таблица `utils/geo_city.py` по lat/lon
- ✅ **Дубли между прогонами** → SQLite `output/dedup.db` с UNIQUE
- ✅ **Парсер тихо зависал** → watchdog алертит, heartbeat каждые 30 мин
- ✅ **Финальный отчёт терялся при падении** → чекпоинты в TG после каждого этапа

---

## Что делать дальше

### Если хотите больше данных
1. **VK Groups** (~500-2000 объектов): создать app на dev.vk.com, взять
   user `access_token`, добавить `VK_TOKEN=...` в `.env`, запустить
   `/run_source vk`.
2. **Госреестр** (~800-1500): найти живой endpoint Национального реестра
   средств размещения (ФЗ-590/2022). Кандидаты для поиска через DevTools:
   сайт Минэкономразвития туризма, ФНС-открытые данные, fsa.gov.ru.
3. **Residential RU-proxy** (~$5-15/мес от Soax/Proxy6): разблокирует
   Авито и потенциально 2ГИС через прокси-цепочку.
4. **Wikidata расширенный**: текущий SPARQL даёт 10-15 объектов. Можно
   расширить типы P31 и добавить запросы по бoundingbox координат.

### Эксплуатация
- Раз в неделю проверять `/last_report` в группе после воскресного прогона
- Если приходит «❌ Парсер упал» — посмотреть `/tail 60` для диагностики
- Раз в квартал проверять селекторы Я.Карт / Суточно / Ostrovok (они меняются)

### Архитектурный долг
- `parsers/twogis.py` и `parsers/avito.py` сейчас бессмысленны на этом
  VPS — можно либо удалить из `RUNNERS`, либо оставить «на случай прокси»
- `parser_admin_bot/` (отдельный старый проект aiogram) и
  `_extracted/crimea_parser/bot/` (новый stdlib-бот) — два бота. Сейчас
  работает только новый. Старый можно удалить когда убедимся что
  весь функционал перенесён.

---

## История фаз (git log)

| Фаза | Коммит | Что добавлено |
|---|---|---|
| 1 | `066c5ad` | Базовый парсер из ТЗ заказчика |
| 2-3 | `e18a002` | parser_admin_bot (aiogram) + XLSX-экспорт |
| 4 | `1f03369` | Telegram control bot (stdlib) + crash-resistance |
| 5 | `548e692` | Crawler + bbox-города + чекпоинты + heartbeat |
| 6 | `b67a919` | Wikipedia + Госреестр stub + VK Groups (opt-in) |

---

## Контакты

- **Заказчик:** Alex (RitualB2B / ritualb2b.ru)
- **Telegram-группа отчётов:** «База_Отель_Сбор» (id `-1003781591836`)
- **Бот:** `@Hotel_Lead2_Bot`
- **Сервер:** root@212.116.115.150 (sprinthost.ru)
