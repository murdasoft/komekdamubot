"""Whisper prompt limits (Groq counts UTF-8 bytes, not Unicode chars)."""

from __future__ import annotations

# Groq Whisper: max 896 (API measures UTF-8 bytes for Kazakh/Cyrillic text)
GROQ_WHISPER_PROMPT_MAX_BYTES = 896

# Together / OpenAI-compatible — char cap in existing client
TOGETHER_WHISPER_PROMPT_MAX_CHARS = 2200


def truncate_whisper_prompt(text: str, max_bytes: int = GROQ_WHISPER_PROMPT_MAX_BYTES) -> str:
    """Trim prompt without breaking UTF-8 multibyte sequences."""
    if not text or max_bytes <= 0:
        return text
    raw = text.strip()
    encoded = raw.encode("utf-8")
    if len(encoded) <= max_bytes:
        return raw
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
