from app.offices import (
    clear_offices_cache,
    detect_city,
    get_office_block,
    get_offices_data,
    OFFICES_FALLBACK,
)
from app.bot.faq_matcher import try_fast_response, _attach_contacts


def test_all_five_cities_in_fallback_block():
    clear_offices_cache()
    block = get_office_block(None, "ru")
    for name in ("Алматы", "Астана", "Шымкент", "Атырау", "Актау"):
        assert name in block
    assert block.count("📍") == 5


def test_merge_partial_supabase_keeps_all_cities(monkeypatch):
    def fake_load():
        return {
            "almaty": {"ru": "📍 Алматы test", "kk": "📍 Алматы test"},
            "astana": {"ru": "📍 Астана test", "kk": "📍 Астана test"},
        }

    monkeypatch.setattr("app.offices._load_from_supabase", fake_load)
    clear_offices_cache()
    data = get_offices_data()
    assert len(data) == 5
    block = get_office_block(None, "ru")
    assert block.count("📍") == 5
    assert "Шымкент" in block
    assert "Атырау" in block
    assert "Актау" in block


def test_detect_city_from_message():
    assert detect_city("мен Шымкенттемін") == "shymkent"
    assert detect_city("я в Алматы") == "almaty"
    assert detect_city("20 млн керек") is None


def test_attach_contacts_one_city_only():
    ans = _attach_contacts("Жауап", "kk", "shymkent")
    assert ans.count("📍") == 1
    assert "Шымкент" in ans
    assert "Астана" not in ans


def test_faq_with_city_session():
    clear_offices_cache()
    r = try_fast_response("даму для ип", "kk", session_city="shymkent")
    assert r and r.count("📍") == 1 and "Шымкент" in r
