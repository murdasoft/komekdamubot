"""Fix common STT confusions for short voice answers (ИП vs ипотека)."""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)

_BORROWER_CLARIFY_MARKERS = (
    "кто вы",
    "физлицо",
    "кимсіз",
    "сіз кімсіз",
    "жеке тұлға",
    "жк (ип)",
    "уточните",
    "сонда нақты",
)

_MORTGAGE_CONTEXT = frozenset({
    "квартира",
    "пәтер",
    "жилье",
    "үй",
    "дом",
    "госпрограмм",
    "гос",
    "первичк",
    "вторичк",
    "ставк",
    "процент",
    "млн",
    "кредит",
    "несие",
    "хочу",
    "нужна",
    "нужен",
    "интерес",
    "можно",
    "взять",
    "алу",
    "керек",
    "бересіз",
    "онлайн",
})


def is_borrower_clarify_message(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _BORROWER_CLARIFY_MARKERS)


def session_awaits_borrower_type(session: dict | None) -> bool:
    if not session:
        return False
    if session.get("awaiting_borrower_type"):
        return True
    if session.get("state") == "in_flow" and session.get("flow_step") == "client_type":
        return True
    for msg in reversed(session.get("conversation_history") or []):
        if msg.get("role") != "assistant":
            continue
        if is_borrower_clarify_message(msg.get("text") or ""):
            return True
        break
    return False


def looks_like_misheard_ip(text: str, *, borrower_context: bool = False) -> bool:
    """
    Whisper often returns «ипотека» for a short spoken «ИП».
    Without borrower context, lone «ипотека» stays a mortgage request.
    """
    norm = text.strip().lower()
    if not norm:
        return False

    words = set(_WORD.findall(norm))
    if words & _MORTGAGE_CONTEXT:
        return False
    if words & {"ип", "жк", "жс", "тоо", "төо", "tovo", "too"}:
        return False

    if re.fullmatch(r"и[\s.\-]*п\.?", norm, re.IGNORECASE):
        return True
    if norm in {"и п", "и.п.", "и.п", "ип.", "ip", "и п."}:
        return True

    if words <= frozenset({"ипотека", "ипотек", "ипотеку", "ипотеки", "ипотекой"}):
        return borrower_context

    if len(norm) <= 8 and len(words) == 1 and norm.startswith("ипотек"):
        return borrower_context

    return False


# Типичные ошибки Whisper на қазақша
_STT_KK_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bменінше\b", re.I), "мен несие"),
    (re.compile(r"\bменше\b", re.I), "мен несие"),
    (re.compile(r"\bменесие\b", re.I), "мен несие"),
    (re.compile(r"\bменеси\b", re.I), "мен несие"),
    (re.compile(r"\bнеси\b", re.I), "несие"),
    (re.compile(r"\bнисие\b", re.I), "несие"),
    (re.compile(r"\bнесиe\b", re.I), "несие"),
    (re.compile(r"\bсалеметсиз\b", re.I), "сәлеметсіз"),
    (re.compile(r"\bсалем\b", re.I), "сәлем"),
    (re.compile(r"\bкасипкер\b", re.I), "кәсіпкер"),
    (re.compile(r"\bкасип\b", re.I), "кәсіп"),
    (re.compile(r"\bалгым\b", re.I), "алғым"),
    (re.compile(r"\bкерек па\b", re.I), "керек па"),
    (re.compile(r"\bалгым келеди\b", re.I), "алғым келеді"),
    (re.compile(r"\bалгым келеді\b", re.I), "алғым келеді"),
)


def normalize_stt_voice_text(text: str, session: dict | None = None) -> str:
    """Поправки STT перед маршрутизацией (голос ≈ текст)."""
    if not text or not text.strip():
        return text
    t = text.strip()
    for pattern, repl in _STT_KK_REWRITES:
        t = pattern.sub(repl, t)
    from app.bot.formatting import strip_foreign_scripts

    lang = (session or {}).get("lang", "kk")
    t = strip_foreign_scripts(t, lang)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_stt_borrower_answer(text: str, session: dict | None = None) -> str:
    """Rewrite misheard entity answers before intent matching."""
    if not text or not text.strip():
        return text
    text = normalize_stt_voice_text(text, session)
    borrower_context = session_awaits_borrower_type(session)
    if looks_like_misheard_ip(text, borrower_context=borrower_context):
        logger.info("STT entity fix: %r -> ИП (borrower_context=%s)", text[:40], borrower_context)
        return "ИП"
    return text.strip()


def stt_prompt_for_session(session: dict | None) -> Optional[str]:
    if session_awaits_borrower_type(session):
        return "ИП, ЖК, ТОО, физлицо, жеке тұлға, кәсіпкер, индивидуальный предприниматель"
    return None
