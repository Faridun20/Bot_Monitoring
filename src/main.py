"""Точка входа userbot'а. Запуск: ``python -m src.main``."""

from __future__ import annotations

import asyncio
import logging
import signal

from telethon import TelegramClient
from telethon.sessions import StringSession

from .config import load_config
from .logger import setup_logging
from .scheduler import setup_scheduler

log = logging.getLogger(__name__)


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    client = TelegramClient(
        StringSession(cfg.session_string),
        cfg.api_id,
        cfg.api_hash,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "SESSION_STRING невалиден или сессия отозвана. "
                "Перегенерируй через `python scripts/generate_session.py`."
            )

        me = await client.get_me()
        log.info(
            "Authorized as %s (@%s) id=%s",
            me.first_name,
            me.username,
            me.id,
        )

        scheduler = setup_scheduler(client, cfg)
        scheduler.start()
        log.info(
            "Scheduler started: %s (%s), groups=%d, drafts=%s",
            cfg.schedule,
            cfg.timezone,
            len(cfg.target_groups),
            cfg.drafts_source,
        )
        # Полный список печатаем отдельной строкой — это единственная
        # проверка перед автоматической отправкой, никакого подтверждения
        # рассылка не спрашивает. Сверяй глазами при каждом рестарте.
        log.info("TARGET_GROUPS: %s", cfg.target_groups)

        # Graceful shutdown по SIGTERM/SIGINT (Railway шлёт SIGTERM при редеплое).
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                # На Windows add_signal_handler не поддерживается — fallback на default.
                signal.signal(sig, lambda *_: stop_event.set())

        await stop_event.wait()

        log.info("Shutting down...")
        scheduler.shutdown(wait=False)
    finally:
        if client.is_connected():
            await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Чистый выход — лог уже написан в main().
        pass
