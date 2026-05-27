from app.bot.chatbot_ux import (
    is_vague_credit_request,
    parse_lang_digit,
    pick_voice_text_nudge,
)


def test_parse_lang_digit():
    assert parse_lang_digit("1") == "1"
    assert parse_lang_digit("Қазақша") == "1"
    assert parse_lang_digit("русский") == "2"
    assert parse_lang_digit("Алматы") is None


def test_vague_credit():
    assert is_vague_credit_request("хочу кредит")
    assert is_vague_credit_request("кредит гарикпа")
    assert not is_vague_credit_request("ипотека")
    assert not is_vague_credit_request("ип кредит")


def test_voice_nudge_stable():
    a = pick_voice_text_nudge("ru", "12345")
    b = pick_voice_text_nudge("ru", "12345")
    assert a == b
    assert len(a) > 10
