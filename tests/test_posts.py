"""Тесты для posts.load_active_posts и pick_random_post."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.posts import Post, load_active_posts, pick_random_post


def _msg(msg_id: int, raw_text: str | None, media=None) -> MagicMock:
    """Сделать минимальный mock telethon.tl.custom.message.Message."""
    m = MagicMock(name=f"Message#{msg_id}")
    m.id = msg_id
    m.raw_text = raw_text
    m.media = media
    return m


def _client_with_messages(messages: list[MagicMock]) -> MagicMock:
    """iter_messages — НЕ корутина: это синхронный вызов, возвращающий async-итератор."""

    async def _aiter(*_args, **_kwargs):
        for m in messages:
            yield m

    client = MagicMock(name="TelegramClient")
    client.iter_messages = MagicMock(side_effect=lambda *a, **kw: _aiter(*a, **kw))
    return client


@pytest.mark.asyncio
async def test_filters_only_active_messages():
    media_obj = MagicMock(name="MessageMediaPhoto")
    messages = [
        _msg(1, "не помечен, не уйдёт"),
        _msg(2, "хороший пост #active"),
        _msg(3, "ещё один #active с медиа", media=media_obj),
        _msg(4, "тоже не помечен"),
    ]
    client = _client_with_messages(messages)

    posts = await load_active_posts(client, "@drafts", 500, "#active")

    assert [p.source_id for p in posts] == [2, 3]
    assert posts[0].text == "хороший пост"
    assert posts[0].media is None
    assert posts[1].text == "ещё один  с медиа"
    assert posts[1].media is media_obj


@pytest.mark.asyncio
async def test_tag_stripped_from_text():
    client = _client_with_messages([_msg(1, "Привет #active")])
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert len(posts) == 1
    assert posts[0].text == "Привет"


@pytest.mark.asyncio
async def test_messages_without_raw_text_are_skipped():
    """Опросы / сервисные сообщения имеют raw_text=None — не падаем."""
    client = _client_with_messages(
        [
            _msg(1, None),
            _msg(2, "нормальный #active"),
        ]
    )
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert [p.source_id for p in posts] == [2]


@pytest.mark.asyncio
async def test_tagged_but_empty_after_strip_and_no_media_is_skipped():
    """Только тег, никакого контента → пропустить."""
    client = _client_with_messages(
        [
            _msg(1, "#active"),
            _msg(2, "  #active   "),
        ]
    )
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert posts == []


@pytest.mark.asyncio
async def test_tagged_media_without_caption_is_kept():
    """Картинка с подписью '#active' (после strip пусто) — попадает в ротацию."""
    media_obj = MagicMock(name="MessageMediaPhoto")
    client = _client_with_messages([_msg(1, "#active", media=media_obj)])
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert len(posts) == 1
    assert posts[0].text == ""
    assert posts[0].media is media_obj


@pytest.mark.asyncio
async def test_media_without_tag_is_skipped():
    """Медиа без тега в подписи — игнорируем."""
    media_obj = MagicMock(name="MessageMediaPhoto")
    client = _client_with_messages([_msg(1, "просто картинка", media=media_obj)])
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert posts == []


@pytest.mark.asyncio
async def test_respects_custom_tag():
    client = _client_with_messages(
        [
            _msg(1, "with #active"),
            _msg(2, "with #live"),
        ]
    )
    posts = await load_active_posts(client, "@drafts", 500, "#live")
    assert [p.source_id for p in posts] == [2]


def test_pick_random_post_empty_raises():
    with pytest.raises(RuntimeError, match="нет постов с активным хэштегом"):
        pick_random_post([])


def test_pick_random_post_returns_member():
    posts = [
        Post(text="a", media=None, source_id=1),
        Post(text="b", media=None, source_id=2),
    ]
    p = pick_random_post(posts)
    assert p in posts
