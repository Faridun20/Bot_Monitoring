"""Загрузка постов из приватного Telegram-канала (источник черновиков).

Пост = сообщение (или альбом сообщений с общим grouped_id) в канале,
помеченное хэштегом-маркером (по умолчанию `#active`). Хэштег вырезается
из текста перед отправкой.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .entities import strip_tag

if TYPE_CHECKING:
    from telethon import TelegramClient


@dataclass
class Post:
    text: str
    media: list[Any]
    source_id: int
    entities: list[Any] = field(default_factory=list)


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
        raw_entities: list = []
        for m in msgs:
            t = getattr(m, "raw_text", None)
            if t:
                raw = t
                raw_entities = list(getattr(m, "entities", None) or [])
                break
        if active_tag not in raw:
            continue
        clean, clean_entities = strip_tag(raw, raw_entities, active_tag)
        media = [m.media for m in msgs if getattr(m, "media", None) is not None]
        if not clean and not media:
            continue
        posts.append(Post(text=clean, media=media, source_id=msgs[0].id, entities=clean_entities))

    return posts


def pick_next_post(
    posts: list[Post],
    deck: list[int],
    last_id: int | None = None,
) -> tuple[Post, list[int]]:
    """Выбрать следующий пост честной ротацией, без чистой случайности.

    `deck` — оставшийся порядок id постов текущего цикла перемешивания.
    Вызывающий код (scheduler.broadcast) хранит его между вызовами и
    передаёт обратно — так за один проход колоды каждый активный пост
    отправится ровно один раз, прежде чем кто-то повторится.

    Когда колода пуста (первый запуск, или весь цикл пройден) — она
    перемешивается заново из текущих активных постов. Посты, которых
    больше нет среди активных (сняли тег), тихо вычищаются из колоды.

    `last_id` (id поста из предыдущей рассылки) нужен только для одного
    случая — чтобы на стыке двух циклов перемешивания новая колода не
    начиналась тем же постом, которым закончилась предыдущая.

    Возвращает (выбранный пост, обновлённая колода без него).
    """
    if not posts:
        raise RuntimeError(
            "В drafts-канале нет постов с активным хэштегом. "
            "Добавь хотя бы одно сообщение с тегом и повтори."
        )

    by_id = {p.source_id: p for p in posts}
    current_ids = set(by_id)

    deck = [pid for pid in deck if pid in current_ids]

    if not deck:
        deck = list(current_ids)
        random.shuffle(deck)
        if last_id is not None and len(deck) > 1 and deck[0] == last_id:
            deck[0], deck[1] = deck[1], deck[0]

    next_id = deck.pop(0)
    return by_id[next_id], deck
