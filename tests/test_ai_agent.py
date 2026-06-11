"""AI-агент с полной базой знаний."""

import pytest

from app.bot.ai_agent import build_knowledge_context
from app.bot.hybrid_flow import looks_like_free_question
from app.prompts import get_agent_system_prompt


class TestKnowledgeContext:
    def test_includes_all_products(self):
        ctx = build_knowledge_context("kk", {}, "кредит керек па")
        assert "Жеке несие" in ctx or "жеке" in ctx.lower()
        assert "DAMU" in ctx
        assert "Ипотека" in ctx or "ипотека" in ctx.lower()

    def test_highlights_intent(self):
        ctx = build_knowledge_context("ru", {}, "кредит для ип")
        assert "business_credit" in ctx or "ИП" in ctx

    def test_includes_faq(self):
        ctx = build_knowledge_context("ru", {}, "вопрос")
        assert "consultation_free" in ctx or "бесплатн" in ctx.lower()


class TestAgentPrompt:
    def test_agent_prompt_ru(self):
        p = get_agent_system_prompt("ru", city="almaty")
        assert "БАЗА ЗНАНИЙ" in p
        assert "KOMEK DAMU" in p

    def test_agent_prompt_kk(self):
        p = get_agent_system_prompt("kk")
        assert "қазақша" in p


class TestFreeQuestionGate:
    def test_any_text_not_nav(self):
        session = {"state": "selecting_city"}
        assert looks_like_free_question("кредит керек па", session)
        assert looks_like_free_question("а сколько процент", session)
        assert not looks_like_free_question("1", session)
