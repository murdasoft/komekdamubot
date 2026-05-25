"""
После STT: нормализация и маршрутизация в цифры меню / FAQ (без свободного ответа LLM).
Опционально Groq — только классификация намерения (GROQ_VOICE_INTENT).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from app.bot.stt_normalize import normalize_stt_borrower_answer

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)

# Голосовые «один», «первый», «бір» → цифра
_SPOKEN_NUMBERS: dict[str, str] = {}
for _digit, _words in {
    "0": ("ноль", "нуль", "нол", "зеро"),
    "1": (
        "один", "одна", "одно", "первый", "первая", "первое", "первую",
        "бір", "бир", "бірінші",
    ),
    "2": ("два", "две", "второй", "вторая", "второе", "екі", "еки", "екінші"),
    "3": ("три", "третий", "третья", "үш", "уш", "үшінші"),
    "4": ("четыре", "четвертый", "төрт", "торт", "төртінші"),
    "5": ("пять", "пятый", "бес", "бесінші"),
    "6": ("шесть", "шестой", "алты", "алтыншы"),
    "7": ("семь", "седьмой", "жеті", "жетінші"),
    "98": ("девяносто восемь", "тоғыз он сегіз", "сменить город", "қаланы ауыстыру"),
    "99": ("девяносто девять", "тоғыз он тоғыз", "сменить язык", "тілді ауыстыру"),
}.items():
    for w in _words:
        _SPOKEN_NUMBERS[w] = _digit

_MENU_PHRASE_TO_DIGIT: list[tuple[str, str]] = [
    ("жеке тұлға", "3"),
    ("жеке туған", "3"),
    ("физлиц", "3"),
    ("физическ", "3"),
    ("жк ", "1"),
    ("жс ", "1"),
    (" ип", "1"),
    ("ип ", "1"),
    ("кәсіпкер", "1"),
    ("касипкер", "1"),
    ("тоо", "2"),
    ("төо", "2"),
    ("ипотек", "4"),
    ("ипотека", "4"),
    ("пәтер", "4"),
    ("даму", "5"),
    ("рефинанс", "6"),
    ("қайта қарж", "6"),
    ("менеджер", "7"),
    ("оператор", "7"),
    ("мәзір", "0"),
    ("меню", "0"),
]


@dataclass(frozen=True)
class VoiceRoute:
    """Результат разбора голоса для обработчика (как будто пользователь напечатал text)."""

    text: str
    source: str  # digit | phrase | groq_intent | raw


def _normalize_low(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def extract_spoken_digit(text: str) -> str | None:
    low = _normalize_low(text)
    if low.isdigit() and len(low) <= 2:
        return low
    words = set(_WORD.findall(low))
    if len(words) == 1:
        w = next(iter(words))
        if w in _SPOKEN_NUMBERS:
            return _SPOKEN_NUMBERS[w]
    for w in sorted(words, key=len, reverse=True):
        if w in _SPOKEN_NUMBERS:
            return _SPOKEN_NUMBERS[w]
    compact = re.sub(r"[^\wа-яёәіңғүұқөһ]+", " ", low)
    for phrase, digit in sorted(_SPOKEN_NUMBERS.items(), key=lambda x: -len(x[0])):
        if phrase in compact:
            return digit
    return None


def map_menu_phrase(text: str) -> str | None:
    low = f" {_normalize_low(text)} "
    for phrase, digit in sorted(_MENU_PHRASE_TO_DIGIT, key=lambda x: -len(x[0])):
        if phrase in low:
            return digit
    return None


async def groq_classify_intent(
    text: str,
    session: dict | None,
    settings: "Settings",
) -> str | None:
    """
    Короткий вызов Groq: только JSON с action, без генерации ответа клиенту.
    Экономия: ~80 токенов, модель 8b instant.
    """
    if not settings.groq_voice_intent or not settings.is_groq_configured:
        return None

    from app.groq_client import GroqClient

    lang = (session or {}).get("lang", "kk")
    state = (session or {}).get("state", "idle")

    system = (
        "Ты классификатор голосовых команд банка KOMEK DAMU. "
        "Верни ТОЛЬКО JSON без markdown: "
        '{"cmd":"1-7|98|99|0|ru|kk|faq_topic|unknown","topic":""}. '
        "cmd: цифра меню 1=ИП 2=ТОО 3=физлицо 4=ипотека 5=DAMU 6=рефинанс 7=менеджер. "
        "98=город, 99=язык, 0=меню. ru/kk=выбор языка на шаге 1. "
        "faq_topic=краткая тема (ip_credit|too|personal|mortgage|damu). "
        f"Состояние диалога: {state}. Язык: {lang}."
    )
    groq = GroqClient(
        settings.groq_api_key,
        model=settings.groq_voice_intent_model,
        stt_model=settings.groq_stt_model,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text[:500]},
    ]
    raw, err = await groq.chat(messages, temperature=0.0, max_tokens=80)
    if err or not raw:
        logger.warning("Groq voice intent failed: %s", err)
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start >= 0 and end > start else {}
    except json.JSONDecodeError:
        logger.warning("Groq voice intent JSON parse fail: %s", raw[:80])
        return None

    cmd = str(data.get("cmd", "unknown")).lower().strip()
    topic = str(data.get("topic", "")).lower().strip()

    if cmd in "0123456789" or cmd in ("98", "99"):
        return cmd
    if cmd == "ru":
        return "2"
    if cmd == "kk":
        return "1"
    if cmd == "0":
        return "0"
    if cmd == "faq_topic":
        mapping = {
            "ip_credit": "ип кредит",
            "ip": "ип",
            "too": "тоо кредит",
            "personal": "жеке несие",
            "mortgage": "ипотека",
            "damu": "даму",
        }
        return mapping.get(topic, text)
    return None


def route_voice_text(
    text: str,
    session: dict | None,
    settings: Optional["Settings"] = None,
) -> VoiceRoute:
    """
    Превратить транскрипт в команду для существующего текстового обработчика.
    """
    from app.config import get_settings

    settings = settings or get_settings()
    cleaned = normalize_stt_borrower_answer(text, session)

    digit = extract_spoken_digit(cleaned)
    if digit:
        return VoiceRoute(text=digit, source="digit")

    phrase_digit = map_menu_phrase(cleaned)
    if phrase_digit:
        return VoiceRoute(text=phrase_digit, source="phrase")

    if len(cleaned) <= 3 and cleaned.isdigit():
        return VoiceRoute(text=cleaned, source="digit")

    return VoiceRoute(text=cleaned, source="raw")


async def prepare_voice_input(
    text: str,
    session: dict | None,
    settings: Optional["Settings"] = None,
) -> VoiceRoute:
    """STT → нормализация; при необходимости Groq только для cmd (не ответа)."""
    from app.config import get_settings

    settings = settings or get_settings()
    route = route_voice_text(text, session, settings)

    if route.source != "raw":
        return route

    if len(route.text.split()) <= 8:
        groq_cmd = await groq_classify_intent(route.text, session, settings)
        if groq_cmd:
            logger.info("Voice Groq intent: %r -> %r", route.text[:40], groq_cmd)
            return VoiceRoute(text=groq_cmd, source="groq_intent")

    return route
