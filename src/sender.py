"""Отправка одного поста в одну группу с обработкой ошибок Telethon."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telethon.errors import (
    ChannelPrivateError,
    ChatSendGifsForbiddenError,
    ChatSendMediaForbiddenError,
    ChatSendPhotosForbiddenError,
    ChatSendStickersForbiddenError,
    ChatSendVideosForbiddenError,
    ChatSendVoicesForbiddenError,
    ChatWriteForbiddenError,
    FloodWaitError,
    SlowModeWaitError,
    UserBannedInChannelError,
)

if TYPE_CHECKING:
    from telethon import TelegramClient

    from .config import Config
    from .posts import Post

log = logging.getLogger(__name__)

# Чат запрещает конкретно этот тип вложения (фото/видео/гиф/...), но обычный
# текст обычно всё равно проходит — есть смысл повторить постом без медиа,
# а не сразу сдаваться.
_MEDIA_FORBIDDEN_ERRORS = (
    ChatSendMediaForbiddenError,
    ChatSendPhotosForbiddenError,
    ChatSendGifsForbiddenError,
    ChatSendVideosForbiddenError,
    ChatSendVoicesForbiddenError,
    ChatSendStickersForbiddenError,
)


async def _send_once(
    client: TelegramClient,
    chat: str | int,
    post: Post,
    *,
    text_only: bool = False,
) -> None:
    """Один сырой вызов send_* без обработки ошибок.

    Telethon принимает `msg.media` напрямую в `send_file` — внутри он
    переотправляет media по ссылке на серверах TG, ничего не скачивая.
    """
    if post.media is not None and not text_only:
        await client.send_file(
            chat,
            file=post.media,
            caption=post.text or None,
        )
        return
    await client.send_message(chat, post.text)


async def send_to(
    client: TelegramClient,
    chat: str | int,
    post: Post,
    cfg: Config,
) -> bool:
    """Отправить пост в чат. Возвращает True при успехе, False при отказе."""
    flood_retries_left = 1
    text_only = False

    while True:
        try:
            await _send_once(client, chat, post, text_only=text_only)
            log.info("sent to %s%s", chat, " (только текстом)" if text_only else "")
            return True

        except _MEDIA_FORBIDDEN_ERRORS as e:
            if text_only or post.media is None:
                # Уже пробовали без медиа, либо это и так был текст — сдаёмся.
                log.warning(
                    "медиа запрещено в %s (%s), альтернативы нет — пропускаю",
                    chat,
                    type(e).__name__,
                )
                return False
            if not post.text:
                log.warning(
                    "медиа запрещено в %s (%s), а текста для фолбэка нет — пропускаю",
                    chat,
                    type(e).__name__,
                )
                return False
            log.warning(
                "медиа запрещено в %s (%s) — повторяю только текстом",
                chat,
                type(e).__name__,
            )
            text_only = True
            continue

        except SlowModeWaitError as e:
            if e.seconds <= cfg.max_slow_mode_wait:
                log.info("slow mode in %s: жду %ss и повторяю", chat, e.seconds)
                await asyncio.sleep(e.seconds + 2)
                continue
            log.warning(
                "slow mode in %s: %ss > max %ss — пропускаю",
                chat,
                e.seconds,
                cfg.max_slow_mode_wait,
            )
            return False

        except FloodWaitError as e:
            if flood_retries_left <= 0:
                log.warning(
                    "flood wait %ss in %s: повтор уже был, сдаюсь",
                    e.seconds,
                    chat,
                )
                return False
            flood_retries_left -= 1
            log.warning(
                "flood wait %ss in %s: жду и повторяю один раз",
                e.seconds,
                chat,
            )
            await asyncio.sleep(e.seconds + 2)
            continue

        except (
            ChatWriteForbiddenError,
            UserBannedInChannelError,
            ChannelPrivateError,
        ) as e:
            log.error(
                "нет доступа к %s (%s) — удалите группу из TARGET_GROUPS",
                chat,
                type(e).__name__,
            )
            return False

        except Exception:
            log.exception("неожиданная ошибка при отправке в %s", chat)
            return False
