# download-bot

Telegram-бот для скачивания видео по ссылке: YouTube, Instagram, TikTok, VK Видео, Rutube
и всё, что поддерживает [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Пользователь присылает ссылку, бот скачивает видео (до 720p, mp4) и отправляет его в чат.

## Запуск

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

**Локально** (нужны Python 3.11+ и `ffmpeg`):
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
| `MAX_HEIGHT` | `720` | Максимальное качество по высоте |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Сколько загрузок одновременно |
| `COOKIES_FILE` | | `cookies.txt` для видео, которые требуют входа (Instagram, TikTok, VK) |
| `YTDLP_PROXY` | | Прокси для скачивания |

## Ограничения

- Обычный Telegram Bot API принимает файлы до 50 МБ. Для больших видео подними
  [локальный Bot API сервер](https://github.com/tdlib/telegram-bot-api), укажи его в
  `TELEGRAM_API_URL` и увеличь `MAX_FILE_MB` до 2000.
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
```
