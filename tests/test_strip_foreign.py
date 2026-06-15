from app.bot.formatting import strip_foreign_scripts, sanitize_for_telegram
from app.bot.response_builder import finalize_bot_response


def test_phone_cjk_replaced():
    raw = "Сұраймын? 电话: 8 702 187 97 26"
    out = strip_foreign_scripts(raw, "kk")
    assert "电话" not in out
    assert "📞" in out
    assert "8 702 187 97 26" in out


def test_sanitize_telegram_strips_cjk():
    out = sanitize_for_telegram("Ответ 手机 8 707 339 10 39")
    assert "手机" not in out
    assert "📞" in out


def test_finalize_bot_response_cleans_ai():
    out = finalize_bot_response(
        "Менеджер жақын арада хабарласады. 电话 8 707 339 10 39",
        "менеджер",
        "kk",
        "almaty",
        city_confirmed=True,
    )
    assert "电话" not in out
    assert "📞" in out
