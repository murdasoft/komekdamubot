"""Tests for STT normalization (ИП vs ипотека)."""

from app.bot.stt_normalize import (
    looks_like_misheard_ip,
    normalize_stt_borrower_answer,
    session_awaits_borrower_type,
)
from app.bot.faq_matcher import try_fast_response


class TestMisheardIp:
    def test_ip_abbreviation_always(self):
        assert looks_like_misheard_ip("и.п.")
        assert looks_like_misheard_ip("и п")

    def test_ipoteka_without_context_is_not_misheard(self):
        assert not looks_like_misheard_ip("ипотека")
        assert not looks_like_misheard_ip("ипотека", borrower_context=False)

    def test_ipoteka_with_borrower_context(self):
        assert looks_like_misheard_ip("ипотека", borrower_context=True)

    def test_mortgage_phrase_not_misheard(self):
        assert not looks_like_misheard_ip("хочу ипотеку на квартиру", borrower_context=True)

    def test_normalize_with_session_flag(self):
        session = {
            "awaiting_borrower_type": True,
            "conversation_history": [],
        }
        assert normalize_stt_borrower_answer("ипотека", session) == "ИП"

    def test_normalize_from_history(self):
        session = {
            "conversation_history": [
                {
                    "role": "assistant",
                    "text": "❓ *Сіз кімсіз?* Жеке тұлға / ЖК (ИП) / ТОО",
                }
            ],
        }
        assert session_awaits_borrower_type(session)
        assert normalize_stt_borrower_answer("ипотека", session) == "ИП"

    def test_fast_response_after_voice_ip_fix(self):
        session = {"awaiting_borrower_type": True, "conversation_history": []}
        from app.bot.stt_normalize import normalize_stt_borrower_answer

        fixed = normalize_stt_borrower_answer("ипотека", session)
        r = try_fast_response(fixed, "kk", "astana", "whatsapp", city_confirmed=True)
        assert r
        assert "Ипотека" not in r or "бизнес" in r.lower() or "кредит" in r.lower() or "несие" in r.lower()

    def test_mortgage_still_works(self):
        r = try_fast_response("ипотека 2 процента", "ru")
        assert r and "2" in r
