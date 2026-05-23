"""Отправка одного поста в одну группу с обработкой ошибок Telethon."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telethon.errors import (
    ChannelPrivateError,
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


async def _send_once(client: TelegramClient, chat: str | int, post: Post) -> None:
    """Один сырой вызов send_* без обработки ошибок.

    Telethon принимает `msg.media` напрямую в `send_file` — внутри он
    переотправляет media по ссылке на серверах TG, ничего не скачивая.
    """
    if post.media is not None:
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

    while True:
        try:
            await _send_once(client, chat, post)
            log.info("sent to %s", chat)
            return True

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
