"""Shared helpers for AI clients."""

from __future__ import annotations


def detect_language_simple(text: str) -> str:
    """Heuristic: Kazakh (kk) vs Russian (ru)."""
    from app.bot.lang_detect import detect_message_lang

    return detect_message_lang(text)
