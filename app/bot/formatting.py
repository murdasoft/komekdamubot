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
        "address_ru": "Сығанақ 47, каб. 433",
        "address_kk": "Сығанақ 47, 433 каб",
        "phone_display": "8 702 187 97 26",
        "phone_tel": "+77021879726",
        "wa_display": "7 702 187 97 26",
    },
    "almaty": {
        "name_ru": "Алматы",
        "name_kk": "Алматы",
        "address_ru": "Муратбаева 134, каб. 311",
        "address_kk": "Муратбаева 134, 311 каб",
        "phone_display": "8 707 339 10 39",
        "phone_tel": "+77073391039",
        "wa_display": "7 707 339 10 39",
    },
    "shymkent": {
        "name_ru": "Шымкент",
        "name_kk": "Шымкент",
        "address_ru": "Мадели Кожа 45, каб. 7",
        "address_kk": "Мадели Кожа 45, 7 каб",
        "phone_display": "8 705 810 28 81",
        "phone_tel": "+77058102881",
        "wa_display": "7 705 810 28 81",
    },
    "atyrau": {
        "name_ru": "Атырау",
        "name_kk": "Атырау",
        "address_ru": "Досмухамедова 139а, каб. 9",
        "address_kk": "Досмухамедова 139а, 9 каб",
        "phone_display": "8 706 686 83 00",
        "phone_tel": "+77066868300",
        "wa_display": "7 706 686 83 00",
    },
    "aktau": {
        "name_ru": "Актау",
        "name_kk": "Ақтау",
        "address_ru": "",
        "address_kk": "",
        "phone_display": "8 705 112 99 22",
        "phone_tel": "+77051129922",
        "wa_display": "7 705 112 99 22",
    },
}

CITY_ORDER = ("astana", "almaty", "shymkent", "atyrau", "aktau")

WORK_HOURS_RU = "🕐 *Часы работы:* ответы с 10:00 до 18:00"
WORK_HOURS_KK = "🕐 *Жұмыс уақыты:* 10:00–18:00 аралығында жауап беріледі"

# Официальное описание услуг KOMEK DAMU
COMPANY_OFFER_KK = (
    "*KOMEK DAMU* – кепілсіз тиімді несие!\n\n"
    "💼 *Бизнеске:*\n"
    "✔️ 35 млн ₸ дейін (кепілсіз)\n"
    "✔️ 500 млн ₸ дейін (кепілмен)\n\n"
    "👤 *Жеке тұлғаларға:*\n"
    "✔️ 25 млн ₸ дейін\n\n"
    "🏢 *ТОО үшін:*\n"
    "✔️ 200 млн ₸ дейін кепілсіз несие рәсімдеуге көмек\n\n"
    "📌 *Талаптар:*\n"
    "• ЖК кемінде 6 ай жұмыс істеген болуы керек\n"
    "• Ашық просрочка болмауы тиіс\n"
    "• ТОО кемінде 1 жыл жұмыс істеген болу керек"
)

COMPANY_OFFER_RU = (
    "*KOMEK DAMU* — выгодный кредит без залога!\n\n"
    "💼 *Для бизнеса:*\n"
    "✔️ до 35 млн ₸ (без залога)\n"
    "✔️ до 500 млн ₸ (с залогом)\n\n"
    "👤 *Для физлиц:*\n"
    "✔️ до 25 млн ₸\n\n"
    "🏢 *Для ТОО:*\n"
    "✔️ помощь с беззалоговым кредитом до 200 млн ₸\n\n"
    "📌 *Требования:*\n"
    "• ИП — бизнес от 6 месяцев\n"
    "• Без открытых просрочек\n"
    "• ТОО — бизнес от 1 года"
)


def mono(text: str, platform: Platform) -> str:
    """Телефон/адрес — на WhatsApp без backticks (ломают переносы)."""
    t = text.replace("`", "'").strip()
    if platform == "whatsapp":
        return t
    return f"`{t}`"


def _bold(text: str, platform: Platform) -> str:
    t = text.replace("*", "")
    return f"*{t}*"


def format_company_offer(lang: str, platform: Platform = "telegram") -> str:
    return COMPANY_OFFER_KK if lang == "kk" else COMPANY_OFFER_RU


def format_office_city(city_key: str, lang: str, platform: Platform = "telegram") -> str:
    o = CITY_OFFICES.get(city_key)
    if not o:
        return ""
    name = o["name_kk"] if lang == "kk" else o["name_ru"]
    addr = (o["address_kk"] if lang == "kk" else o["address_ru"]).strip()
    phone = o["phone_display"]
    if platform == "whatsapp":
        lines = [f"📍 *{name}*"]
        if addr:
            lines.append(addr)
        lines.append(f"📞 {phone}")
        return "\n".join(lines)
    phone_md = mono(phone, platform)
    if platform == "telegram":
        tel = o["phone_tel"]
        phone_btn = f"[{o['phone_display']}](tel:{tel})"
    else:
        phone_btn = phone_md
    if addr:
        return f"📍 {name}: {mono(addr, platform)}\n📞 {phone_btn}"
    return f"📍 {name}: 📞 {phone_btn}"


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
    """Приветствие с условиями KOMEK DAMU и офисами."""
    if platform == "whatsapp":
        from app.bot.menu import get_main_menu_text

        greet = "Сәлеметсіз бе!" if lang == "kk" else "Здравствуйте!"
        pick = (
            "👇 Таңдаңыз: 1–7 санын жазыңыз"
            if lang == "kk"
            else "👇 Выберите: напишите цифру 1–7"
        )
        lines = [
            greet,
            "",
            pick,
            "",
            get_main_menu_text(lang),
            "",
            format_offices_block(lang, platform=platform, with_header=False),
            "",
            WORK_HOURS_KK if lang == "kk" else WORK_HOURS_RU,
        ]
        return "\n".join(lines)

    from app.bot.menu import get_main_menu_text

    greet = _bold("Сәлеметсіз бе!", platform) if lang == "kk" else _bold("Здравствуйте!", platform)
    pick = (
        "👇 *Таңдаңыз:* төмендегі сандарды жазыңыз немесе түймелерді басыңыз"
        if lang == "kk"
        else "👇 *Выберите раздел:* цифрой ниже или кнопкой"
    )
    lines = [
        greet,
        "",
        pick,
        "",
        get_main_menu_text(lang),
        "",
        format_offices_block(lang, platform=platform, with_header=False),
        "",
        WORK_HOURS_KK if lang == "kk" else WORK_HOURS_RU,
    ]
    return "\n".join(lines)


def has_contact_block(text: str) -> bool:
    """В ответе уже есть офисы или несколько телефонов."""
    if "📍" in text:
        return True
    return len(re.findall(r"8\s*7\d{2}", text)) >= 2


def has_city_question(text: str) -> bool:
    low = text.lower()
    return "город" in low or "қала" in low


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
        header = "📍 *Офистер / байланыс*" if lang == "kk" else "📍 *Офисы / контакты*"
        body = format_offices_block(lang, platform=platform, with_header=False)
        return (
            f"{header}\n\n{body}\n\n"
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
