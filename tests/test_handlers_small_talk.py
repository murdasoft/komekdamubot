"""Tests for small-talk intent detection."""

from app.bot.handlers import detect_small_talk_intent


class TestDetectSmallTalkIntent:
    def test_pure_greeting_detected(self):
        assert detect_small_talk_intent("Привет") == "greeting"

    def test_greeting_with_question_not_small_talk(self):
        assert detect_small_talk_intent("здравствуйте хочу кредит") is None

    def test_thanks_on_pure_message(self):
        assert detect_small_talk_intent("спасибо") == "thanks"
