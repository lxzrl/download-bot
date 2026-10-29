import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import yt_dlp

from .config import Config

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")


class DownloadError(Exception):
    """Error with a message that is safe to show to the user."""


class FileTooLarge(DownloadError):
    pass


@dataclass
class Video:
    path: Path
    title: str
    duration: int | None
    width: int | None
    height: int | None


def extract_url(text: str | None) -> str | None:
    if not text:
        return None
    match = URL_RE.search(text)
    return match.group(0).rstrip(").,!?»\"'") if match else None


def _ydl_options(config: Config, workdir: Path) -> dict:
    h = config.max_height
    opts = {
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        # Prefer mp4/h264 so Telegram can play the video inline, cap the height,
        # and fall back to any single file if separate streams are unavailable.
        "format": (
            f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/"
            f"bv*[height<={h}]+ba/"
            f"b[height<={h}]/b"
        ),
        "merge_output_format": "mp4",
        "max_filesize": config.max_file_bytes,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        # Use the system ffmpeg if installed, otherwise the bundled binary,
        # so the bot works on Windows without installing ffmpeg by hand.
        "ffmpeg_location": shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe(),
    }
    if config.cookies_file:
        opts["cookiefile"] = str(config.cookies_file)
    if config.proxy:
        opts["proxy"] = config.proxy
    return opts


def _download_sync(url: str, config: Config, workdir: Path) -> Video:
    with yt_dlp.YoutubeDL(_ydl_options(config, workdir)) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.UnsupportedError as e:
            raise DownloadError("Эта ссылка не поддерживается.") from e
        except yt_dlp.utils.DownloadError as e:
            log.warning("yt-dlp failed for %s: %s", url, e)
            raise DownloadError(
                "Не удалось скачать видео. Возможно, оно приватное, удалено "
                "или требует входа в аккаунт."
            ) from e

    if info is None:
        raise DownloadError("Не удалось получить информацию о видео.")
    if info.get("_type") == "playlist":
        entries = [e for e in info.get("entries") or [] if e]
        if not entries:
            raise DownloadError("В плейлисте нет доступных видео.")
        info = entries[0]

    files = [p for p in workdir.iterdir() if p.is_file() and not p.name.endswith(".part")]
    if not files:
        # yt-dlp skips files above max_filesize without raising.
        raise FileTooLarge(f"Видео больше {config.max_file_mb} МБ, Telegram не даст его отправить.")
    path = max(files, key=lambda p: p.stat().st_size)
    if path.stat().st_size > config.max_file_bytes:
        raise FileTooLarge(f"Видео больше {config.max_file_mb} МБ, Telegram не даст его отправить.")

    return Video(
        path=path,
        title=info.get("title") or "video",
        duration=int(info["duration"]) if info.get("duration") else None,
        width=info.get("width"),
        height=info.get("height"),
    )


async def download(url: str, config: Config, workdir: Path) -> Video:
    return await asyncio.to_thread(_download_sync, url, config, workdir)
