"""Политика языка: kk по умолчанию, ru после выбора или русского текста."""

from app.bot.content import DEFAULT_LANG
from app.bot.lang_policy import (
    apply_lang_switch,
    detect_lang_from_free_text,
    is_explicit_lang_message,
    resolve_reply_lang,
)


def test_default_kazakh():
    session = {"lang": DEFAULT_LANG, "lang_locked": False}
    assert resolve_reply_lang("несие керек", session) == "kk"


def test_russian_text_locks_ru():
    session = {"lang": DEFAULT_LANG, "lang_locked": False}
    assert resolve_reply_lang("Здравствуйте, нужен кредит на 5 млн", session) == "ru"
    assert session["lang_locked"] is True


def test_explicit_russian_no_reask():
    session = {"lang": "kk", "lang_locked": False}
    assert apply_lang_switch("русский", session) is True
    assert session["lang"] == "ru"
    assert session["lang_locked"] is True


def test_explicit_kazakh():
    session = {"lang": "ru", "lang_locked": False}
    assert apply_lang_switch("қазақша", session) is True
    assert session["lang"] == "kk"


def test_locked_stays_ru():
    session = {"lang": "ru", "lang_locked": True}
    assert resolve_reply_lang("сәлем", session) == "ru"


def test_is_explicit_lang():
    assert is_explicit_lang_message("русский")
    assert is_explicit_lang_message("2")
    assert not is_explicit_lang_message("нужен кредит 5 млн")


def test_resolve_voice_russian_no_kk():
    from app.bot.lang_policy import resolve_voice_lang

    session = {"lang": "kk", "lang_locked": False}
    assert resolve_voice_lang("здравствуйте нужен кредит на пять миллионов", session) == "ru"
    assert session["lang"] == "ru"


def test_resolve_voice_kk_with_one_word():
    from app.bot.lang_policy import resolve_voice_lang

    session = {"lang": "ru", "lang_locked": False}
    assert resolve_voice_lang("сәлем, нужен кредит", session) == "kk"
    assert session["lang"] == "kk"


def test_resolve_voice_continues_russian_session():
    from app.bot.lang_policy import resolve_voice_lang

    session = {"lang": "ru", "lang_locked": False}
    assert resolve_voice_lang("ипотека на квартиру", session) == "ru"


def test_has_kazakh_marker_mixed():
    from app.bot.lang_detect import has_kazakh_marker

    assert has_kazakh_marker("хочу кредит алғым келеді") is True
    assert has_kazakh_marker("нужен кредит на квартиру") is False
