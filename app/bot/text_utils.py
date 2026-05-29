"""Нормализация пользовательских сообщений."""

from __future__ import annotations

import re

_GREETING_START = re.compile(
    r"^(\s*(?:"
    r"здравствуйте?|добрый\s+(?:день|вечер|утро)|привет|"
    r"салам(?:атсыз)?(?:\s+бе)?|салем|сәлем(?:етсіз)?(?:\s+бе)?|"
    r"ассаламу|hello|hi|hey"
    r")[\s,!.\-—]*\s*)+",
    re.IGNORECASE,
)


def strip_leading_greeting(text: str) -> str:
    """Убрать приветствие в начале, оставить суть вопроса."""
    t = text.strip()
    prev = None
    while t != prev:
        prev = t
        t = _GREETING_START.sub("", t, count=1).strip()
    return t or text.strip()


def is_pure_greeting(text: str) -> bool:
    """Только приветствие без вопроса."""
    core = strip_leading_greeting(text).lower().strip("!?., ")
    if not core or len(core) < 3:
        return True
    pure = {
        "привет", "здравствуйте", "здравствуй", "добрый день", "добрый вечер",
        "салам", "сәлем", "салем", "саламатсызба", "саламатсыз",
        "салеметсезбе", "салеметсізбе", "сәлеметсізбе", "сalemetsizbe",
        "ассаламу", "assalomu",
        "hello", "hi",
        # WhatsApp voice transcription artifacts
        "dzień dobry",
    }
    return core in pure
