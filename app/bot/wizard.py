"""
Пошаговый мастер: 1 — язык, 2 — город, 3+ — продуктовое меню (в основном WhatsApp цифрами).
"""

from __future__ import annotations

from app.bot.formatting import CITY_OFFICES, format_office_city

# 1 Алматы, 2 Астана, 3 Шымкент, 4 Атырау, 5 Актау
CITY_DIGIT_MAP: dict[str, str] = {
    "1": "almaty",
    "2": "astana",
    "3": "shymkent",
    "4": "atyrau",
    "5": "aktau",
}

CITY_DIGIT_ORDER = ("almaty", "astana", "shymkent", "atyrau", "aktau")


def resolve_city_digit(digit: str) -> str | None:
    return CITY_DIGIT_MAP.get(digit.strip())


def get_lang_step_text() -> str:
    return (
        "👋 *KOMEK DAMU*\n\n"
        "🌐 *Шаг 1 — язык / Тіл:*\n\n"
        "1 — Қазақша\n"
        "2 — Русский\n\n"
        "Напишите *1* или *2*"
    )


def get_city_step_text(lang: str) -> str:
    lines = ["📍 *Шаг 2 — город / қала:*\n"]
    for i, key in enumerate(CITY_DIGIT_ORDER, start=1):
        o = CITY_OFFICES[key]
        name = o["name_kk"] if lang == "kk" else o["name_ru"]
        lines.append(f"{i} — {name}")
    lines.append("\nНапишите цифру *1–5*")
    if lang == "kk":
        lines[-1] = "\n*1–5* санын жазыңыз"
    return "\n".join(lines)


def get_city_step_help(lang: str) -> str:
    """0 на шаге города — не зацикливать, объяснить что дальше будет меню 1–7."""
    if lang == "kk":
        return (
            "📍 *Алдымен қалады таңдаңыз (2-қадам)*\n\n"
            "Содан кейін негізгі мәзір *1–7* ашылады.\n\n"
            f"{get_city_step_text(lang)}"
        )
    return (
        "📍 *Сначала выберите город (шаг 2)*\n\n"
        "После этого откроется главное меню разделов *1–7*.\n\n"
        f"{get_city_step_text(lang)}"
    )


def get_city_invalid_reply(lang: str) -> str:
    """Непонятный ввод на шаге города — универсальный ответ (офисы + 7), не «только 99»."""
    from app.bot.city_routing import get_universal_fallback_reply

    return get_universal_fallback_reply(lang, platform="whatsapp")


def get_welcome_with_menu(lang: str, city: str, platform: str = "whatsapp") -> str:
    """После выбора города — офис + меню продуктов."""
    from app.bot.menu import get_main_menu_text

    greet = "Сәлеметсіз бе!" if lang == "kk" else "Здравствуйте!"
    office = format_office_city(city, lang, platform)  # type: ignore[arg-type]
    pick = (
        "👇 *Шаг 3 — бөлімді таңдаңыз (1–7):*"
        if lang == "kk"
        else "👇 *Шаг 3 — выберите раздел (1–7):*"
    )
    return f"{greet}\n\n{office}\n\n{pick}\n\n{get_main_menu_text(lang)}"
