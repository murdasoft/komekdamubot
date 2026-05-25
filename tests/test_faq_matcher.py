"""Tests for fast FAQ matcher."""

from app.bot.faq_matcher import try_fast_response, format_product_card


class TestTryFastResponse:
    def test_prepayment_ru(self):
        r = try_fast_response("Вы берёте предоплату?", "ru")
        assert r and "предоплат" in r.lower()

    def test_damu_product(self):
        r = try_fast_response("Расскажите про DAMU 12,6", "ru")
        assert r and "DAMU" in r

    def test_damu_ip_no_unsecured(self):
        r = try_fast_response("даму для ип без залога", "ru")
        assert r and ("не оформляется" in r.lower() or " damu *нет" in r.lower() or "damu *нет" in r.lower())
        assert "3 лет" in r.lower()

    def test_ip_no_damu_short(self):
        r = try_fast_response("на ип", "ru", "astana", "whatsapp")
        assert r and "3 лет" in r.lower()
        assert "damu" in r.lower() and "нет" in r.lower()

    def test_ip_rate_question(self):
        r = try_fast_response("процент по кредиту на ип сколько", "ru", "astana", "whatsapp")
        assert r and "3 лет" in r.lower()
        assert "damu" in r.lower() and "нет" in r.lower()

    def test_ip_not_triggered_in_unrelated_long_text(self):
        text = (
            "я вчера ходил в банк и там сказали много всего про документы и про то "
            "как оформляют на ип бумаги но это был просто разговор "
            "на ип тему в общем очень длинное сообщение без вопроса"
        )
        assert try_fast_response(text, "ru") is None

    def test_ambiguous_credit_asks_type(self):
        r = try_fast_response("в Астане кредит дадите", "ru", "astana", "whatsapp")
        assert r and ("ИП" in r or "физлиц" in r.lower() or "1️⃣" in r)

    def test_greeting(self):
        r = try_fast_response("Привет", "ru")
        assert r and "KOMEK DAMU" in r

    def test_mortgage_gov_and_partner_rates(self):
        r = try_fast_response(
            "ипотека какие госпрограммы 2% 9% диапазон 18-22", "ru"
        )
        assert r
        assert "2" in r and "9" in r
        assert "15" in r and "22" in r
        assert "офлайн" in r.lower() or "офис" in r.lower()
        assert "18-22" not in r.replace("15–22", "").replace("15-22", "")

    def test_mortgage_gov(self):
        r = try_fast_response("ипотека 2 процента", "ru")
        assert r and ("2" in r or "гос" in r.lower() or "ипотек" in r.lower())
        assert "15" in r or "22" in r

    def test_no_match_long_gibberish(self):
        assert try_fast_response("asdf qwerty zxcv", "ru") is None

    def test_product_card_format(self):
        card = format_product_card("personal_credit", "ru")
        assert "Кредит" in card
        assert "/start" not in card

    def test_loan_request_kk_asks_city_without_confirmed_session(self):
        r = try_fast_response(
            "1 000 000 тенге кредит на тоо хочу взять",
            "kk",
            session_city="almaty",
            platform="whatsapp",
            city_confirmed=False,
        )
        assert r
        assert "1 000 000" in r
        assert "Муратбаева" not in r
        assert "Қай" in r or "?" in r

    def test_loan_request_shows_office_when_city_confirmed(self):
        r = try_fast_response(
            "1 000 000 тенге кредит на тоо",
            "kk",
            session_city="almaty",
            platform="whatsapp",
            city_confirmed=True,
        )
        assert r
        assert "Муратбаева" in r

        r = try_fast_response("здравствуйте взять хочу кредит на 1 000 000", "ru")
        assert r
        assert "1 000 000" in r
        assert "Ежемесяч" not in r and "Переплата" not in r
        assert "Муратбаева" not in r

    def test_loan_calc_only_when_asked(self):
        r = try_fast_response("посчитай кредит 1 000 000", "ru")
        assert r and "месяц" in r.lower()

    def test_personal_limit_ru(self):
        r = try_fast_response("лимит на физлицо", "ru", platform="whatsapp")
        assert r
        assert "25 млн" in r
        assert "8 млн" in r
        assert "21%" in r

    def test_personal_followup_rate(self):
        session = {"last_intent": "personal_credit", "lang_locked": True}
        r = try_fast_response(
            "а процент",
            "ru",
            "almaty",
            "whatsapp",
            city_confirmed=True,
            session=session,
        )
        assert r
        assert "21%" in r
        assert "9:00" not in r

    def test_personal_followup_term_not_10_years_only(self):
        session = {"last_intent": "personal_credit"}
        r = try_fast_response(
            "сколько лимит лет на физлицо",
            "ru",
            platform="whatsapp",
            session=session,
        )
        assert r
        assert "5 лет" in r
        assert "10 лет" in r

    def test_personal_city_after_question(self):
        session = {"last_intent": "personal_credit"}
        r = try_fast_response(
            "алматы",
            "ru",
            session_city="almaty",
            platform="whatsapp",
            city_confirmed=True,
            session=session,
        )
        assert r
        assert "25 млн" in r
        assert "Муратбаева" in r

    def test_ip_credit_kk_not_personal_after_session(self):
        session = {"last_intent": "personal_credit"}
        r = try_fast_response(
            "ип кредит керек па канша процент",
            "kk",
            platform="whatsapp",
            session=session,
        )
        assert r
        assert "40 млн" in r
        assert "21%" in r
        assert "25 млн" not in r
        assert "Жеке тұлға" not in r

    def test_credit_mortgage_kk_not_clarify(self):
        r = try_fast_response("кредит ипотека", "kk", platform="whatsapp")
        assert r
        assert "Ипотека" in r or "ипотек" in r.lower()
        assert "Сіз кімсіз" not in r

    def test_menu_digit_1_ip_kk(self):
        from app.bot.menu import menu_choice_body

        body = menu_choice_body("ip_business", "kk")
        assert body and "40 млн" in body and "21%" in body

    def test_menu_digit_2_too_ru(self):
        from app.bot.menu import menu_choice_body

        body = menu_choice_body("too_business", "ru")
        assert body and "200 млн" in body and "12,6%" in body
