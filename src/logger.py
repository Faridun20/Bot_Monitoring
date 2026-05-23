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
