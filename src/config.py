"""Загрузка и валидация конфигурации из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str = field(repr=False)
    session_string: str = field(repr=False)
    target_groups: list[str | int]
    schedule: list[tuple[int, int]]
    timezone: str
    drafts_source: str | int
    drafts_scan_limit: int
    active_tag: str
    delay_min: int
    delay_max: int
    jitter_minutes: int
    max_slow_mode_wait: int
    shuffle_groups: bool
    log_level: str


_TRUTHY = {"true", "1", "yes", "y", "on"}


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Переменная окружения {name} не задана или пустая. "
            f"Заполни её в .env (локально) или в Railway → Variables."
        )
    return value


def _optional_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Переменная {name}={raw!r} должна быть целым числом.") from exc


def _optional_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in _TRUTHY


def _parse_chat_ref(s: str) -> str | int:
    """Превратить строковую ссылку на чат в int (если это id) или оставить str."""
    # Числовой id (например -1001234567890 или 12345) → int.
    if s.lstrip("-").isdigit():
        return int(s)
    # @username или username — кладём строкой. Telethon примет оба варианта.
    return s


def _parse_target_groups(raw: str) -> list[str | int]:
    items = [_parse_chat_ref(s.strip()) for s in raw.split(",") if s.strip()]
    if not items:
        raise RuntimeError(
            "TARGET_GROUPS пуст. Укажи список групп через запятую, "
            "например: @group1,@group2,-1001234567890"
        )
    return items


def _parse_schedule(raw: str) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for chunk in raw.split(","):
        s = chunk.strip()
        if not s:
            continue
        if ":" not in s:
            raise RuntimeError(f"SCHEDULE: элемент {s!r} не в формате HH:MM.")
        h_str, m_str = s.split(":", 1)
        try:
            h, m = int(h_str), int(m_str)
        except ValueError as exc:
            raise RuntimeError(f"SCHEDULE: элемент {s!r} содержит не-числа.") from exc
        if not (0 <= h < 24 and 0 <= m < 60):
            raise RuntimeError(f"SCHEDULE: {s!r} вне диапазона (0–23 часов, 0–59 минут).")
        result.append((h, m))
    if not result:
        raise RuntimeError("SCHEDULE пуст. Укажи времена через запятую, например: 10:00,19:30")
    return result


def load_config() -> Config:
    """Прочитать .env (если есть) и собрать Config из окружения."""
    # На Railway .env-файла не будет — переменные приходят из окружения.
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    api_id_raw = _require("API_ID")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise RuntimeError(f"API_ID={api_id_raw!r} должен быть целым числом.") from exc

    delay_min = _optional_int("DELAY_BETWEEN_GROUPS_MIN", 8)
    delay_max = _optional_int("DELAY_BETWEEN_GROUPS_MAX", 25)
    if delay_min < 0 or delay_max < 0 or delay_max < delay_min:
        raise RuntimeError(
            f"DELAY_BETWEEN_GROUPS_MIN={delay_min}, MAX={delay_max}: "
            "оба должны быть >=0 и MAX >= MIN."
        )

    jitter = _optional_int("JITTER_MINUTES", 7)
    if jitter < 0:
        raise RuntimeError("JITTER_MINUTES должен быть >= 0.")

    max_slow = _optional_int("MAX_SLOW_MODE_WAIT", 120)
    if max_slow < 0:
        raise RuntimeError("MAX_SLOW_MODE_WAIT должен быть >= 0.")

    drafts_scan_limit = _optional_int("DRAFTS_SCAN_LIMIT", 500)
    if drafts_scan_limit <= 0:
        raise RuntimeError("DRAFTS_SCAN_LIMIT должен быть > 0.")

    active_tag = (os.environ.get("ACTIVE_TAG") or "#active").strip()
    if not active_tag:
        raise RuntimeError("ACTIVE_TAG не должен быть пустым.")

    return Config(
        api_id=api_id,
        api_hash=_require("API_HASH"),
        session_string=_require("SESSION_STRING"),
        target_groups=_parse_target_groups(_require("TARGET_GROUPS")),
        schedule=_parse_schedule(_require("SCHEDULE")),
        timezone=_require("TIMEZONE"),
        drafts_source=_parse_chat_ref(_require("DRAFTS_SOURCE")),
        drafts_scan_limit=drafts_scan_limit,
        active_tag=active_tag,
        delay_min=delay_min,
        delay_max=delay_max,
        jitter_minutes=jitter,
        max_slow_mode_wait=max_slow,
        shuffle_groups=_optional_bool("SHUFFLE_GROUPS", True),
        log_level=os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO",
    )
