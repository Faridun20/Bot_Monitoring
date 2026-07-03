"""APScheduler-обёртка: cron-джобы на времена из cfg.schedule, broadcast по группам."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon.errors import PeerFloodError

from .posts import load_active_posts, pick_random_post
from .sender import send_to

if TYPE_CHECKING:
    from telethon import TelegramClient

    from .config import Config

log = logging.getLogger(__name__)


async def broadcast(client: TelegramClient, cfg: Config) -> None:
    """Одна итерация рассылки: один пост во все группы с задержками."""
    if cfg.jitter_minutes > 0:
        jitter = random.uniform(0, cfg.jitter_minutes * 60)
        log.info("broadcast: jitter %.1fs", jitter)
        await asyncio.sleep(jitter)

    try:
        posts = await load_active_posts(
            client,
            cfg.drafts_source,
            cfg.drafts_scan_limit,
            cfg.active_tag,
        )
        post = pick_random_post(posts)
    except RuntimeError as e:
        log.warning("Skip broadcast: %s", e)
        return
    except Exception:
        log.exception("Failed to load posts from drafts channel")
        return

    log.info(
        "Picked post id=%s from drafts, text_len=%d, has_media=%s",
        post.source_id,
        len(post.text),
        post.media is not None,
    )

    groups: list[str | int] = list(cfg.target_groups)
    if cfg.shuffle_groups:
        random.shuffle(groups)

    sent = 0
    total = len(groups)
    for i, chat in enumerate(groups):
        try:
            ok = await send_to(client, chat, post, cfg)
        except PeerFloodError:
            log.error(
                "broadcast прерван из-за PeerFloodError: %d/%d успели отправить "
                "до ограничения, остальные %d чатов пропущены",
                sent,
                total,
                total - i,
            )
            return
        if ok:
            sent += 1
        # Пауза только между группами, не после последней.
        if i < total - 1:
            delay = random.uniform(cfg.delay_min, cfg.delay_max)
            log.debug("sleep %.1fs before next group", delay)
            await asyncio.sleep(delay)

    log.info("broadcast done: %d/%d sent", sent, total)


def setup_scheduler(client: TelegramClient, cfg: Config) -> AsyncIOScheduler:
    """Создать AsyncIOScheduler и зарегистрировать cron-джобы по cfg.schedule."""
    scheduler = AsyncIOScheduler(timezone=cfg.timezone)

    for h, m in cfg.schedule:
        scheduler.add_job(
            broadcast,
            trigger="cron",
            hour=h,
            minute=m,
            args=[client, cfg],
            id=f"broadcast-{h:02d}-{m:02d}",
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )

    return scheduler
