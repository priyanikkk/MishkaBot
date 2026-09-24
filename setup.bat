@echo off
chcp 65001 >nul
title Установка и настройка Telegram Gifts & Stars Bot

echo ===================================================
echo 🎁 Установка Telegram Gifts & Stars Bot (Windows)
echo ===================================================
echo.

:: 1. Проверка Python
echo [1/5] 🔍 Проверка наличия Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Ошибка: Python не найден!
    echo.
    echo Скачайте Python с официального сайта: https://www.python.org/downloads/
    echo ⚠️ ОБЯЗАТЕЛЬНО отметьте галочку: "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo ✅ Обнаружен %PY_VER%
echo.

:: 2. Создание папок
echo [2/5] 📁 Создание папок...
if not exist "data" mkdir data
if not exist "handlers" mkdir handlers
if not exist "utils" mkdir utils
if not exist "secrets" mkdir secrets
echo ✅ Папки готовы.
echo.

:: 3. Виртуальное окружение
echo [3/5] 🐍 Создание виртуального окружения (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo ✅ Окружение .venv создано.
) else (
    echo ℹ️ Окружение .venv уже существует.
)
echo.

:: 4. Установка зависимостей
echo [4/5] 📦 Установка зависимостей...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ❌ Ошибка при установке зависимостей!
    pause
    exit /b 1
)
echo ✅ Зависимости установлены.
echo.

:: 5. Запуск мастера настройки
echo [5/5] ⚙️ Запуск мастера настройки...
python wizard.py

echo.
echo ===================================================
echo 🚀 Запуск бота...
echo Для последующих запусков открывайте: start.bat
echo ===================================================
echo.

call start.bat
