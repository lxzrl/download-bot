#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Get a bot token from @BotFather in Telegram (/newbot)."
    read -rp "Paste the bot token and press Enter: " TOKEN
    [ -n "$TOKEN" ] || { echo "Token is empty."; exit 1; }
    sed "s|^BOT_TOKEN=.*|BOT_TOKEN=$TOKEN|" .env.example > .env
    echo "Saved token to .env"
fi

[ -x .venv/bin/python ] || python3 -m venv .venv
echo "Installing dependencies, this can take a few minutes on first run..."
.venv/bin/python -m pip install -q --disable-pip-version-check --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Bot is running. Press Ctrl+C to stop."
exec .venv/bin/python -m bot
