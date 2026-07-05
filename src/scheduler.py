"""APScheduler-обёртка: cron-джобы на времена из cfg.schedule, broadcast по группам."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon.errors import PeerFloodError

from .posts import load_active_posts, pick_next_post
from .sender import send_to

if TYPE_CHECKING:
    from telethon import TelegramClient

    from .config import Config

log = logging.getLogger(__name__)

# Состояние ротации постов между вызовами broadcast(): _post_deck — порядок
# id текущего цикла перемешивания (см. pick_next_post), _last_sent_id — id
# последнего отправленного, нужен только чтобы не повторить пост на стыке
# двух циклов. Живёт в памяти процесса; после рестарта просто обнуляется —
# не страшно, это не гарантия на всю жизнь бота, а защита от явных повторов.
_post_deck: list[int] = []
_last_sent_id: int | None = None


async def broadcast(client: TelegramClient, cfg: Config) -> None:
    """Одна итерация рассылки: один пост во все группы с задержками."""
    global _post_deck, _last_sent_id

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
        post, _post_deck = pick_next_post(posts, _post_deck, last_id=_last_sent_id)
    except RuntimeError as e:
        log.warning("Skip broadcast: %s", e)
        return
    except Exception:
        log.exception("Failed to load posts from drafts channel")
        return

    _last_sent_id = post.source_id

    log.info(
        "Picked post id=%s from drafts, text_len=%d, media_count=%d",
        post.source_id,
        len(post.text),
        len(post.media),
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
