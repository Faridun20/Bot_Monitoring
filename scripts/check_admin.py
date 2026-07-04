"""Проверка прав администратора в каждом чате из TARGET_GROUPS.

Использование:
    python scripts/check_admin.py

Только читает статус участника (get_permissions) — ничего никуда не
отправляет. Безопасно запускать в любой момент, не расходует лимиты
на сообщения.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telethon import TelegramClient  # noqa: E402
from telethon.sessions import StringSession  # noqa: E402

from src.config import _parse_chat_ref, load_config  # noqa: E402
from src.logger import setup_logging  # noqa: E402


async def run() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    # Список чатов можно передать явно первым аргументом (через запятую),
    # не трогая TARGET_GROUPS в .env. По умолчанию — берётся оттуда же.
    if len(sys.argv) > 1:
        target_groups = [_parse_chat_ref(s.strip()) for s in sys.argv[1].split(",") if s.strip()]
    else:
        target_groups = cfg.target_groups

    client = TelegramClient(StringSession(cfg.session_string), cfg.api_id, cfg.api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("SESSION_STRING невалиден. Перегенерируй через generate_session.py.")
        me = await client.get_me()
        print(f"Проверяю права {me.first_name} (@{me.username}) в {len(target_groups)} чатах:\n")

        print(f"{'chat_id':>16}  {'title':45}  статус")
        print("-" * 90)

        admin_count = 0
        for chat in target_groups:
            try:
                entity = await client.get_entity(chat)
                title = getattr(entity, "title", None) or getattr(entity, "username", None) or "?"
                perms = await client.get_permissions(entity, me)
                if perms.is_creator:
                    status = "СОЗДАТЕЛЬ"
                    admin_count += 1
                elif perms.is_admin:
                    status = "админ"
                    admin_count += 1
                else:
                    status = "просто участник"
                print(f"{str(chat):>16}  {title[:45]:45}  {status}")
            except Exception as e:
                print(f"{str(chat):>16}  {'?':45}  ошибка: {type(e).__name__}: {e}")

        print(f"\nИтого: админ/создатель в {admin_count} из {len(target_groups)}.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
