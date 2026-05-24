from app.supabase_client import _row_to_session


def test_row_to_session_merges_json():
    row = {
        "chat_id": "77001234567",
        "platform": "whatsapp",
        "lang": "kk",
        "lang_locked": True,
        "state": "in_flow",
        "product": "business_credit",
        "city": "almaty",
        "data": {"amount": "1000000"},
        "conversation_history": [{"role": "user", "text": "сәлем"}],
        "session_json": {"message_count": 3, "submenu": None},
    }
    s = _row_to_session(row)
    assert s["lang"] == "kk"
    assert s["lang_locked"] is True
    assert s["city"] == "almaty"
    assert s["message_count"] == 3
    assert s["data"]["amount"] == "1000000"
