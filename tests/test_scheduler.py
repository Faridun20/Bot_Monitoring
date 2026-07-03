"""Тесты для scheduler.broadcast — критичная ветка аварийной остановки."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest
from telethon.errors import PeerFloodError

from src.posts import Post
from src.scheduler import broadcast


@dataclass
class FakeConfig:
    """Подмена config.Config — нужны только поля, которые читает broadcast."""

    target_groups: list[str] = field(default_factory=lambda: ["@a", "@b", "@c"])
    shuffle_groups: bool = False
    delay_min: int = 0
    delay_max: int = 0
    jitter_minutes: int = 0
    drafts_source: str = "@drafts"
    drafts_scan_limit: int = 500
    active_tag: str = "#active"


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("src.scheduler.asyncio.sleep", new=AsyncMock()):
        yield


def _make_error(cls, **kwargs):
    err = cls.__new__(cls)
    for k, v in kwargs.items():
        setattr(err, k, v)
    Exception.__init__(err, f"test {cls.__name__}")
    return err


@pytest.mark.asyncio
async def test_peer_flood_stops_remaining_chats():
    """Второй чат ловит PeerFloodError — третий не должен быть тронут вообще."""
    cfg = FakeConfig(target_groups=["@a", "@b", "@c"])
    post = Post(text="hi", media=None, source_id=1)
    flood = _make_error(PeerFloodError)

    with (
        patch("src.scheduler.load_active_posts", new=AsyncMock(return_value=[post])),
        patch("src.scheduler.pick_random_post", return_value=post),
        patch(
            "src.scheduler.send_to",
            new=AsyncMock(side_effect=[True, flood]),
        ) as mock_send,
    ):
        await broadcast(AsyncMock(), cfg)

    assert mock_send.await_count == 2
