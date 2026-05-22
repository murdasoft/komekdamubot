from app.offices import clear_offices_cache, get_office_block, get_offices_data, OFFICES_FALLBACK


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
