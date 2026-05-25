from app.bot.unclear_input import (
    is_operator_or_phone_request,
    is_frustration_or_unclear,
    should_use_universal_fallback,
)


def test_operator_phone():
    assert is_operator_or_phone_request("Дайте свой номер")
    assert is_operator_or_phone_request("7")


def test_frustration():
    assert is_frustration_or_unclear("Чат непонятно что то")
    assert is_frustration_or_unclear("😖")


def test_universal_not_for_digits():
    assert not should_use_universal_fallback("3")
    assert should_use_universal_fallback("Дайте свой номер") is False  # operator path
