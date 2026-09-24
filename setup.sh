#!/usr/bin/env bash
set -e

# ==========================================
# MishkaBot - Setup & Installation Script
# ==========================================

echo "================================================="
echo "🐻 Добро пожаловать в установщик MishkaBot!"
echo "================================================="

# 1. Проверка наличия Python 3
echo -e "\n[1/8] 🔍 Проверка Python..."
if ! command -v python3 &>/dev/null; then
    echo "❌ Ошибка: python3 не найден! Пожалуйста, установите Python 3.9+."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Обнаружен Python $PY_VERSION"

# 2. Создание необходимых директорий
echo -e "\n[2/8] 📁 Создание папок проекта..."
mkdir -p data handlers utils tests
echo "✅ Директории готовы."

# 3. Создание виртуального окружения
echo -e "\n[3/8] 🐍 Настройка виртуального окружения (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Виртуальное окружение создано."
else
    echo "ℹ️ Виртуальное окружение уже существует."
fi

# 4. Активация окружения и установка зависимостей
echo -e "\n[4/8] 📦 Установка зависимостей..."
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Зависимости успешно установлены."

# 5. Проверка и создание .env
echo -e "\n[5/8] ⚙️ Настройка конфигурации (.env)..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Файл .env создан из .env.example."
    else
        cat << 'EOF' > .env
BOT_TOKEN=
MISHKA_CHANCE=5
COMMON_MISHKA_CHANCE=70
RARE_MISHKA_CHANCE=20
EPIC_MISHKA_CHANCE=8
LEGENDARY_MISHKA_CHANCE=2
DATABASE_PATH=data/mishka.db
SPAM_COOLDOWN_SECONDS=3
ADMIN_IDS=
EOF
        echo "✅ Файл .env создан с настройками по умолчанию."
    fi
fi

# 6. Проверка и запрос Telegram Bot Token
echo -e "\n[6/8] 🔑 Проверка Telegram Bot Token..."
CURRENT_TOKEN=$(grep -E '^BOT_TOKEN=' .env | cut -d '=' -f2- | tr -d ' "' || true)

if [ -z "$CURRENT_TOKEN" ]; then
    if [ -n "$BOT_TOKEN" ]; then
        echo "ℹ️ Найден BOT_TOKEN в системных переменных окружения."
        CURRENT_TOKEN="$BOT_TOKEN"
    else
        echo ""
        echo "--------------------------------------------------------"
        echo "Для работы бота требуется токен от @BotFather в Telegram."
        echo "--------------------------------------------------------"
        while [ -z "$CURRENT_TOKEN" ]; do
            read -r -p "👉 Введите ваш Bot Token: " INPUT_TOKEN
            INPUT_TOKEN=$(echo "$INPUT_TOKEN" | xargs)
            if [ -n "$INPUT_TOKEN" ]; then
                CURRENT_TOKEN="$INPUT_TOKEN"
            else
                echo "⚠️ Токен не может быть пустым. Попробуйте еще раз."
            fi
        done
    fi

    # Сохраняем токен в .env
    python3 -c "
import config
config.update_env_variable('BOT_TOKEN', '$CURRENT_TOKEN')
"
    echo "✅ Токен сохранен в .env."
else
    echo "✅ Токен найден в файле .env."
fi

# 7. Проверка валидности токена через Telegram API
echo -e "\n[7/8] 🌐 Проверка токена через Telegram API..."
CHECK_RESULT=$(python3 -c "
import urllib.request
import json
import sys

token = '$CURRENT_TOKEN'.strip()
if not token:
    print('EMPTY')
    sys.exit(0)

url = f'https://api.telegram.org/bot{token}/getMe'
req = urllib.request.Request(url, headers={'User-Agent': 'MishkaBotSetup/1.0'})

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode('utf-8'))
        if data.get('ok'):
            user = data.get('result', {})
            print(f'OK:{user.get(\"username\")}:{user.get(\"first_name\")}')
        else:
            print('INVALID')
except urllib.error.HTTPError as e:
    if e.code == 401 or e.code == 404:
        print('INVALID')
    else:
        print(f'HTTP_{e.code}')
except Exception as e:
    print(f'ERROR:{e}')
" 2>/dev/null || echo "ERROR")

case "$CHECK_RESULT" in
    OK:*)
        BOT_USERNAME=$(echo "$CHECK_RESULT" | cut -d ':' -f2)
        BOT_NAME=$(echo "$CHECK_RESULT" | cut -d ':' -f3)
        echo "🎉 Токен подтвержден! Бот: @$BOT_USERNAME ($BOT_NAME)"
        ;;
    INVALID)
        echo "⚠️ Внимание: Telegram API отклонил токен (Неверный токен)!"
        echo "Вы можете изменить его в файле .env."
        ;;
    ERROR*|HTTP_*)
        echo "ℹ️ Не удалось связаться с api.telegram.org (нет интернета или таймаут). Пропуск онлайн-проверки."
        ;;
    *)
        echo "ℹ️ Пропуск проверки токена."
        ;;
esac

# 8. Запуск бота
echo -e "\n[8/8] 🚀 Запуск MishkaBot..."
echo "================================================="
echo "Для остановки бота нажмите Ctrl+C"
echo "Для последующих запусков используйте: ./start.sh"
echo "================================================="
exec ./start.sh
