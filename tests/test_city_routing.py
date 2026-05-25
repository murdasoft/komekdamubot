"""City routing: geo distance to nearest offices."""

from app.bot.city_routing import (
    detect_nearby_offices,
    format_nearby_offices_reply,
    get_universal_fallback_reply,
    looks_like_place_only,
)
from app.bot.kz_geo import nearest_office_keys, haversine_km, OFFICE_COORDS
from app.offices import detect_city


def test_taraz_nearest_shymkent_then_almaty():
    r = detect_nearby_offices("Таразданмын", "ru")
    assert r is not None
    place, keys, dists = r
    assert "араз" in place.lower()
    assert keys == ["shymkent", "almaty"]
    assert dists[0] < dists[1]


def test_karaganda_nearest_astana_then_almaty():
    r = detect_nearby_offices("караганда", "ru")
    assert r and r[1] == ["astana", "almaty"]


def test_semey_nearest_astana():
    r = detect_nearby_offices("Семей", "ru")
    assert r and r[1][0] == "astana"


def test_kaskelen_only_almaty_close():
    r = detect_nearby_offices("Қаскелеңнен", "ru")
    assert r
    assert r[1] == ["almaty"]
    assert r[2][0] < 50


def test_taraz_not_direct_office():
    assert detect_city("Тараз") is None


def test_nearby_reply_shows_km():
    msg = format_nearby_offices_reply(
        "Тараз", ["shymkent", "almaty"], "ru", distances_km=[159, 453]
    )
    assert "~159 км" in msg
    assert "1 — Шымкент" in msg


def test_universal_fallback_has_offices_not_full_menu():
    msg = get_universal_fallback_reply("kk")
    assert "Муратбаева" in msg or "📍" in msg
    assert "1️⃣ ЖК" not in msg


def test_place_only_kaskelen():
    assert looks_like_place_only("Қаскелеңнен") is True


def test_haversine_karaganda_astana_closer_than_almaty():
    k = (49.805, 73.086)
    d_ast = haversine_km(k[0], k[1], *OFFICE_COORDS["astana"])
    d_alm = haversine_km(k[0], k[1], *OFFICE_COORDS["almaty"])
    assert d_ast < d_alm
    assert nearest_office_keys(k[0], k[1], 2) == ["astana", "almaty"]
