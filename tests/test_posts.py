"""Тесты для posts.load_active_posts и pick_random_post."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.posts import Post, load_active_posts, pick_next_post


def _msg(
    msg_id: int,
    raw_text: str | None,
    media=None,
    grouped_id: int | None = None,
    entities=None,
) -> MagicMock:
    """Сделать минимальный mock telethon.tl.custom.message.Message."""
    m = MagicMock(name=f"Message#{msg_id}")
    m.id = msg_id
    m.raw_text = raw_text
    m.media = media
    m.grouped_id = grouped_id
    m.entities = entities
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


@dataclass
class _FakeEntity:
    """Мини-заглушка telethon MessageEntity* — только offset/length, как в strip_tag."""

    offset: int
    length: int


@pytest.mark.asyncio
async def test_entities_carried_and_offsets_adjusted_when_tag_stripped():
    bold = _FakeEntity(offset=0, length=4)  # покрывает "Пост"
    client = _client_with_messages([_msg(1, "Пост #active", entities=[bold])])
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert len(posts) == 1
    assert posts[0].text == "Пост"
    assert posts[0].entities == [_FakeEntity(offset=0, length=4)]


@pytest.mark.asyncio
async def test_entities_missing_attribute_on_message_defaults_to_empty():
    """Сообщение вообще без атрибута entities — не падаем, Post.entities == []."""
    m = _msg(1, "без entities #active")
    del m.entities
    client = _client_with_messages([m])
    posts = await load_active_posts(client, "@drafts", 500, "#active")
    assert len(posts) == 1
    assert posts[0].entities == []


@pytest.mark.asyncio
async def test_album_entities_come_from_captioned_message():
    """Entities должны браться с того же сообщения альбома, что дало подпись,
    а не с другого сообщения в группе."""
    photo1 = MagicMock(name="Photo1")
    photo2 = MagicMock(name="Photo2")
    caption_bold = _FakeEntity(offset=0, length=7)  # покрывает "Реклама"
    other_bold = _FakeEntity(offset=0, length=99)  # на сообщении без caption
    messages = [
        _msg(11, "Реклама #active", media=photo2, grouped_id=100, entities=[caption_bold]),
        _msg(10, None, media=photo1, grouped_id=100, entities=[other_bold]),
    ]
    client = _client_with_messages(messages)

    posts = await load_active_posts(client, "@drafts", 500, "#active")

    assert len(posts) == 1
    assert posts[0].entities == [_FakeEntity(offset=0, length=7)]


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


def test_pick_next_post_empty_raises():
    with pytest.raises(RuntimeError, match="нет постов с активным хэштегом"):
        pick_next_post([], [])


def test_pick_next_post_returns_member_and_updates_deck():
    posts = [
        Post(text="a", media=[], source_id=1),
        Post(text="b", media=[], source_id=2),
    ]
    post, deck = pick_next_post(posts, [])
    assert post in posts
    assert deck == [p.source_id for p in posts if p.source_id != post.source_id]


def test_pick_next_post_full_cycle_uses_each_post_exactly_once():
    """За N вызовов подряд (N = число активных постов) без внешнего сброса
    колоды каждый пост встречается ровно один раз — честная ротация, не
    чистая случайность с возможными повторами."""
    posts = [Post(text=str(i), media=[], source_id=i) for i in range(1, 6)]
    deck: list[int] = []
    seen = []
    for _ in range(len(posts)):
        post, deck = pick_next_post(posts, deck)
        seen.append(post.source_id)
    assert sorted(seen) == [1, 2, 3, 4, 5]
    assert deck == []


def test_pick_next_post_no_repeat_across_cycle_boundary():
    """3 активных поста, 3 полных цикла подряд (9 вызовов) — ни разу подряд
    не повторяется тот же пост, даже на стыке между циклами перемешивания."""
    posts = [Post(text=str(i), media=[], source_id=i) for i in (1, 2, 3)]
    deck: list[int] = []
    last_id = None
    picks = []
    for _ in range(9):
        post, deck = pick_next_post(posts, deck, last_id=last_id)
        picks.append(post.source_id)
        last_id = post.source_id

    assert all(a != b for a, b in zip(picks, picks[1:]))
    assert sorted(picks[0:3]) == [1, 2, 3]
    assert sorted(picks[3:6]) == [1, 2, 3]
    assert sorted(picks[6:9]) == [1, 2, 3]


def test_pick_next_post_deck_drops_deactivated_posts():
    """id в колоде, которого больше нет среди активных (сняли тег) —
    просто вычищается, не роняет функцию и не выбирается."""
    posts = [
        Post(text="a", media=[], source_id=1),
        Post(text="b", media=[], source_id=2),
    ]
    post, deck = pick_next_post(posts, deck=[999, 1, 2])
    assert post.source_id == 1
    assert deck == [2]


def test_pick_next_post_single_post_repeats_when_no_alternative():
    """Единственный активный пост — не пропускать рассылку только потому,
    что он же был выбран прошлый раз, повторов избежать физически нельзя."""
    posts = [Post(text="a", media=[], source_id=1)]
    post, deck = pick_next_post(posts, [], last_id=1)
    assert post.source_id == 1
