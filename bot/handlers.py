import asyncio
import logging
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from .config import Config
from .downloader import DownloadError, download, extract_url

log = logging.getLogger(__name__)

router = Router()

HELP_TEXT = (
    "Привет! Пришли мне ссылку на видео, и я его скачаю.\n\n"
    "Поддерживаются YouTube, Instagram, TikTok, VK Видео, Rutube "
    "и многие другие сайты."
)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text)
async def handle_link(message: Message, config: Config, semaphore: asyncio.Semaphore) -> None:
    url = extract_url(message.text)
    if url is None:
        await message.answer("Не вижу ссылки. Пришли ссылку на видео.")
        return

    status = await message.reply("⏳ Скачиваю...")
    try:
        async with semaphore:
            with tempfile.TemporaryDirectory(prefix="dl-") as tmp:
                await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
                video = await download(url, config, Path(tmp))
                await status.edit_text("📤 Отправляю...")
                await message.answer_video(
                    FSInputFile(video.path),
                    caption=video.title[:1024],
                    duration=video.duration,
                    width=video.width,
                    height=video.height,
                    supports_streaming=True,
                    reply_to_message_id=message.message_id,
                )
    except DownloadError as e:
        await status.edit_text(f"❌ {e}")
        return
    except Exception:
        log.exception("Failed to process %s", url)
        await status.edit_text("❌ Что-то пошло не так. Попробуй ещё раз позже.")
        return

    await status.delete()
