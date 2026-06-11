"""Голосовой разбор: цифры, фразы, intent → меню."""

import pytest

from app.bot.voice_router import (
    extract_spoken_digit,
    intent_to_menu_digit,
    map_intent_from_text,
    map_menu_phrase,
    resolve_menu_digit_from_text,
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
        ("жеті", "7"),
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
        ("кәсіпкерге кредит керек", "1"),
        ("қайта қаржыландыру", "6"),
        ("менеджерге қос", "7"),
    ],
)
def test_map_menu_phrase(text, digit):
    assert map_menu_phrase(text) == digit


def test_resolve_kazakh_credit_intent():
    assert resolve_menu_digit_from_text("несие алғым келеді", {}) == "3"


def test_route_voice_ip_not_mortgage():
    session = {"lang": "ru", "state": "idle"}
    r = route_voice_text("ип кредит процент", session)
    assert r.source in ("raw", "phrase", "digit", "intent")
    assert "ип" in r.text.lower() or r.text == "1"


def test_route_voice_digit_over_phrase():
    session = {"lang": "kk", "state": "selecting_city"}
    r = route_voice_text("екі", session)
    assert r.text == "2"
    assert r.source == "digit"


def test_route_voice_lang_selection():
    session = {"lang": "kk", "state": "selecting_lang"}
    r = route_voice_text("қазақша", session)
    assert r.text == "1"
    assert r.source == "lang"


def test_intent_mortgage_to_digit():
    assert intent_to_menu_digit("mortgage_standard", "хочу ипотеку", {}) == "4"


def test_intent_business_ip_to_digit():
    assert intent_to_menu_digit("business_credit", "кредит для ип", {}) == "1"


def test_intent_business_too_to_digit():
    assert intent_to_menu_digit("business_credit", "тоо кредит", {}) == "2"


def test_map_intent_from_kazakh_voice():
    digit = map_intent_from_text("пәтерге ипотека керек", {})
    assert digit == "4"


def test_voice_greeting_plus_credit_not_menu_zero():
    """«сәлеметсізбе + несие» — не сворачивать в меню 0."""
    from app.bot.voice_router import map_menu_phrase, route_voice_text

    raw = "сәлеметсізбе менінше алғым келеді"
    assert map_menu_phrase(raw) is None
    r = route_voice_text(raw, {"lang": "kk", "state": "idle", "city_confirmed": True})
    assert r.source == "raw"
    assert "алғым" in r.text


def test_stt_fix_meninshe_to_nesie():
    from app.bot.stt_normalize import normalize_stt_voice_text

    assert "несие" in normalize_stt_voice_text("сәлеметсізбе менінше алғым келеді")


def test_resolve_menu_digit_combined():
    session = {"lang": "ru", "state": "idle"}
    assert resolve_menu_digit_from_text("рефинансирование кредита", session) == "6"
    assert resolve_menu_digit_from_text("четыре", session) == "4"
