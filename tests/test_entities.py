"""Тесты для entities.strip_tag — вырезание тега с поправкой смещений entities."""

from __future__ import annotations

from dataclasses import dataclass

from src.entities import strip_tag


@dataclass
class _E:
    """Мини-заглушка telethon MessageEntity* — offset/length, как в strip_tag."""

    offset: int
    length: int


def test_no_entities_behaves_like_plain_replace_and_strip():
    text, entities = strip_tag("  Привет #active мир  ", [], "#active")
    assert text == "Привет  мир"
    assert entities == []


def test_tag_before_entity_shifts_offset_length_unchanged():
    # "#active Привет" -> entity покрывает "Привет" (offset=8, length=6)
    entity = _E(offset=8, length=6)
    text, entities = strip_tag("#active Привет", [entity], "#active")
    assert text == "Привет"
    assert entities == [_E(offset=0, length=6)]


def test_tag_inside_entity_shrinks_length_offset_unchanged():
    # "Привет #active мир" целиком под одной entity (offset=0, length=19)
    entity = _E(offset=0, length=19)
    text, entities = strip_tag("Привет #active мир", [entity], "#active")
    assert text == "Привет  мир" == text
    assert entities == [_E(offset=0, length=len(text))]


def test_tag_after_entity_untouched():
    # "Привет #active" -> entity покрывает "Привет" (offset=0, length=6)
    entity = _E(offset=0, length=6)
    text, entities = strip_tag("Привет #active", [entity], "#active")
    assert text == "Привет"
    assert entities == [_E(offset=0, length=6)]


def test_tag_exactly_covers_entity_drops_it():
    entity = _E(offset=0, length=7)  # ровно "#active"
    text, entities = strip_tag("#active", [entity], "#active")
    assert text == ""
    assert entities == []


def test_two_tag_occurrences_one_before_one_inside_different_entities():
    # "#active Жирный #active текст" — первый тег перед entity1, второй внутри entity2
    entity1 = _E(offset=8, length=6)  # "Жирный" после первого тега
    entity2 = _E(offset=8, length=21)  # "Жирный #active текст" целиком
    text, entities = strip_tag("#active Жирный #active текст", [entity1, entity2], "#active")
    assert text == "Жирный  текст"
    e1, e2 = entities
    assert (e1.offset, e1.length) == (0, 6)
    assert (e2.offset, e2.length) == (0, len(text))


def test_astral_emoji_before_entity_offset_correct_under_utf16():
    # "😀" — суррогатная пара (2 UTF-16 code unit), но 1 Python code point.
    # entity должна сдвинуться на длину тега, посчитанную в UTF-16 unit'ах.
    text_in = "😀 #active Привет"
    # "Привет" начинается после "😀 #active " -> в UTF-16: 2 (emoji) + 1 (space)
    # + 7 (#active) + 1 (space) = 11 code units.
    entity = _E(offset=11, length=6)
    text, entities = strip_tag(text_in, [entity], "#active")
    assert text == "😀  Привет"
    # После вырезания тега "Привет" сдвигается на 7 code units (длина "#active")
    assert entities == [_E(offset=4, length=6)]


def test_whitespace_only_after_strip():
    text, entities = strip_tag("   #active   ", [], "#active")
    assert text == ""
    assert entities == []


def test_no_tag_occurrence_leaves_entities_untouched():
    entity = _E(offset=0, length=5)
    text, entities = strip_tag("Привет", [entity], "#active")
    assert text == "Привет"
    assert entities == [_E(offset=0, length=5)]
