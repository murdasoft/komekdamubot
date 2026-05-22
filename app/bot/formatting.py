"""
Форматирование ответов для Telegram и WhatsApp.
Телефоны и адреса — в моноширинном виде (удобно копировать долгим нажатием).
"""

from __future__ import annotations

import re
from typing import Literal

Platform = Literal["telegram", "whatsapp"]

# Структура офисов (единый источник)
CITY_OFFICES = {
    "astana": {
        "name_ru": "Астана",
        "name_kk": "Астана",
        "address_ru": "Сығанақ 47, офис 433",
        "address_kk": "Сығанақ 47, офис 433",
        "phone_display": "8 702 187 97 26",
        "phone_tel": "+77021879726",
        "wa_display": "7 702 187 97 26",
    },
    "almaty": {
        "name_ru": "Алматы",
        "name_kk": "Алматы",
        "address_ru": "Муратбаева 134, офис 311",
        "address_kk": "Муратбаева 134, 311 офис",
        "phone_display": "8 707 339 10 39",
        "phone_tel": "+77073391039",
        "wa_display": "7 707 339 10 39",
    },
    "shymkent": {
        "name_ru": "Шымкент",
        "name_kk": "Шымкент",
        "address_ru": "Мадели Кожа 45, офис 7",
        "address_kk": "Мадели Кожа 45, 7 офис",
        "phone_display": "8 705 810 28 81",
        "phone_tel": "+77058102881",
        "wa_display": "7 705 810 28 81",
    },
    "atyrau": {
        "name_ru": "Атырау",
        "name_kk": "Атырау",
        "address_ru": "Досмухамедова 139, офис 9",
        "address_kk": "Досмухамедова 139, 9 офис",
        "phone_display": "8 706 686 83 00",
        "phone_tel": "+77066868300",
        "wa_display": "7 706 686 83 00",
    },
    "aktau": {
        "name_ru": "Актау",
        "name_kk": "Ақтау",
        "address_ru": "Актау",
        "address_kk": "Ақтау",
        "phone_display": "8 705 112 99 22",
        "phone_tel": "+77051129922",
        "wa_display": "7 705 112 99 22",
    },
}

CITY_ORDER = ("astana", "almaty", "shymkent", "atyrau", "aktau")

WORK_HOURS_RU = "🕐 *Часы работы:* ответы с 10:00 до 18:00"
WORK_HOURS_KK = "🕐 *Жұмыс уақыты:* 10:00–18:00 аралығында жауап беріледі"


def mono(text: str, platform: Platform) -> str:
    """Моноширинный текст — удобно копировать."""
    t = text.replace("`", "'")
    if platform == "whatsapp":
        return f"```{t}```"
    return f"`{t}`"


def _bold(text: str, platform: Platform) -> str:
    t = text.replace("*", "")
    return f"*{t}*"


def _phone_line(
    office: dict,
    lang: str,
    platform: Platform,
) -> str:
    phone = mono(office["phone_display"], platform)
    if platform == "telegram":
        tel = office["phone_tel"]
        wa = mono(office["wa_display"], platform)
        call = f"[📞 {office['phone_display']}](tel:{tel})"
        return f"📞 {call}  ·  WA {wa}"
    wa = mono(office["wa_display"], platform)
    return f"📞 {phone}  ·  WA {wa}"


def format_office_city(city_key: str, lang: str, platform: Platform = "telegram") -> str:
    o = CITY_OFFICES.get(city_key)
    if not o:
        return ""
    name = o["name_kk"] if lang == "kk" else o["name_ru"]
    addr = o["address_kk"] if lang == "kk" else o["address_ru"]
    lines = [
        f"🏙 {_bold(name, platform)}",
        f"📍 {mono(addr, platform)}",
        _phone_line(o, lang, platform),
    ]
    return "\n".join(lines)


def format_offices_block(
    lang: str,
    *,
    city: str | None = None,
    platform: Platform = "telegram",
    with_header: bool = True,
) -> str:
    """Все офисы или один город."""
    if lang == "kk":
        header = "📍 *Офистер / байланыс*"
        city_q = "❓ *Қай қаладасыз?*"
    else:
        header = "📍 *Офисы / контакты*"
        city_q = "❓ *Из какого вы города?*"

    keys = (city,) if city and city in CITY_OFFICES else CITY_ORDER
    blocks = [format_office_city(k, lang, platform) for k in keys if k in CITY_OFFICES]
    body = "\n\n".join(blocks)
    parts = []
    if with_header and not city:
        parts.extend([header, city_q, ""])
    parts.append(body)
    return "\n".join(parts)


def format_welcome(lang: str, platform: Platform = "telegram") -> str:
    """Приветствие как в шаблоне клиента."""
    if lang == "kk":
        lines = [
            _bold("Сәлеметсіз бе!", platform),
            "",
            "👤 *Сіз кімсіз?*",
            "• Жеке тұлға",
            "• ЖК (жеке кәсіпкер)",
            "• ТОО",
            "",
            format_offices_block(lang, platform=platform, with_header=True),
            "",
            WORK_HOURS_KK,
            "",
            "💬 Сұрағыңызды жазыңыз немесе мәзір: /start",
        ]
    else:
        lines = [
            _bold("Здравствуйте!", platform),
            "",
            "👤 *Кто вы?*",
            "• Физическое лицо",
            "• ИП",
            "• ТОО",
            "",
            format_offices_block(lang, platform=platform, with_header=True),
            "",
            WORK_HOURS_RU,
            "",
            "💬 Напишите ваш вопрос или меню: /start",
        ]
    return "\n".join(lines)


def format_contact_footer(
    lang: str,
    city: str | None = None,
    *,
    all_cities: bool = False,
    platform: Platform = "telegram",
) -> str:
    if city and not all_cities:
        block = format_offices_block(lang, city=city, platform=platform, with_header=False)
        if lang == "kk":
            tail = "\n\n📲 Қоңырау шалыңыз немесе офиске келіңіз."
        else:
            tail = "\n\n📲 Позвоните или приходите в офис."
        return f"{block}{tail}"

    if all_cities:
        return (
            f"{format_offices_block(lang, platform=platform, with_header=True)}\n\n"
            f"{WORK_HOURS_KK if lang == 'kk' else WORK_HOURS_RU}"
        )

    if lang == "kk":
        return "❓ *Қай қаладасыз?* Офис пен телефон жібереміз."
    return "❓ *Из какого вы города?* Подскажу офис и телефон."


def escape_telegram_markdown(text: str) -> str:
    """Экранирование для legacy Markdown (не внутри ` и []())."""
    parts = re.split(r"(`[^`]*`|\[[^\]]*\]\([^)]*\))", text)
    out = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(part)
        else:
            for ch in ("_", "*", "[", "`"):
                part = part.replace(ch, "\\" + ch) if ch != "[" else part
            # legacy: only escape _ * ` in plain segments
            part = re.sub(r"(?<![\\`])([_*`])", r"\\\1", part)
            out.append(part)
    return "".join(out)


def sanitize_for_telegram(text: str) -> str:
    """Убрать битую разметку — оставить * и ` где возможно."""
    # Непарные backticks
    if text.count("`") % 2:
        text = text.replace("`", "'")
    return text
