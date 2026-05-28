"""
География KZ: координаты населённых пунктов и расчёт ближайших офисов (5 городов).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Офисы KOMEK DAMU (центр города, WGS84)
OFFICE_COORDS: dict[str, tuple[float, float]] = {
    "almaty": (43.239, 76.945),
    "astana": (51.169, 71.449),
    "shymkent": (42.320, 69.596),
    "aktau": (43.651, 51.197),
}

OFFICE_CITY_KEYS = frozenset(OFFICE_COORDS.keys())

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "kz_localities.json"


@dataclass(frozen=True)
class Locality:
    name_ru: str
    name_kk: str
    lat: float
    lon: float
    keywords: tuple[str, ...]


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2
    a += math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def nearest_office_keys(lat: float, lon: float, count: int = 2) -> list[str]:
    """Ближайшие офисы по расстоянию (км)."""
    ranked = sorted(
        (haversine_km(lat, lon, olat, olon), key)
        for key, (olat, olon) in OFFICE_COORDS.items()
    )
    return [key for _, key in ranked[:count]]


@lru_cache(maxsize=1)
def _load_localities() -> list[Locality]:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    out: list[Locality] = []
    for row in raw:
        kw = tuple(_normalize(k) for k in row.get("kw", []) if k)
        out.append(
            Locality(
                name_ru=row["ru"],
                name_kk=row.get("kk") or row["ru"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                keywords=kw + (_normalize(row["ru"]), _normalize(row.get("kk", ""))),
            )
        )
    return out


def find_locality(text: str) -> Locality | None:
    """Найти населённый пункт в справочнике по подстроке (самое длинное совпадение)."""
    low = _normalize(text)
    if len(low) < 3:
        return None

    best: tuple[int, Locality] | None = None
    for loc in _load_localities():
        for kw in loc.keywords:
            if len(kw) < 3:
                continue
            if kw in low and (best is None or len(kw) > best[0]):
                best = (len(kw), loc)
    return best[1] if best else None


def resolve_nearby_from_text(
    text: str, lang: str = "ru"
) -> tuple[str, list[str], list[int]] | None:
    """
    Текст с названием города → (название, [офисы], [км до каждого]).
    None если не распознали или это один из 5 городов с офисом.
    """
    from app.offices import detect_city

    if detect_city(text) in OFFICE_CITY_KEYS:
        return None

    loc = find_locality(text)
    if not loc:
        return None

    name = loc.name_kk if lang == "kk" else loc.name_ru
    offices = nearest_office_keys(loc.lat, loc.lon, count=2)
    dists = [
        int(round(haversine_km(loc.lat, loc.lon, OFFICE_COORDS[k][0], OFFICE_COORDS[k][1])))
        for k in offices
    ]
    # Один вариант только у «пригорода» офиса (Каскелен → только Алматы)
    if len(dists) == 2 and dists[0] < 80 and dists[1] > dists[0] * 3:
        offices = offices[:1]
        dists = dists[:1]
    return name, offices, dists
