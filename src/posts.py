"""Загрузка постов из приватного Telegram-канала (источник черновиков).

Пост = сообщение (или альбом сообщений с общим grouped_id) в канале,
помеченное хэштегом-маркером (по умолчанию `#active`). Хэштег вырезается
из текста перед отправкой.
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
    media: list[Any]
    source_id: int


async def load_active_posts(
    client: TelegramClient,
    source: str | int,
    scan_limit: int,
    active_tag: str,
) -> list[Post]:
    """Прочитать последние scan_limit сообщений канала, оставить помеченные active_tag.

    Альбом (несколько фото/видео одним постом) Telegram хранит как отдельные
    сообщения с общим `grouped_id` — подпись обычно висит только на одном
    из них. Такие сообщения собираются в один Post с несколькими media,
    а не теряются: раньше уходило только то фото, на котором была подпись
    с тегом, остальные из альбома молча пропускались.

    Хэштег-маркер вырезается из итогового текста. Сообщения без `raw_text`
    (опросы, сервисные) пропускаются. Пост, в котором после удаления тега
    не осталось ни текста, ни медиа, тоже пропускается.
    """
    groups: dict[int, list] = {}
    singles: list[list] = []

    async for msg in client.iter_messages(source, limit=scan_limit):
        grouped_id = getattr(msg, "grouped_id", None)
        if grouped_id is not None:
            groups.setdefault(grouped_id, []).append(msg)
        else:
            singles.append([msg])

    posts: list[Post] = []
    for msgs in singles + list(groups.values()):
        msgs = sorted(msgs, key=lambda m: m.id)
        raw = ""
        for m in msgs:
            t = getattr(m, "raw_text", None)
            if t:
                raw = t
                break
        if active_tag not in raw:
            continue
        clean = raw.replace(active_tag, "").strip()
        media = [m.media for m in msgs if getattr(m, "media", None) is not None]
        if not clean and not media:
            continue
        posts.append(Post(text=clean, media=media, source_id=msgs[0].id))

    return posts


def pick_random_post(posts: list[Post], exclude_id: int | None = None) -> Post:
    """Выбрать случайный пост.

    Если активных постов больше одного, не повторяет `exclude_id` (обычно —
    id поста из предыдущей рассылки). Без этого при нескольких активных
    постах чистая случайность могла выбрать один и тот же пост несколько
    раз подряд — а нужно, чтобы со временем реально чередовались разные.
    """
    if not posts:
        raise RuntimeError(
            "В drafts-канале нет постов с активным хэштегом. "
            "Добавь хотя бы одно сообщение с тегом и повтори."
        )
    if exclude_id is not None and len(posts) > 1:
        candidates = [p for p in posts if p.source_id != exclude_id]
        if candidates:
            return random.choice(candidates)
    return random.choice(posts)
