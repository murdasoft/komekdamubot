"""Постобработка ответов бота."""

from __future__ import annotations

import re

from app.offices import detect_city, get_contact_footer, resolve_city

_UNCERTAIN_MARKERS = (
    "не знаю", "не уверен", "уточните", "уточнить", "подробнее",
    "менеджер", "білмеймін", "нақтылаңыз",
)


def finalize_bot_response(
    text: str,
    user_message: str,
    lang: str,
    session_city: str | None,
    platform: str = "telegram",
) -> str:
    """Короткий ответ + контакты при неуверенности."""
    if not text:
        return text

    clean = text.replace("[NOTIFY_MANAGER]", "").replace("[DONE]", "").strip()
    city = resolve_city(user_message, session_city) or detect_city(clean)

    lower = clean.lower()
    needs_contacts = (
        "[NOTIFY_MANAGER]" in text
        or any(m in lower for m in _UNCERTAIN_MARKERS)
        or "?" in clean[-80:]
        and len(clean) < 120
    )

    # Уже есть телефон 8 7xx
    if re.search(r"8\s*7\d{2}", clean):
        if "[DONE]" not in text:
            clean += " [DONE]"
        return clean.replace("  [DONE]", " [DONE]")

    if needs_contacts:
        footer = get_contact_footer(
            city, lang, all_cities=not bool(city), platform=platform  # type: ignore[arg-type]
        )
        clean = f"{clean}\n\n{footer}"

    notify = "[NOTIFY_MANAGER]" in text
    # Не обрезаем ответ, если уже есть контакты нескольких городов
    if clean.count("📍") < 3:
        lines = [ln.strip() for ln in clean.split("\n") if ln.strip()]
        if len(lines) > 8:
            clean = "\n".join(lines[:8]) + "\n…"

    out = clean
    if notify:
        out += " [NOTIFY_MANAGER]"
    out += " [DONE]"
    return out
