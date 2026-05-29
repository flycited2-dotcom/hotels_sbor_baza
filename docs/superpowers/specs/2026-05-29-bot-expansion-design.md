# Спека — расширение бота №2 «АдминБотHotels» (этап 3)

Дата: 2026-05-29
Код бота: репозиторий `parser_admin_bot/`, сервер `/opt/parser_admin_bot/`.
Сервис: `parser_admin_bot.service`.

## Цель

Дать владельцу полный контроль и видимость процесса через Telegram: пульт-меню на кнопках, аналитику базы, прозрачность по Google Drive и живой прогресс. Управление прогонами/файлами/расписанием уже есть — добавляем то, чего нет: контроль данных и Drive.

## Принцип архитектуры

Логику рендера выносим в сервисы (возвращают готовый текст/разметку). Команды и кнопки меню вызывают одни и те же функции — без дублирования. Хендлеры компактные (5–15 строк), как в текущем `commands.py`.

## Новые модули

### `services/stats.py`
Аналитика `output/master_all.csv` (читается напрямую, без импорта парсера):
- `get_stats_text() -> str` — всего записей; % с email / телефоном / сайтом; топ-10 городов; разбивка по источникам и типам клиентов.
- Дельта: снапшот `output/.stats_prev.json` (`total, email, phone, csv_mtime`). Логика: нет снапшота → создать, показать «дельта со следующего прогона»; `csv_mtime` изменился → показать `+N записей, +M email, +K тел.` и обновить снапшот; не изменился → «без изменений с прошлого прогона».

### `services/progress.py`
- `get_progress_text() -> str` — парсит `output/progress.json`: `status`, `stage`, `current_count`, `completed_sources`, `last_update`. Если `status=running`, а `last_update` старше 20 мин → пометка «возможно завис/упал».

### `services/drive.py`
- При импорте подхватывает `/home/crimea_parser/.env` (там `GDRIVE_FOLDER_ID`, `GDRIVE_TOKEN`), `load_dotenv` без override.
- `folder_link() -> str` — ссылка на папку.
- `get_drive_text() -> str` — ссылка + последние 5 файлов с датами/размерами (через `utils.gdrive._get_service`, тот же scope `drive.file`).
- `reupload_master() -> list[str]` — пересобрать `master_all` (`utils.merger.build_master_xlsx`) и залить (`utils.gdrive.upload_file`); вернуть ссылки.

### `services/panel.py`
- `async def status_text() -> str` — статус юнитов (`is_active`) + стадия + сводка последнего CSV. Используют и `/status`, и кнопка меню (убирает дублирование).
- `main_menu_kb()`, `run_menu_kb()`, `drive_kb()` — `InlineKeyboardMarkup` для панелей.

## Хендлеры

### `handlers/menu.py` (новый роутер `menu_router`)
- `/menu` — пульт: `▶ Прогон · 📊 Статус · 🗄 Стата базы · 📁 Файлы · ☁ Drive · 🗓 Расписание · 🔄 Прогресс`.
- `/stats`, `/drive`, `/progress` — текстовые алиасы кнопок.
- Callback-роутер по префиксу `menu:*` — каждый раздел редактирует сообщение (текст + кнопка `◀ Назад`). Подменю «Прогон»: Полный прогон / Обогатить master (email) / Стоп / Назад.
- Авторизация callback'ов: `from_user.id in ADMIN_IDS` (как в существующем `cb_download_file`).

### Правки `handlers/commands.py`
- `VALID_SOURCES` += `vk`, `wikipedia`, `crawler` (шаблон-юнит `crimea_parser_source@.service` уже есть).
- `cmd_status` → вызывает `panel.status_text()`.
- `/help`: пояснить, что `/run_emails` обогащает `master_all`; добавить `/menu`, `/stats`, `/drive`, `/progress`.

### Правка `bot.py`
- `dp.include_router(menu_router)` после `commands.router`. Порядок важен: `_block_strangers` в commands отсекает чужих раньше, чем сообщение дойдёт до menu.

## Заметки по интеграции

- `/run_emails` уже обогащает `master_all` (в `.env` нет `ENRICH_LATEST` → дефолт master). Отдельная команда `/enrich_master` не нужна — только понятная подпись кнопки.
- Импорт парсерских модулей из бота — через `sys.path.insert(0, "/home/crimea_parser")` (паттерн уже есть в `cmd_master`).

## Вне скоупа

- Парсеры, формат Excel (этап 1 готов), логика прогона — не трогаем.
- Чистка VK-шума (этап 4) и добор email (этап 5) — отдельно.
- Разбор упавшего прогона `crimea_parser.service` (failed на «Я.Карты») — отдельная задача, не часть бота.

## Проверка

Локальный синтаксис-импорт всех модулей; деплой в `/opt/parser_admin_bot/`; `systemctl restart parser_admin_bot.service`; в Telegram проверить `/menu`, навигацию по кнопкам, `/stats` (с дельтой), `/drive` (ссылка + перезалив), `/progress`, `/run_source vk`.
