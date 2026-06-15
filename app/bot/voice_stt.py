"""
Голос → текст: Together Whisper (приоритет), ensemble Together+Groq, kk первым.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from app.ai_utils import detect_language_simple
from app.bot.lang_detect import detect_message_lang, has_kazakh_marker
from app.bot.kk_stt_lexicon import (
    build_kk_whisper_prompt,
    build_kk_whisper_prompt_for_duration,
    pick_stt_prompt_profile,
)
from app.bot.stt_normalize import normalize_stt_voice_text
from app.bot.stt_prompt_utils import GROQ_WHISPER_PROMPT_MAX_BYTES, truncate_whisper_prompt
from app.bot.stt_refine import refine_kk_transcript

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_MIN_GOOD_SCORE = 22
_HF_KK_BOOST = 28
_HF_TIMEOUT_SEC = 18.0
_TOGETHER_KK_BOOST = 20
_GROQ_KK_BOOST = 8


def _stt_prefer_kk(session: dict | None) -> bool:
    """Орысша STT только если пользователь явно выбрал ru (1/2 → 2)."""
    session = session or {}
    return not (session.get("lang_locked") and session.get("lang") == "ru")


def is_voice_stt_available(settings: "Settings") -> bool:
    return bool(
        settings.is_together_configured
        or settings.is_hf_stt_configured
        or settings.is_groq_configured
        or settings.local_whisper_url
        or settings.is_local_ai_configured
    )


def _score_transcript(
    text: str,
    lang_hint: str | None,
    *,
    prefer_kk: bool = True,
) -> int:
    t = text.strip()
    if len(t) < 2:
        return 0
    score = min(len(t) * 3, 120)
    low = t.lower()
    kk_chars = sum(1 for c in low if c in "әіңғүұқөһ")
    if kk_chars > 0:
        score += 28
    elif prefer_kk and lang_hint != "ru":
        score += 10
    if lang_hint == "kk" and kk_chars > 0:
        score += 20
    if lang_hint == "ru" and kk_chars == 0 and any(c in low for c in "аяуюы"):
        score += 10
    if prefer_kk and lang_hint == "ru" and kk_chars == 0:
        score -= 12
    fin_words = (
        "кредит", "несие", "ипотек", "даму", "ип", "тоо", "жк", "жеке",
        "рефинанс", "млн", "процент", "ставк", "пайыз", "кәсіп", "бизнес",
        "пәтер", "қайта", "менеджер", "оператор", "сәлем", "салам",
        "алғым", "келеді", "керек", "бересіз",
    )
    if any(w in low for w in fin_words):
        score += 18
    if len(t) <= 3 and not t.isdigit():
        score -= 12
    return score


def _pick_best_candidate(
    candidates: list[tuple[str, str | None, int]],
    lang_hint: str | None,
    *,
    prefer_kk: bool = True,
) -> tuple[str | None, str]:
    if not candidates:
        return None, lang_hint or "kk"
    best_score = max(c[2] for c in candidates)
    top = [c for c in candidates if c[2] >= best_score - 5]
    if prefer_kk and len(top) > 1:
        kk_top = [
            c for c in top
            if (c[1] or detect_language_simple(c[0])) == "kk"
            or any(ch in c[0].lower() for ch in "әіңғүұқөһ")
        ]
        if kk_top:
            top = kk_top
    best = max(top, key=lambda x: x[2])
    text, det, score = best
    detected = detect_message_lang(text)
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
    from app.together_client import get_together_client

    client = get_together_client(settings)
    text, err = await client.transcribe(
        audio_bytes, filename=filename, language=lang, prompt=prompt, temperature=0.0
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


async def _try_hf(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
) -> tuple[str | None, str | None]:
    if not settings.is_hf_stt_configured:
        return None, None
    from app.hf_stt_client import HuggingFaceSTTClient

    client = HuggingFaceSTTClient(
        settings.huggingface_api_key,
        model=settings.hf_stt_model or None,
    )
    text, err = await client.transcribe(
        audio_bytes, filename=filename, language=lang or "kk", prompt=prompt
    )
    if text:
        return text, lang or "kk"
    if err:
        logger.warning("HF STT lang=%s: %s", lang, err)
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
        logger.warning("Groq STT FAILED lang=%s: %s", lang, err)
    return None, None


async def _run_stt(
    fn,
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
    *,
    boost: int = 0,
    prefer_kk: bool,
    lang_hint: str | None,
) -> list[tuple[str, str | None, int]]:
    try:
        text, det = await fn(settings, audio_bytes, filename, lang, prompt)
        if text and text.strip():
            score = _score_transcript(text, lang or lang_hint, prefer_kk=prefer_kk) + boost
            logger.info("STT %s lang=%s score=%s text=%s", fn.__name__, lang, score, text[:50])
            return [(text.strip(), det, score)]
    except Exception:
        logger.exception("STT %s lang=%s exception", fn.__name__, lang)
    return []


async def _try_hf_bounded(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    lang: str | None,
    prompt: str,
    *,
    timeout: float = _HF_TIMEOUT_SEC,
) -> tuple[str | None, str | None]:
    if not settings.is_hf_stt_configured:
        return None, None
    try:
        return await asyncio.wait_for(
            _try_hf(settings, audio_bytes, filename, lang, prompt),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("HF STT timeout after %.0fs", timeout)
        return None, None


async def _collect_kk_ensemble(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    prompt: str,
    session: dict | None,
    *,
    duration_sec: float | None = None,
) -> list[tuple[str, str | None, int]]:
    """Together + Groq параллельно (kk), HF — только если пусто/слабо."""
    prefer_kk = True
    provider = (settings.voice_stt_provider or "ensemble").lower()
    use_together = settings.is_together_configured and provider in ("together", "ensemble")
    use_groq = settings.is_groq_configured and provider in ("groq", "ensemble")
    if settings.voice_stt_prefer_groq and provider != "together":
        use_groq = settings.is_groq_configured
        use_together = settings.is_together_configured and provider == "ensemble"

    nbytes = len(audio_bytes)
    profile = pick_stt_prompt_profile(duration_sec, nbytes)
    primary = build_kk_whisper_prompt_for_duration(
        session, duration_sec=duration_sec, audio_bytes=nbytes, variant=0,
    )
    logger.info(
        "STT prompt profile=%s dur=%s bytes=%s len=%s",
        profile,
        duration_sec,
        nbytes,
        len(primary),
    )

    tasks = []
    if use_together:
        tasks.append(
            _run_stt(
                _try_together, settings, audio_bytes, filename, "kk", primary,
                boost=_TOGETHER_KK_BOOST, prefer_kk=prefer_kk, lang_hint="kk",
            )
        )
        tasks.append(
            _run_stt(
                _try_together, settings, audio_bytes, filename, None, primary,
                boost=_TOGETHER_KK_BOOST - 4, prefer_kk=prefer_kk, lang_hint="kk",
            )
        )
    if use_groq:
        tasks.append(
            _run_stt(
                _try_groq, settings, audio_bytes, filename, "kk", primary,
                boost=_GROQ_KK_BOOST, prefer_kk=prefer_kk, lang_hint="kk",
            )
        )
    if not tasks and settings.local_whisper_url:
        tasks.append(
            _run_stt(
                _try_local_url, settings, audio_bytes, filename, "kk", prompt,
                boost=4, prefer_kk=prefer_kk, lang_hint="kk",
            )
        )

    out: list[tuple[str, str | None, int]] = []
    if tasks:
        chunks = await asyncio.gather(*tasks)
        for part in chunks:
            out.extend(part)

    best_score = max((c[2] for c in out), default=0)
    if best_score < _MIN_GOOD_SCORE and use_together:
        prompt_rich = build_kk_whisper_prompt(session, variant=1 if profile == "rich" else 0)
        extra, _ = await _try_together(
            settings, audio_bytes, filename, "kk", prompt_rich[:2200]
        )
        if extra and extra.strip():
            score = _score_transcript(extra, "kk", prefer_kk=True) + _TOGETHER_KK_BOOST
            out.append((extra.strip(), "kk", score))
            best_score = max(best_score, score)

    if best_score < _MIN_GOOD_SCORE:
        hf_part = await _run_stt(
            _try_hf_bounded,
            settings,
            audio_bytes,
            filename,
            "kk",
            primary,
            boost=_HF_KK_BOOST,
            prefer_kk=prefer_kk,
            lang_hint="kk",
        )
        out.extend(hf_part)

    return out


async def _collect_ru_stt(
    settings: "Settings",
    audio_bytes: bytes,
    filename: str,
    prompt: str,
) -> list[tuple[str, str | None, int]]:
    provider = (settings.voice_stt_provider or "ensemble").lower()
    if settings.is_together_configured and provider in ("together", "ensemble"):
        text, det = await _try_together(settings, audio_bytes, filename, "ru", prompt)
        if text:
            return [(text.strip(), det, _score_transcript(text, "ru", prefer_kk=False))]
    if settings.is_groq_configured:
        text, det = await _try_groq(settings, audio_bytes, filename, "ru", prompt)
        if text:
            return [(text.strip(), det, _score_transcript(text, "ru", prefer_kk=False))]
    return []


async def _finalize_transcript(
    text: str,
    detected: str,
    settings: "Settings",
    session: dict | None,
) -> tuple[str, str]:
    content_lang = detect_message_lang(text)
    refine_kk = content_lang == "kk" or has_kazakh_marker(text)
    if refine_kk and _stt_prefer_kk(session):
        text = await refine_kk_transcript(text, settings, session)
        text = normalize_stt_voice_text(text, session)
    else:
        text = normalize_stt_voice_text(text, session)
    final_lang = detect_message_lang(text)
    if session and session.get("lang_locked"):
        final_lang = session.get("lang", final_lang)
    return text, final_lang


async def transcribe_voice_message(
    audio_bytes: bytes,
    settings: "Settings",
    ai=None,
    *,
    lang_hint: str | None = None,
    filename: str = "voice.ogg",
    session: dict | None = None,
    duration_sec: float | None = None,
) -> tuple[str | None, str]:
    """
    STT: Together Whisper (kk) + Groq (резерв) → LLM refine → нормализация.
    Prompt подбирается по длительности аудио (compact / standard / rich).
    """
    if not audio_bytes:
        return None, lang_hint or "kk"

    nbytes = len(audio_bytes)
    prompt = build_kk_whisper_prompt_for_duration(
        session, duration_sec=duration_sec, audio_bytes=nbytes,
    )
    prefer_kk = _stt_prefer_kk(session)
    effective_hint = "ru" if not prefer_kk else "kk"

    candidates: list[tuple[str, str | None, int]] = []

    if prefer_kk:
        candidates = await _collect_kk_ensemble(
            settings,
            audio_bytes,
            filename,
            prompt,
            session,
            duration_sec=duration_sec,
        )
        best_score = max((c[2] for c in candidates), default=0)
        if best_score < _MIN_GOOD_SCORE and settings.is_together_configured:
            extra, _ = await _try_together(
                settings, audio_bytes, filename, "kk", prompt + " Несие алғым келеді."
            )
            if extra and extra.strip():
                score = _score_transcript(extra, "kk", prefer_kk=True) + _TOGETHER_KK_BOOST
                candidates.append((extra.strip(), "kk", score))
    else:
        candidates = await _collect_ru_stt(settings, audio_bytes, filename, prompt)

    if candidates:
        text, detected = _pick_best_candidate(
            candidates, effective_hint, prefer_kk=prefer_kk
        )
        if text:
            text, detected = await _finalize_transcript(text, detected, settings, session)
            logger.info("Voice STT SUCCESS provider=ensemble lang=%s text=%s", detected, text[:50])
            return text, detected

    stt_lang_order = ("kk", "ru", None) if prefer_kk else ("ru", "kk", None)
    for lang in stt_lang_order:
        for try_fn in (_try_hf, _try_together, _try_groq, _try_local_url):
            try:
                text, det = await try_fn(settings, audio_bytes, filename, lang, prompt)
                if text and text.strip():
                    text, detected = await _finalize_transcript(
                        text.strip(), det or lang_hint or "kk", settings, session
                    )
                    logger.info("Voice STT fallback %s lang=%s", try_fn.__name__, lang)
                    return text, detected
            except Exception:
                logger.exception("STT fallback %s lang=%s FAILED", try_fn.__name__, lang)

    # Последний шанс: короткий prompt (Groq лимит — 896 UTF-8 байт)
    short_prompt = truncate_whisper_prompt(
        "KOMEK DAMU. Несие, кредит, ипотека, DAMU. "
        "Сәлеметсіз бе, мен несие алғым келеді.",
        GROQ_WHISPER_PROMPT_MAX_BYTES,
    )
    for lang in stt_lang_order:
        for try_fn in (_try_groq, _try_together):
            try:
                text, det = await try_fn(
                    settings, audio_bytes, filename, lang, short_prompt
                )
                if text and text.strip():
                    text, detected = await _finalize_transcript(
                        text.strip(), det or lang_hint or "kk", settings, session
                    )
                    logger.info("Voice STT short-prompt fallback %s lang=%s", try_fn.__name__, lang)
                    return text, detected
            except Exception:
                logger.exception("STT short-prompt fallback %s failed", try_fn.__name__)

    logger.warning("Voice STT: all providers failed")
    return None, lang_hint or "kk"
