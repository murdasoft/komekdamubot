"""Постобработка ответов бота."""

from __future__ import annotations

import re

from app.offices import detect_city, get_contact_footer, city_for_contacts
from app.bot.formatting import has_city_question, has_contact_block

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
    *,
    city_confirmed: bool = False,
) -> str:
    """Короткий ответ + контакты при неуверенности."""
    if not text:
        return text

    clean = text.replace("[NOTIFY_MANAGER]", "").replace("[DONE]", "").strip()
    city = city_for_contacts(user_message, session_city, city_confirmed=city_confirmed)

    lower = clean.lower()
    needs_contacts = (
        "[NOTIFY_MANAGER]" in text
        or any(m in lower for m in _UNCERTAIN_MARKERS)
    ) and not has_contact_block(clean)

    if has_contact_block(clean):
        if "[DONE]" not in text:
            clean += " [DONE]"
        return clean.replace("  [DONE]", " [DONE]")

    if needs_contacts:
        footer = get_contact_footer(
            city, lang, all_cities=not bool(city), platform=platform  # type: ignore[arg-type]
        )
        if has_city_question(clean) and "📍" in footer:
            # Уже спросили город — только список офисов без повторного вопроса
            from app.bot.formatting import format_offices_block, WORK_HOURS_RU, WORK_HOURS_KK

            footer = format_offices_block(
                lang, platform=platform, with_header=False  # type: ignore[arg-type]
            )
            footer += "\n\n" + (WORK_HOURS_KK if lang == "kk" else WORK_HOURS_RU)
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
