"""LLM-постобработка казахского STT (Together)."""

from __future__ import annotations

import logging
import re

from app.bot.lang_detect import detect_message_lang, has_kazakh_marker

logger = logging.getLogger(__name__)

_REFINE_LEAK_MARKERS = (
    "кіріс:", "шығыс:", "stt транскрипт", "түзетілген", "ereje:", "whisper",
    "сен komek", "түзетуші",
)

_REFINE_SYSTEM_KK = (
    "Сен KOMEK DAMU үшін қазақша STT түзетушісісің. "
    "Кіріс — Whisper транскрипті, шығыс — ТЕК түзетілген қазақша мәтін, басқа ештеңе жоқ.\n"
    "Ереже:\n"
    "1) Мәнін өзгертпе, тек қате сөздерді түзет (мысалы: менінше→мен несие).\n"
    "2) Несие, кредит, ипотека, ЖК, ТОО, DAMU, пайыз — дұрыс жаз.\n"
    "3) Орысшаға аударма. Егер кіріс қазақша болса — қазақша қалдыр.\n"
    "4) Егер кіріс тек орысша және нақты қазақша емес — солай қайтар.\n"
    "5) Тыныс белгілерін қой, әріптерді қазақша нормаға келтір (ә, і, ң, ғ, ү, ұ, қ, ө, һ)."
)


async def refine_kk_transcript(
    raw: str,
    settings,
    session: dict | None = None,
) -> str:
    """Together LLM: поправить казахский транскрипт."""
    if not raw or not raw.strip():
        return raw
    if not getattr(settings, "stt_llm_refine_enabled", True):
        return raw
    if not settings.is_together_configured:
        return raw

    session = session or {}
    if session.get("lang_locked") and session.get("lang") == "ru":
        return raw
    if detect_message_lang(raw) == "ru" and not has_kazakh_marker(raw):
        return raw

    from app.together_client import get_together_client

    client = get_together_client(settings)
    user = f"STT транскрипт:\n{raw.strip()}"
    messages = [
        {"role": "system", "content": _REFINE_SYSTEM_KK},
        {"role": "user", "content": user},
    ]
    try:
        fixed, err = await client.chat(messages, temperature=0.05, max_tokens=220)
        if err or not fixed:
            logger.warning("STT LLM refine skipped: %s", err)
            return raw
        out = fixed.strip().strip('"').strip("'")
        out = re.sub(r"^(түзетілген|исправлено|corrected):\s*", "", out, flags=re.I)
        low_out = out.lower()
        if any(m in low_out for m in _REFINE_LEAK_MARKERS):
            logger.warning("STT LLM refine leak detected, using raw")
            return raw
        if len(out) < 2:
            return raw
        if len(out) > len(raw) * 2 or len(out) > 500:
            return raw
        from app.bot.formatting import strip_foreign_scripts

        lang = (session or {}).get("lang", "kk")
        out = strip_foreign_scripts(out, lang)
        logger.info("STT LLM refine: %r -> %r", raw[:50], out[:50])
        return out
    except Exception:
        logger.exception("STT LLM refine failed")
        return raw
