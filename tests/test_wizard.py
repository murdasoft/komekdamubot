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


def test_nav_hint_has_98():
    from app.bot.content import WA_NAV_HINT_MAIN, wa_nav_hint_for_step

    assert "98" in WA_NAV_HINT_MAIN
    assert "99" not in wa_nav_hint_for_step("lang")
    assert wa_nav_hint_for_step("lang") == ""
    city_hint = wa_nav_hint_for_step("city")
    assert "99" in city_hint
    assert "0" in city_hint
    assert "98" in city_hint
    assert "98" in wa_nav_hint_for_step("main")


def test_city_invalid_reply_has_manager_and_help():
    from app.bot.wizard import get_city_invalid_reply, get_city_step_help

    ru = get_city_invalid_reply("ru")
    assert "7" in ru and "менеджер" in ru.lower()
    assert "0" in ru
    help_ru = get_city_step_help("ru")
    assert "1–7" in help_ru or "1-7" in help_ru


def test_lang_step_no_inline_99():
    assert "99" not in get_lang_step_text()
