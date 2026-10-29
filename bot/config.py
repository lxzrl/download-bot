import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    max_file_mb: int
    telegram_api_url: str | None
    max_height: int
    max_concurrent_downloads: int
    cookies_file: Path | None
    proxy: str | None

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    cookies = os.getenv("COOKIES_FILE", "").strip()

    return Config(
        bot_token=token,
        max_file_mb=int(os.getenv("MAX_FILE_MB", "50")),
        telegram_api_url=os.getenv("TELEGRAM_API_URL", "").strip() or None,
        max_height=int(os.getenv("MAX_HEIGHT", "1080")),
        max_concurrent_downloads=int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3")),
        cookies_file=Path(cookies) if cookies else None,
        proxy=os.getenv("YTDLP_PROXY", "").strip() or None,
    )
