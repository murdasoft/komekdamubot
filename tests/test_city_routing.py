"""City routing: nearby offices and universal fallback."""

from app.bot.city_routing import (
    detect_nearby_offices,
    format_nearby_offices_reply,
    get_universal_fallback_reply,
    looks_like_place_only,
)
from app.offices import detect_city


def test_taraz_suggests_almaty_shymkent():
    r = detect_nearby_offices("Таразданмын")
    assert r is not None
    place, keys = r
    assert "тараз" in place.lower() or "Тараз" in place
    assert keys == ["almaty", "shymkent"]


def test_kaskelen_suggests_almaty():
    r = detect_nearby_offices("Қаскелеңнен")
    assert r and r[1] == ["almaty"]


def test_taraz_not_direct_office():
    assert detect_city("Тараз") is None


def test_nearby_reply_lists_digits():
    msg = format_nearby_offices_reply("Тараз", ["almaty", "shymkent"], "ru")
    assert "офиса нет" in msg.lower()
    assert "1 — Алматы" in msg
    assert "2 — Шымкент" in msg
    assert "98" in msg


def test_universal_fallback_has_offices_not_full_menu():
    msg = get_universal_fallback_reply("kk")
    assert "Муратбаева" in msg or "📍" in msg
    assert "1️⃣ ЖК" not in msg
    assert "түсінбедім" in msg.lower() or "Сұрақты" in msg


def test_place_only_kaskelen():
    assert looks_like_place_only("Қаскелеңнен") is True
