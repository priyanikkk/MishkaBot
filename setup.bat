@echo off
chcp 65001 >nul
title Установка и настройка MishkaBot

echo ===================================================
echo 🐻 Добро пожаловать в установщик MishkaBot (Windows)
echo ===================================================
echo.

:: 1. Проверка Python
echo [1/6] 🔍 Проверка наличия Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Ошибка: Python не найден!
    echo.
    echo Пожалуйста, скачайте и установите Python с официального сайта:
    echo https://www.python.org/downloads/
    echo.
    echo ⚠️ ВАЖНО: При установке обязательно поставьте галочку:
    echo    "Add python.exe to PATH" (Добавить Python в переменные PATH)
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo ✅ Обнаружен %PY_VER%
echo.

:: 2. Создание необходимых папок
echo [2/6] 📁 Создание папок проекта...
if not exist "data" mkdir data
if not exist "handlers" mkdir handlers
if not exist "utils" mkdir utils
echo ✅ Папки готовы.
echo.

:: 3. Создание виртуального окружения
echo [3/6] 🐍 Настройка виртуального окружения (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo ✅ Виртуальное окружение .venv создано.
) else (
    echo ℹ️ Виртуальное окружение уже существует.
)
echo.

:: 4. Установка зависимостей
echo [4/6] 📦 Установка необходимых библиотек...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ❌ Ошибка при установке зависимостей!
    pause
    exit /b 1
)
echo ✅ Зависимости успешно установлены.
echo.

:: 5. Настройка файла .env
echo [5/6] ⚙️ Проверка файла конфигурации .env...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo ✅ Файл .env создан из .env.example.
    )
)

:: Проверяем, задан ли токен
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')
token = os.getenv('BOT_TOKEN', '').strip()
if not token:
    exit(1)
" >nul 2>&1

if %errorlevel% neq 0 (
    echo.
    echo --------------------------------------------------------
    echo Для работы бота требуется токен от @BotFather в Telegram.
    echo --------------------------------------------------------
    set /p USER_TOKEN="👉 Вставьте ваш Bot Token и нажмите Enter: "
    
    python -c "
import config
config.update_env_variable('BOT_TOKEN', '''%USER_TOKEN%''')
"
    echo ✅ Токен сохранен в файл .env.
) else (
    echo ✅ Токен уже настроен в файле .env.
)
echo.

:: 6. Запуск бота
echo [6/6] 🚀 Запуск бота...
echo ===================================================
echo Бот запускается! Для остановки закройте это окно или нажмите Ctrl+C.
echo Для последующих запусков просто открывайте: start.bat
echo ===================================================
echo.

call start.bat
