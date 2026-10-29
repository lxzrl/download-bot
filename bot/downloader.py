import asyncio
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg
import yt_dlp

from .config import Config

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")

# Use the system ffmpeg if installed, otherwise the bundled binary,
# so the bot works on Windows without installing ffmpeg by hand.
FFMPEG = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

AUDIO = 0  # "height" value meaning audio only


class DownloadError(Exception):
    """Error with a message that is safe to show to the user."""


class FileTooLarge(DownloadError):
    pass


@dataclass
class Quality:
    height: int  # AUDIO for audio only
    size: int | None  # estimated bytes, None if unknown

    @property
    def label(self) -> str:
        name = "🎵 Аудио" if self.height == AUDIO else f"{self.height}p"
        if self.size:
            name += f" · ~{self.size / 1024 / 1024:.0f} МБ"
        return name


@dataclass
class VideoInfo:
    title: str
    qualities: list[Quality] = field(default_factory=list)


@dataclass
class Media:
    path: Path
    title: str
    is_audio: bool
    duration: int | None = None
    width: int | None = None
    height: int | None = None
    thumbnail: Path | None = None


def extract_url(text: str | None) -> str | None:
    if not text:
        return None
    match = URL_RE.search(text)
    return match.group(0).rstrip(").,!?»\"'") if match else None


def _base_options(config: Config) -> dict:
    opts = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "ffmpeg_location": FFMPEG,
    }
    if config.cookies_file:
        opts["cookiefile"] = str(config.cookies_file)
    if config.proxy:
        opts["proxy"] = config.proxy
    return opts


def _extract(ydl: yt_dlp.YoutubeDL, url: str, download: bool) -> dict:
    try:
        info = ydl.extract_info(url, download=download)
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
    return info


def _format_size(f: dict) -> int | None:
    return f.get("filesize") or f.get("filesize_approx")


def _probe_sync(url: str, config: Config) -> VideoInfo:
    with yt_dlp.YoutubeDL(_base_options(config)) as ydl:
        info = _extract(ydl, url, download=False)

    formats = info.get("formats") or []
    audio_sizes = [
        _format_size(f) for f in formats
        if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")
    ]
    best_audio = max((s for s in audio_sizes if s), default=None)

    by_height: dict[int, int | None] = {}
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") == "none" or h > config.max_height:
            continue
        size = _format_size(f)
        if size and f.get("acodec") == "none" and best_audio:
            size += best_audio
        if h not in by_height or (size and (by_height[h] is None or size > by_height[h])):
            by_height[h] = size

    qualities = [Quality(h, by_height[h]) for h in sorted(by_height, reverse=True)]
    if audio_sizes:
        qualities.append(Quality(AUDIO, best_audio))
    return VideoInfo(title=info.get("title") or "video", qualities=qualities)


def _ffmpeg(*args: str) -> None:
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True, capture_output=True)


def _make_thumbnail(video: Path) -> Path | None:
    # Telegram wants a JPEG up to 320px on the longest side, otherwise the
    # video shows up as a grey box in the chat.
    thumb = video.with_suffix(".jpg")
    scale = "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'"
    try:
        _ffmpeg("-ss", "1", "-i", str(video), "-frames:v", "1", "-vf", scale, str(thumb))
    except subprocess.CalledProcessError:
        try:
            _ffmpeg("-i", str(video), "-frames:v", "1", "-vf", scale, str(thumb))
        except subprocess.CalledProcessError:
            return None
    return thumb if thumb.exists() else None


def _to_h264(video: Path) -> Path:
    # Telegram clients only reliably play H.264. VP9/AV1 in mp4 plays as
    # sound over a black screen, so re-encode those.
    out = video.with_name(video.stem + ".h264.mp4")
    _ffmpeg(
        "-i", str(video),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    )
    video.unlink()
    return out


def _is_h264(info: dict) -> bool:
    vcodecs = [info.get("vcodec")]
    vcodecs += [f.get("vcodec") for f in info.get("requested_formats") or []]
    return any(c and (c.startswith("avc") or c.startswith("h264")) for c in vcodecs)


def _download_sync(url: str, config: Config, workdir: Path, height: int) -> Media:
    opts = _base_options(config)
    opts["outtmpl"] = str(workdir / "%(id)s.%(ext)s")
    opts["max_filesize"] = config.max_file_bytes
    if height == AUDIO:
        opts["format"] = "ba[ext=m4a]/ba/b"
    else:
        opts["format"] = f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b"
        # Within the chosen height prefer H.264 + AAC in mp4, so most videos
        # need no re-encoding to play in Telegram.
        opts["format_sort"] = ["res", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"]
        opts["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = _extract(ydl, url, download=True)

    too_large = FileTooLarge(
        f"Файл больше {config.max_file_mb} МБ, Telegram не даст его отправить. "
        "Попробуй качество пониже."
    )
    files = [p for p in workdir.iterdir() if p.is_file() and not p.name.endswith(".part")]
    if not files:
        # yt-dlp skips files above max_filesize without raising.
        raise too_large
    path = max(files, key=lambda p: p.stat().st_size)

    media = Media(
        path=path,
        title=info.get("title") or "video",
        is_audio=height == AUDIO,
        duration=int(info["duration"]) if info.get("duration") else None,
        width=info.get("width"),
        height=info.get("height"),
    )
    if not media.is_audio:
        if not _is_h264(info):
            log.info("Re-encoding %s (vcodec=%s) to H.264", url, info.get("vcodec"))
            media.path = _to_h264(media.path)
        media.thumbnail = _make_thumbnail(media.path)

    if media.path.stat().st_size > config.max_file_bytes:
        raise too_large
    return media


async def probe(url: str, config: Config) -> VideoInfo:
    return await asyncio.to_thread(_probe_sync, url, config)


async def download(url: str, config: Config, workdir: Path, height: int) -> Media:
    return await asyncio.to_thread(_download_sync, url, config, workdir, height)
