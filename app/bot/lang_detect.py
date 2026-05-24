"""Определение языка RU/KK без ложных срабатываний на «кредит», «ипотека» и т.п."""

from __future__ import annotations

import re

from app.bot.content import DEFAULT_LANG
from app.bot.kazakh_dict import (
    KK_CHARS,
    ALL_KK_WORDS,
    KK_PHRASES_EXTENDED as KK_PHRASES,
)

_WORD_RE = re.compile(r"[a-zа-яёәіңғүұқөһ]+", re.IGNORECASE)

# Слова, которые пишут и на русском, и в кредитном жаргоне KK — не маркер языка
_AMBIGUOUS = {
    "кредит", "несие", "ипотека", "ипотек", "даму", "залог", "офис",
    "менеджер", "бизнес", "паспорт", "телефон", "компания", "клиент",
    "удостоверение", "пенсия", "пенсионка", "ип", "тоо", "млн", "миллион",
    "тенге", "ставка", "процент", "whatsapp", "telegram",
}

# Явные русские слова / приветствия
_RU_MARKERS = {
    "здравствуйте", "здравствуй", "добрый", "доброе", "привет", "пожалуйста",
    "спасибо", "хочу", "взять", "нужен", "нужно", "можно", "сколько",
    "какой", "какая", "какие", "почему", "зачем", "или", "если", "очень",
    "хорошо", "подскажите", "расскажите", "интересует", "оформить", "получить",
    "рубль", "рублей", "наличными", "потребительский", "рефинансирование",
}

_RU_PHRASES = (
    "добрый день", "добрый вечер", "как дела", "хочу взять", "взять хочу",
    "нужен кредит", "кредит на",
)


def detect_message_lang(text: str) -> str:
    """
    kk — по умолчанию; ru — при явных русских маркерах.
    """
    if not text or not text.strip():
        return DEFAULT_LANG

    lower = text.lower()

    if any(c in KK_CHARS for c in lower):
        return "kk"

    for phrase in _RU_PHRASES:
        if phrase in lower:
            return "ru"

    words = set(_WORD_RE.findall(lower))
    if words & _RU_MARKERS:
        return "ru"

    for phrase in KK_PHRASES:
        if phrase in lower:
            return "kk"

    kk_only = words - _AMBIGUOUS
    if kk_only & ALL_KK_WORDS:
        return "kk"

    return DEFAULT_LANG
