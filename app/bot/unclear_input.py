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


_FINANCE_HINTS = (
    "кредит", "несие", "ипотек", "даму", "рефинанс", "займ", "тенге", "тг",
    "млн", "миллион", "процент", "ставк", "пайыз", "лимит", "залог", "кепіл",
    "ип", "жк", "тоо", "төо", "жеке", "физлиц", "бизнес", "кәсіп", "пәтер",
    "қарыз", "карыз", "ақша", "акша", "офис", "менеджер", "оператор",
)

_OFF_TOPIC_HINTS = (
    "футбол", "football", "погод", "ауа рай", "рецепт", "кино", "фильм",
    "сериал", "любов", "махаббат", "анекдот", "әзіл", "шутк", "политик",
    "президент", "война", "соғыс", "игра", "ойын", "minecraft", "тикток",
    "instagram", "песн", "ән", "music", "музык", "ресторан", "мейрамхана",
    "такси", "uber", "пицц", "пиво", "водк",
)


def is_off_topic_message(text: str) -> bool:
    """Сообщение явно не про кредиты/ипотеку."""
    low = text.lower().strip()
    if not low or len(low) <= 2:
        return False
    if any(h in low for h in _FINANCE_HINTS):
        return False
    if any(h in low for h in _OFF_TOPIC_HINTS):
        return True
    greet = (
        "салам", "сәлем", "привет", "здравств", "рахмет", "спасибо",
        "калай", "қалай", "саламатсыз",
    )
    if any(g in low for g in greet):
        return False
    words = low.split()
    if len(words) >= 5 and not any(
        h in low for h in ("керек", "көмек", "помог", "help", "несие", "кредит")
    ):
        return True
    return False


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
