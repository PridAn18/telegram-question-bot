#!/usr/bin/env bash
#
# Обновление Telegram Question Bot.
# Автоматически: git pull, обновление зависимостей, перезапуск сервиса.
# Схема БД применяется автоматически при старте (CREATE TABLE IF NOT EXISTS).
#
# Запуск от root / sudo:  sudo ./update.sh
#
set -euo pipefail

SERVICE_NAME="telegram-bot"
INSTALL_DIR="/opt/telegram-bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: update.sh нужно запускать от root (sudo)."
    exit 1
fi

if [ -d "$SCRIPT_DIR/.git" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
else
    PROJECT_DIR="$INSTALL_DIR"
fi

echo "Обновляю проект в $PROJECT_DIR"
cd "$PROJECT_DIR"
git pull --ff-only
./venv/bin/pip install -r requirements.txt
systemctl restart "$SERVICE_NAME"
echo "Обновление завершено, $SERVICE_NAME перезапущен."