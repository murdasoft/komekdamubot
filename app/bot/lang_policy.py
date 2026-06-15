"""
Язык диалога: қазақша — по умолчанию; орысша — после выбора 1/2, «русский» или русского текста.
Без зацикливания «выберите язык» после явного переключения.
"""

from __future__ import annotations

from typing import Optional

from app.bot.chatbot_ux import parse_lang_digit
from app.bot.content import DEFAULT_LANG
from app.bot.lang_detect import detect_message_lang, has_kazakh_marker

_LANG_ONLY_MAX_WORDS = 4


def is_explicit_lang_message(text: str) -> bool:
    """Только выбор языка: «русский», «2», «қазақша»."""
    t = text.strip()
    if not t:
        return False
    if parse_lang_digit(t) and len(t.split()) <= _LANG_ONLY_MAX_WORDS:
        return True
    return False


def apply_lang_switch(text: str, session: dict) -> bool:
    """
    Явное переключение языка. True — язык обновлён и заблокирован.
    «русский» / 2 → ru; «қазақша» / 1 → kk.
    """
    digit = parse_lang_digit(text.strip())
    if digit == "1":
        session["lang"] = "kk"
        session["lang_locked"] = True
        session.pop("ru_streak", None)
        session.pop("lang_retry", None)
        return True
    if digit == "2":
        session["lang"] = "ru"
        session["lang_locked"] = True
        session.pop("ru_streak", None)
        session.pop("lang_retry", None)
        return True
    return False


def lang_switch_confirmation(lang: str) -> str:
    if lang == "ru":
        return "✅ *Ок, общаемся по-русски.*\nНапишите вопрос или цифру раздела (1–7)."
    return "✅ *Жарайды, қазақша жалғастырамыз.*\nСұрағыңызды немесе бөлім санын (1–7) жазыңыз."


def resolve_voice_lang(
    text: str,
    session: dict,
    *,
    stt_lang: str | None = None,
) -> str:
    """
    Язык после голосового STT:
    - хотя бы 1 казахское слово/буква → kk
    - явный русский без kk → ru
    - иначе продолжаем session.lang (kk по умолчанию)
    """
    if session.get("lang_locked"):
        return session.get("lang", DEFAULT_LANG)

    if has_kazakh_marker(text):
        session["lang"] = "kk"
        session.pop("ru_streak", None)
        return "kk"

    detected = detect_message_lang(text)
    if detected == "ru":
        session["lang"] = "ru"
        session.pop("ru_streak", None)
        return "ru"

    if stt_lang == "ru" and not has_kazakh_marker(text):
        session["lang"] = "ru"
        return "ru"

    if session.get("lang") == "ru":
        return "ru"

    session["lang"] = DEFAULT_LANG
    return DEFAULT_LANG


def resolve_reply_lang(text: str, session: dict) -> str:
    """
    Язык ответа бота.
    - lang_locked → сохранённый язык
    - явный выбор / «русский» → ru + lock
    - русский текст → ru (+ lock)
    - иначе → kk (приоритет)
    """
    if session.get("lang_locked"):
        return session.get("lang", DEFAULT_LANG)

    if apply_lang_switch(text, session):
        return session["lang"]

    detected = detect_message_lang(text)
    if detected == "ru":
        session["lang"] = "ru"
        session["lang_locked"] = True
        session.pop("ru_streak", None)
        return "ru"

    session.pop("ru_streak", None)
    session["lang"] = DEFAULT_LANG
    return DEFAULT_LANG


def detect_lang_from_free_text(text: str) -> str:
    """Для шага выбора языка/города: kk по умолчанию, ru при явных маркерах."""
    digit = parse_lang_digit(text.strip())
    if digit == "1":
        return "kk"
    if digit == "2":
        return "ru"
    return detect_message_lang(text)


def hybrid_menu_footer(lang: str, session: dict) -> str:
    """Подсказка меню / шага мастера после гибридного ответа."""
    state = session.get("state")
    if state == "selecting_city" and not session.get("city_confirmed"):
        if lang == "kk":
            return (
                "\n\n📍 _Қалаңызды таңдаңыз (сан):_ "
                "1–Алматы · 2–Астана · 3–Шымкент · 4–Ақтау"
            )
        return (
            "\n\n📍 _Выберите город (цифрой):_ "
            "1–Алматы · 2–Астана · 3–Шымкент · 4–Актау"
        )
    if not session.get("city_confirmed"):
        return ""
    if state not in (None, "idle", "office_directed"):
        return ""
    if lang == "kk":
        return (
            "\n\n📋 _Бөлім таңдау: 1–ЖК · 2–ТОО · 3–жеке · 4–ипотека · "
            "5–DAMU · 6–рефинанс · 7–менеджер_"
        )
    return (
        "\n\n📋 _Разделы: 1–ИП · 2–ТОО · 3–физлицо · 4–ипотека · "
        "5–DAMU · 6–рефинанс · 7–менеджер_"
    )


def attach_hybrid_footer(reply: str, lang: str, session: dict, *, enabled: bool = True) -> str:
    if not enabled or not reply:
        return reply
    footer = hybrid_menu_footer(lang, session)
    if footer and footer.strip() not in reply:
        return f"{reply.rstrip()}{footer}"
    return reply
