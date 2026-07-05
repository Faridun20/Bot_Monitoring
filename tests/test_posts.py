"""Тесты для posts.load_active_posts и pick_random_post."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.posts import Post, load_active_posts, pick_random_post


def _msg(msg_id: int, raw_text: str | None, media=None, grouped_id: int | None = None) -> MagicMock:
    """Сделать минимальный mock telethon.tl.custom.message.Message."""
    m = MagicMock(name=f"Message#{msg_id}")
    m.id = msg_id
    m.raw_text = raw_text
    m.media = media
    m.grouped_id = grouped_id
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
    assert posts[0].media == []
    assert posts[1].text == "ещё один  с медиа"
    assert posts[1].media == [media_obj]


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
    assert posts[0].media == [media_obj]


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


@pytest.mark.asyncio
async def test_album_messages_combined_into_one_post():
    """Альбом — Telethon отдаёт отдельными сообщениями с общим grouped_id,
    подпись обычно висит только на одном из них. Раньше остальные фото
    альбома молча терялись — теперь собираются в один Post."""
    photo1 = MagicMock(name="Photo1")
    photo2 = MagicMock(name="Photo2")
    photo3 = MagicMock(name="Photo3")
    messages = [
        _msg(12, None, media=photo3, grouped_id=100),
        _msg(11, "Реклама #active", media=photo2, grouped_id=100),
        _msg(10, None, media=photo1, grouped_id=100),
    ]
    client = _client_with_messages(messages)

    posts = await load_active_posts(client, "@drafts", 500, "#active")

    assert len(posts) == 1
    assert posts[0].text == "Реклама"
    assert posts[0].media == [photo1, photo2, photo3]
    assert posts[0].source_id == 10


@pytest.mark.asyncio
async def test_album_without_tag_is_skipped():
    photo1 = MagicMock(name="Photo1")
    photo2 = MagicMock(name="Photo2")
    messages = [
        _msg(2, None, media=photo2, grouped_id=200),
        _msg(1, "без тега", media=photo1, grouped_id=200),
    ]
    client = _client_with_messages(messages)
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert posts == []


def test_pick_random_post_empty_raises():
    with pytest.raises(RuntimeError, match="нет постов с активным хэштегом"):
        pick_random_post([])


def test_pick_random_post_returns_member():
    posts = [
        Post(text="a", media=[], source_id=1),
        Post(text="b", media=[], source_id=2),
    ]
    p = pick_random_post(posts)
    assert p in posts


def test_pick_random_post_avoids_immediate_repeat():
    posts = [
        Post(text="a", media=[], source_id=1),
        Post(text="b", media=[], source_id=2),
    ]
    p = pick_random_post(posts, exclude_id=1)
    assert p.source_id == 2


def test_pick_random_post_exclude_id_ignored_when_only_option():
    """Единственный активный пост — не пропускать рассылку только потому,
    что он же был выбран прошлый раз."""
    posts = [Post(text="a", media=[], source_id=1)]
    p = pick_random_post(posts, exclude_id=1)
    assert p.source_id == 1
