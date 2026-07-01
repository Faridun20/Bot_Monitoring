"""Распечатать список каналов/групп, на которые подписан userbot.

Использование:
    python scripts/list_dialogs.py

Читает API_ID / API_HASH / SESSION_STRING из .env. Удобно, когда нужно найти
ID нужного канала для DRAFTS_SOURCE или TARGET_GROUPS — особенно если канал
приватный и нет username.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

# На Windows stdout по умолчанию в cp1251 — переключаем в UTF-8,
# иначе имена с эмодзи/спец-символами падают с UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _require(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        print(f"{name} не задан. Заполни .env.", file=sys.stderr)
        sys.exit(1)
    return v


async def run() -> None:
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    api_id = int(_require("API_ID"))
    api_hash = _require("API_HASH")
    session_string = _require("SESSION_STRING")

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print("SESSION_STRING невалиден.", file=sys.stderr)
            sys.exit(1)

        print(f"{'ID':>16}  {'type':<8}  {'@username':<24}  title")
        print("-" * 80)
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            kind = type(entity).__name__
            username = f"@{entity.username}" if getattr(entity, "username", None) else "—"
            print(f"{dialog.id:>16}  {kind:<8}  {username:<24}  {dialog.name}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
