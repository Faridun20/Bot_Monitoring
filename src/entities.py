"""Обрезка хэштега-маркера из текста поста с сохранением entity-разметки.

Telegram считает смещения entities (`offset`/`length`) в UTF-16 code units,
а не в code points — обычная индексация Python-строк для этого не годится
(эмодзи вне BMP занимают 2 code unit, но 1 code point). Поэтому вся работа
со смещениями идёт через `telethon.helpers.add_surrogate`/`del_surrogate`.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from telethon import helpers


def strip_tag(text: str, entities: list[Any], tag: str) -> tuple[str, list[Any]]:
    """Вырезать все вхождения `tag` из `text`, поправив entities под новые
    смещения, затем обрезать пробелы по краям (как раньше делал `.strip()`).

    Не мутирует переданный список entities — возвращает новый.
    """
    entities = [copy.copy(e) for e in entities]

    surr_text = helpers.add_surrogate(text)
    surr_tag = helpers.add_surrogate(tag)

    matches = list(re.finditer(re.escape(surr_tag), surr_text))

    for match in reversed(matches):
        start, end = match.span()
        surr_text = surr_text[:start] + surr_text[end:]

        for e in entities:
            o, length = e.offset, e.length
            removed_before = max(0, min(end, o) - start)
            overlap = max(0, min(o + length, end) - max(o, start))
            e.offset = o - removed_before
            e.length = length - overlap

        entities = [e for e in entities if e.length > 0]

    surr_text = helpers.strip_text(surr_text, entities)

    return helpers.del_surrogate(surr_text), entities
