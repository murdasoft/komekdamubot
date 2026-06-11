"""
AI-агент KOMEK DAMU: отвечает по полной базе знаний (продукты + FAQ).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from app.bot.faq_matcher import EXTRA_FAQ
from app.bot.knowledge_base import (
    FAQ_ANSWERS,
    PRODUCTS,
    detect_intent,
    format_ip_credit_answer,
    format_mortgage_programs_answer,
    format_personal_credit_answer,
    format_too_credit_answer,
    get_product_info,
)
from app.config import get_settings
from app.gemini_client import get_gemini_client
from app.offices import detect_city, get_office_block
from app.prompts import get_agent_system_prompt

if TYPE_CHECKING:
    from app.ai_client import AIClient

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 8
_HISTORY_MSG_CHARS = 600


def build_knowledge_context(lang: str, session: dict, user_text: str) -> str:
    """Полная база знаний + акцент на релевантный продукт."""
    lines: list[str] = ["=== БАЗА ЗНАНИЙ KOMEK DAMU ==="]

    intent = detect_intent(user_text, session) or session.get("last_intent")
    if intent:
        lines.append(f"\n[Релевантный продукт: {intent}]")
        info = get_product_info(intent, lang)
        if info:
            lines.append(f"Название: {info['name']}")
            lines.append(f"Описание: {info['description']}")
            lines.append(f"Условия:\n{info['conditions'].replace(chr(92) + 'n', chr(10))}")
            docs = info.get("docs") or []
            if docs:
                lines.append("Документы: " + ", ".join(docs))

    lines.append("\n--- Все продукты ---")
    for key, product in PRODUCTS.items():
        if key == intent:
            continue
        info = get_product_info(key, lang)
        if not info:
            continue
        lines.append(
            f"\n• {info['name']}: {info['description']}\n"
            f"  Условия: {info['conditions'].replace(chr(92) + 'n', ' | ')}"
        )

    lines.append("\n--- Справочные ответы (ИП / ТОО / ипотека) ---")
    lines.append(format_ip_credit_answer(lang))
    lines.append(format_too_credit_answer(lang))
    lines.append(format_mortgage_programs_answer(lang))
    lines.append(format_personal_credit_answer(lang, user_text))

    lines.append("\n--- FAQ ---")
    for faq_key, answers in FAQ_ANSWERS.items():
        text = answers.get(lang) or answers.get("ru", "")
        if text:
            lines.append(f"[{faq_key}]: {text}")

    for faq_key, answers in EXTRA_FAQ.items():
        if faq_key in ("greeting", "thanks"):
            continue
        text = answers.get(lang) or answers.get("ru", "")
        if text:
            lines.append(f"[{faq_key}]: {text}")

    city = session.get("city")
    if city:
        lines.append(f"\n--- Офис клиента ({city}) ---")
        lines.append(get_office_block(city, lang, platform="whatsapp"))

    last_intent = session.get("last_intent")
    if last_intent and last_intent != intent:
        lines.append(f"\n[Контекст диалога: ранее обсуждали {last_intent}]")

    return "\n".join(lines)


def _build_messages(
    lang: str,
    session: dict,
    user_text: str,
    city: str | None,
) -> list[dict]:
    kb = build_knowledge_context(lang, session, user_text)
    system = get_agent_system_prompt(lang, city=city)
    messages: list[dict] = [
        {"role": "system", "content": f"{system}\n\n{kb}"},
    ]
    for msg in session.get("conversation_history", [])[-_HISTORY_LIMIT:]:
        role = "user" if msg.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": str(msg.get("text", ""))[:_HISTORY_MSG_CHARS]})
    messages.append({"role": "user", "content": user_text})
    return messages


async def _call_llm(
    messages: list[dict],
    ai: "AIClient",
    *,
    lang: str,
    city: str | None,
) -> str | None:
    settings = get_settings()
    from app.groq_client import GroqClient

    max_tok = settings.local_llm_max_tokens
    provider = settings.effective_ai_provider
    use_groq = provider == "groq" or (
        settings.groq_enabled and settings.is_groq_configured and provider != "together"
    )
    response, err = None, None

    if use_groq and settings.is_groq_configured:
        groq = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_stt_model)
        response, err = await groq.chat(messages, temperature=0.55, max_tokens=max_tok)
    elif provider == "together" and ai:
        response, err = await ai.chat(messages, temperature=0.5, max_tokens=max_tok)
    elif ai:
        try:
            response, err = await asyncio.wait_for(
                ai.chat(messages, temperature=0.55, max_tokens=max_tok),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            err = "local llm timeout"
            response = None

    if (err or not response) and settings.is_groq_configured and not use_groq:
        logger.warning("Primary LLM failed (%s), Groq fallback", err)
        groq = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_stt_model)
        response, err = await groq.chat(messages, temperature=0.55, max_tokens=max_tok)

    if err:
        logger.error("AI agent error: %s", err)
        if "429" in str(err) or "rate_limit" in str(err).lower():
            gemini = get_gemini_client()
            response, gemini_err = await gemini.chat(messages, temperature=0.6)
            if gemini_err:
                logger.error("Gemini fallback failed: %s", gemini_err)
                from app.bot import content

                return content.get_ai_fallback_message(lang, city) + " [DONE]"
        else:
            return None

    return response


async def run_kb_agent(
    text: str,
    session: dict,
    ai: Optional["AIClient"],
) -> str | None:
    """Ответ AI-агента по базе знаний."""
    if not ai:
        return None
    settings = get_settings()
    if not settings.is_ai_configured:
        return None

    found_city = detect_city(text)
    if found_city:
        session["city"] = found_city
        session["city_confirmed"] = True

    lang = session.get("lang", "kk")
    city = session.get("city")
    messages = _build_messages(lang, session, text, city)
    response = await _call_llm(messages, ai, lang=lang, city=city)
    if response:
        logger.info("KB agent reply for '%s': %s...", text[:40], response[:80])
    return response
