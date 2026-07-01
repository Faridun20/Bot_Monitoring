"""Одноразовая тестовая рассылка — без ожидания расписания.

Использование:
    python scripts/test_broadcast.py

Подключается к Telegram под .env, вычитывает посты из DRAFTS_SOURCE и
делает ОДНУ рассылку в TARGET_GROUPS прямо сейчас. Ни APScheduler, ни
signal handlers — только чистый broadcast().

Прежде чем запускать: убедись, что в TARGET_GROUPS сейчас стоит ТОЛЬКО
твой тестовый чат, а не боевые каналы — иначе улетит в прод.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Разрешаем `from src.xxx` при запуске из корня проекта или из scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import TelegramClient  # noqa: E402
from telethon.sessions import StringSession  # noqa: E402

from src.config import load_config  # noqa: E402
from src.logger import setup_logging  # noqa: E402
from src.scheduler import broadcast  # noqa: E402

log = logging.getLogger(__name__)


async def run() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    log.info("TEST: target_groups=%s, drafts=%s", cfg.target_groups, cfg.drafts_source)

    if len(cfg.target_groups) > 3:
        log.warning(
            "TEST: в TARGET_GROUPS %d чатов — уверен, что все тестовые?",
            len(cfg.target_groups),
        )

    client = TelegramClient(
        StringSession(cfg.session_string),
        cfg.api_id,
        cfg.api_hash,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("SESSION_STRING невалиден. Перегенерируй через generate_session.py.")
        me = await client.get_me()
        log.info("Authorized as %s (@%s) id=%s", me.first_name, me.username, me.id)

        await broadcast(client, cfg)
    finally:
        await client.disconnect()

    log.info("TEST: готово. Проверь тестовый чат в Telegram.")


if __name__ == "__main__":
    asyncio.run(run())
