@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found.
    echo Install Python 3.11+ from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

if exist .env goto install
echo Get a bot token from @BotFather in Telegram ^(/newbot^).
set /p TOKEN=Paste the bot token and press Enter: 
if "%TOKEN%"=="" (
    echo Token is empty.
    pause
    exit /b 1
)
powershell -NoProfile -Command "(Get-Content '.env.example') -replace '^BOT_TOKEN=.*', ('BOT_TOKEN=' + $env:TOKEN) | Set-Content '.env'"
echo Saved token to .env

:install
if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv .venv
)
echo Installing dependencies...
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Bot is running. Press Ctrl+C to stop.
.venv\Scripts\python -m bot
pause
