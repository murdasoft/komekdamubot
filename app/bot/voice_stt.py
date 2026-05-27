"""
Голос → текст: Groq Whisper (основной), faster-whisper (VPS), Together (legacy).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from app.ai_utils import detect_language_simple
from app.bot.stt_normalize import stt_prompt_for_session

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

DOMAIN_STT_PROMPT = (
    "KOMEK DAMU. Кредит, ипотека, DAMU 12,6, несие, рефинансирование. "
    "ИП, ЖК, ТОО, жеке тұлға, физлицо. "
    "Алматы, Астана, Шымкент, Атырау, Актау. "
    "Қазақша, орысша, процент, млн."
)


def is_voice_stt_available(settings: "Settings") -> bool:
    if settings.is_groq_configured:
        return True
    if settings.local_whisper_url:
        return True
    if settings.is_together_configured:
        return True
    return settings.is_local_ai_configured


def _score_transcript(text: str, lang_hint: str | None) -> int:
    t = text.strip()
    if len(t) < 2:
        return 0
    score = min(len(t) * 3, 120)
    kk = sum(1 for c in t.lower() if c in "әіңғүұқөһ")
    if lang_hint == "kk" and kk > 0:
        score += 15
    if lang_hint == "ru" and kk == 0 and any(c in t.lower() for c in "аяуюы"):
        score += 10
    if any(w in t.lower() for w in ("кредит", "несие", "ипотек", "даму", "ип", "тоо", "жк")):
        score += 12
    return score


async def _try_together(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
) -> tuple[str | None, str | None]:
    if not settings.is_together_configured:
        return None, None
    from app.together_client import TogetherClient

    client = TogetherClient(
        settings.together_api_key,
        model=settings.together_model,
        stt_model=settings.together_stt_model,
    )
    text, err = await client.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt
    )
    if text:
        return text, lang or detect_language_simple(text)
    if err:
        logger.warning("Together STT lang=%s: %s", lang, err)
    return None, None


async def _try_local_url(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
) -> tuple[str | None, str | None]:
    if not settings.local_whisper_url:
        return None, None
    from app.local_ai_client import LocalAIClient

    client = LocalAIClient(
        llm_base_url=settings.local_llm_base_url or "http://127.0.0.1:11434",
        llm_model=settings.local_llm_model,
        whisper_url=settings.local_whisper_url,
    )
    text, err = await client.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt
    )
    if text:
        return text, lang or detect_language_simple(text)
    if err:
        logger.warning("Local Whisper URL lang=%s: %s", lang, err)
    return None, None


async def _try_ai_client(
    ai,
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
) -> tuple[str | None, str | None]:
    if not ai or not hasattr(ai, "transcribe"):
        return None, None
    text, err = await ai.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt
    )
    if text:
        detected = lang or ai.detect_language_simple(text)
        return text, detected
    return None, None


async def _try_groq(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
) -> tuple[str | None, str | None]:
    if not settings.is_groq_configured:
        return None, None
    from app.groq_client import GroqClient

    groq = GroqClient(
        settings.groq_api_key,
        model=settings.groq_model,
        stt_model=settings.groq_stt_model,
    )
    text, err = await groq.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt
    )
    if text:
        return text, lang or groq.detect_language_simple(text)
    if err:
        logger.warning("Groq STT lang=%s: %s", lang, err)
    return None, None


async def transcribe_voice_message(
    audio_bytes: bytes,
    settings: "Settings",
    ai=None,
    *,
    lang_hint: str | None = None,
    filename: str = "voice.ogg",
    session: dict | None = None,
) -> tuple[str | None, str]:
    """
    Быстрый STT: Groq (1-2 попытки) → Together fallback.
    Макс 3 HTTP-запроса чтобы влезть в Vercel 60-сек лимит.
    """
    if not audio_bytes:
        return None, lang_hint or "kk"

    base_prompt = DOMAIN_STT_PROMPT
    extra = stt_prompt_for_session(session)
    prompt = f"{base_prompt} {extra}" if extra else base_prompt

    # Попытка 1: Groq с автоопределением языка (None = auto)
    if settings.is_groq_configured:
        text, det = await _try_groq(settings, audio_bytes, filename, None, prompt)
        if text and text.strip():
            detected = det or detect_language_simple(text)
            logger.info("Voice STT Groq auto lang=%s text=%s", detected, text[:50])
            return text.strip(), detected

    # Попытка 2: Groq с подсказкой языка
    if settings.is_groq_configured and lang_hint:
        text, det = await _try_groq(settings, audio_bytes, filename, lang_hint, prompt)
        if text and text.strip():
            detected = det or lang_hint
            logger.info("Voice STT Groq hint=%s text=%s", detected, text[:50])
            return text.strip(), detected

    # Попытка 3: Together fallback
    if settings.is_together_configured:
        text, det = await _try_together(settings, audio_bytes, filename, lang_hint, prompt)
        if text and text.strip():
            detected = det or lang_hint or detect_language_simple(text)
            logger.info("Voice STT Together lang=%s text=%s", detected, text[:50])
            return text.strip(), detected

    logger.warning("Voice STT: all providers failed")
    return None, lang_hint or "kk"
