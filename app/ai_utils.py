"""Shared helpers for AI clients."""

from __future__ import annotations


def detect_language_simple(text: str) -> str:
    """Heuristic: Kazakh (kk) vs Russian (ru)."""
    kazakh_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
    text_sample = text[:200]

    for char in kazakh_chars:
        if char in text_sample:
            return "kk"

    kazakh_words = ["сіз", "мен", "біз", "немесе", "және", "болды", "қазақстан", "қазақ"]
    text_lower = text.lower()
    if sum(1 for w in kazakh_words if w in text_lower) >= 2:
        return "kk"

    return "ru"
