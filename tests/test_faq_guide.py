"""Умный гид к FAQ — не свободный чат."""

import pytest

from app.bot.faq_guide import try_faq_guide_reply
from app.bot.unclear_input import is_off_topic_message


def test_off_topic_football():
    assert is_off_topic_message("бүгін футбол матчы қашан")
    session = {"city_confirmed": True, "lang": "kk"}
    reply = try_faq_guide_reply("бүгін футбол матчы қашан", "kk", session)
    assert reply
    assert "несие" in reply.lower() or "KOMEK" in reply
    assert "1" in reply or "3" in reply


def test_off_topic_not_finance_question():
    session = {"city_confirmed": True}
    reply = try_faq_guide_reply("кино көргім келеді", "kk", session)
    assert reply
    assert "?" in reply or "❓" in reply


def test_guide_asks_city_when_missing():
    session = {"city_confirmed": False}
    reply = try_faq_guide_reply("несие керек", "kk", session)
    assert reply
    assert "қала" in reply.lower() or "Қай" in reply


def test_guide_menu_when_no_intent():
    session = {"city_confirmed": True, "city": "almaty"}
    reply = try_faq_guide_reply("көмек керек", "kk", session)
    assert reply
    assert "1" in reply and "4" in reply


def test_finance_not_off_topic():
    assert not is_off_topic_message("ипотека 2 процент")


def test_frustration_redirect():
    session = {"city_confirmed": True}
    reply = try_faq_guide_reply("непонятно что-то", "ru", session)
    assert reply
    assert "3" in reply or "цифр" in reply.lower()
