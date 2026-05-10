import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))

# Список Telegram user_id через запятую. Если пусто — доступ открыт всем.
_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: list[int] = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "credentials.json")
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "23"))
DAILY_REPORT_MINUTE = int(os.getenv("DAILY_REPORT_MINUTE", "0"))
WEEKLY_REPORT_WEEKDAY = os.getenv("WEEKLY_REPORT_WEEKDAY", "fri")
WEEKLY_REPORT_HOUR = int(os.getenv("WEEKLY_REPORT_HOUR", "17"))
WEEKLY_REPORT_MINUTE = int(os.getenv("WEEKLY_REPORT_MINUTE", "0"))

OBJECT_TYPES = [
    "Гостиница",
    "Пансионат",
    "Хостел",
    "База отдыха",
    "Санаторий",
    "Другое",
]

OBJECT_SIZES = [
    "Малый (до 20 номеров)",
    "Средний (20–100 номеров)",
    "Крупный (100+ номеров)",
]

INTEREST_CATEGORIES = [
    "Кондиционеры",
    "КБТ (МБТ)",
    "Кухонное оборудование",
    "Обеспечение Хоз.Мат",
    "Неустановлено",
    "Прочее",
]

STATUSES = [
    "Новый",
    "В работе",
    "Отправлено КП",
    "Отказ",
    "Клиент",
]

EXCEL_HEADERS = [
    "№",
    "Дата добавления",
    "Название объекта",
    "Тип объекта",
    "Город",
    "Регион",
    "Адрес",
    "Телефон",
    "Email",
    "Telegram",
    "Сайт",
    "Размер объекта",
    "Категория интереса",
    "Статус",
    "Комментарий",
    "Кто добавил",
    "Дата изменения статуса",
]
