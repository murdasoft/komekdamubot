"""
Main handler for KOMEK DAMU bot.
Supports: Telegram + WhatsApp, Russian + Kazakh, Voice messages.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional, List
from collections import defaultdict

from app.config import get_settings
from app.ai_client import AIClient
from app.prompts import get_system_prompt
from app.offices import detect_city
from app.bot.text_utils import is_pure_greeting, strip_leading_greeting
from app.bot.response_builder import finalize_bot_response
from app.gemini_client import GeminiClient, get_gemini_client
from app.bot.faq_matcher import try_fast_response
from app.bot.loan_calc import calculate_loan_payment, format_calculator_result
from app.bot.knowledge_base import (
    detect_intent, get_product_info, get_faq_answer,
    PRODUCTS, FAQ_ANSWERS
)
from app.bot.flows import (
    get_flow_for_product, get_first_step, FlowStep,
    validate_phone, validate_number, validate_yes_no
)
from app.bot import content
from app.bot.lang_detect import detect_message_lang
from app.supabase_client import save_session, load_session, log_message, create_lead

logger = logging.getLogger(__name__)

# In-memory session storage (replace with DB for production)
_sessions: Dict[str, Dict] = defaultdict(lambda: {
    "state": "idle",  # idle, in_flow, handoff
    "lang": "ru",
    "product": None,
    "flow_step": None,
    "data": {},
    "last_message_id": None,
    "contact_name": None,
    "handoff_until": 0,
    "conversation_history": [],  # Store last messages for context
    "context_topic": None,  # Current conversation topic
    "message_count": 0,  # Count messages for auto-handoff
    "platform": "telegram",  # telegram or whatsapp
})

# Compact random responses for small talk (single response per category)
SMALL_TALK = {
    "ru": {
        "greeting": "Здравствуйте! 👋",
        "thanks": "Пожалуйста! Всегда рад помочь 🤝",
        "how_are_you": "Всё отлично, готов помочь с финансами! 💪",
        "bye": "До свидания! Обращайтесь ещё 👋",
        "unknown": "Интересный вопрос! Давайте разберёмся 🤔",
    },
    "kk": {
        "greeting": "Сәлем! 👋",
        "thanks": "Өтінемін! Көмектесуге дайынмын 🤝",
        "how_are_you": "Барлық жақсы, қаржы бойынша көмектесуге дайынмын! 💪",
        "bye": "Сау болыңыз! Келесі жолы хабарласыңыз 👋",
        "unknown": "Қызықты сұрақ! Келіңіз, талдайық 🤔",
    },
}

def get_small_talk_response(category: str, lang: str = "ru") -> str:
    """Get small talk response for category."""
    return SMALL_TALK.get(lang, SMALL_TALK["ru"]).get(category, SMALL_TALK["ru"]["unknown"])

def _has_business_content(text_lower: str) -> bool:
    """Сообщение про продукт/сумму — не считать чистым приветствием."""
    hints = (
        "кредит", "ипотек", "несие", "даму", "рефинанс", "тенге", "тг",
        "млн", "миллион", "займ", "сумм", "ставк", "процент", "взять", "оформ",
    )
    if any(h in text_lower for h in hints):
        return True
    digits = re.sub(r"\D", "", text_lower)
    return len(digits) >= 5


def detect_small_talk_intent(text: str) -> str | None:
    """Detect if user is making small talk vs asking about products."""
    text_lower = text.lower().strip()
    if not text_lower:
        return None

    if _has_business_content(text_lower):
        return None
    if not is_pure_greeting(text):
        return None

    # «пока ещё не знаю» — не прощание; только явное «пока» в конце или отдельной фразой
    if re.search(r"(?:^|\s)пока\s*(?:[!?.]|$)", text_lower) and not re.search(
        r"пока\s+(?:еще|ещё|не|что|так|сейчас|здесь)", text_lower
    ):
        return "bye"

    greetings = ["привет", "здравствуй", "сәлем", "сәлеметсіз", "hi", "hello", "hey"]
    thanks = ["спасибо", "благодар", "рахмет", "рақмет", "спс", "thanks", "thank you"]
    how_are_you = ["как дела", "как ты", "қалайсыз", "қалай", "how are you", "как поживаешь"]
    bye = ["до свидания", "сау бол", "bye", "goodbye", "до встречи"]

    for phrase in greetings:
        if phrase in text_lower:
            return "greeting"
    for phrase in thanks:
        if phrase in text_lower:
            return "thanks"
    for phrase in how_are_you:
        if phrase in text_lower:
            return "how_are_you"
    for phrase in bye:
        if phrase in text_lower:
            return "bye"

    return None


def detect_calculator_intent(text: str) -> tuple[bool, dict | None]:
    """Detect if user wants to calculate loan payment.
    
    Returns:
        (is_calculation, params_dict or None)
        params_dict: {'amount', 'rate', 'years', 'product'}
    """
    text_lower = text.lower()
    
    # Keywords for calculation
    calc_keywords = [
        "рассчитай", "сколько платить", "платеж", "калькулятор", "выплата",
        "посчитай", "сколько будет", "ежемесячный", "аннуитет",
        "если возьму", "хочу взять", "взять хочу", "хочу взять", "взять кредит",
        "кредит на", "планирую взять", "нужен кредит", "нужно взять",
        "есіптей", "есептеу", "түсім", "калькулятор", "алсам", "алмақпын",
    ]
    
    has_calc_keyword = any(kw in text_lower for kw in calc_keywords)
    
    if not has_calc_keyword:
        return False, None
    
    # Extract numbers (amount, rate, term)
    # Match patterns like: 200 млн, 200000, 12.6%, 3 года, 36 месяцев
    numbers = re.findall(r'\d+(?:[.,]\d+)?', text)
    
    # Product detection - use word boundaries to avoid partial matches
    product = None
    words = set(re.findall(r'\b\w+\b', text_lower))
    
    if words & {"тоо", "төо", "тово", "too"}:
        product = "too"
    elif words & {"ипотека", "ипотек", "ипотекасы", "mortgage", "үй", "квартира"}:
        product = "mortgage"
    elif words & {"ип", "жеке", "кәсіпкер", "иң", "индивидуальный"}:
        product = "ip"
    elif words & {"физлицо", "физическое", "физ", "жеке", "тұлға"}:
        product = "personal"
    
    # Default values based on product
    defaults = {
        "too": {"amount": 200_000_000, "rate": 12.6, "years": 3},
        "ip": {"amount": 40_000_000, "rate": 21.0, "years": 10},  # ИП только с залогом (ДАМУ)
        "mortgage": {"amount": 50_000_000, "rate": 7.0, "years": 25},
        "personal": {"amount": 25_000_000, "rate": 21.0, "years": 5},
    }
    
    params = {
        "amount": None,
        "rate": None,
        "years": None,
        "product": product,
    }
    
    # Parse extracted numbers
    for num_str in numbers:
        num = float(num_str.replace(',', '.'))
        
        # Amount: if > 1000 (assume in thousands) or has "млн", "миллион"
        if num > 1000 and params["amount"] is None:
            if "млн" in text_lower or "миллион" in text_lower or "миллион" in text_lower:
                params["amount"] = num * 1_000_000
            elif num > 1_000_000:
                params["amount"] = num
            elif num > 100_000:
                params["amount"] = num
        
        # Rate: if has % or between 2-50
        if ("%" in text or (2 <= num <= 50)) and params["rate"] is None:
            params["rate"] = num
        
        # Years: if has "год", "лет", "жыл" or between 1-30 without other context
        year_keywords = ["год", "лет", "года", "жыл", "жылды", "летний", "year"]
        if any(yk in text_lower for yk in year_keywords) or (1 <= num <= 30 and params["years"] is None):
            if num <= 30:  # Assume years if <= 30
                params["years"] = int(num)
    
    # Apply defaults for missing values
    if product and product in defaults:
        for key, val in defaults[product].items():
            if params[key] is None:
                params[key] = val
    
    # Must have at least amount to calculate
    if params["amount"] is None:
        return False, None
    
    # Fill remaining defaults
    if params["rate"] is None:
        params["rate"] = 15.0
    if params["years"] is None:
        params["years"] = 3
    
    return True, params


async def _get_session(chat_id: str) -> Dict:
    """Get session from Supabase or memory."""
    # Try to load from Supabase first
    db_session = await load_session(chat_id)
    if db_session:
        # Merge with memory session
        _sessions[chat_id].update(db_session)
    
    session = _sessions[chat_id]
    # Ensure all fields exist
    if "conversation_history" not in session:
        session["conversation_history"] = []
    if "platform" not in session:
        session["platform"] = "telegram"
    if "context_topic" not in session:
        session["context_topic"] = None
    return session


def _reset_session(chat_id: str, platform: str = "telegram"):
    """Reset session to initial state."""
    _sessions[chat_id] = {
        "state": "idle",
        "lang": "ru",
        "product": None,
        "flow_step": None,
        "data": {},
        "last_message_id": None,
        "contact_name": None,
        "handoff_until": 0,
        "platform": platform,
    }


def _is_handoff_active(session: Dict) -> bool:
    """Check if session is in handoff mode."""
    if session.get("state") == "handoff":
        until = session.get("handoff_until", 0)
        if until > time.time():
            return True
        # Handoff expired, reset
        session["state"] = "idle"
        session["handoff_until"] = 0
    return False


async def _transcribe_voice(
    audio_bytes: bytes,
    ai: AIClient | None,
    lang_hint: str | None = None
) -> tuple[str | None, str]:
    """Transcribe voice: local faster-whisper first; Groq only if GROQ_ENABLED=true."""
    if not audio_bytes:
        return None, lang_hint or "ru"

    langs_to_try: list[str | None] = []
    for lang in (lang_hint, "ru", "kk", None):
        if lang not in langs_to_try:
            langs_to_try.append(lang)

    settings = get_settings()
    groq_first = (
        settings.effective_ai_provider == "groq"
        or (settings.groq_enabled and settings.is_groq_configured)
    ) and settings.effective_ai_provider != "together"

    async def _try_local() -> tuple[str | None, str | None]:
        if not ai:
            return None, None
        for lang in langs_to_try:
            text, err = await ai.transcribe(audio_bytes, language=lang, filename="voice.ogg")
            if text:
                return text, lang or ai.detect_language_simple(text)
            if err:
                logger.warning("Local Whisper failed lang=%s: %s", lang, err)
        return None, None

    async def _try_groq() -> tuple[str | None, str | None]:
        if not settings.is_groq_configured:
            return None, None
        from app.groq_client import GroqClient
        groq = GroqClient(
            settings.groq_api_key,
            model=settings.groq_model,
            stt_model=settings.groq_stt_model,
        )
        for lang in langs_to_try:
            text, err = await groq.transcribe(audio_bytes, filename="voice.ogg", language=lang)
            if text:
                return text, lang or groq.detect_language_simple(text)
            if err:
                logger.warning("Groq STT failed lang=%s: %s", lang, err)
        return None, None

    if groq_first:
        text, detected = await _try_groq()
        if text:
            logger.info("Voice via Groq STT (lang=%s): %s", detected, text[:60])
            return text, detected or "ru"
        text, detected = await _try_local()
        if text:
            logger.info("Voice via local STT fallback (lang=%s): %s", detected, text[:60])
            return text, detected or "ru"
    else:
        text, detected = await _try_local()
        if text:
            logger.info("Voice via local STT (lang=%s): %s", detected, text[:60])
            return text, detected or "ru"
        text, detected = await _try_groq()
        if text:
            logger.info("Voice via Groq STT fallback (lang=%s): %s", detected, text[:60])
            return text, detected or "ru"

    return None, lang_hint or "ru"


def _build_summary(data: Dict, product_key: str, lang: str) -> str:
    """Build lead summary for manager notification."""
    product = get_product_info(product_key, lang)
    product_name = product["name"] if product else product_key
    
    lines = [
        f"🆕 *Новая заявка / Жаңа өтініш*",
        f"",
        f"📋 *Продукт:* {product_name}",
        f"🌐 *Язык:* {'Русский' if lang == 'ru' else 'Қазақша'}",
    ]
    
    # Add collected data
    for key, value in data.items():
        if key.startswith("_"):
            continue
        label = key.replace("_", " ").title()
        lines.append(f"• {label}: {value}")
    
    return "\n".join(lines)


async def _send_to_bitrix24(data: Dict, product_key: str, chat_id: str, lang: str):
    """Send lead to Bitrix24."""
    settings = get_settings()
    if not settings.bitrix24_webhook_url:
        logger.info("Bitrix24 not configured, skipping")
        return
    
    import httpx
    
    payload = {
        "source": "komek_damu_bot",
        "product": product_key,
        "lang": lang,
        "chat_id": chat_id,
        "data": data,
        "created_at": int(time.time()),
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(settings.bitrix24_webhook_url, json=payload)
    except Exception as e:
        logger.exception("Bitrix24 send failed: %s", e)


async def _notify_manager(message: str, chat_id: str, platform: str = "telegram", session: Dict | None = None):
    """Send notification to manager via Telegram with reply instructions."""
    settings = get_settings()
    if not settings.telegram_alert_chat_id or not settings.telegram_bot_token:
        return
    
    from app.telegram_api import TelegramClient
    api = TelegramClient(settings.telegram_bot_token)
    
    # Build history snippet
    history_text = ""
    if session:
        history = session.get("conversation_history", [])[-5:]
        if history:
            lines = []
            for m in history:
                role = "👤" if m["role"] == "user" else "🤖"
                lines.append(f"{role} {m['text'][:100]}")
            history_text = "\n\n📜 *Последние сообщения:*\n" + "\n".join(lines)
    
    full_message = (
        f"{message}"
        f"\n\n👤 Chat ID: `{chat_id}`\n📱 Platform: {platform}"
        f"{history_text}"
        f"\n\n💬 *Чтобы ответить пользователю:*\n`/reply {chat_id} ваш текст`"
    )
    await api.send_message(settings.telegram_alert_chat_id, full_message)


async def _handle_ai_response(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """Get AI response for free-text queries."""
    if not ai:
        return None
    lang = session.get("lang", "ru")
    system_prompt = get_system_prompt(lang)
    
    # Build context from knowledge base
    context = "Доступные продукты:\n"
    for key, product in PRODUCTS.items():
        name = product.name_ru if lang == "ru" else product.name_kk
        context += f"- {name}\n"
    
    messages = [
        {"role": "system", "content": system_prompt + "\n\n" + context},
        {"role": "user", "content": text},
    ]
    
    response, err = await ai.chat(messages, temperature=0.7)
    if err:
        logger.error("AI error: %s", err)
        return None
    return response


def _detect_lang(text: str) -> str:
    return detect_message_lang(text)


_detect_language = _detect_lang  # alias for tests


def _update_session_lang(text: str, session: Dict) -> str:
    """kk только при явных признаках; русский текст → сразу ru."""
    detected = detect_message_lang(text)
    if detected == "kk":
        session["lang"] = "kk"
    else:
        session["lang"] = "ru"
    session.pop("lang_streak_candidate", None)
    session.pop("lang_streak", None)
    return session["lang"]


async def _get_bot_reply(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """FAQ без LLM, иначе Together/Groq."""
    settings = get_settings()
    lang = _update_session_lang(text, session)
    core = strip_leading_greeting(text)
    if settings.fast_faq_enabled:
        fast = try_fast_response(core, lang, session.get("city"))
        if fast:
            logger.info("Fast FAQ hit for: %s", core[:40])
            return fast
    raw = await _handle_ai_response_with_context(text, session, ai)
    if not raw:
        return None
    return finalize_bot_response(raw, text, lang, session.get("city"))


async def _handle_ai_response_with_context(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """Get AI response with conversation history for context understanding."""
    if not ai:
        return None
    lang = session.get("lang", "ru")
    found_city = detect_city(text)
    if found_city:
        session["city"] = found_city
    city = session.get("city")
    system_prompt = get_system_prompt(lang, city=city)

    intent = detect_intent(text)
    if intent:
        info = get_product_info(intent, lang)
        if info:
            context = (
                f"Продукт: {info['name']}. {info['description']}. "
                f"Условия: {info['conditions'][:400]}"
            )
        else:
            context = ""
    else:
        names = [
            (p.name_ru if lang == "ru" else p.name_kk)
            for p in PRODUCTS.values()
        ]
        context = "Продукты: " + ", ".join(names)

    history = session.get("conversation_history", [])
    messages = [{"role": "system", "content": system_prompt + "\n\n" + context}]

    for msg in history[-2:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["text"][:300]})

    messages.append({"role": "user", "content": text})

    settings = get_settings()
    from app.groq_client import GroqClient
    response, err = None, None
    max_tok = settings.local_llm_max_tokens
    provider = settings.effective_ai_provider
    use_groq = provider == "groq" or (
        settings.groq_enabled and settings.is_groq_configured and provider != "together"
    )

    if provider == "together" and ai:
        response, err = await ai.chat(messages, temperature=0.5, max_tokens=max_tok)
    elif use_groq and settings.is_groq_configured:
        groq = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_stt_model)
        response, err = await groq.chat(messages, temperature=0.6, max_tokens=max_tok)
    elif ai:
        import asyncio
        try:
            response, err = await asyncio.wait_for(
                ai.chat(messages, temperature=0.6, max_tokens=max_tok),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            err = "local llm timeout"
            response = None
    if (err or not response) and settings.is_groq_configured and not use_groq:
        logger.warning("Local LLM failed (%s), Groq fallback", err)
        groq = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_stt_model)
        response, err = await groq.chat(messages, temperature=0.6, max_tokens=max_tok)
    if err:
        logger.error("AI chat error: %s", err)
        if "429" in str(err) or "rate_limit" in str(err).lower():
            logger.info("Rate limit, trying Gemini fallback...")
            gemini = get_gemini_client()
            response, gemini_err = await gemini.chat(messages, temperature=0.7)
            if gemini_err:
                logger.error("Gemini fallback also failed: %s", gemini_err)
                return content.get_ai_fallback_message(lang, city) + " [DONE]"
            logger.info(f"Gemini fallback success: '{response[:100] if response else 'None'}...'")
            return response
        return None
    logger.info(f"Groq AI response: '{response[:100] if response else 'None'}...' for text='{text[:30]}...'")
    return response


async def _process_flow_step(
    chat_id: str,
    text: str,
    session: Dict,
    send_message_func,
    ai: AIClient | None,
) -> bool:
    """
    Process flow step. Returns True if flow should continue.
    """
    product_key = session.get("product")
    flow_step_key = session.get("flow_step")
    lang = session.get("lang", "ru")
    
    if not product_key or not flow_step_key:
        return False
    
    flow = get_flow_for_product(product_key)
    if not flow:
        return False
    
    step = flow.get(flow_step_key)
    if not step:
        return False
    
    # Allow escape from flow: "стоп", "отмена", "выход", "stop", "cancel"
    exit_words = ["стоп", "отмена", "выход", "stop", "cancel", "тоқта", "болдырмау"]
    if any(w in text.lower() for w in exit_words):
        _reset_session(chat_id, session.get("platform", "telegram"))
        exit_msg = (
            "Хорошо, анкета отменена. Напишите ваш вопрос или «меню» для списка услуг."
            if lang == "ru" else
            "Жарайды, анкета тоқтатылды. Сұрағыңызды жазыңыз немесе қызметтер тізімі үшін «мәзір» деп жазыңыз."
        )
        await send_message_func(exit_msg)
        return False
    
    # Validate input if validator exists
    validated_value = text
    if step.validate:
        is_valid, validated = step.validate(text)
        if not is_valid:
            # If looks like off-topic free text (not a number/yes/no) — answer via AI and stay in flow
            if ai and len(text) > 5 and not any(c.isdigit() for c in text):
                ai_reply = await ai.chat(
                    system=(
                        "Ты консультант KOMEK DAMU. Пользователь заполняет анкету на кредит и написал вопрос. "
                        "Ответь коротко (1-2 предложения) и напомни ему продолжить заполнение анкеты."
                    ),
                    messages=[{"role": "user", "content": text}],
                )
                if ai_reply:
                    question = step.question_ru if lang == "ru" else step.question_kk
                    await send_message_func(f"{ai_reply}\n\n{question}")
                    return True
            # Invalid input, ask again
            question = step.question_ru if lang == "ru" else step.question_kk
            await send_message_func(
                f"❌ {'Неверный формат. Попробуйте еще раз.' if lang == 'ru' else 'Қате формат. Қайтадан көріңіз.'}\n\n{question}"
            )
            return True
        validated_value = validated
    
    # Store validated data
    session["data"][step.key] = validated_value
    
    # Check for payment delays - reject if yes
    if step.key == "has_delays" and validated_value == "да":
        lang = session.get("lang", "ru")
        reject_msg = (
            "❌ *К сожалению, мы не можем выдать кредит при наличии открытых просрочек.*\n\n"
            "Пожалуйста, закройте просрочки и обратитесь снова.\n\n"
            "Для сложных случаев нажмите 7 — «Связаться с оператором»."
            if lang == "ru" else
            "❌ *Кешігу бар болса, несие бере алмаймыз.*\n\n"
            "Кешігуіңізді жабыңыз және қайтадан хабарласыңыз.\n\n"
            "Күрделі жағдайлар үшін 7 басыңыз — «Оператормен байланыс»."
        )
        await send_message_func(reject_msg)
        _reset_session(chat_id, session.get("platform", "telegram"))
        return False
    
    # Move to next step
    next_step_key = step.next_step
    if next_step_key == "done" or not next_step_key:
        # Flow completed
        await _finish_flow(chat_id, session, send_message_func, ai)
        return False
    
    # Set next step
    session["flow_step"] = next_step_key
    next_step = flow.get(next_step_key)
    if next_step:
        question = next_step.question_ru if lang == "ru" else next_step.question_kk
        await send_message_func(question)
    
    return True


async def _finish_flow(
    chat_id: str,
    session: Dict,
    send_message_func,
    ai: AIClient | None,
):
    """Complete flow and send lead to manager."""
    product_key = session.get("product", "unknown")
    lang = session.get("lang", "ru")
    data = session.get("data", {})
    platform = session.get("platform", "telegram")
    
    # Build summary
    summary = _build_summary(data, product_key, lang)
    
    # Send to Bitrix24
    await _send_to_bitrix24(data, product_key, chat_id, lang)
    
    # Notify manager
    await _notify_manager(summary, chat_id, platform)
    
    # Thank you message
    thanks_msg = (
        "✅ *Заявка принята!*\n\n"
        "Менеджер свяжется с вами в ближайшее время.\n\n"
        "Если нужно — напишите /start для нового обращения."
        if lang == "ru" else
        "✅ *Өтініш қабылданды!*\n\n"
        "Менеджер жақын арада хабарласады.\n\n"
        "Қажет болса — жаңа өтініш үшін /start жазыңыз."
    )
    await send_message_func(thanks_msg)
    
    # Reset session
    _reset_session(chat_id, platform)


async def _start_product_flow(
    chat_id: str,
    product_key: str,
    session: Dict,
    send_message_func,
):
    """Start product selection flow."""
    flow = get_flow_for_product(product_key)
    if not flow:
        logger.error(f"No flow found for product: {product_key}")
        return
    
    lang = session.get("lang", "ru")
    first_step_key = get_first_step(flow)
    if not first_step_key:
        return
    
    session["state"] = "in_flow"
    session["product"] = product_key
    session["flow_step"] = first_step_key
    
    first_step = flow[first_step_key]
    question = first_step.question_ru if lang == "ru" else first_step.question_kk
    
    # Show product info first
    product_info = get_product_info(product_key, lang)
    if product_info:
        intro = (
            f"*{product_info['name']}*\n\n"
            f"{product_info['description']}\n\n"
            f"📋 *Условия / Шарттар:*\n{product_info['conditions']}"
        )
        await send_message_func(intro)
    
    await send_message_func(question)


async def handle_telegram_update(
    body: Dict[str, Any],
    tg_client,
    ai: AIClient | None,
):
    """Handle Telegram webhook update."""
    from app.telegram_api import (
        extract_update_info, get_message_id,
        is_voice_message, get_voice_file_id, get_file_url
    )
    
    chat_id, text, sender_name, callback_id = extract_update_info(body)
    if not chat_id:
        return
    
    msg_id = get_message_id(body)
    
    # Handle /reply command from manager (proxy reply to user)
    if text and text.strip().startswith("/reply "):
        settings = get_settings()
        # Only allow from manager chat
        if str(chat_id) == str(settings.telegram_alert_chat_id):
            parts = text.strip().split(" ", 2)
            if len(parts) >= 3:
                target_chat_id = parts[1]
                reply_text = parts[2]
                try:
                    await tg_client.send_message(target_chat_id, f"👨‍💼 {reply_text}")
                    await tg_client.send_message(chat_id, f"✅ Отправлено пользователю {target_chat_id}")
                    logger.info(f"Manager reply sent to {target_chat_id}")
                except Exception as e:
                    await tg_client.send_message(chat_id, f"❌ Ошибка: {e}")
            else:
                await tg_client.send_message(chat_id, "Формат: /reply CHAT_ID текст")
        return

    # Handle /start immediately — force language selection first
    if text and text.strip() in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        if not chat_id or chat_id == "None":
            logger.error(f"Invalid chat_id for /start: {chat_id}")
            return
        _reset_session(chat_id, "tg")
        _sessions[chat_id]["state"] = "selecting_lang"
        _sessions[chat_id]["platform"] = "tg"
        await save_session(chat_id, _sessions[chat_id])
        lang_prompt = (
            "Сәлеметсіз бе! Мен KOMEK DAMU кеңесшісімін 👋\n"
            "Здравствуйте! Я консультант KOMEK DAMU 👋\n\n"
            "Несие, ипотека, бизнес қаржыландыру бойынша сұрақтарыңызды қойыңыз — жауап беремін.\n"
            "Задавайте вопросы по кредитам, ипотеке, бизнес-финансированию — отвечу.\n\n"
            "1 — Қазақша\n"
            "2 — Русский"
        )
        logger.info(f"Sending language selection to chat_id={chat_id}")
        try:
            await tg_client.send_message(chat_id, lang_prompt, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send /start response: {e}")
        return
    
    # Handle language selection (1 or 2)
    if text and text.strip() in ["1", "2"]:
        session = await _get_session(chat_id)
        if session.get("state") == "selecting_lang":
            selected_lang = "kk" if text.strip() == "1" else "ru"
            session["lang"] = selected_lang
            session["state"] = "idle"
            await save_session(chat_id, session)
            
            if selected_lang == "kk":
                greeting = (
                    "Сәлеметсіз бе! Мен KOMEK DAMU кеңесшісімін 👋\n\n"
                    "Несие, ипотека, бизнес қаржыландыру бойынша сұрақтарыңызды қойыңыз — жауап беремін.\n\n"
                    "📋 Қызметтер тізімі: /menu"
                )
            else:
                greeting = (
                    "Здравствуйте! Я консультант KOMEK DAMU 👋\n\n"
                    "Задавайте вопросы по кредитам, ипотеке, бизнес-финансированию — отвечу.\n\n"
                    "📋 Список услуг: /menu"
                )
            await tg_client.send_message(chat_id, greeting)
            return

    # После /start можно сразу писать вопрос — не обязательно жать 1 или 2
    session_early = await _get_session(chat_id)
    if session_early.get("state") == "selecting_lang" and text and text.strip() not in ["1", "2"]:
        t = text.strip()
        session_early["lang"] = "kk" if any(c in _KK_CHARS for c in t.lower()) else "ru"
        session_early["state"] = "idle"
        await save_session(chat_id, session_early)
        logger.info("Auto language %s from text, processing: %s", session_early["lang"], text[:40])
    
    # Handle 99 for language re-selection (from menu)
    if text and text.strip() == "99":
        session = await _get_session(chat_id)
        session["state"] = "selecting_lang"
        await save_session(chat_id, session)
        lang_prompt = (
            "Тілді ауыстыру / Сменить язык:\n\n"
            "1 — Қазақша\n"
            "2 — Русский"
        )
        await tg_client.send_message(chat_id, lang_prompt)
        return
    
    session = await _get_session(chat_id)
    
    if sender_name:
        session["contact_name"] = sender_name
    
    # After office redirect — always reset and answer, never stay silent
    if session.get("state") == "office_directed" and (text or "").strip() not in ["/start", "/menu"]:
        session["state"] = "idle"

    # Check handoff
    if _is_handoff_active(session):
        # Check for "бот" or "bot" to release
        if text and text.lower() in ["бот", "bot", "жүйе", "system"]:
            session["state"] = "idle"
            session["handoff_until"] = 0
            await tg_client.send_message(
                chat_id,
                content.HANDOFF_RELEASED_RU if session.get("lang", "ru") == "ru" else content.HANDOFF_RELEASED_KK
            )
            return
        # Still answer questions via AI even in handoff
        if text:
            lang_h = session.get("lang", "ru")
            ai_response = await _handle_ai_response_with_context(text.strip(), session, ai)
            if ai_response:
                await tg_client.send_message(chat_id, ai_response)
            else:
                note = (
                    "Менеджер скоро ответит. Напишите *бот* чтобы вернуться к боту."
                    if lang_h == "ru" else
                    "Менеджер жақын арада жауап береді. Ботқа оралу үшін *бот* жазыңыз."
                )
                await tg_client.send_message(chat_id, note)
        return
    
    # Handle voice message
    if is_voice_message(body):
        settings = get_settings()
        if not settings.is_ai_configured and not settings.is_groq_configured:
            await tg_client.send_message(
                chat_id,
                "Голосовые сообщения временно недоступны. Пожалуйста, напишите текстом."
            )
            return

        lang_ui = session.get("lang", "ru")
        await tg_client.send_message(
            chat_id,
            "🎤 Слушаю голосовое, секунду..."
            if lang_ui == "ru" else "🎤 Дауыстық хабарламаны тыңдап жатырмын..."
        )

        file_id = get_voice_file_id(body)
        if file_id:
            file_info = await tg_client.get_file(file_id)
            if file_info and file_info.get("result", {}).get("file_path"):
                file_path = file_info["result"]["file_path"]
                file_url = get_file_url(settings.telegram_bot_token, file_path)

                import httpx
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.get(file_url)
                    audio_bytes = r.content

                transcribed, detected_lang = await _transcribe_voice(
                    audio_bytes, ai, session.get("lang") if session.get("lang") in ("ru", "kk") else "ru"
                )

                logger.info("Voice result chat=%s: lang=%s text=%s", chat_id, detected_lang, transcribed)

                if transcribed and transcribed.strip():
                    # Язык от Whisper/Groq; словарь только если есть казахские буквы
                    if any(c in _KK_CHARS for c in transcribed.lower()):
                        session["lang"] = "kk"
                    elif detected_lang in ("ru", "kk"):
                        session["lang"] = detected_lang
                    elif session.get("lang") not in ("ru", "kk"):
                        session["lang"] = "ru"
                    session["state"] = "idle"
                    text = transcribed.strip()
                    logger.info("Voice OK: lang=%s text=%s", session["lang"], text[:50])
                elif transcribed:
                    await tg_client.send_message(chat_id, "Не расслышал. Повторите, пожалуйста.")
                    return
                else:
                    await tg_client.send_message(
                        chat_id,
                        content.LANG_DETECT_FAILED_RU if lang_ui == "ru" else content.LANG_DETECT_FAILED_KK
                    )
                    return
    
    if not text:
        return
    
    text_stripped = text.strip()
    lang = session.get("lang", "ru")
    
    # Handle /start or menu return
    if text_stripped in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        return
    
    # Auto-detect language from text for voice/any input
    kk_chars = set('әіңғүұқөһ')
    if any(c in text_stripped.lower() for c in kk_chars):
        session["lang"] = "kk"
        lang = "kk"
        
        session["conversation_history"].append({
            "role": "user",
            "text": text_stripped,
            "timestamp": time.time()
        })
        ai_response = await _handle_ai_response_with_context(text_stripped, session, ai)
        if ai_response:
            session["conversation_history"].append({
                "role": "assistant",
                "text": ai_response,
                "timestamp": time.time()
            })
            await tg_client.send_message(chat_id, ai_response)
        else:
            await tg_client.send_message(chat_id, content.get_ai_fallback_message(lang, session.get("city")))
        await save_session(chat_id, session)
        return
    
    # Handle operator request
    if any(word in text_stripped.lower() for word in ["оператор", "менеджер", "человек", "маман", "админ"]):
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await tg_client.send_message(chat_id, content.get_operator_message_with_phone(lang, session.get("city")))
        await _notify_manager(
            f"🚨 *Запрос оператора*\nChat: `{chat_id}`\nСообщение: {text_stripped}",
            chat_id,
            "telegram",
            session=session
        )
        return
    
    # Store message in conversation history for context
    session["conversation_history"].append({
        "role": "user",
        "text": text_stripped,
        "timestamp": time.time()
    })
    # Keep only last 10 messages for context
    session["conversation_history"] = session["conversation_history"][-10:]
    
    session["message_count"] = session.get("message_count", 0) + 1
    platform = session.get("platform", "tg")
    
    # Check if user asked for menu (any platform)
    menu_keywords = ["меню", "menu", "мәзір", "список", "варианты", "нұсқалар", "/menu"]
    if any(w in text_stripped.lower() for w in menu_keywords) and session.get("state") == "idle":
        lang = session.get("lang", "ru")
        await tg_client.send_message(chat_id, content.get_greeting(lang))
        return

    # Log message to database
    await log_message(chat_id, platform, "user", text_stripped, lang)
    
    # Check for small talk (random responses)
    small_talk_intent = detect_small_talk_intent(text_stripped)
    if small_talk_intent and session.get("state") == "idle":
        response = get_small_talk_response(small_talk_intent, lang)
        await tg_client.send_message(chat_id, response)
        return
    
    # Check for loan calculator request
    is_calc, calc_params = detect_calculator_intent(text_stripped)
    if is_calc and calc_params:
        calc_result = format_calculator_result(calc_params, lang)
        await tg_client.send_message(chat_id, calc_result)
        # Store in history
        session["conversation_history"].append({
            "role": "assistant",
            "text": calc_result,
            "timestamp": time.time()
        })
        await log_message(chat_id, platform, "assistant", calc_result, lang)
        return
    
    # Ответ: FAQ мгновенно, иначе LLM (idle, не в сценарии)
    if session.get("state") == "idle" and not callback_id:
        ai_response = await _get_bot_reply(text_stripped, session, ai)
        if ai_response:
            # Extract control tags
            notify_manager = "[NOTIFY_MANAGER]" in ai_response
            dialog_done = "[DONE]" in ai_response
            clean_response = ai_response.replace("[NOTIFY_MANAGER]", "").replace("[DONE]", "").strip()
            session["conversation_history"].append({
                "role": "assistant",
                "text": clean_response,
                "timestamp": time.time()
            })
            await tg_client.send_message(chat_id, clean_response)
            await log_message(chat_id, platform, "assistant", clean_response, lang)
            if notify_manager:
                await _notify_manager(
                    f"❓ *Клиент задал вопрос вне базы знаний*\nВопрос: {text_stripped}",
                    chat_id,
                    platform,
                    session=session
                )
            if dialog_done:
                # Mark session as directed to office — repeat office reminder on further messages
                session["state"] = "office_directed"
        else:
            await tg_client.send_message(chat_id, content.get_ai_fallback_message(lang, session.get("city")))
        await save_session(chat_id, session)
        return
    
    # Handle callback queries (button clicks)
    if callback_id and text_stripped.startswith(("product:", "menu:", "action:", "lang:", "platform:")):
        await tg_client.answer_callback_query(callback_id)
        
        if text_stripped.startswith("product:"):
            product_key = text_stripped.split(":", 1)[1]
            await _start_product_flow(chat_id, product_key, session, lambda m: tg_client.send_message(chat_id, m))
            return
        
        elif text_stripped == "menu:mortgage":
            await tg_client.send_message(chat_id, "Ипотека — тек офисте кеңес алады. Келіңіз / Приходите в офис.")
            return
        
        elif text_stripped == "menu:main":
            await tg_client.send_message(chat_id, content.get_greeting(lang))
            return
        
        elif text_stripped == "action:operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await tg_client.send_message(chat_id, content.get_operator_message_with_phone(lang, session.get("city")))
            return
        
        elif text_stripped == "demo:whatsapp":
            await tg_client.send_message(chat_id, content.get_whatsapp_demo(lang))
            return
    
    # Handle active flow
    if session.get("state") == "in_flow" and session.get("product"):
        await _process_flow_step(
            chat_id, text_stripped, session,
            lambda m: tg_client.send_message(chat_id, m),
            ai
        )
        return
    
    ai_response = await _get_bot_reply(text_stripped, session, ai)
    if ai_response:
        # Store bot response in history
        session["conversation_history"].append({
            "role": "assistant",
            "text": ai_response,
            "timestamp": time.time()
        })
        # Send AI response (no keyboards, text only)
        await tg_client.send_message(chat_id, ai_response)
    else:
        # AI failed — give friendly fallback (not 'не понял')
        fallback_msg = content.get_ai_fallback_message(lang, session.get("city"))
        await tg_client.send_message(chat_id, fallback_msg)


async def handle_whatsapp_update(
    body: Dict[str, Any],
    wa_client,
    ai: AIClient | None,
):
    """Handle WhatsApp (Green API) webhook update."""
    from app.green_api import extract_green_info, is_voice_message
    import logging
    logger = logging.getLogger(__name__)
    
    chat_id, text, sender_name, media_url = extract_green_info(body)
    logger.info(f"handle_whatsapp_update: chat_id={chat_id}, text={text}, sender={sender_name}")
    if not chat_id:
        logger.warning("No chat_id extracted from body")
        return
    
    session = await _get_session(chat_id)
    session["platform"] = "whatsapp"
    
    if sender_name:
        session["contact_name"] = sender_name
    
    # Handle voice message
    if is_voice_message(body) and media_url:
        settings = get_settings()
        if settings.is_ai_configured and settings.is_whatsapp_configured:
            # Download and transcribe
            audio_bytes = await wa_client.download_file(media_url)
            if audio_bytes:
                transcribed, detected_lang = await _transcribe_voice(
                    audio_bytes, ai, session.get("lang")
                )
                if transcribed:
                    session["lang"] = detected_lang
                    text = transcribed
                    # Transcription used internally — not sent to client
    
    if not text:
        return
    
    text_stripped = text.strip()
    
    lang = session.get("lang", "ru")
    
    # Helper to send message with back hint
    async def send_wa_with_hint(message: str):
        await wa_client.send_message(chat_id, content.add_wa_back_hint(message, lang))
    
    # Handle /start or menu commands
    if text_stripped in ["/start", "start", "меню", "мәзір", "menu"]:
        _reset_session(chat_id, "whatsapp")
        session["lang"] = lang
        await send_wa_with_hint(content.get_wa_menu(lang))
        return
    
    # Handle 0 to return to main menu (check BEFORE flow)
    if text_stripped == "0":
        _reset_session(chat_id, "whatsapp")
        await send_wa_with_hint(content.get_wa_menu(lang))
        return
    
    # Handle 99 for language selection
    if text_stripped == "99":
        session["state"] = "selecting_lang"
        await save_session(chat_id, session)
        wa_lang_menu = (
            "🌐 *Выберите язык / Тілді таңдаңыз:*\n\n"
            "1️⃣ Русский\n"
            "2️⃣ Қазақша\n\n"
            "*Напишите цифру 1 или 2*"
        )
        await send_wa_with_hint(wa_lang_menu)
        return
    
    # Handle operator request
    if any(word in text_stripped.lower() for word in ["оператор", "менеджер", "человек", "маман", "7"]):
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await send_wa_with_hint(content.get_operator_message_with_phone(lang, session.get("city")))
        await _notify_manager(
            f"🚨 *Запрос оператора (WhatsApp)*\nPhone: `{chat_id}`\nСообщение: {text_stripped}",
            chat_id,
            "whatsapp",
            session=session
        )
        return
    
    # Handle WA digit menu
    if session.get("state") == "idle" or session.get("state") == "wa_menu":
        # Check for mortgage submenu
        if session.get("submenu") == "mortgage":
            mapped = content.WA_MORTGAGE_DIGIT_MAP.get(text_stripped)
            if mapped == "back_to_main":
                session["submenu"] = None
                await send_wa_with_hint(content.get_wa_menu(lang))
                return
            elif mapped:
                session["submenu"] = None
                await _start_product_flow(
                    chat_id, mapped, session,
                    lambda m: send_wa_with_hint(m)
                )
                return
        
        # Main menu digits
        mapped = content.WA_DIGIT_MAP.get(text_stripped)
        if mapped == "mortgage_menu":
            session["submenu"] = "mortgage"
            await send_wa_with_hint(content.get_wa_mortgage_menu(lang))
            return
        elif mapped == "operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await send_wa_with_hint(content.get_operator_message_with_phone(lang, session.get("city")))
            return
        elif mapped:
            await _start_product_flow(
                chat_id, mapped, session,
                lambda m: send_wa_with_hint(m)
            )
            return
    
    # Handle active flow
    if session.get("state") == "in_flow" and session.get("product"):
        await _process_flow_step(
            chat_id, text_stripped, session,
            lambda m: send_wa_with_hint(m),
            ai
        )
        return
    
    small_talk_intent = detect_small_talk_intent(text_stripped)
    if small_talk_intent and session.get("state") == "idle":
        await send_wa_with_hint(get_small_talk_response(small_talk_intent, lang))
        return

    # Check for loan calculator request (WhatsApp)
    is_calc, calc_params = detect_calculator_intent(text_stripped)
    if is_calc and calc_params:
        calc_result = format_calculator_result(calc_params, lang)
        await send_wa_with_hint(calc_result)
        # Store in history
        session["conversation_history"] = session.get("conversation_history", [])
        session["conversation_history"].append({
            "role": "assistant",
            "text": calc_result,
            "timestamp": time.time()
        })
        await save_session(chat_id, session)
        return
    
    # AI response for free text
    session["conversation_history"] = session.get("conversation_history", [])
    session["conversation_history"].append({
        "role": "user",
        "text": text_stripped,
        "timestamp": time.time()
    })
    ai_response = await _get_bot_reply(text_stripped, session, ai)
    if ai_response:
        notify_manager = "[NOTIFY_MANAGER]" in ai_response
        clean_response = ai_response.replace("[NOTIFY_MANAGER]", "").replace("[DONE]", "").strip()
        session["conversation_history"].append({
            "role": "assistant",
            "text": clean_response,
            "timestamp": time.time()
        })
        await send_wa_with_hint(clean_response)
        if notify_manager:
            await _notify_manager(
                f"\u2753 *Клиент задал вопрос вне базы знаний*\nВопрос: {text_stripped}",
                chat_id, "whatsapp", session=session
            )
    else:
        await send_wa_with_hint(content.get_ai_fallback_message(lang, session.get("city")))
    await save_session(chat_id, session)
