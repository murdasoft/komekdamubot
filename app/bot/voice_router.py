"""
После STT: нормализация и маршрутизация в цифры меню / FAQ (без свободного ответа LLM).
Опционально Groq — только классификация намерения (GROQ_VOICE_INTENT).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from app.bot.stt_normalize import normalize_stt_borrower_answer

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)

_SPOKEN_NUMBERS: dict[str, str] = {}
for _digit, _words in {
    "0": ("ноль", "нуль", "нол", "зеро", "нөл"),
    "1": (
        "один", "одна", "одно", "первый", "первая", "первое", "первую",
        "бір", "бир", "бірінші", "биринши",
    ),
    "2": ("два", "две", "второй", "вторая", "второе", "екі", "еки", "екінші", "екинши"),
    "3": ("три", "третий", "третья", "үш", "уш", "үшінші", "ушинши"),
    "4": ("четыре", "четвертый", "төрт", "торт", "төртінші", "тортинши"),
    "5": ("пять", "пятый", "бес", "бесінші", "бесинши"),
    "6": ("шесть", "шестой", "алты", "алтыншы", "алтынши"),
    "7": ("семь", "седьмой", "жеті", "жетинши", "жетінші"),
    "98": ("девяносто восемь", "тоғыз он сегіз", "сменить город", "қаланы ауыстыру", "қала ауыстыру"),
    "99": ("девяносто девять", "тоғыз он тоғыз", "сменить язык", "тілді ауыстыру", "тіл ауыстыру"),
}.items():
    for w in _words:
        _SPOKEN_NUMBERS[w] = _digit

_MENU_PHRASE_TO_DIGIT: list[tuple[str, str]] = [
    # Физлицо
    ("жеке тұлға", "3"),
    ("жеке туған", "3"),
    ("жеке несие", "3"),
    ("жеке адам", "3"),
    ("физлиц", "3"),
    ("физическ", "3"),
    ("для себя", "3"),
    ("өзіме", "3"),
    ("өзіне", "3"),
    ("жеке", "3"),
    # ИП / бизнес
    ("индивидуальн", "1"),
    ("предпринимател", "1"),
    ("кәсіпкер", "1"),
    ("касипкер", "1"),
    ("жк ", "1"),
    ("жс ", "1"),
    (" ип", "1"),
    ("ип ", "1"),
    ("бизнес", "1"),
    ("кәсіп", "1"),
    ("касип", "1"),
    # ТОО
    ("тоо", "2"),
    ("төо", "2"),
    ("компания", "2"),
    ("компанияға", "2"),
    # Ипотека
    ("гос ипотек", "4"),
    ("мемлекеттік ипотека", "4"),
    ("ипотек", "4"),
    ("ипотека", "4"),
    ("пәтер", "4"),
    ("пәтерге", "4"),
    ("квартир", "4"),
    ("үй сатып", "4"),
    ("үй алу", "4"),
    # DAMU
    ("даму 12", "5"),
    ("даму", "5"),
    ("damu", "5"),
    # Рефинанс
    ("рефинанс", "6"),
    ("қайта қарж", "6"),
    ("қайта қаржыландыру", "6"),
    ("перекрыть кредит", "6"),
    ("қайта", "6"),
    # Оператор / меню
    ("менеджер", "7"),
    ("оператор", "7"),
    ("маман", "7"),
    ("қос", "7"),
    ("байланыс", "7"),
    ("мәзір", "0"),
    ("меню", "0"),
    ("бастау", "0"),
]


@dataclass(frozen=True)
class VoiceRoute:
    """Результат разбора голоса для обработчика (как будто пользователь напечатал text)."""

    text: str
    source: str  # digit | phrase | intent | groq_intent | lang | raw
    raw_transcript: str = ""


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


def looks_like_credit_question(text: str) -> bool:
    """Общий вопрос про несие — в AI, как при тексте (не цифра меню)."""
    from app.bot.text_utils import strip_leading_greeting

    core = strip_leading_greeting(text).lower().strip()
    if not core:
        return False
    open_markers = (
        "алғым келеді", "несие алу", "несие керек", "кредит керек",
        "қарыз керек", "нужен кредит", "хочу кредит", "хочу взять",
    )
    if any(m in core for m in open_markers):
        return True
    product_hints = (
        "жк", " ип", "ип ", "тоо", "төо", "жеке", "физлиц", "ипотек",
        "даму", "кәсіп", "касип", "бизнес", "пәтер", "квартир",
    )
    if ("несие" in core or "кредит" in core) and not any(h in core for h in product_hints):
        return True
    return False


def map_menu_phrase(text: str) -> str | None:
    from app.bot.text_utils import strip_leading_greeting

    core = strip_leading_greeting(text).strip()
    if not core:
        return None
    low = f" {_normalize_low(core)} "
    for phrase, digit in sorted(_MENU_PHRASE_TO_DIGIT, key=lambda x: -len(x[0])):
        if phrase in low:
            return digit
    return None


def intent_to_menu_digit(intent: str, text: str, session: dict | None = None) -> str | None:
    """Продуктовый intent → цифра главного меню (1–7)."""
    from app.bot.knowledge_base import detect_business_entity, mentions_ip, mentions_too

    if intent == "personal_credit":
        return "3"
    if intent in ("mortgage_standard", "mortgage_gov"):
        return "4"
    if intent == "damu":
        return "5"
    if intent == "refinancing":
        return "6"
    if intent == "business_credit":
        entity = detect_business_entity(text)
        if entity == "too" or mentions_too(text):
            return "2"
        if entity == "ip" or mentions_ip(text):
            return "1"
        last_ent = (session or {}).get("last_entity")
        if last_ent == "too":
            return "2"
        if last_ent == "ip":
            return "1"
        return "1"
    return None


def map_intent_from_text(text: str, session: dict | None = None) -> str | None:
    """detect_intent → цифра меню."""
    from app.bot.knowledge_base import detect_intent

    intent = detect_intent(text, session)
    if not intent:
        return None
    return intent_to_menu_digit(intent, text, session)


def parse_voice_lang_digit(text: str) -> str | None:
    """Голосовой выбор языка: «қазақша», «русский», «бір», «екі»."""
    from app.bot.chatbot_ux import parse_lang_digit

    return parse_lang_digit(text)


async def groq_classify_intent(
    text: str,
    session: dict | None,
    settings: "Settings",
) -> str | None:
    """
    Короткий вызов Groq: только JSON с action, без генерации ответа клиенту.
    """
    if not settings.groq_voice_intent or not settings.is_groq_configured:
        return None

    from app.groq_client import GroqClient

    lang = (session or {}).get("lang", "kk")
    state = (session or {}).get("state", "idle")

    system = (
        "Ты классификатор голосовых команд банка KOMEK DAMU (Казахстан). "
        "Верни ТОЛЬКО JSON без markdown: "
        '{"cmd":"1-7|98|99|0|ru|kk|faq_topic|unknown","topic":""}. '
        "cmd: 1=ИП/ЖК бизнес 2=ТОО 3=физлицо/жеке 4=ипотека 5=DAMU 6=рефинанс 7=менеджер. "
        "98=город, 99=язык, 0=меню. ru/kk=выбор языка. "
        "faq_topic=ip_credit|too|personal|mortgage|damu|refinancing. "
        "Числительные: бір/один=1, екі/два=2, үш/три=3, төрт/четыре=4, "
        "бес/пять=5, алты/шесть=6, жеті/семь=7. "
        "Қазақша және орысша түсін. "
        f"Состояние: {state}. Язык: {lang}."
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
            "ip_credit": "1",
            "ip": "1",
            "too": "2",
            "personal": "3",
            "mortgage": "4",
            "damu": "5",
            "refinancing": "6",
        }
        return mapping.get(topic)
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
    raw = text.strip()
    cleaned = normalize_stt_borrower_answer(raw, session)

    if looks_like_credit_question(cleaned):
        return VoiceRoute(text=cleaned, source="raw", raw_transcript=raw)

    state = (session or {}).get("state", "idle")

    if state == "selecting_lang":
        lang_digit = parse_voice_lang_digit(cleaned)
        if lang_digit:
            return VoiceRoute(text=lang_digit, source="lang", raw_transcript=raw)

    digit = extract_spoken_digit(cleaned)
    if digit:
        return VoiceRoute(text=digit, source="digit", raw_transcript=raw)

    phrase_digit = map_menu_phrase(cleaned)
    if phrase_digit:
        return VoiceRoute(text=phrase_digit, source="phrase", raw_transcript=raw)

    intent_digit = map_intent_from_text(cleaned, session)
    if intent_digit:
        return VoiceRoute(text=intent_digit, source="intent", raw_transcript=raw)

    if len(cleaned) <= 3 and cleaned.isdigit():
        return VoiceRoute(text=cleaned, source="digit", raw_transcript=raw)

    return VoiceRoute(text=cleaned, source="raw", raw_transcript=raw)


async def prepare_voice_input(
    text: str,
    session: dict | None,
    settings: Optional["Settings"] = None,
) -> VoiceRoute:
    """STT → нормализация → меню/FAQ; при необходимости Groq только для cmd."""
    from app.config import get_settings

    settings = settings or get_settings()
    route = route_voice_text(text, session, settings)

    if route.source != "raw":
        return route

    # Groq-классификатор для коротких и средних фраз (до ~25 слов)
    word_count = len(route.text.split())
    if word_count <= 25:
        groq_cmd = await groq_classify_intent(route.text, session, settings)
        if groq_cmd:
            logger.info("Voice Groq intent: %r -> %r", route.text[:40], groq_cmd)
            return VoiceRoute(
                text=groq_cmd,
                source="groq_intent",
                raw_transcript=route.raw_transcript or text.strip(),
            )

    return route


def resolve_menu_digit_from_text(text: str, session: dict | None = None) -> str | None:
    """Цифра меню из текста: явная цифра, словесная, фраза или intent."""
    from app.bot.menu import MAIN_MENU_DIGIT_MAP

    t = text.strip()
    if t in MAIN_MENU_DIGIT_MAP:
        return t
    digit = extract_spoken_digit(t)
    if digit and digit in MAIN_MENU_DIGIT_MAP:
        return digit
    phrase = map_menu_phrase(t)
    if phrase and phrase in MAIN_MENU_DIGIT_MAP:
        return phrase
    intent_digit = map_intent_from_text(t, session)
    if intent_digit and intent_digit in MAIN_MENU_DIGIT_MAP:
        return intent_digit
    return None


async def try_dispatch_voice_menu(
    voice_cmd: str,
    session: dict,
    lang: str,
    send_fn: Callable,
    *,
    platform: str = "whatsapp",
    ai=None,
) -> bool:
    """
    Попытка ответить по голосовой команде: меню 1–7 или FAQ.
    send_fn — async (message: str) -> None.
    True — обработано, False — передать в общий обработчик.
    """
    from app.bot.content import WA_DIGIT_MAP
    from app.bot.faq_matcher import try_fast_response
    from app.bot.menu import menu_choice_body
    from app.bot.text_utils import strip_leading_greeting

    cmd = (voice_cmd or "").strip()
    if not cmd:
        return False

    digit = resolve_menu_digit_from_text(cmd, session)
    if digit and digit in WA_DIGIT_MAP and digit not in ("0", "98", "99"):
        mapped = WA_DIGIT_MAP.get(digit)
        if mapped and mapped != "operator":
            body = menu_choice_body(mapped, lang)
            if body:
                await send_fn(body)
                logger.info("Voice dispatch menu digit=%s mapped=%s", digit, mapped)
                return True

    core = strip_leading_greeting(cmd)
    fast = try_fast_response(
        core,
        lang,
        session.get("city"),
        platform,
        city_confirmed=session.get("city_confirmed", False),
        session=session,
    )
    if fast:
        await send_fn(fast)
        logger.info("Voice dispatch FAQ for: %s", core[:50])
        return True

    from app.bot.faq_guide import build_faq_guide_reply

    guide = await build_faq_guide_reply(core, lang, session, ai, platform=platform)
    if guide:
        await send_fn(guide)
        logger.info("Voice dispatch FAQ guide for: %s", core[:50])
        return True

    return False
