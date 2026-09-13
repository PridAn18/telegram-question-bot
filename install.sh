#!/usr/bin/env bash
#
# Автоматическая установка Telegram Question Bot.
#
# Запуск от root / sudo:
#   sudo ./install.sh
#   sudo ./install.sh "https://github.com/USER/telegram-question-bot.git"
#
# Параметры можно передать аргументами или переменными окружения:
#   REPO_URL, BOT_TOKEN, ADMIN_IDS
#
set -euo pipefail

INSTALL_DIR="/opt/telegram-bot"
SERVICE_USER="telegram-bot"
SERVICE_NAME="telegram-bot"

REPO_URL="${1:-${REPO_URL:-}}"
BOT_TOKEN="${2:-${BOT_TOKEN:-}}"
ADMIN_IDS="${3:-${ADMIN_IDS:-}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Ошибка: install.sh нужно запускать от root (sudo)."
    exit 1
fi

if [ -z "$REPO_URL" ] && [ ! -f "$SCRIPT_DIR/bot.py" ]; then
    read -r -p "URL git-репозитория для клонирования: " REPO_URL
fi
if [ -z "$BOT_TOKEN" ]; then
    read -r -p "BOT_TOKEN (токен бота из @BotFather): " BOT_TOKEN
fi
if [ -z "$ADMIN_IDS" ]; then
    read -r -p "ADMIN_IDS (ID через запятую, например 919410233): " ADMIN_IDS
fi
if [ -z "$BOT_TOKEN" ] || [ -z "$ADMIN_IDS" ]; then
    echo "Ошибка: BOT_TOKEN и ADMIN_IDS обязательны."
    exit 1
fi

echo "[1/7] Установка системных пакетов..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git

echo "[2/7] Получение кода проекта..."
if [ -f "$SCRIPT_DIR/bot.py" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
    TEMPLATE="$SCRIPT_DIR/telegram-bot.service"
    echo "Использую текущий каталог: $PROJECT_DIR"
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    PROJECT_DIR="$INSTALL_DIR"
    TEMPLATE="$INSTALL_DIR/telegram-bot.service"
    echo "Клонирован репозиторий в $PROJECT_DIR"
fi

echo "[3/7] Виртуальное окружение и зависимости..."
python3 -m venv "$PROJECT_DIR/venv"
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "[4/7] Создание .env..."
cat > "$PROJECT_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
DATABASE_PATH=$PROJECT_DIR/data/questions.db
LOG_PATH=$PROJECT_DIR/logs/bot.log
EOF

echo "[5/7] Пользователь для сервиса..."
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home "$PROJECT_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"
chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_DIR"

echo "[6/7] Системный сервис..."
sed -e "s|__INSTALL_DIR__|$PROJECT_DIR|g" "$TEMPLATE" \
    > "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload

echo "[7/7] Запуск и автозапуск..."
systemctl enable --now "$SERVICE_NAME"

echo ""
echo "Готово. Команды для проверки:"
echo "  systemctl status $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"