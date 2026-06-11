"""
Умный гид к FAQ: не свободный чат, а короткий ответ + один вопрос по кредитной теме.
Приоритет: қазақша. Цель — вернуть клиента к базе знаний / меню 1–7.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

from app.bot.chatbot_ux import get_credit_choice_menu
from app.bot.knowledge_base import PRODUCTS, detect_intent, get_product_info
from app.bot.menu import get_main_menu_text
from app.bot.unclear_input import is_frustration_or_unclear, is_off_topic_message

if TYPE_CHECKING:
    from app.ai_client import AIClient

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)

_MAX_GUIDE_ATTEMPTS = 3

_FOLLOW_UP_MARKERS = (
    "процент", "ставк", "пайыз", "лимит", "срок", "мерзім", "жыл", "лет",
    "сколько", "канша", "қанша", "млн", "сома", "услов", "шарт", "керек",
    "дадите", "берес", "можно", "болама", "неше",
)


def _menu_hint_kk() -> str:
    return (
        "1 — ЖК/ИП · 2 — ТОО · 3 — жеке тұлға · 4 — ипотека · "
        "5 — DAMU · 6 — рефинанс · 7 — менеджер"
    )


def _menu_hint_ru() -> str:
    return (
        "1 — ИП · 2 — ТОО · 3 — физлицо · 4 — ипотека · "
        "5 — DAMU · 6 — рефинанс · 7 — менеджер"
    )


def _city_question(lang: str) -> str:
    if lang == "kk":
        return "❓ *Қай қаладасыз?* (Алматы, Астана, Шымкент, Ақтау)"
    return "❓ *Из какого вы города?* (Алматы, Астана, Шымкент, Актау)"


def _off_topic_redirect(lang: str) -> str:
    if lang == "kk":
        return (
            "🤖 *KOMEK DAMU чат-боты* — тек несие, ипотека, DAMU және рефинанс бойынша.\n\n"
            "❓ *Қай өнім қызықтырады?*\n"
            f"{_menu_hint_kk()}\n\n"
            "Санын жазыңыз (мысалы *3* — жеке несие)."
        )
    return (
        "🤖 *Чат-бот KOMEK DAMU* — только кредиты, ипотека, DAMU и рефинанс.\n\n"
        "❓ *Какой продукт вас интересует?*\n"
        f"{_menu_hint_ru()}\n\n"
        "Напишите цифру (например *3* — кредит для себя)."
    )


def _frustration_redirect(lang: str) -> str:
    if lang == "kk":
        return (
            "🤖 Түсіндім, қарапайым етіп көрейік.\n\n"
            "❓ *Несие кімге керек?*\n"
            "• *3* — өзіңізге (жеке тұлға)\n"
            "• *1* — ЖК/ИП бизнесіне\n"
            "• *2* — ТОО\n"
            "• *4* — ипотека\n\n"
            "Тек бір сан жазыңыз."
        )
    return (
        "🤖 Понял, упростим.\n\n"
        "❓ *Кому нужен кредит?*\n"
        "• *3* — себе (физлицо)\n"
        "• *1* — ИП/бизнес\n"
        "• *2* — ТОО\n"
        "• *4* — ипотека\n\n"
        "Напишите одну цифру."
    )


def _intent_nudge(intent: str, lang: str) -> str | None:
    info = get_product_info(intent, lang)
    if not info:
        return None
    name = info["name"]
    if lang == "kk":
        return (
            f"📋 *{name}* бойынша көмектесемін.\n\n"
            "❓ *Нақтырақ не білгіңіз келеді?* "
            "Лимит, пайыз, мерзім немесе сома — жазыңыз."
        )
    return (
        f"📋 Помогу по *{name}*.\n\n"
        "❓ *Что уточнить?* Лимит, ставка, срок или сумма — напишите."
    )


def try_faq_guide_reply(
    text: str,
    lang: str,
    session: dict,
    *,
    platform: str = "telegram",
) -> Optional[str]:
    """
    Правило-базовый гид к FAQ. Без LLM.
    """
    _ = platform
    t = (text or "").strip()
    if not t:
        return _off_topic_redirect(lang)

    attempts = int(session.get("guide_attempts") or 0)
    if attempts >= _MAX_GUIDE_ATTEMPTS:
        session["guide_attempts"] = 0
        return None

    if is_frustration_or_unclear(t) and not is_off_topic_message(t):
        session["guide_attempts"] = attempts + 1
        return _frustration_redirect(lang)

    if is_off_topic_message(t):
        session["guide_attempts"] = attempts + 1
        return _off_topic_redirect(lang)

    if not session.get("city_confirmed"):
        session["guide_attempts"] = attempts + 1
        return _city_question(lang)

    intent = detect_intent(t, session) or session.get("last_intent")
    low = t.lower()

    if intent and any(m in low for m in _FOLLOW_UP_MARKERS) and len(_WORD.findall(low)) <= 8:
        nudge = _intent_nudge(intent, lang)
        if nudge:
            session["guide_attempts"] = attempts + 1
            session["last_intent"] = intent
            return nudge

    if not intent:
        session["guide_attempts"] = attempts + 1
        if lang == "kk":
            return (
                "🤖 *KOMEK DAMU* — несие және ипотека бойынша кеңес.\n\n"
                "❓ *Қай бөлім керек?*\n"
                f"{get_main_menu_text(lang)}\n\n"
                "Тек санын жазыңыз."
            )
        return get_credit_choice_menu(lang)

    session["guide_attempts"] = attempts + 1
    session["last_intent"] = intent
    return _intent_nudge(intent, lang) or _off_topic_redirect(lang)


def _faq_guide_system_prompt(lang: str, session: dict) -> str:
    product_lines = []
    for key, p in PRODUCTS.items():
        name = p.name_kk if lang == "kk" else p.name_ru
        product_lines.append(f"- {key}: {name}")
    products = "\n".join(product_lines)
    state = session.get("state", "idle")
    city = session.get("city") or "?"
    last_intent = session.get("last_intent") or "—"

    if lang == "kk":
        return (
            "Сен KOMEK DAMU банкінің бағыттаушы чат-ботысың.\n"
            "МАҚСАТ: клиентті FAQ/өнімдерге қайтару. Еркін әңгіме ЖОҚ.\n\n"
            "ЕРЕЖЕ:\n"
            "1) ТЕК қазақша, 2-3 қысқа сөйлем.\n"
            "2) Бір ғана нақты сұрақ — өнім (1-7), қала, немесе сома.\n"
            "3) Кредит/ипотека/DAMU тақырыбынан тыс сұрақтарға жауап берме — қайта бағытта.\n"
            "4) Факт ойлап таппа, тек сұрақ қой немесе мәзірге жібер.\n"
            "5) Мәзір: 1-ЖК, 2-ТОО, 3-жеке, 4-ипотека, 5-DAMU, 6-рефинанс, 7-менеджер.\n"
            f"Күй: {state}, қала: {city}, соңғы өнім: {last_intent}.\n"
            f"Өнімдер:\n{products}"
        )
    return (
        "Ты направляющий чат-бот KOMEK DAMU.\n"
        "ЦЕЛЬ: вернуть клиента к FAQ/продуктам. Свободный чат ЗАПРЕЩЁН.\n\n"
        "ПРАВИЛА:\n"
        "1) ТОЛЬКО русский, 2-3 коротких предложения.\n"
        "2) Один уточняющий вопрос — продукт (1-7), город или сумма.\n"
        "3) Вне темы кредитов — не отвечай по сути, перенаправь.\n"
        "4) Не выдумывай факты — только вопрос или меню.\n"
        "5) Меню: 1-ИП, 2-ТОО, 3-физлицо, 4-ипотека, 5-DAMU, 6-рефинанс, 7-менеджер.\n"
        f"Состояние: {state}, город: {city}, продукт: {last_intent}.\n"
        f"Продукты:\n{products}"
    )


async def try_faq_guide_llm(
    text: str,
    lang: str,
    session: dict,
    ai: "AIClient | None",
) -> Optional[str]:
    """Короткий LLM-гид к FAQ (Together/Groq/local)."""
    if not ai:
        return None

    from app.config import get_settings
    from app.groq_client import GroqClient

    settings = get_settings()
    if not settings.faq_guide_llm_enabled:
        return None

    messages = [
        {"role": "system", "content": _faq_guide_system_prompt(lang, session)},
        {"role": "user", "content": text[:400]},
    ]
    max_tok = min(settings.local_llm_max_tokens, 180)
    provider = settings.effective_ai_provider
    response, err = None, None

    if provider == "together" and settings.is_together_configured:
        response, err = await ai.chat(messages, temperature=0.2, max_tokens=max_tok)
    elif provider == "groq" and settings.is_groq_configured:
        groq = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_stt_model)
        response, err = await groq.chat(messages, temperature=0.2, max_tokens=max_tok)
    elif ai:
        response, err = await ai.chat(messages, temperature=0.2, max_tokens=max_tok)

    if err or not response:
        logger.warning("FAQ guide LLM failed: %s", err)
        return None

    cleaned = response.strip().replace("[GUIDE]", "").replace("[DONE]", "").strip()
    if len(cleaned) < 8:
        return None
    logger.info("FAQ guide LLM: %s", cleaned[:80])
    return cleaned


async def build_faq_guide_reply(
    text: str,
    lang: str,
    session: dict,
    ai: "AIClient | None",
    *,
    platform: str = "telegram",
) -> str:
    """FAQ → правила → LLM-гид → универсальный fallback."""
    from app.bot.menu import get_text_fallback_reply

    core = text.strip()
    guide = try_faq_guide_reply(core, lang, session, platform=platform)
    if guide:
        return guide

    llm = await try_faq_guide_llm(core, lang, session, ai)
    if llm:
        return llm

    session.pop("guide_attempts", None)
    return get_text_fallback_reply(lang, platform=platform)
