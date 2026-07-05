"""Тесты для sender.send_to с замоканным TelegramClient."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import (
    ChatSendPhotosForbiddenError,
    ChatWriteForbiddenError,
    FloodWaitError,
    PeerFloodError,
    SlowModeWaitError,
)

from src.posts import Post
from src.sender import send_to


@dataclass
class FakeConfig:
    """Подмена config.Config — нужны только поля, которые читает sender."""

    max_slow_mode_wait: int = 120
    delay_min: int = 0
    delay_max: int = 0
    jitter_minutes: int = 0


@pytest.fixture
def cfg() -> FakeConfig:
    return FakeConfig()


@pytest.fixture
def client() -> AsyncMock:
    c = AsyncMock()
    c.send_message = AsyncMock()
    c.send_file = AsyncMock()
    return c


@pytest.fixture(autouse=True)
def _no_sleep():
    """Делаем asyncio.sleep no-op, чтобы тесты были мгновенные."""
    with patch("src.sender.asyncio.sleep", new=AsyncMock()) as m:
        yield m


def _make_error(cls, **kwargs):
    """Сконструировать исключение Telethon с нужными полями, без обращения к API."""
    err = cls.__new__(cls)
    for k, v in kwargs.items():
        setattr(err, k, v)
    Exception.__init__(err, f"test {cls.__name__}")
    return err


@pytest.mark.asyncio
async def test_send_to_success_text(client, cfg):
    post = Post(text="hello", media=[], source_id=1)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is True
    client.send_message.assert_awaited_once_with("@chat", "hello")
    client.send_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_with_media(client, cfg):
    media = MagicMock(name="MessageMediaPhoto")
    post = Post(text="caption", media=[media], source_id=2)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is True
    client.send_file.assert_awaited_once_with("@chat", file=media, caption="caption")
    client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_media_without_caption_passes_none(client, cfg):
    """Картинка без подписи → caption=None, не пустая строка."""
    media = MagicMock(name="MessageMediaPhoto")
    post = Post(text="", media=[media], source_id=3)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is True
    client.send_file.assert_awaited_once_with("@chat", file=media, caption=None)
    client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_with_album_passes_list(client, cfg):
    """2+ media в посте → send_file получает список (альбом), а не голый объект."""
    photo1 = MagicMock(name="Photo1")
    photo2 = MagicMock(name="Photo2")
    photo3 = MagicMock(name="Photo3")
    post = Post(text="caption", media=[photo1, photo2, photo3], source_id=6)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is True
    client.send_file.assert_awaited_once_with(
        "@chat", file=[photo1, photo2, photo3], caption="caption"
    )
    client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_mode_within_limit_retries(client, cfg):
    err = _make_error(SlowModeWaitError, seconds=5)
    client.send_message.side_effect = [err, None]
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is True
    assert client.send_message.await_count == 2


@pytest.mark.asyncio
async def test_slow_mode_over_limit_gives_up(client, cfg):
    err = _make_error(SlowModeWaitError, seconds=600)
    client.send_message.side_effect = err
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is False
    assert client.send_message.await_count == 1


@pytest.mark.asyncio
async def test_chat_write_forbidden(client, cfg):
    err = _make_error(ChatWriteForbiddenError)
    client.send_message.side_effect = err
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is False
    assert client.send_message.await_count == 1


@pytest.mark.asyncio
async def test_flood_wait_retries_once(client, cfg):
    err = _make_error(FloodWaitError, seconds=3)
    client.send_message.side_effect = [err, None]
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is True
    assert client.send_message.await_count == 2


@pytest.mark.asyncio
async def test_flood_wait_twice_gives_up(client, cfg):
    err = _make_error(FloodWaitError, seconds=3)
    client.send_message.side_effect = [err, err]
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is False
    assert client.send_message.await_count == 2


@pytest.mark.asyncio
async def test_media_forbidden_falls_back_to_text(client, cfg):
    media = MagicMock(name="MessageMediaPhoto")
    err = _make_error(ChatSendPhotosForbiddenError)
    client.send_file.side_effect = err
    post = Post(text="caption", media=[media], source_id=4)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is True
    client.send_file.assert_awaited_once_with("@chat", file=media, caption="caption")
    client.send_message.assert_awaited_once_with("@chat", "caption")


@pytest.mark.asyncio
async def test_media_forbidden_no_caption_gives_up(client, cfg):
    media = MagicMock(name="MessageMediaPhoto")
    err = _make_error(ChatSendPhotosForbiddenError)
    client.send_file.side_effect = err
    post = Post(text="", media=[media], source_id=5)
    ok = await send_to(client, "@chat", post, cfg)
    assert ok is False
    client.send_file.assert_awaited_once()
    client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_peer_flood_propagates_instead_of_swallowed(client, cfg):
    """PeerFloodError = аккаунт под ограничением целиком, не проблема чата —
    send_to должен пробросить исключение наверх, а не вернуть False."""
    err = _make_error(PeerFloodError)
    client.send_message.side_effect = err
    with pytest.raises(PeerFloodError):
        await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert client.send_message.await_count == 1


@pytest.mark.asyncio
async def test_unknown_exception(client, cfg):
    client.send_message.side_effect = RuntimeError("boom")
    ok = await send_to(client, "@chat", Post(text="x", media=[], source_id=1), cfg)
    assert ok is False
    assert client.send_message.await_count == 1
