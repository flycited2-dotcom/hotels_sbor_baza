#!/bin/bash
# Ручной запуск парсера (headless по умолчанию)
cd /home/crimea_parser
echo "[$(date)] Запуск парсера..."
PYTHONUNBUFFERED=1 /home/crimea_parser/venv/bin/python main.py
echo "[$(date)] Парсер завершил работу"
