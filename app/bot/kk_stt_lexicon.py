"""Казахский лексикон для Whisper prompt (из корпусов + kazakh_dict)."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.bot.kazakh_phrases import KK_PHRASES_EXTENDED
from app.bot.stt_normalize import stt_prompt_for_session
from app.bot.stt_prompt_utils import GROQ_WHISPER_PROMPT_MAX_BYTES, truncate_whisper_prompt
from app.kk_corpus_loader import get_phrases_top10k, get_stt_vocab

logger = logging.getLogger(__name__)

_DOMAIN_CORE = (
    "KOMEK DAMU қазақстандық қаржы боты. Тіл: қазақша. "
    "Несие, кредит, ипотека, DAMU 12,6%, рефинансирование. "
    "ЖК, ТОО, жеке тұлға, кәсіпкер. Алматы, Астана, Шымкент, Ақтау. "
    "пайыз, млн, тенге, зейнетақы, кешігу, жүктеме. "
    "Сандар: бір=1, екі=2, үш=3, төрт=4, бес=5, алты=6, жеті=7."
)


def _load_vocab() -> dict:
    data = get_stt_vocab()
    if not data:
        logger.warning("kk_stt_vocab missing — run scripts/build_kk_stt_vocab.py + upload_kk_corpus_blob.py")
    return data


def _load_top_phrases() -> dict:
    return get_phrases_top10k()


def get_finance_words(limit: int = 200) -> list[str]:
    data = _load_vocab()
    words = data.get("finance_words") or []
    return list(words)[:limit]


def get_corpus_phrases(limit: int = 40, *, finance_only: bool = False) -> list[str]:
    top = _load_top_phrases()
    if top.get("phrases"):
        items = top["phrases"]
        if finance_only:
            items = [p for p in items if p.get("finance")]
        phrases = [p["text"] if isinstance(p, dict) else str(p) for p in items]
    else:
        data = _load_vocab()
        phrases = list(data.get("phrases") or [])

    for p in KK_PHRASES_EXTENDED:
        if p not in phrases:
            phrases.append(p)
        if len(phrases) >= limit * 3:
            break
    return phrases[:limit]


def get_prompt_chunk(index: int = 0) -> str:
    """Ротация словарных чанков для ensemble STT."""
    data = _load_vocab()
    chunks = data.get("prompt_chunks") or []
    if not chunks:
        return ", ".join(get_finance_words(80))
    return chunks[index % len(chunks)]


def get_phrase_chunk(index: int = 0) -> str:
    data = _load_vocab()
    chunks = data.get("top_phrase_chunks") or data.get("phrase_chunks") or []
    if not chunks:
        top = _load_top_phrases()
        chunks = top.get("phrase_chunks") or []
    if not chunks:
        return "; ".join(get_corpus_phrases(25))
    return chunks[index % len(chunks)]


def build_kk_whisper_prompt(session: dict | None = None, *, variant: int = 0) -> str:
    """Полный prompt (~1500–2200) — длинные голосовые 15 с+."""
    parts = [
        _DOMAIN_CORE,
        f"Сөздер: {get_prompt_chunk(variant)}.",
        f"Фразалар: {get_phrase_chunk(variant)}.",
        f"Тағы: {get_phrase_chunk(variant + 1)}.",
        "Мысал: Сәлеметсіз бе, мен несие алғым келеді. Ипотека керек, қанша пайыз?",
    ]
    extra = stt_prompt_for_session(session)
    if extra:
        parts.append(extra)
    return " ".join(parts)[:2200]


@lru_cache(maxsize=1)
def _compact_prompt_base() -> str:
    words = ", ".join(get_finance_words(45))
    phrases = "; ".join(get_corpus_phrases(12, finance_only=True) or get_corpus_phrases(12))
    return truncate_whisper_prompt(
        " ".join(
            [
                _DOMAIN_CORE,
                f"Сөздер: {words}.",
                f"Мысалдар: {phrases}.",
                "Сәлеметсіз бе, мен несие алғым келеді. Несие керек па.",
            ]
        ),
        GROQ_WHISPER_PROMPT_MAX_BYTES,
    )


def build_kk_whisper_prompt_compact(session: dict | None = None) -> str:
    """Короткий prompt (~720) — команды и фразы до ~4 с."""
    parts = [_compact_prompt_base()]
    extra = stt_prompt_for_session(session)
    if extra:
        parts.append(extra)
    return truncate_whisper_prompt(" ".join(parts), GROQ_WHISPER_PROMPT_MAX_BYTES)


@lru_cache(maxsize=2)
def _standard_prompt_base(variant: int = 0) -> str:
    words = ", ".join(get_finance_words(55))
    phrases = "; ".join(get_corpus_phrases(16, finance_only=True) or get_corpus_phrases(16))
    return " ".join(
        [
            _DOMAIN_CORE,
            f"Сөздер: {words}.",
            f"Фразалар: {phrases}.",
            "Мысал: Сәлеметсіз бе, мен несие алғым келеді. Қанша пайызбен бересіз?",
        ]
    )


def build_kk_whisper_prompt_standard(
    session: dict | None = None,
    *,
    variant: int = 0,
) -> str:
    """Средний prompt (~1200) — типичные вопросы 4–15 с."""
    parts = [_standard_prompt_base(variant)]
    extra = stt_prompt_for_session(session)
    if extra:
        parts.append(extra)
    return truncate_whisper_prompt(" ".join(parts), GROQ_WHISPER_PROMPT_MAX_BYTES)


def estimate_audio_duration_sec(
    duration_sec: float | None,
    audio_bytes: int = 0,
) -> float:
    """Telegram duration или оценка по размеру opus (~24 kbps)."""
    if duration_sec is not None and duration_sec > 0:
        return float(duration_sec)
    if audio_bytes > 500:
        return max(1.0, audio_bytes / 3000.0)
    return 6.0


def pick_stt_prompt_profile(
    duration_sec: float | None,
    audio_bytes: int = 0,
) -> str:
    """
    compact  — до ~4 с (короткая команда)
    standard — ~4–15 с (обычный вопрос)
    rich     — 15 с+ (развёрнутый рассказ)
    """
    sec = estimate_audio_duration_sec(duration_sec, audio_bytes)
    if sec < 4.0:
        return "compact"
    if sec < 15.0:
        return "standard"
    return "rich"


def build_kk_whisper_prompt_for_duration(
    session: dict | None = None,
    *,
    duration_sec: float | None = None,
    audio_bytes: int = 0,
    variant: int = 0,
) -> str:
    """Whisper prompt под длину голосового."""
    profile = pick_stt_prompt_profile(duration_sec, audio_bytes)
    if profile == "compact":
        return build_kk_whisper_prompt_compact(session)
    if profile == "standard":
        return build_kk_whisper_prompt_standard(session, variant=variant)
    return build_kk_whisper_prompt(session, variant=variant)
