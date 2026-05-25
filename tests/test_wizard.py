"""Wizard steps: language → city → menu."""

from app.bot.wizard import resolve_city_digit, get_city_step_text, get_lang_step_text


def test_resolve_city_digit():
    assert resolve_city_digit("1") == "almaty"
    assert resolve_city_digit("2") == "astana"
    assert resolve_city_digit("9") is None


def test_lang_step_has_digits():
    t = get_lang_step_text()
    assert "1 —" in t and "2 —" in t


def test_city_step_five_cities():
    t = get_city_step_text("ru")
    assert "1 —" in t and "5 —" in t or "5 — Актау" in t
