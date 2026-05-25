"""
Непонятный ввод: оператор, фрустрация, эмодзи — универсальный ответ, не зацикливание на 99.
"""

from __future__ import annotations

import re

_EMOJI_ONLY = re.compile(
    r"^[\s\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+$"
)

_OPERATOR_WORDS = (
    "оператор",
    "менеджер",
    "человек",
    "маман",
    "админ",
    "номер",
    "телефон",
    "позвон",
    "звон",
    "звоните",
    "позвони",
    "дайте",
    "дай",
    "беріңіз",
    "бер",
    "нөмір",
    "нөмірің",
    "қоңырау",
    "контакт",
    "связ",
    "свяж",
    "перезвон",
    "хабарлас",
    "whatsapp",
    "ватсап",
)

_FRUSTRATION_WORDS = (
    "непонят",
    "не понял",
    "не понима",
    "түсінбед",
    "с ума",
    "бесит",
    "заеб",
    "хуйн",
    "чушь",
    "ерунд",
    "глуп",
    "туп",
    "не работ",
    "не отвеч",
    "чат не",
    "бот не",
)


def is_operator_or_phone_request(text: str) -> bool:
    low = text.lower().strip()
    if not low:
        return False
    if low in ("7", "07"):
        return True
    return any(w in low for w in _OPERATOR_WORDS)


def is_frustration_or_unclear(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if len(t) <= 2 and not t.isdigit():
        return True
    if _EMOJI_ONLY.match(t):
        return True
    low = t.lower()
    return any(w in low for w in _FRUSTRATION_WORDS)


def should_use_universal_fallback(text: str) -> bool:
    """Свободный текст не похож на выбор шага мастера."""
    t = text.strip()
    if t in ("0", "98", "99"):
        return False
    if t.isdigit() and len(t) == 1:
        return False
    if is_operator_or_phone_request(t):
        return False
    return is_frustration_or_unclear(t) or len(t.split()) >= 2
