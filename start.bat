@echo off
chcp 65001 >nul
title MishkaBot

echo 🐻 Запуск MishkaBot...
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ⚠️ Виртуальное окружение не найдено. Запустите сначала setup.bat!
    pause
    exit /b 1
)

python main.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Бот завершил работу с ошибкой.
    echo Проверьте правильность токена в файле .env
    pause
)
