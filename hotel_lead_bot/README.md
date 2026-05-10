# HotelLeadBot — Инструкция по деплою на VPS

## 1. Загрузить файлы на сервер

```bash
scp -r hotel_lead_bot/ root@YOUR_VPS_IP:/opt/hotel_lead_bot
```

## 2. Создать виртуальное окружение и установить зависимости

```bash
cd /opt/hotel_lead_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Создать .env файл

```bash
cp .env.example .env
nano .env
```

Заполните:
- `BOT_TOKEN` — токен от @BotFather
- `GROUP_CHAT_ID` — ID вашей группы (с минусом, например -1001234567890)
- `GOOGLE_SHEET_ID` — ID таблицы из URL Google Sheets
- Время отчётов по умолчанию: дайджест в 23:00, мастер-файл в пятницу 17:00

## 4. Настроить Google Sheets API

1. Перейдите на https://console.cloud.google.com
2. Создайте проект → API & Services → Enable APIs → Google Sheets API + Google Drive API
3. Credentials → Create Credentials → Service Account
4. Скачайте JSON-ключ, сохраните как `credentials.json` в папке бота
5. Скопируйте email сервисного аккаунта (вида xxx@xxx.iam.gserviceaccount.com)
6. Откройте вашу Google Таблицу → Настройки доступа → добавьте этот email с правом редактора

## 5. Установить systemd сервис

```bash
cp hotel_lead_bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hotel_lead_bot
systemctl start hotel_lead_bot
```

## 6. Проверить статус

```bash
systemctl status hotel_lead_bot
journalctl -u hotel_lead_bot -f
```

## 7. Узнать GROUP_CHAT_ID

Добавьте бота в группу, напишите любое сообщение, затем откройте:
```
https://api.telegram.org/botYOUR_TOKEN/getUpdates
```
Найдите `"chat":{"id": -100XXXXXXXXX}` — это и есть GROUP_CHAT_ID.

## Структура файлов

```
/opt/hotel_lead_bot/
├── bot.py
├── config.py
├── scheduler.py
├── requirements.txt
├── .env
├── credentials.json        ← Google Service Account key
├── handlers/
│   ├── new_lead.py
│   └── commands.py
├── services/
│   ├── db.py
│   ├── excel.py
│   ├── sheets.py
│   └── notifier.py
├── data/
│   └── leads.db            ← создаётся автоматически
└── reports/                ← Excel файлы (создаётся автоматически)
```

## Команды менеджера

| Команда | Действие |
|---------|----------|
| /new | Добавить контакт (13 шагов) |
| /status | Статистика сегодня / всего |
| /report | Скачать Excel за сегодня |
| /edit | Просмотр последнего контакта |
| /setstatus 5 В работе | Изменить статус контакта #5 |
| /cancel | Отменить текущий ввод |
| /help | Справка |
