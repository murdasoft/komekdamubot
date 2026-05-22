"""Офисы KOMEK DAMU — Supabase + fallback."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback если Supabase недоступен
OFFICES_FALLBACK = {
    "almaty": {
        "ru": "📍 Алматы, ул. Муратбаева 134, каб. 311\n📞 8 707 339 10 39 | WhatsApp: 7 707 339 10 39",
        "kk": "📍 Алматы, Муратбаева 134, 311 каб\n📞 8 707 339 10 39 | WhatsApp: 7 707 339 10 39",
    },
    "astana": {
        "ru": "📍 Астана, ул. Сыганак 47, каб. 433\n📞 8 702 187 97 26 | WhatsApp: 7 702 187 97 26",
        "kk": "📍 Астана, Сығанақ 47, 433 каб\n📞 8 702 187 97 26 | WhatsApp: 7 702 187 97 26",
    },
    "shymkent": {
        "ru": "📍 Шымкент, ул. Мадели Кожа 45, каб. 7\n📞 8 705 810 28 81 | WhatsApp: 7 705 810 28 81",
        "kk": "📍 Шымкент, Мадели Кожа 45, 7 каб\n📞 8 705 810 28 81 | WhatsApp: 7 705 810 28 81",
    },
    "atyrau": {
        "ru": "📍 Атырау, ул. Досмухамедова 139а, каб. 9\n📞 8 706 686 83 00 | WhatsApp: 7 706 686 83 00",
        "kk": "📍 Атырау, Досмухамедова 139а, 9 каб\n📞 8 706 686 83 00 | WhatsApp: 7 706 686 83 00",
    },
    "aktau": {
        "ru": "📍 Актау\n📞 8 705 112 99 22 | WhatsApp: 7 705 112 99 22",
        "kk": "📍 Ақтау\n📞 8 705 112 99 22 | WhatsApp: 7 705 112 99 22",
    },
}

# Порядок вывода всех офисов в ответе
CITY_ORDER = ("almaty", "astana", "shymkent", "atyrau", "aktau")

CITY_KEYWORDS = {
    "almaty": ["алматы", "алма-ата", "almaty"],
    "astana": ["астана", "нур-султан", "нурсултан", "astana"],
    "shymkent": ["шымкент", "шимкент", "shymkent"],
    "atyrau": ["атырау", "atyrau"],
    "aktau": ["актау", "ақтау", "aktau"],
}

_cache: dict | None = None


def detect_city(text: str) -> str | None:
    lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return city
    return None


def _load_from_supabase() -> dict:
    from app.supabase_client import get_supabase

    sb = get_supabase()
    if not sb:
        return {}
    try:
        rows = sb.table("offices").select("*").execute().data or []
        out: dict = {}
        for row in rows:
            key = row.get("city_key")
            if not key:
                continue
            out[key] = {
                "ru": row.get("text_ru") or "",
                "kk": row.get("text_kk") or row.get("text_ru") or "",
            }
        return out
    except Exception as e:
        logger.warning("offices table: %s — using fallback", e)
        return {}


def get_offices_data() -> dict:
    """Все 5 городов: fallback + данные Supabase (дополняют, не заменяют)."""
    global _cache
    if _cache is None:
        merged = {k: dict(v) for k, v in OFFICES_FALLBACK.items()}
        db = _load_from_supabase()
        for key, val in db.items():
            ru = (val.get("ru") or "").strip()
            kk = (val.get("kk") or "").strip()
            if ru or kk:
                merged[key] = {
                    "ru": ru or merged.get(key, {}).get("ru", ""),
                    "kk": kk or merged.get(key, {}).get("ru", ""),
                }
        _cache = merged
    return _cache


def clear_offices_cache() -> None:
    """Сброс кэша (тесты / после обновления offices в Supabase)."""
    global _cache
    _cache = None


def get_office_block(city: str | None, lang: str) -> str:
    offices = get_offices_data()
    if city and city in offices:
        return offices[city].get(lang, offices[city]["ru"])
    lines = [
        offices[c].get(lang, offices[c].get("ru", ""))
        for c in CITY_ORDER
        if c in offices and offices[c].get(lang, offices[c].get("ru"))
    ]
    return "\n\n".join(lines) if lines else OFFICES_FALLBACK["almaty"][lang]


def get_contact_footer(city: str | None, lang: str, *, all_cities: bool = False) -> str:
    """Контакты: один город или все."""
    if lang == "kk":
        lead = "Байланыс:\n"
        ask = "Немесе қоңырау шалыңыз / офиске келіңіз."
    else:
        lead = "Контакты:\n"
        ask = "Или позвоните / приходите в офис."
    if city and not all_cities:
        return f"{lead}{get_office_block(city, lang)}\n{ask}"
    return f"{lead}{get_office_block(None, lang)}\n{ask}"
