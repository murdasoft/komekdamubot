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
from app.bot.city_routing import (
    detect_nearby_offices,
    format_nearby_offices_reply,
    looks_like_place_only,
)
from app.bot.text_utils import strip_leading_greeting
from app.bot.response_builder import finalize_bot_response
from app.gemini_client import GeminiClient, get_gemini_client
from app.bot.stt_normalize import (
    is_borrower_clarify_message,
    normalize_stt_borrower_answer,
    stt_prompt_for_session,
)
from app.bot.voice_router import prepare_voice_input
from app.bot.voice_stt import transcribe_voice_message
from app.bot.faq_matcher import try_fast_response, is_pure_greeting
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
from app.bot.content import DEFAULT_LANG
from app.bot.menu import (
    get_main_menu_text,
    get_media_menu_reply,
    get_text_fallback_reply,
    menu_choice_body,
    resolve_menu_digit,
)
from app.bot.telegram_nav import (
    handle_nav_callback,
    render_screen,
    use_buttons_hint,
)
from app.bot.wizard import (
    get_city_invalid_reply,
    get_city_step_help,
    get_city_step_text,
    get_lang_step_text,
    get_welcome_with_menu,
    resolve_city_digit,
)
from app.offices import get_contact_footer
from app.bot.lang_detect import detect_message_lang
from app.bot.kazakh_dict import KK_CHARS
from app.supabase_client import save_session, load_session, log_message, create_lead

logger = logging.getLogger(__name__)

# In-memory session storage (replace with DB for production)
_sessions: Dict[str, Dict] = defaultdict(lambda: {
    "state": "idle",  # idle, in_flow, handoff
    "lang": DEFAULT_LANG,
    "lang_locked": False,
    "city_confirmed": False,
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
        "рассчитай", "сколько платить", "платеж", "платёж", "калькулятор",
        "посчитай", "сколько будет", "ежемесячный", "аннуитет", "переплат",
        "есепте", "есептеу", "айлық төлем", "ай сайын",
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
        "too": {"amount": 200_000_000, "rate": 21.0, "years": 5},
        "ip": {"amount": 35_000_000, "rate": 21.0, "years": 5},
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
    if "lang_locked" not in session:
        session["lang_locked"] = False
    if "city_confirmed" not in session:
        session["city_confirmed"] = False
    return session


def _reset_session(chat_id: str, platform: str = "telegram"):
    """Reset session to initial state."""
    _sessions[chat_id] = {
        "state": "idle",
        "lang": DEFAULT_LANG,
        "lang_locked": False,
        "city_confirmed": False,
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
    lang_hint: str | None = None,
    filename: str = "voice.ogg",
    session: Dict | None = None,
) -> tuple[str | None, str]:
    """STT: Together / VPS Whisper; Groq Whisper только при GROQ_VOICE_STT или fallback."""
    settings = get_settings()
    return await transcribe_voice_message(
        audio_bytes,
        settings,
        ai=ai,
        lang_hint=lang_hint,
        filename=filename,
        session=session,
    )


async def _voice_text_for_handler(transcribed: str, session: Dict) -> str:
    """Разбор голоса → команда меню/FAQ (без свободного ответа LLM)."""
    route = await prepare_voice_input(transcribed, session)
    logger.info("Voice route source=%s text=%s", route.source, route.text[:60])
    return route.text


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
    lang = session.get("lang", DEFAULT_LANG)
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
    """Язык ответа: kk по умолчанию; ru только после явного выбора через 99."""
    _ = text
    if session.get("lang_locked"):
        return session.get("lang", DEFAULT_LANG)
    session["lang"] = DEFAULT_LANG
    session.pop("lang_streak_candidate", None)
    session.pop("lang_streak", None)
    return session["lang"]


def _update_session_intent(text: str, session: Dict) -> None:
    """Запомнить продукт для уточняющих вопросов («а процент?», «сколько лет?»)."""
    from app.bot.knowledge_base import (
        detect_intent,
        is_ip_credit_question,
        is_personal_credit_question,
    )

    intent = detect_intent(text, session)
    if intent:
        session["last_intent"] = intent
    elif is_personal_credit_question(text, session):
        session["last_intent"] = "personal_credit"
    elif is_ip_credit_question(text):
        session["last_intent"] = "business_credit"


async def _get_bot_reply(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """Только FAQ и меню — без нейросети в текстовых ответах."""
    _ = ai
    text = normalize_stt_borrower_answer(text, session)
    lang = _update_session_lang(text, session)
    found_city = detect_city(text)
    if found_city:
        session["city"] = found_city
        session["city_confirmed"] = True
    core = strip_leading_greeting(text)
    platform = session.get("platform", "telegram")
    fast = try_fast_response(
        core,
        lang,
        session.get("city"),
        platform,
        city_confirmed=session.get("city_confirmed", False),
        session=session,
    )
    if fast:
        logger.info("Fast FAQ hit for: %s", core[:40])
        _update_session_intent(core, session)
        if is_borrower_clarify_message(fast):
            session["awaiting_borrower_type"] = True
        elif session.get("awaiting_borrower_type"):
            from app.bot.knowledge_base import detect_business_entity

            if detect_business_entity(core):
                session.pop("awaiting_borrower_type", None)
        return fast
    logger.info("No FAQ match, menu fallback: %s", core[:40])
    platform = session.get("platform", "telegram")
    return get_text_fallback_reply(lang, platform=platform)


async def _handle_ai_response_with_context(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """Get AI response with conversation history for context understanding."""
    if not ai:
        return None
    lang = session.get("lang", DEFAULT_LANG)
    found_city = detect_city(text)
    if found_city:
        session["city"] = found_city
        session["city_confirmed"] = True
    city = session.get("city")
    system_prompt = get_system_prompt(lang, city=city)

    intent = detect_intent(text, session)
    if intent:
        info = get_product_info(intent, lang)
        if info:
            if intent == "personal_credit":
                from app.bot.knowledge_base import format_personal_credit_answer

                context = format_personal_credit_answer(lang, text)
            else:
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
    lang = session.get("lang", DEFAULT_LANG)
    
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

    if step.key == "city":
        c = detect_city(str(validated_value)) or detect_city(text)
        if c:
            session["city"] = c
            session["city_confirmed"] = True
    
    # Check for payment delays - reject if yes
    if step.key == "has_delays" and validated_value == "да":
        lang = session.get("lang", DEFAULT_LANG)
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
    lang = session.get("lang", DEFAULT_LANG)
    data = session.get("data", {})
    platform = session.get("platform", "telegram")
    
    # Build summary
    summary = _build_summary(data, product_key, lang)
    
    # Send to Bitrix24
    await _send_to_bitrix24(data, product_key, chat_id, lang)
    
    # Notify manager
    await _notify_manager(summary, chat_id, platform)

    await create_lead(chat_id, platform, product_key, data, lang)
    
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
    """Карточка продукта из базы — без сценария и без LLM."""
    _ = chat_id
    platform = session.get("platform", "telegram")
    key = product_key
    if key in ("mortgage_gov", "mortgage_standard"):
        await _send_menu_choice(key, session, send_message_func, platform=platform)
        return
    legacy_map = {
        "business_credit": "ip_business",
        "damu": "damu",
        "refinancing": "refinancing",
        "personal_credit": "personal_credit",
    }
    mapped = legacy_map.get(key, key)
    if not await _send_menu_choice(mapped, session, send_message_func, platform=platform):
        lang = session.get("lang", DEFAULT_LANG)
        await send_message_func(get_text_fallback_reply(lang))


def _set_menu_intent(choice_key: str, session: Dict) -> None:
    mapping = {
        "ip_business": ("business_credit", "ip"),
        "too_business": ("business_credit", "too"),
        "personal_credit": ("personal_credit", "personal"),
        "mortgage_menu": ("mortgage_standard", None),
        "mortgage_gov": ("mortgage_gov", None),
        "mortgage_standard": ("mortgage_standard", None),
        "damu": ("damu", None),
        "refinancing": ("refinancing", None),
    }
    intent, entity = mapping.get(choice_key, (choice_key, None))
    session["last_intent"] = intent
    if entity:
        session["last_entity"] = entity
    session.pop("awaiting_borrower_type", None)
    session["state"] = "idle"
    session["product"] = None
    session["flow_step"] = None


async def _send_menu_choice(
    choice_key: str,
    session: Dict,
    send_message_func,
    *,
    platform: str = "telegram",
    attach_contacts: bool = True,
) -> bool:
    """Ответ по цифре меню без лишних вопросов. True если обработано."""
    if choice_key == "operator":
        return False

    lang = session.get("lang", DEFAULT_LANG)
    body = menu_choice_body(choice_key, lang)
    if not body:
        return False

    _set_menu_intent(choice_key, session)
    city = session.get("city")
    if attach_contacts and city:
        body = f"{body}\n\n{get_contact_footer(city, lang, all_cities=False, platform=platform)}"  # type: ignore[arg-type]
    elif attach_contacts and platform == "whatsapp":
        if lang == "kk":
            body = f"{body}\n\n❓ *Қай қаладасыз?*"
        else:
            body = f"{body}\n\n❓ *Из какого вы города?*"

    await send_message_func(body)

    if choice_key == "mortgage_menu" and platform == "whatsapp":
        session["submenu"] = "mortgage"
        await send_message_func(content.get_wa_mortgage_menu(lang))
    return True


async def _try_handle_menu_digit(
    digit: str,
    session: Dict,
    send_message_func,
    *,
    platform: str = "telegram",
) -> bool:
    choice = resolve_menu_digit(digit)
    if not choice:
        return False
    if choice == "operator":
        return False
    return await _send_menu_choice(
        choice, session, send_message_func, platform=platform
    )


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

    # Handle /start — шаг 1: язык (кнопки в одном сообщении)
    if text and text.strip() in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        if not chat_id or chat_id == "None":
            logger.error(f"Invalid chat_id for /start: {chat_id}")
            return
        _reset_session(chat_id, "tg")
        _sessions[chat_id]["state"] = "selecting_lang"
        _sessions[chat_id]["platform"] = "tg"
        session = _sessions[chat_id]
        await save_session(chat_id, session)
        await render_screen(tg_client, chat_id, session, "lang")
        return

    session = await _get_session(chat_id)

    # Inline-кнопки: одно сообщение, редактирование на месте
    if callback_id and text and text.strip().startswith(("nav:", "menu:", "mort:")):
        await tg_client.answer_callback_query(callback_id)
        cq_msg = body.get("callback_query", {}).get("message", {})
        nav_mid = cq_msg.get("message_id")
        lang = session.get("lang", DEFAULT_LANG)
        action = await handle_nav_callback(
            text.strip(), session, tg_client, chat_id, nav_mid
        )
        if action == "operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await tg_client.send_message(
                chat_id,
                content.get_operator_message_with_phone(lang, session.get("city")),
            )
            await _notify_manager(
                f"🚨 *Меню → менеджер (Telegram)*\nChat: `{chat_id}`",
                chat_id,
                "telegram",
                session=session,
            )
        await save_session(chat_id, session)
        return

    # Handle 99 for language re-selection
    if text and text.strip() == "99":
        session["state"] = "selecting_lang"
        mid = session.get("menu_message_id")
        await render_screen(tg_client, chat_id, session, "lang", message_id=mid)
        await save_session(chat_id, session)
        return
    
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
                content.HANDOFF_RELEASED_RU if session.get("lang", DEFAULT_LANG) == "ru" else content.HANDOFF_RELEASED_KK
            )
            return
        if text:
            lang_h = session.get("lang", DEFAULT_LANG)
            note = (
                "Менеджер скоро ответит. Напишите *бот* чтобы вернуться к боту."
                if lang_h == "ru"
                else "Менеджер жақын арада жауап береді. Ботқа оралу үшін *бот* жазыңыз."
            )
            await tg_client.send_message(chat_id, note)
        return
    
    # Handle voice message
    if is_voice_message(body):
        settings = get_settings()
        if not settings.is_voice_stt_configured:
            await tg_client.send_message(
                chat_id,
                "Голосовые сообщения временно недоступны. Пожалуйста, напишите текстом."
            )
            return

        lang_ui = session.get("lang", DEFAULT_LANG)
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
                    audio_bytes,
                    ai,
                    session.get("lang")
                    if session.get("lang") in ("ru", "kk")
                    else DEFAULT_LANG,
                    session=session,
                )

                logger.info("Voice result chat=%s: lang=%s text=%s", chat_id, detected_lang, transcribed)

                if transcribed and transcribed.strip():
                    if not session.get("lang_locked") and any(
                        c in KK_CHARS for c in transcribed.lower()
                    ):
                        session["lang"] = "kk"
                    text = await _voice_text_for_handler(transcribed.strip(), session)
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
    
    msg = body.get("message") or {}
    if not text and msg and (msg.get("photo") or msg.get("document")):
        lang_ph = session.get("lang", DEFAULT_LANG)
        screen = "main" if session.get("city_confirmed") else (
            "city" if session.get("state") == "selecting_city" else "lang"
        )
        mid = session.get("menu_message_id")
        hint = get_media_menu_reply(lang_ph)
        if mid:
            await tg_client.edit_message(
                chat_id, mid, hint, reply_markup=None
            )
        await render_screen(tg_client, chat_id, session, screen, message_id=mid)
        return

    if not text:
        return
    
    text_stripped = text.strip()
    lang = session.get("lang", DEFAULT_LANG)
    
    # Handle /start or menu return
    if text_stripped in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        return

    if session.get("state") in ("selecting_lang", "selecting_city"):
        mid = session.get("menu_message_id")
        if mid:
            await tg_client.edit_message(
                chat_id, mid, use_buttons_hint(lang), reply_markup=None
            )
        else:
            await tg_client.send_message(chat_id, use_buttons_hint(lang))
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
        if session.get("city_confirmed"):
            await render_screen(
                tg_client, chat_id, session, "main", message_id=session.get("menu_message_id")
            )
        else:
            await render_screen(tg_client, chat_id, session, "lang")
        return

    if session.get("state") == "idle" and not session.get("city_confirmed"):
        await render_screen(tg_client, chat_id, session, "lang")
        return

    # Log message to database
    await log_message(chat_id, platform, "user", text_stripped, lang)
    
    # Check for small talk (random responses)
    if session.get("state") == "idle" and (
        is_pure_greeting(text_stripped) or detect_small_talk_intent(text_stripped) == "greeting"
    ):
        if not session.get("lang_locked"):
            await render_screen(tg_client, chat_id, session, "lang")
        elif not session.get("city_confirmed"):
            await render_screen(tg_client, chat_id, session, "city", message_id=session.get("menu_message_id"))
        else:
            await render_screen(tg_client, chat_id, session, "main", message_id=session.get("menu_message_id"))
        await save_session(chat_id, session)
        return

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
    
    if session.get("state") == "idle" and not callback_id:
        if session.get("nearby_pick") and text_stripped.isdigit():
            opts = session.get("nearby_pick") or []
            idx = int(text_stripped) - 1
            if 0 <= idx < len(opts):
                session["city"] = opts[idx]
                session["city_confirmed"] = True
                session.pop("nearby_pick", None)
                await render_screen(tg_client, chat_id, session, "main")
                await save_session(chat_id, session)
                return
            session.pop("nearby_pick", None)

        found_city = detect_city(text_stripped)
        if found_city:
            session["city"] = found_city
            session["city_confirmed"] = True
            session.pop("nearby_pick", None)
            await render_screen(tg_client, chat_id, session, "main", message_id=session.get("menu_message_id"))
            await save_session(chat_id, session)
            return

        nearby = detect_nearby_offices(text_stripped, lang)
        if nearby:
            place, keys, _dists = nearby
            session["nearby_pick"] = keys
            await tg_client.send_message(
                chat_id,
                format_nearby_offices_reply(place, keys, lang),
            )
            await save_session(chat_id, session)
            return

    # Ответ: FAQ мгновенно, без нейросети (idle, не в сценарии)
    if session.get("state") == "idle" and not callback_id:
        if is_pure_greeting(text_stripped):
            await render_screen(
                tg_client, chat_id, session, "main", message_id=session.get("menu_message_id")
            )
            await save_session(chat_id, session)
            return
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
            await tg_client.send_message(
                chat_id, get_text_fallback_reply(lang, platform="telegram")
            )
        await save_session(chat_id, session)
        return
    
    # Legacy callback queries
    if callback_id and text_stripped.startswith(("product:", "action:", "lang:", "platform:")):
        await tg_client.answer_callback_query(callback_id)

        if text_stripped.startswith("product:"):
            product_key = text_stripped.split(":", 1)[1]
            await _start_product_flow(chat_id, product_key, session, lambda m: tg_client.send_message(chat_id, m))
            return
        
        elif text_stripped == "action:operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await tg_client.send_message(chat_id, content.get_operator_message_with_phone(lang, session.get("city")))
            return
        
        elif text_stripped == "demo:whatsapp":
            await tg_client.send_message(chat_id, content.get_whatsapp_demo(lang))
            return
    
    if session.get("state") == "in_flow":
        session["state"] = "idle"
        session.pop("product", None)
        session.pop("flow_step", None)

    ai_response = await _get_bot_reply(text_stripped, session, ai)
    if ai_response:
        session["conversation_history"].append({
            "role": "assistant",
            "text": ai_response,
            "timestamp": time.time()
        })
        await tg_client.send_message(chat_id, ai_response)
    else:
        await tg_client.send_message(
            chat_id, get_text_fallback_reply(lang, platform="telegram")
        )


async def handle_whatsapp_update(
    body: Dict[str, Any],
    wa_client,
    ai: AIClient | None,
):
    """Handle WhatsApp (Green API) webhook update."""
    from app.green_api import (
        extract_green_info,
        get_audio_filename,
        extract_media_download_url,
        is_image_message,
        is_voice_message,
    )
    import logging
    logger = logging.getLogger(__name__)

    chat_id, text, sender_name, media_url = extract_green_info(body)
    logger.info(
        "handle_whatsapp_update: chat_id=%s text=%s voice=%s sender=%s",
        chat_id,
        (text or "")[:40],
        is_voice_message(body),
        sender_name,
    )
    if not chat_id:
        logger.warning("No chat_id extracted from body")
        return

    session = await _get_session(chat_id)
    session["platform"] = "whatsapp"

    if sender_name:
        session["contact_name"] = sender_name

    lang = session.get("lang", DEFAULT_LANG)

    def _wa_nav_step() -> str | None:
        st = session.get("state")
        if st == "selecting_lang":
            return "lang"
        if st == "selecting_city":
            return "city"
        return "main"

    async def send_wa_with_hint(message: str, reply_lang: str | None = None):
        use_lang = reply_lang or session.get("lang", lang)
        await wa_client.send_message(
            chat_id,
            content.add_wa_back_hint(message, use_lang, step=_wa_nav_step()),
        )

    # Голосовое (audioMessage / voiceMessage)
    if is_voice_message(body):
        settings = get_settings()
        lang_ui = session.get("lang", DEFAULT_LANG)
        if not settings.is_voice_stt_configured:
            await send_wa_with_hint(
                "🎤 Дауыстық хабарлама уақытша жоқ. Мәтінмен жазыңыз."
                if lang_ui == "kk"
                else "🎤 Голосовые временно недоступны. Напишите текстом."
            )
            return

        await send_wa_with_hint(
            "🎤 Тыңдап жатырмын, секунду..."
            if lang_ui == "kk"
            else "🎤 Слушаю голосовое, секунду..."
        )

        id_message = body.get("idMessage", "")
        media_url = media_url or extract_media_download_url(body)
        try:
            logger.info("WA voice start chat=%s msg=%s", chat_id, id_message)
            audio_bytes = await wa_client.download_incoming_file(
                chat_id, id_message, media_url
            )
            if not audio_bytes:
                logger.error("WA voice download failed chat=%s msg=%s", chat_id, id_message)
                await send_wa_with_hint(
                    "Файлды жүктей алмадым. Қайта жіберіңіз немесе мәтінмен жазыңыз."
                    if lang_ui == "kk"
                    else "Не удалось загрузить аудио. Отправьте ещё раз или напишите текстом."
                )
                return

            fname = get_audio_filename(body)
            logger.info("WA voice STT start chat=%s bytes=%s", chat_id, len(audio_bytes))
            transcribed, detected_lang = await _transcribe_voice(
                audio_bytes, ai, session.get("lang"), filename=fname, session=session
            )
            if transcribed and transcribed.strip():
                if not session.get("lang_locked") and any(
                    c in KK_CHARS for c in transcribed.lower()
                ):
                    session["lang"] = "kk"
                text = await _voice_text_for_handler(transcribed.strip(), session)
                await save_session(chat_id, session)
                logger.info("WA voice OK chat=%s: %s", chat_id, text[:60])
            else:
                logger.warning("WA voice STT empty chat=%s", chat_id)
                await send_wa_with_hint(
                    content.VOICE_STT_FAILED_KK
                    if lang_ui == "kk"
                    else content.VOICE_STT_FAILED_RU
                )
                return
        except Exception:
            logger.exception("WA voice pipeline failed chat=%s msg=%s", chat_id, id_message)
            await send_wa_with_hint(
                "Дауыстық хабарламада қате. Қайта жіберіңіз немесе мәтінмен жазыңыз."
                if lang_ui == "kk"
                else "Ошибка обработки голосового. Отправьте ещё раз или напишите текстом."
            )
            return

    if is_image_message(body):
        if session.get("state") == "selecting_lang":
            await send_wa_with_hint(get_lang_step_text())
        elif session.get("state") == "selecting_city":
            await send_wa_with_hint(get_city_step_text(lang), lang)
        elif session.get("city_confirmed") and session.get("city"):
            await send_wa_with_hint(
                f"{get_media_menu_reply(lang)}\n\n{get_welcome_with_menu(lang, session['city'], 'whatsapp')}",
                lang,
            )
        else:
            await send_wa_with_hint(get_lang_step_text())
        return

    if not text:
        return

    text_stripped = text.strip()
    lang = session.get("lang", DEFAULT_LANG)
    platform = session.get("platform", "whatsapp")
    await log_message(chat_id, platform, "user", text_stripped, lang)

    # Handle /start — шаг 1: язык
    if text_stripped in ["/start", "start", "меню", "мәзір", "menu"]:
        _reset_session(chat_id, "whatsapp")
        session = await _get_session(chat_id)
        session["state"] = "selecting_lang"
        await save_session(chat_id, session)
        await send_wa_with_hint(get_lang_step_text())
        return

    # 99 — смена языка (шаг 1)
    if text_stripped == "99":
        session["state"] = "selecting_lang"
        session.pop("city_confirmed", None)
        await save_session(chat_id, session)
        await send_wa_with_hint(get_lang_step_text())
        return

    # 98 — выбор города (шаг 2)
    if text_stripped == "98":
        if not session.get("lang_locked"):
            await send_wa_with_hint(get_lang_step_text())
            return
        session["state"] = "selecting_city"
        await save_session(chat_id, session)
        await send_wa_with_hint(get_city_step_text(session.get("lang", lang)), session.get("lang", lang))
        return

    # Шаг 1: язык
    if text_stripped in ["1", "2"] and session.get("state") == "selecting_lang":
        session["lang"] = "kk" if text_stripped == "1" else "ru"
        session["lang_locked"] = True
        session["state"] = "selecting_city"
        await save_session(chat_id, session)
        await send_wa_with_hint(get_city_step_text(session["lang"]), session["lang"])
        return

    if session.get("state") == "selecting_lang":
        await send_wa_with_hint(
            "🌐 Жазыңыз *1* (қазақша) немесе *2* (орысша)"
            if lang == "kk"
            else "🌐 Напишите *1* (казахский) или *2* (русский)"
        )
        return

    # Шаг 2: город
    if session.get("state") == "selecting_city":
        if text_stripped == "7":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await send_wa_with_hint(
                content.get_operator_message_with_phone(lang, None, "whatsapp"),
                lang,
            )
            await _notify_manager(
                f"🚨 *Менеджер на шаге города (WhatsApp)*\nPhone: `{chat_id}`\nСообщение: {text_stripped}",
                chat_id,
                "whatsapp",
                session=session,
            )
            await save_session(chat_id, session)
            return

        city_key = resolve_city_digit(text_stripped)
        if not city_key:
            city_key = detect_city(text_stripped)
        if city_key:
            session["city"] = city_key
            session["city_confirmed"] = True
            session["state"] = "idle"
            await save_session(chat_id, session)
            await send_wa_with_hint(
                get_welcome_with_menu(session["lang"], city_key, "whatsapp"),
                session["lang"],
            )
            return

        lower = text_stripped.lower()
        if any(
            w in lower
            for w in (
                "номер",
                "телефон",
                "позвон",
                "звон",
                "менеджер",
                "оператор",
                "человек",
                "маман",
                "дайте",
                "беріңіз",
                "нөмір",
            )
        ):
            await send_wa_with_hint(
                content.get_operator_message_with_phone(lang, None, "whatsapp"),
                lang,
            )
            return

        await send_wa_with_hint(get_city_invalid_reply(lang), lang)
        return

    # 0 — главное меню (шаг 3), язык и город сохраняются
    if text_stripped == "0":
        if session.get("city_confirmed") and session.get("city"):
            await send_wa_with_hint(
                get_welcome_with_menu(lang, session["city"], "whatsapp"), lang
            )
        elif session.get("state") == "selecting_city":
            await send_wa_with_hint(get_city_step_help(lang), lang)
        elif session.get("lang_locked"):
            session["state"] = "selecting_city"
            await send_wa_with_hint(get_city_step_text(lang), lang)
        else:
            session["state"] = "selecting_lang"
            await send_wa_with_hint(get_lang_step_text())
        return

    if session.get("nearby_pick") and text_stripped.isdigit():
        opts = session.get("nearby_pick") or []
        idx = int(text_stripped) - 1
        if 0 <= idx < len(opts):
            session["city"] = opts[idx]
            session["city_confirmed"] = True
            session.pop("nearby_pick", None)
            session["state"] = "idle"
            await save_session(chat_id, session)
            await send_wa_with_hint(
                get_welcome_with_menu(session["lang"], opts[idx], "whatsapp"),
                session["lang"],
            )
            return
        session.pop("nearby_pick", None)

    if session.get("state") == "idle":
        found_city = detect_city(text_stripped)
        if found_city:
            session["city"] = found_city
            session["city_confirmed"] = True
            session.pop("nearby_pick", None)
            await save_session(chat_id, session)
            await send_wa_with_hint(
                get_welcome_with_menu(lang, found_city, "whatsapp"), lang
            )
            return

        nearby = detect_nearby_offices(text_stripped, lang)
        if nearby:
            place, keys, _dists = nearby
            session["nearby_pick"] = keys
            await save_session(chat_id, session)
            await send_wa_with_hint(format_nearby_offices_reply(place, keys, lang), lang)
            return

        if looks_like_place_only(text_stripped):
            await send_wa_with_hint(get_text_fallback_reply(lang, platform="whatsapp"), lang)
            return

    # Handle operator request
    if any(word in text_stripped.lower() for word in ["оператор", "менеджер", "человек", "маман"]) or (
        session.get("state") == "idle" and text_stripped == "7"
    ):
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await send_wa_with_hint(
            content.get_operator_message_with_phone(
                lang, session.get("city"), "whatsapp"
            )
        )
        await _notify_manager(
            f"🚨 *Запрос оператора (WhatsApp)*\nPhone: `{chat_id}`\nСообщение: {text_stripped}",
            chat_id,
            "whatsapp",
            session=session
        )
        return
    
    # Handle WA digit menu
    if session.get("state") == "idle" or session.get("state") == "wa_menu":
        session.pop("nearby_pick", None)
        # Check for mortgage submenu
        if session.get("submenu") == "mortgage":
            mapped = content.WA_MORTGAGE_DIGIT_MAP.get(text_stripped)
            if mapped == "back_to_main":
                session["submenu"] = None
                if session.get("city"):
                    await send_wa_with_hint(
                        get_welcome_with_menu(lang, session["city"], "whatsapp"), lang
                    )
                else:
                    await send_wa_with_hint(content.get_wa_menu(lang), lang)
                return
            elif mapped:
                session["submenu"] = None
                await _send_menu_choice(
                    mapped,
                    session,
                    lambda m, rl=lang: send_wa_with_hint(m, rl),
                    platform="whatsapp",
                )
                await save_session(chat_id, session)
                return
        
        # Main menu digits 1–7
        mapped = content.WA_DIGIT_MAP.get(text_stripped)
        if mapped == "operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await send_wa_with_hint(
                content.get_operator_message_with_phone(
                    lang, session.get("city"), "whatsapp"
                )
            )
            await _notify_manager(
                f"🚨 *Меню → менеджер (WhatsApp)*\nPhone: `{chat_id}`",
                chat_id,
                "whatsapp",
                session=session,
            )
            await save_session(chat_id, session)
            return
        if mapped:
            if await _send_menu_choice(
                mapped,
                session,
                lambda m, rl=lang: send_wa_with_hint(m, rl),
                platform="whatsapp",
            ):
                await save_session(chat_id, session)
                return
    
    if session.get("state") == "in_flow":
        session["state"] = "idle"
        session.pop("product", None)
        session.pop("flow_step", None)

    if (
        session.get("state") == "idle"
        and (is_pure_greeting(text_stripped) or detect_small_talk_intent(text_stripped) == "greeting")
    ):
        if not session.get("lang_locked"):
            session["state"] = "selecting_lang"
            await save_session(chat_id, session)
            await send_wa_with_hint(get_lang_step_text())
            return
        if not session.get("city_confirmed"):
            session["state"] = "selecting_city"
            await save_session(chat_id, session)
            await send_wa_with_hint(get_city_step_text(lang), lang)
            return
        await send_wa_with_hint(get_welcome_with_menu(lang, session["city"], "whatsapp"), lang)
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
        await log_message(chat_id, platform, "assistant", calc_result, lang)
        await save_session(chat_id, session)
        return
    
    if session.get("state") == "idle" and not session.get("city_confirmed"):
        if not session.get("lang_locked"):
            session["state"] = "selecting_lang"
            await send_wa_with_hint(get_lang_step_text())
        else:
            session["state"] = "selecting_city"
            await send_wa_with_hint(get_city_step_text(lang), lang)
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
        await log_message(chat_id, platform, "assistant", clean_response, lang)
        if notify_manager:
            await _notify_manager(
                f"\u2753 *Клиент задал вопрос вне базы знаний*\nВопрос: {text_stripped}",
                chat_id, "whatsapp", session=session
            )
    else:
        fallback = get_text_fallback_reply(lang)
        await send_wa_with_hint(fallback)
        await log_message(chat_id, platform, "assistant", fallback, lang)
    await save_session(chat_id, session)
