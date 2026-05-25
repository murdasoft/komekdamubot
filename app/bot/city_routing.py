"""
Города без офиса → ближайшие офисы; универсальный ответ при непонятном тексте.
"""

from __future__ import annotations

import re

from app.bot.formatting import CITY_OFFICES, format_offices_block

# Ключевые слова населённого пункта → офисы (порядок = цифры 1, 2, …)
_LOCALITY_NEARBY: tuple[tuple[str, ...], list[str]] = (
    (("тараз", "taraz", "жамбыл"), ["almaty", "shymkent"]),
    (("сарыагаш", "сарыағаш", "saryagash"), ["shymkent"]),
    (("қызылорда", "кызылорда", "kyzylorda", "қызылордадан"), ["shymkent"]),
    (("талгар", "talgar", "талгардан"), ["almaty"]),
    (("қаскелең", "каскелен", "kaskelen", "қаскелеңнен"), ["almaty"]),
    (("түркістан", "туркестан", "turkistan"), ["shymkent"]),
    (("караганда", "қарағанды", "karaganda"), ["almaty", "astana"]),
    (("павлодар", "pavlodar"), ["astana"]),
    (("костанай", "қостанай", "kostanay"), ["astana"]),
    (("уральск", "oral"), ["atyrau"]),
    (("семей", "semei"), ["almaty", "astana"]),
    (("петропавл", "petropavl"), ["astana"]),
    (("кокшетау", "көкшетау"), ["astana"]),
)

_PLACE_SUFFIX = re.compile(
    r"(данмын|денмін|тенмін|нен|нан|ден|дан|тен|даны|дены|боламын|"
    r"мын|мін|болам|жақын|жакын|област|облыс|район|аудан|село|селосы|"
    r"поселок|посёлок|қала|кала|город)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def _city_display(key: str, lang: str) -> str:
    o = CITY_OFFICES[key]
    return o["name_kk"] if lang == "kk" else o["name_ru"]


def detect_nearby_offices(text: str) -> tuple[str, list[str]] | None:
    """
    Населённый пункт без своего офиса → (как показать пользователю, [almaty, …]).
    """
    low = _normalize(text)
    if not low or len(low) < 3:
        return None
    if len(low.split()) > 6:
        return None

    best: tuple[int, str, list[str]] | None = None
    for keywords, offices in _LOCALITY_NEARBY:
        for kw in keywords:
            if kw in low and (best is None or len(kw) > best[0]):
                label = kw.strip().title()
                if kw.startswith("тараз"):
                    label = "Тараз" if "taraz" not in kw else "Taraz"
                best = (len(kw), label, offices)

    if best:
        return best[1], best[2]

    return None


def looks_like_place_only(text: str) -> bool:
    """Короткое сообщение похоже на название места, не на вопрос."""
    low = _normalize(text)
    if len(low.split()) > 4:
        return False
    if _PLACE_SUFFIX.search(low):
        return True
    if len(low) <= 25 and not any(
        w in low
        for w in (
            "кредит", "несие", "ипотек", "даму", "процент", "ставк", "млн",
            "сколько", "канша", "қанша", "лимит", "help",
        )
    ):
        return True
    return False


def format_nearby_offices_reply(place: str, office_keys: list[str], lang: str) -> str:
    lines: list[str] = []
    if lang == "kk":
        lines.append(f"📍 *{place}* — біздің кеңсе жоқ.")
        lines.append("Жақын офистер:")
    else:
        lines.append(f"📍 В *{place}* нашего офиса нет.")
        lines.append("Ближайшие города с офисом:")
    for i, key in enumerate(office_keys, start=1):
        lines.append(f"{i} — {_city_display(key, lang)}")
    if lang == "kk":
        lines.append("\nЖақын қаланы *санмен* таңдаңыз немесе *98* — қалалар тізімі.")
    else:
        lines.append("\nВыберите ближайший город *цифрой* или *98* — список городов.")
    return "\n".join(lines)


def get_universal_fallback_reply(lang: str, *, platform: str = "whatsapp") -> str:
    """Коротко: не понял + все офисы + навигация 0/98/99 внизу (через add_wa_back_hint)."""
    offices = format_offices_block(lang, platform=platform, with_header=False)  # type: ignore[arg-type]
    if lang == "kk":
        lead = (
            "ℹ️ Сұрақты толық түсінбедім.\n"
            "Жақын офиске қоңырау шалыңыз немесе келіңіз:\n\n"
        )
    else:
        lead = (
            "ℹ️ Не до конца понял ваш запрос.\n"
            "Позвоните в ближайший офис или приезжайте:\n\n"
        )
    tail = (
        "\n\n*7* — менеджер"
        if lang == "kk"
        else "\n\n*7* — менеджер"
    )
    return f"{lead}{offices}{tail}"
