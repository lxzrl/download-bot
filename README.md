# download-bot

Telegram-бот для скачивания видео по ссылке: YouTube, Instagram, TikTok, VK Видео, Rutube
и всё, что поддерживает [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Пользователь присылает ссылку, бот показывает доступные качества (или «только аудио»)
с примерным размером, скачивает выбранное и отправляет в чат. Видео всегда приходит
в H.264, чтобы оно играло в любом клиенте Telegram.

## Быстрый запуск

- **Windows:** дважды кликни `start.bat`.
- **Linux / macOS:** выполни `./start.sh`.

При первом запуске скрипт спросит токен бота от [@BotFather](https://t.me/BotFather),
сохранит его в `.env`, установит зависимости и запустит бота. Нужен только
[Python 3.11+](https://www.python.org/downloads/) (на Windows при установке отметь
«Add python.exe to PATH»). ffmpeg ставить не обязательно, он подтягивается автоматически.

## Запуск вручную

1. Создай бота у [@BotFather](https://t.me/BotFather) и получи токен.
2. Скопируй настройки и впиши токен:
   ```bash
   cp .env.example .env
   ```
3. Запусти одним из способов.

**Docker (проще всего):**
```bash
docker compose up -d --build
```

**Локально** (нужен Python 3.11+):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bot
```

## Настройки (`.env`)

| Переменная | По умолчанию | Что делает |
|---|---|---|
| `BOT_TOKEN` | | Токен бота, обязательно |
| `MAX_FILE_MB` | `50` | Максимальный размер видео |
| `TELEGRAM_API_URL` | | Локальный Bot API сервер, чтобы отправлять файлы до 2 ГБ |
| `MAX_HEIGHT` | `1080` | Самое высокое качество, которое бот предложит |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Сколько загрузок одновременно |
| `COOKIES_FILE` | | `cookies.txt` для видео, которые требуют входа (Instagram, TikTok, VK) |
| `YTDLP_PROXY` | | Прокси для скачивания |

## Файлы больше 50 МБ

Telegram разрешает ботам отправлять через свои сервера файлы только до 50 МБ. Это
ограничение самого Telegram, обойти его можно только своим
[локальным Bot API сервером](https://github.com/tdlib/telegram-bot-api), тогда лимит 2 ГБ.

1. Получи `api_id` и `api_hash` на https://my.telegram.org → API development tools.
2. В `.env` впиши `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, а также
   `TELEGRAM_API_URL=http://telegram-bot-api:8081` и `MAX_FILE_MB=2000`.
3. Один раз отвяжи бота от облачного API: открой в браузере
   `https://api.telegram.org/bot<ТОКЕН>/logOut`.
4. Запусти вместе с сервером: `docker compose --profile big-files up -d --build`.

## Ограничения

- Instagram и TikTok часто блокируют анонимные запросы. Если видео не скачивается,
  выгрузи cookies из браузера в `cookies.txt` и укажи путь в `COOKIES_FILE`.
- Сайты регулярно меняются, поэтому yt-dlp стоит обновлять: `pip install -U yt-dlp`.

## Структура

```
bot/
  __main__.py   запуск бота
  config.py     чтение настроек из .env
  downloader.py скачивание через yt-dlp
  handlers.py   обработка сообщений
start.bat       быстрый запуск на Windows
start.sh        быстрый запуск на Linux/macOS
```
