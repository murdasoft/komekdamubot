"""
Голос → текст: Groq Whisper (основной), faster-whisper (VPS), Together (legacy).
Пробуем ru + kk и выбираем лучший транскрипт по score.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from app.ai_utils import detect_language_simple
from app.bot.stt_normalize import stt_prompt_for_session

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

# Финансовый словарь для Whisper prompt (ru + kk)
DOMAIN_STT_PROMPT = (
    "KOMEK DAMU. Кредит, ипотека, DAMU 12,6, несие, рефинансирование. "
    "ИП, ЖК, ТОО, жеке тұлға, физлицо, кәсіпкер, индивидуальный предприниматель. "
    "Алматы, Астана, Шымкент, Актау, Атырау, Қарағанды. "
    "Қазақша, орысша, процент, пайыз, ставка, млн, миллион, тенге, сома. "
    "пенсия, зейнет, нагрузка, жүктеме, просрочка, кешігу, скоринг. "
    "онлайн, гарантия, менеджер, оператор, мәзір, меню. "
    "Цифры: бір/один=1, екі/два=2, үш/три=3, төрт/четыре=4, "
    "бес/пять=5, алты/шесть=6, жеті/семь=7."
)

_MIN_GOOD_SCORE = 32


def is_voice_stt_available(settings: "Settings") -> bool:
    return bool(
        settings.is_groq_configured
        or settings.local_whisper_url
        or settings.is_together_configured
        or settings.is_local_ai_configured
    )


def _score_transcript(text: str, lang_hint: str | None) -> int:
    t = text.strip()
    if len(t) < 2:
        return 0
    score = min(len(t) * 3, 120)
    low = t.lower()
    kk_chars = sum(1 for c in low if c in "әіңғүұқөһ")
    if lang_hint == "kk" and kk_chars > 0:
        score += 18
    if lang_hint == "ru" and kk_chars == 0 and any(c in low for c in "аяуюы"):
        score += 12
    fin_words = (
        "кредит", "несие", "ипотек", "даму", "ип", "тоо", "жк", "жеке",
        "рефинанс", "млн", "процент", "ставк", "пайыз", "кәсіп", "бизнес",
        "пәтер", "қайта", "менеджер", "оператор", "салам", "сәлем",
    )
    if any(w in low for w in fin_words):
        score += 15
    # Штраф за явный мусор STT
    if len(t) <= 3 and not t.isdigit():
        score -= 10
    return score


def _pick_best_candidate(
    candidates: list[tuple[str, str | None, int]],
    lang_hint: str | None,
) -> tuple[str | None, str]:
    if not candidates:
        return None, lang_hint or "kk"
    best = max(candidates, key=lambda x: x[2])
    text, det, score = best
    detected = det or detect_language_simple(text)
    logger.info(
        "STT best of %s candidates: score=%s lang=%s text=%s",
        len(candidates),
        score,
        detected,
        text[:60],
    )
    return text.strip(), detected


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
    logger.info("Groq STT API call: lang=%s model=%s bytes=%s", lang, settings.groq_stt_model, len(audio_bytes))
    text, err = await groq.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt
    )
    if text:
        return text, lang or groq.detect_language_simple(text)
    if err:
        logger.warning("Groq STT FAILED lang=%s: %s", lang, err)
    return None, None


async def _groq_candidates(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    prompt: str,
    lang_hint: str | None,
) -> list[tuple[str, str | None, int]]:
    """До 3 попыток Groq: auto → hint → ru+kk параллельно при слабом результате."""
    candidates: list[tuple[str, str | None, int]] = []
    tried_langs: set[str | None] = set()

    async def _add(lang: str | None) -> None:
        if lang in tried_langs:
            return
        tried_langs.add(lang)
        try:
            text, det = await _try_groq(settings, audio_bytes, filename, lang, prompt)
            if text and text.strip():
                score = _score_transcript(text, lang or lang_hint)
                candidates.append((text.strip(), det, score))
                logger.info("STT Groq lang=%s score=%s text=%s", lang, score, text[:50])
        except Exception:
            logger.exception("STT Groq lang=%s exception", lang)

    await _add(None)
    best_score = max((c[2] for c in candidates), default=0)
    if best_score >= _MIN_GOOD_SCORE:
        return candidates

    if lang_hint in ("ru", "kk"):
        await _add(lang_hint)
        best_score = max((c[2] for c in candidates), default=0)
        if best_score >= _MIN_GOOD_SCORE:
            return candidates

    # Параллельно ru + kk — выбираем лучший по score
    other_langs = [l for l in ("ru", "kk") if l not in tried_langs]
    if other_langs:
        await asyncio.gather(*[_add(l) for l in other_langs])

    return candidates


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
    STT: Groq (auto + ru + kk с выбором лучшего) → Local Whisper → Together.
    """
    if not audio_bytes:
        return None, lang_hint or "kk"

    base_prompt = DOMAIN_STT_PROMPT
    extra = stt_prompt_for_session(session)
    prompt = f"{base_prompt} {extra}" if extra else base_prompt

    if settings.is_groq_configured:
        try:
            candidates = await _groq_candidates(
                settings, audio_bytes, filename, prompt, lang_hint
            )
            text, detected = _pick_best_candidate(candidates, lang_hint)
            if text:
                logger.info("Voice STT Groq SUCCESS lang=%s text=%s", detected, text[:50])
                return text, detected
            logger.warning("STT Groq: all attempts weak or empty")
        except Exception:
            logger.exception("STT Groq pipeline FAILED, trying next provider")

    if settings.local_whisper_url:
        for lang in (lang_hint, "kk", "ru", None):
            try:
                text, det = await _try_local_url(
                    settings, audio_bytes, filename, lang, prompt
                )
                if text and text.strip():
                    detected = det or lang_hint or detect_language_simple(text)
                    logger.info("Voice STT Local Whisper SUCCESS lang=%s", detected)
                    return text.strip(), detected
            except Exception:
                logger.exception("STT Local Whisper lang=%s FAILED", lang)

    if settings.is_together_configured:
        for lang in (lang_hint, "kk", "ru", None):
            try:
                text, det = await _try_together(
                    settings, audio_bytes, filename, lang, prompt
                )
                if text and text.strip():
                    detected = det or lang_hint or detect_language_simple(text)
                    logger.info("Voice STT Together SUCCESS lang=%s", detected)
                    return text.strip(), detected
            except Exception:
                logger.exception("STT Together lang=%s FAILED", lang)

    logger.warning("Voice STT: all providers failed")
    return None, lang_hint or "kk"
