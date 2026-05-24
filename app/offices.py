"""Офисы KOMEK DAMU — Supabase + форматирование."""

from __future__ import annotations

import logging

from app.bot.formatting import (
    CITY_OFFICES,
    CITY_ORDER,
    format_contact_footer,
    format_office_city,
    Platform,
)

logger = logging.getLogger(__name__)

# Для обратной совместимости
OFFICES_FALLBACK = {
    key: {
        "ru": format_office_city(key, "ru", "telegram"),
        "kk": format_office_city(key, "kk", "telegram"),
    }
    for key in CITY_OFFICES
}

CITY_KEYWORDS = {
    "almaty": [
        "алматы", "алма-ата", "almaty", "алматылы", "алматиден", "алматыдан",
        "в алматы", "из алматы", "мен алматы",
    ],
    "astana": [
        "астана", "нур-султан", "нурсултан", "astana", "астанадан",
        "в астане", "из астаны", "мен астана",
    ],
    "shymkent": [
        "шымкент", "шимкент", "shymkent", "шымкентте", "шымкенттен", "шымкенттемін",
        "в шымкенте", "из шымкента", "мен шымкент",
    ],
    "atyrau": [
        "атырау", "atyrau", "атырауда", "атыраудан", "в атырау", "из атырау",
    ],
    "aktau": [
        "актау", "ақтау", "aktau", "актауда", "актаудан", "в актау", "в ақтау",
    ],
}

_cache: dict | None = None


def detect_city(text: str) -> str | None:
    lower = text.lower().replace("ё", "е")
    best: tuple[int, str] | None = None
    for city, keywords in CITY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower and (best is None or len(kw) > best[0]):
                best = (len(kw), city)
    return best[1] if best else None


def resolve_city(text: str, session_city: str | None = None) -> str | None:
    return detect_city(text) or session_city


def city_for_contacts(
    text: str,
    session_city: str | None = None,
    *,
    city_confirmed: bool = False,
) -> str | None:
    """Город для офиса: только из текущего сообщения или подтверждённый в сессии."""
    found = detect_city(text)
    if found:
        return found
    if city_confirmed and session_city:
        return session_city
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
        logger.warning("offices table: %s — using formatted fallback", e)
        return {}


def get_offices_data() -> dict:
    global _cache
    if _cache is None:
        _cache = dict(OFFICES_FALLBACK)
        db = _load_from_supabase()
        for key, val in db.items():
            if val.get("ru") or val.get("kk"):
                _cache[key] = val
    return _cache


def clear_offices_cache() -> None:
    global _cache
    _cache = None


def get_office_block(city: str | None, lang: str, platform: Platform = "telegram") -> str:
    """Текст офисов для промпта LLM или сообщения."""
    if city and city in CITY_OFFICES:
        return format_office_city(city, lang, platform)
    from app.bot.formatting import format_offices_block

    return format_offices_block(lang, platform=platform, with_header=False)


def get_contact_footer(
    city: str | None,
    lang: str,
    *,
    all_cities: bool = False,
    platform: Platform = "telegram",
) -> str:
    return format_contact_footer(lang, city, all_cities=all_cities, platform=platform)
