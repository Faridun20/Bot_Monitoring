"""Одноразовый локальный скрипт для получения SESSION_STRING.

Запускать ЛОКАЛЬНО, на своей машине (не на Railway):

    python scripts/generate_session.py

Telethon интерактивно запросит телефон, код из Telegram и (если включена) 2FA.
После авторизации скрипт распечатает SESSION_STRING — скопируй её в Railway →
Variables → SESSION_STRING.

ВНИМАНИЕ: SESSION_STRING = полный доступ к Telegram-аккаунту. Никогда не
коммить, не пересылай, не вставляй в чаты. Только в Railway Variables.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


def _ask(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        print("Пустое значение — отмена.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    api_id_raw = os.environ.get("API_ID", "").strip()
    api_hash = os.environ.get("API_HASH", "").strip()

    if not api_id_raw:
        api_id_raw = _ask("API_ID: ")
    if not api_hash:
        api_hash = _ask("API_HASH: ")

    try:
        api_id = int(api_id_raw)
    except ValueError:
        print(f"API_ID должен быть числом, а не {api_id_raw!r}", file=sys.stderr)
        sys.exit(1)

    print()
    print("Подключаюсь к Telegram. Сейчас спросят телефон / код / 2FA.")
    print()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = client.get_me()
        session_string = client.session.save()

    print()
    print("=" * 72)
    print("Авторизация успешна:")
    print(f"  user_id : {me.id}")
    print(f"  name    : {me.first_name or ''} {me.last_name or ''}".rstrip())
    if me.username:
        print(f"  username: @{me.username}")
    print("=" * 72)
    print()
    print("SESSION_STRING (скопируй в Railway → Variables → SESSION_STRING):")
    print()
    print(session_string)
    print()
    print("ВАЖНО: это секрет уровня пароля. Никогда не коммить, не пересылай.")
    print("Если случайно где-то засветил — открой Telegram → Settings →")
    print("Devices → Terminate sessions, и сгенерируй заново.")


if __name__ == "__main__":
    main()
