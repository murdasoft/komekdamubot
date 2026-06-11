"""Гибридный FAQ/AI во время мастера."""

import pytest

from app.bot.hybrid_flow import is_wizard_nav_input, looks_like_free_question, send_hybrid_reply


class TestWizardNav:
    def test_city_digit_is_nav(self):
        session = {"state": "selecting_city"}
        assert is_wizard_nav_input("1", session)
        assert not is_wizard_nav_input("кредит керек па", session)

    def test_lang_digit_is_nav(self):
        session = {"state": "selecting_lang"}
        assert is_wizard_nav_input("1", session)
        assert is_wizard_nav_input("2", session)


class TestFreeQuestion:
    def test_credit_question_on_city_step(self):
        session = {"state": "selecting_city", "lang": "kk"}
        assert looks_like_free_question("кредит керек па", session)

    def test_single_char_not_question(self):
        session = {"state": "selecting_city"}
        assert not looks_like_free_question("?", session)
        assert looks_like_free_question("ok", session)


@pytest.mark.asyncio
async def test_send_hybrid_reply_uses_get_reply():
    sent = []

    async def send_fn(msg: str):
        sent.append(msg)

    async def fake_get_reply(text, session, ai):
        return f"Ответ: {text}"

    session = {"state": "selecting_city", "lang": "kk"}
    ok = await send_hybrid_reply(
        "кредит керек па",
        session,
        None,
        send_fn,
        get_reply=fake_get_reply,
    )
    assert ok
    assert sent
    assert "кредит керек па" in sent[0]
    assert session["conversation_history"]
