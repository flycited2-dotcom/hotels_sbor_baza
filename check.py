#!/usr/bin/env python3
"""
Скрипт проверки окружения HotelLeadBot.
Запустите перед первым стартом: python check.py
"""

import os
import sys

REQUIRED_ENV = [
    "BOT_TOKEN",
    "GROUP_CHAT_ID",
]

OPTIONAL_ENV = [
    "GOOGLE_SHEET_ID",
    "GOOGLE_CREDENTIALS_JSON",
]

REQUIRED_PACKAGES = [
    "aiogram",
    "openpyxl",
    "gspread",
    "google.auth",
    "apscheduler",
    "dotenv",
    "aiosqlite",
]

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

ok = True


def check(label, condition, error_msg="", warn=False):
    global ok
    if condition:
        print(f"  {GREEN}✓{RESET} {label}")
    else:
        symbol = f"{YELLOW}⚠{RESET}" if warn else f"{RED}✗{RESET}"
        print(f"  {symbol} {label}", end="")
        if error_msg:
            print(f" — {error_msg}", end="")
        print()
        if not warn:
            ok = False


print("\n=== HotelLeadBot — Проверка окружения ===\n")

# 1. Python version
print("[1] Python:")
check(
    f"Python 3.9+  (текущая: {sys.version.split()[0]})",
    sys.version_info >= (3, 9),
    "Требуется Python 3.9 или выше"
)

# 2. .env файл
print("\n[2] Файл .env:")
env_exists = os.path.exists(".env")
check(".env файл существует", env_exists, "Выполните: cp .env.example .env && nano .env")

if env_exists:
    from dotenv import load_dotenv
    load_dotenv()

print("\n[3] Обязательные переменные окружения:")
for var in REQUIRED_ENV:
    val = os.getenv(var, "")
    check(
        f"{var}",
        bool(val and val != f"YOUR_{var}_HERE" and "XXXXXXXXXX" not in val),
        f"Не задан или не заменён placeholder в .env"
    )

print("\n[4] Google Sheets (опционально):")
for var in OPTIONAL_ENV:
    val = os.getenv(var, "")
    is_set = bool(val and "YOUR_" not in val)
    check(
        f"{var}",
        is_set,
        "Не задан — Google Sheets интеграция будет отключена",
        warn=not is_set
    )

creds_file = os.getenv("GOOGLE_CREDENTIALS_JSON", "credentials.json")
creds_exists = os.path.exists(creds_file)
check(
    f"credentials.json существует ({creds_file})",
    creds_exists,
    "Скачайте JSON-ключ сервисного аккаунта Google и положите сюда",
    warn=not creds_exists
)

# 3. Packages
print("\n[5] Python пакеты:")
for pkg in REQUIRED_PACKAGES:
    try:
        __import__(pkg.replace("-", "_"))
        check(pkg, True)
    except ImportError:
        check(pkg, False, "pip install -r requirements.txt")

# 4. Directories
print("\n[6] Директории:")
for d in ["data", "reports"]:
    try:
        os.makedirs(d, exist_ok=True)
        check(f"./{d}/ существует или создана", True)
    except Exception as e:
        check(f"./{d}/", False, str(e))

# 5. aiogram version
print("\n[7] Версия aiogram:")
try:
    import aiogram
    version = aiogram.__version__
    major = int(version.split(".")[0])
    check(
        f"aiogram {version} (требуется 3.x)",
        major == 3,
        "Нужна aiogram 3.x: pip install 'aiogram==3.7.0'"
    )
except Exception:
    check("aiogram импортируется", False)

# Result
print("\n" + "=" * 45)
if ok:
    print(f"{GREEN}✓ Всё готово! Запускайте: python bot.py{RESET}")
else:
    print(f"{RED}✗ Есть ошибки — исправьте их перед запуском{RESET}")
print()
