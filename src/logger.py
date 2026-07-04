"""Stdout-логгер для Railway. Никаких файлов — Railway собирает stdout сам."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Настроить корневой логгер: один StreamHandler в stdout."""
    root = logging.getLogger()

    # Снимаем все хендлеры, которые могли прицепить библиотеки до нас.
    for h in list(root.handlers):
        root.removeHandler(h)

    # На Windows stdout по умолчанию в cp1251 — переключаем в UTF-8,
    # иначе кириллица в сообщениях лога превращается в кракозябры.
    # На Railway/Linux stdout уже UTF-8, reconfigure — no-op.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Приглушаем болтливых
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
