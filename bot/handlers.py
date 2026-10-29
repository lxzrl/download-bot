import asyncio
import logging
import secrets
import tempfile
import time
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .config import Config
from .downloader import AUDIO, DownloadError, download, extract_url, probe

log = logging.getLogger(__name__)

router = Router()

HELP_TEXT = (
    "Привет! Пришли мне ссылку на видео, я предложу выбрать качество и скачаю его.\n\n"
    "Поддерживаются YouTube, Instagram, TikTok, VK Видео, Rutube "
    "и многие другие сайты."
)

# Links waiting for the user to pick a quality: token -> (url, created_at).
PENDING_TTL = 60 * 60
pending: dict[str, tuple[str, float]] = {}


def _remember(url: str) -> str:
    now = time.monotonic()
    for token, (_, created) in list(pending.items()):
        if now - created > PENDING_TTL:
            del pending[token]
    token = secrets.token_hex(4)
    pending[token] = (url, now)
    return token


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(F.text)
async def handle_link(message: Message, config: Config, semaphore: asyncio.Semaphore) -> None:
    url = extract_url(message.text)
    if url is None:
        await message.answer("Не вижу ссылки. Пришли ссылку на видео.")
        return

    status = await message.reply("🔎 Смотрю, что есть по ссылке...")
    try:
        info = await probe(url, config)
    except DownloadError as e:
        await status.edit_text(f"❌ {e}")
        return
    except Exception:
        log.exception("Failed to probe %s", url)
        await status.edit_text("❌ Что-то пошло не так. Попробуй ещё раз позже.")
        return

    # Sites like TikTok usually offer a single quality, no point asking.
    if len(info.qualities) <= 1:
        height = info.qualities[0].height if info.qualities else config.max_height
        await _send(message, status, url, height, config, semaphore)
        return

    token = _remember(url)
    limit = config.max_file_bytes
    buttons = [
        InlineKeyboardButton(
            text=("⚠️ " if q.size and q.size > limit else "") + q.label,
            callback_data=f"q:{token}:{q.height}",
        )
        for q in info.qualities
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    await status.edit_text(
        f"🎬 {info.title[:200]}\n\nВыбери качество (⚠️ значит, что файл может не "
        f"пройти лимит {config.max_file_mb} МБ):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("q:"))
async def handle_quality(callback: CallbackQuery, config: Config, semaphore: asyncio.Semaphore) -> None:
    _, token, height = callback.data.split(":")
    entry = pending.pop(token, None)
    if entry is None or callback.message is None:
        await callback.answer("Ссылка устарела, пришли её ещё раз.", show_alert=True)
        return
    await callback.answer()

    status = callback.message
    source = status.reply_to_message or status
    await status.edit_reply_markup(reply_markup=None)
    await _send(source, status, entry[0], int(height), config, semaphore)


async def _send(
    message: Message,
    status: Message,
    url: str,
    height: int,
    config: Config,
    semaphore: asyncio.Semaphore,
) -> None:
    await status.edit_text("⏳ Скачиваю...")
    try:
        async with semaphore:
            with tempfile.TemporaryDirectory(prefix="dl-") as tmp:
                is_audio = height == AUDIO
                action = ChatAction.UPLOAD_VOICE if is_audio else ChatAction.UPLOAD_VIDEO
                await message.bot.send_chat_action(message.chat.id, action)
                media = await download(url, config, Path(tmp), height)
                await status.edit_text("📤 Отправляю...")
                if media.is_audio:
                    await message.answer_audio(
                        FSInputFile(media.path),
                        title=media.title[:64],
                        duration=media.duration,
                        reply_to_message_id=message.message_id,
                    )
                else:
                    await message.answer_video(
                        FSInputFile(media.path),
                        caption=media.title[:1024],
                        duration=media.duration,
                        width=media.width,
                        height=media.height,
                        thumbnail=FSInputFile(media.thumbnail) if media.thumbnail else None,
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
