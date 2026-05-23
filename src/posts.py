"""Загрузка постов из приватного Telegram-канала (источник черновиков).

Пост = сообщение в канале, помеченное хэштегом-маркером (по умолчанию
`#active`). Хэштег вырезается из текста перед отправкой.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telethon import TelegramClient


@dataclass
class Post:
    text: str
    media: Any | None
    source_id: int


async def load_active_posts(
    client: TelegramClient,
    source: str | int,
    scan_limit: int,
    active_tag: str,
) -> list[Post]:
    """Прочитать последние scan_limit сообщений канала, оставить помеченные active_tag.

    Хэштег-маркер вырезается из итогового текста. Сообщения без `raw_text`
    (опросы, сервисные) пропускаются. Пост, в котором после удаления тега
    не осталось ни текста, ни медиа, тоже пропускается.
    """
    posts: list[Post] = []
    async for msg in client.iter_messages(source, limit=scan_limit):
        raw = getattr(msg, "raw_text", None) or ""
        if active_tag not in raw:
            continue
        clean = raw.replace(active_tag, "").strip()
        media = getattr(msg, "media", None)
        if not clean and not media:
            continue
        posts.append(Post(text=clean, media=media, source_id=msg.id))
    return posts


def pick_random_post(posts: list[Post]) -> Post:
    if not posts:
        raise RuntimeError(
            "В drafts-канале нет постов с активным хэштегом. "
            "Добавь хотя бы одно сообщение с тегом и повтори."
        )
    return random.choice(posts)
