"""Голосовой разбор: цифры и фразы меню без LLM."""

import pytest

from app.bot.voice_router import (
    extract_spoken_digit,
    map_menu_phrase,
    route_voice_text,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("один", "1"),
        ("первый", "1"),
        ("бір", "1"),
        ("екі", "2"),
        ("три", "3"),
        ("7", "7"),
        ("98", "98"),
    ],
)
def test_extract_spoken_digit(text, expected):
    assert extract_spoken_digit(text) == expected


@pytest.mark.parametrize(
    "text,digit",
    [
        ("хочу ипотеку", "4"),
        ("жеке тұлға кредит", "3"),
        ("тоо несие", "2"),
        ("даму 12 6", "5"),
    ],
)
def test_map_menu_phrase(text, digit):
    assert map_menu_phrase(text) == digit


def test_route_voice_ip_not_mortgage():
    session = {"lang": "ru", "state": "idle"}
    r = route_voice_text("ип кредит процент", session)
    assert r.source in ("raw", "phrase", "digit")
    assert "ип" in r.text.lower()


def test_route_voice_digit_over_phrase():
    session = {"lang": "kk", "state": "selecting_city"}
    r = route_voice_text("екі", session)
    assert r.text == "2"
    assert r.source == "digit"
