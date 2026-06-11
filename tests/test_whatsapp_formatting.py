"""Tests for WhatsApp message formatting."""

from app.bot.content import add_wa_back_hint
from app.bot.formatting import format_office_city, format_welcome
from app.bot.outbound import clean_whatsapp_text, adapt_message_for_platform


def test_whatsapp_office_vertical():
    block = format_office_city("astana", "ru", "whatsapp")
    assert "📍 *Астана*" in block
    assert "Сығанақ" in block
    assert "📞 8 702" in block
    assert "```" not in block
    assert block.count("\n") >= 2


def test_whatsapp_welcome_no_backticks():
    msg = format_welcome("ru", "whatsapp")
    assert "```" not in msg
    assert "📍 *Астана*" in msg
    assert "1️⃣ ИП" in msg or "1️⃣" in msg
    assert "цифру 1–7" in msg or "1–7" in msg


def test_clean_whatsapp_dedupe_city_question():
    raw = (
        "Нет, на выходных не работаем.\n\n"
        "Из какого вы города? Подскажу офис и телефон.\n\n"
        "Из какого вы города? Подскажу офис и телефон.\n\n"
        "📍 Астана\n📞 8 702 187 97 26"
    )
    out = clean_whatsapp_text(raw)
    assert out.count("Из какого вы города") == 1


def test_clean_whatsapp_strips_tel_markdown():
    raw = (
        "Не істейміз деп ойласыз? "
        "**[8 702 187 97 26](tel:+77021879726)** нөмірімен хабарласыңыз"
    )
    out = clean_whatsapp_text(raw)
    assert "[8 702" not in out
    assert "(tel:" not in out
    assert "8 702 187 97 26" in out
    assert "*8 702 187 97 26*" in out


def test_adapt_strips_backticks():
    assert "```" not in adapt_message_for_platform("📍 `адрес`", "whatsapp")


def test_wa_back_hint_bilingual():
    out = add_wa_back_hint("Сәлем", "kk")
    assert "Бөлімдерге қайту" in out
    assert "Назад к разделам" in out
    assert "Тілді ауыстыру" in out
    assert "Сменить язык" in out
