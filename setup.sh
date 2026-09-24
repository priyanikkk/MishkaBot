#!/usr/bin/env bash
set -e

# ===================================================
# Telegram Gifts & Stars Bot - Setup Script
# ===================================================

echo "================================================="
echo "🎁 Установка и настройка Telegram Gifts & Stars Bot"
echo "================================================="

# 1. Проверка Python 3
echo -e "\n[1/5] 🔍 Проверка Python..."
if ! command -v python3 &>/dev/null; then
    echo "❌ Ошибка: python3 не найден! Пожалуйста, установите Python 3.10+."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Обнаружен Python $PY_VERSION"

# 2. Создание директорий
echo -e "\n[2/5] 📁 Создание папок проекта..."
mkdir -p data handlers utils tests secrets
echo "✅ Директории готовы."

# 3. Виртуальное окружение
echo -e "\n[3/5] 🐍 Настройка виртуального окружения (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Виртуальное окружение создано."
else
    echo "ℹ️ Виртуальное окружение уже существует."
fi

# 4. Установка зависимостей
echo -e "\n[4/5] 📦 Установка зависимостей..."
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Зависимости успешно установлены."

# 5. Запуск мастера настройки
echo -e "\n[5/5] ⚙️ Запуск интерактивного мастера настройки..."
python3 wizard.py

echo "================================================="
echo "🚀 Запуск бота..."
echo "Для остановки нажмите Ctrl+C"
echo "Для последующих запусков: ./start.sh"
echo "================================================="
exec ./start.sh
