"""Tests for fast FAQ matcher."""

from app.bot.faq_matcher import try_fast_response, format_product_card


class TestTryFastResponse:
    def test_prepayment_ru(self):
        r = try_fast_response("Вы берёте предоплату?", "ru")
        assert r and "предоплат" in r.lower()

    def test_damu_product(self):
        r = try_fast_response("Расскажите про DAMU 12,6", "ru")
        assert r and "DAMU" in r

    def test_greeting(self):
        r = try_fast_response("Привет", "ru")
        assert r and "KOMEK DAMU" in r

    def test_mortgage_gov(self):
        r = try_fast_response("ипотека 2 процента", "ru")
        assert r and ("2" in r or "гос" in r.lower() or "ипотек" in r.lower())

    def test_no_match_long_gibberish(self):
        assert try_fast_response("asdf qwerty zxcv", "ru") is None

    def test_product_card_format(self):
        card = format_product_card("personal_credit", "ru")
        assert "Кредит" in card
        assert "/start" not in card

    def test_loan_request_short_no_calc(self):
        r = try_fast_response("здравствуйте взять хочу кредит на 1 000 000", "ru")
        assert r
        assert "1 000 000" in r
        assert "Ежемесяч" not in r and "Переплата" not in r
        assert "Муратбаева" not in r

    def test_loan_calc_only_when_asked(self):
        r = try_fast_response("посчитай кредит 1 000 000", "ru")
        assert r and "месяц" in r.lower()
