"""
Main handler for KOMEK DAMU bot.
Supports: Telegram + WhatsApp, Russian + Kazakh, Voice messages.
"""

from __future__ import annotations

import logging
import time
import random
from typing import Any, Dict, Optional, List
from collections import defaultdict

from app.config import get_settings
from app.groq_client import GroqClient, get_system_prompt
from app.bot.knowledge_base import (
    detect_intent, get_product_info, get_faq_answer,
    PRODUCTS, FAQ_ANSWERS
)
from app.bot.flows import (
    get_flow_for_product, get_first_step, FlowStep,
    validate_phone, validate_number, validate_yes_no
)
from app.bot import content
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

# Random responses for small talk
RANDOM_RESPONSES_RU = {
    "greeting": ["Привет! 👋", "Здравствуйте! 🌟", "Рад вас видеть! 😊"],
    "thanks": ["Пожалуйста! Всегда рад помочь 🤝", "Обращайтесь! 👍", "Всегда к вашим услугам! 😊"],
    "how_are_you": ["Всё отлично, готов помочь с финансами! 💪", "Работаю на полную, спрашивайте! 🚀", "В прекрасном настроении! Чем помочь? 😊"],
    "bye": ["До свидания! Обращайтесь ещё 👋", "Всего доброго! 🌟", "До встречи! 🤝"],
    "unknown": ["Интересный вопрос! Давайте разберёмся 🤔", "Хм, давайте посмотрим... 🤓", "Отличный вопрос! 🎯"],
}

RANDOM_RESPONSES_KK = {
    "greeting": ["Сәлем! 👋", "Қош келдіңіз! 🌟", "Сізді көргеніме қуаныштымын! 😊"],
    "thanks": ["Өтінемін! Көмектесуге әрқашан дайынмын 🤝", "Хабарласыңыз! 👍", "Әрқашан қызметтіңіздемін! 😊"],
    "how_are_you": ["Барлық жақсы, қаржы бойынша көмектесуге дайынмын! 💪", "Толық жұмыс істеймін, сұраңыз! 🚀", "Керемет көңіл-күйде! Қалай көмектесе аламын? 😊"],
    "bye": ["Сау болыңыз! Келесі жолы хабарласыңыз 👋", "Бәрі жақсы болсын! 🌟", "Келесі кездескенше! 🤝"],
    "unknown": ["Қызықты сұрақ! Келіңіз, талдайық 🤔", "Хм, қарап көрейік... 🤓", "Керемет сұрақ! 🎯"],
}

def get_random_response(category: str, lang: str = "ru") -> str:
    """Get random response for category."""
    responses = RANDOM_RESPONSES_RU if lang == "ru" else RANDOM_RESPONSES_KK
    return random.choice(responses.get(category, responses["unknown"]))

def detect_small_talk_intent(text: str) -> str | None:
    """Detect if user is making small talk vs asking about products."""
    text_lower = text.lower()
    
    greetings = ["привет", "здравствуй", "сәлем", "сәлеметсіз", "hi", "hello", "hey"]
    thanks = ["спасибо", "благодар", "рахмет", "рақмет", "спс", "thanks", "thank you"]
    how_are_you = ["как дела", "как ты", "қалайсыз", "қалай", "how are you", "как поживаешь"]
    bye = ["пока", "до свидания", "сау", "сау бол", "bye", "goodbye", "до встречи"]
    
    for word in greetings:
        if word in text_lower:
            return "greeting"
    for word in thanks:
        if word in text_lower:
            return "thanks"
    for word in how_are_you:
        if word in text_lower:
            return "how_are_you"
    for word in bye:
        if word in text_lower:
            return "bye"
    
    return None


def _detect_language(text: str) -> str:
    """Detect if text is Kazakh or Russian. For mixed language, default to Kazakh."""
    # Kazakh-specific characters
    kazakh_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
    if any(c in text for c in kazakh_chars):
        return "kk"
    
    # Common Kazakh words (expanded list for шала-казахский)
    kazakh_words = ["сіз", "мен", "біз", "және", "болды", "қазақстан", "қазақ", "несие", "ипотека",
                     "салеметсіз", "рахмет", "қалай", "не", "бар", "жоқ", "көмектес", "алай", "әрі", "бәрі",
                     "дейін", "үшін", "бірге", "сонымен", "бірақ", "сондай", "әрине", "жаса", "қыл"]
    text_lower = text.lower()
    kazakh_score = sum(1 for w in kazakh_words if w in text_lower)
    
    # For mixed language (шала-казахский): ANY Kazakh word = Kazakh
    if kazakh_score >= 1:
        return "kk"
    
    return "ru"


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
    groq: GroqClient,
    lang_hint: str | None = None
) -> tuple[str | None, str]:
    """Transcribe voice message using Groq Whisper."""
    detected_lang = None
    
    # Try with language hint first
    if lang_hint:
        text, err = await groq.transcribe(audio_bytes, language=lang_hint)
        if text:
            detected_lang = lang_hint
            return text, detected_lang
    
    # Try auto-detection
    text, err = await groq.transcribe(audio_bytes, language=None)
    if text:
        # Detect language from transcribed text
        detected_lang = groq.detect_language_simple(text)
        return text, detected_lang
    
    return None, "ru"  # Default to Russian on failure


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
    groq: GroqClient,
) -> str | None:
    """Get AI response for free-text queries."""
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
    
    response, err = await groq.chat(messages, temperature=0.7)
    if err:
        logger.error("AI error: %s", err)
        return None
    return response


def _detect_lang(text: str) -> str:
    """Detect language from text. Russian wins if mixed — only pure Kazakh triggers kk."""
    lower = text.lower()
    words = set(lower.split())

    # Strong Russian signals — if present, it's Russian regardless
    ru_chars = set('ёъэ')  # ы removed: exists in Kazakh too
    if any(c in lower for c in ru_chars):
        return "ru"
    # Common Russian-only words
    ru_words = {"здравствуйте", "привет", "хочу", "можно", "нужно", "мне", "как",
                "что", "это", "есть", "не", "да", "нет", "хорошо", "спасибо",
                "взять", "оформить", "получить", "узнать", "сколько", "какой",
                "ваш", "наш", "для", "при", "без", "под", "про", "или"}
    if len(words & ru_words) >= 1:
        return "ru"

    # Kazakh-specific characters
    kk_chars = set('әіңғүұқөһ')
    if any(c in lower for c in kk_chars):
        return "kk"

    # Kazakh-specific words (exact)
    kk_words = {
        "керек", "жоқ", "алу", "беру", "болды", "береспа", "аламын",
        "болады", "маған", "саған", "оған", "бізге", "сізге", "қалай",
        "неше", "қанша", "салеметсізбе", "сәлем", "рахмет", "жақсы",
        "иә", "өтінем", "қарыз", "пайыз", "мерзім", "құжат",
        "бола", "болса", "алсам", "берсе", "келсем", "барсам",
        "несие", "даму"
    }
    if len(words & kk_words) >= 1:
        return "kk"
    # Kazakh suffix forms (substrings)
    kk_stems = ["бойынша", "алуға", "беруге", "болуға", "несие", "орайынша",
                "болады", "келіңіз", "офисіміз"]
    if any(stem in lower for stem in kk_stems):
        return "kk"
    # Transliterated kazakh greetings/words (no special chars)
    kk_translit = ["салеметсезбе", "саламетсызба", "салем", "рахмет", "жаксы",
                   "кайда", "канша", "несие", "болады", "керек"]
    if any(t in lower for t in kk_translit):
        return "kk"

    return "ru"


async def _handle_ai_response_with_context(
    text: str,
    session: Dict,
    groq: GroqClient,
) -> str | None:
    """Get AI response with conversation history for context understanding."""
    # Always detect lang from current message — fully overrides session lang
    detected = _detect_lang(text)
    session["lang"] = detected
    lang = detected
    system_prompt = get_system_prompt(lang)
    
    # Build context from knowledge base
    context = "Доступные продукты:\n"
    for key, product in PRODUCTS.items():
        name = product.name_ru if lang == "ru" else product.name_kk
        context += f"- {name}\n"
    
    # Build conversation history
    history = session.get("conversation_history", [])
    messages = [{"role": "system", "content": system_prompt + "\n\n" + context}]
    
    # Add last 5 messages for context
    for msg in history[-5:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["text"]})
    
    # Add current message
    messages.append({"role": "user", "content": text})
    
    response, err = await groq.chat(messages, temperature=0.8)
    if err:
        logger.error("AI error with context: %s", err)
        return None
    return response


async def _process_flow_step(
    chat_id: str,
    text: str,
    session: Dict,
    send_message_func,
    groq: GroqClient,
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
            if groq and len(text) > 5 and not any(c.isdigit() for c in text):
                ai_reply = await groq.chat(
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
        await _finish_flow(chat_id, session, send_message_func, groq)
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
    groq: GroqClient,
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
    groq: GroqClient,
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

    # Handle /start immediately without loading session
    if text and text.strip() in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        if not chat_id or chat_id == "None":
            logger.error(f"Invalid chat_id for /start: {chat_id}")
            return
        _reset_session(chat_id, "tg")
        _sessions[chat_id]["state"] = "idle"
        _sessions[chat_id]["platform"] = "tg"
        await save_session(chat_id, _sessions[chat_id])
        greeting = (
            "Сәлеметсіз бе! Мен KOMEK DAMU кеңесшісімін 👋\n"
            "Здравствуйте! Я консультант KOMEK DAMU 👋\n\n"
            "Несие, ипотека, бизнес қаржыландыру бойынша сұрақтарыңызды қойыңыз — жауап беремін.\n"
            "Задавайте вопросы по кредитам, ипотеке, бизнес-финансированию — отвечу."
        )
        logger.info(f"Sending /start greeting to chat_id={chat_id}")
        try:
            await tg_client.send_message(chat_id, greeting)
        except Exception as e:
            logger.error(f"Failed to send /start response: {e}")
        return
    
    # Handle 99 for language selection
    if text and text.strip() == "99":
        session = await _get_session(chat_id)
        session["state"] = "selecting_lang"
        await save_session(chat_id, session)
        await tg_client.send_message(
            chat_id,
            content.get_language_prompt("ru"),
            reply_markup=content.get_language_keyboard()
        )
        return
    
    session = await _get_session(chat_id)
    
    if sender_name:
        session["contact_name"] = sender_name
    
    # Check if dialog already done — client directed to office
    if session.get("state") == "office_directed" and text_stripped not in ["/start", "/menu"]:
        # If new question/topic — reset and answer again
        new_question_signals = ["?", "керек", "хочу", "можно", "как", "кредит",
                                 "ипотека", "несие", "даму", "рефинанс"]
        is_new_question = any(s in text_stripped.lower() for s in new_question_signals)
        if is_new_question:
            session["state"] = "idle"
        else:
            office_msg = (
                "Для полной консультации приходите в наш офис. Адрес: г. Алматы, [адрес офиса]."
                if lang == "ru" else
                "Толық кеңес алу үшін офисімізге келіңіз. Мекенжай: Алматы қ., [офис мекенжайы]."
            )
            await tg_client.send_message(chat_id, office_msg)
            await save_session(chat_id, session)
            return

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
            ai_response = await _handle_ai_response_with_context(text.strip(), session, groq)
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
        if not settings.is_groq_configured:
            await tg_client.send_message(
                chat_id,
                "Голосовые сообщения временно недоступны. Пожалуйста, напишите текстом."
            )
            return
        
        file_id = get_voice_file_id(body)
        if file_id:
            # Download voice file
            file_info = await tg_client.get_file(file_id)
            if file_info and file_info.get("result", {}).get("file_path"):
                file_path = file_info["result"]["file_path"]
                file_url = get_file_url(settings.telegram_bot_token, file_path)
                
                import httpx
                async with httpx.AsyncClient() as client:
                    r = await client.get(file_url)
                    audio_bytes = r.content
                
                # Transcribe
                transcribed, detected_lang = await _transcribe_voice(
                    audio_bytes, groq, session.get("lang")
                )
                
                if transcribed:
                    # Detect lang from transcribed text, not from Whisper (more reliable)
                    detected_lang = _detect_lang(transcribed)
                    session["lang"] = detected_lang
                    text = transcribed
                    # Confirm transcription
                    confirm_msg = (
                        f"🎤 *Распознано:* {transcribed}"
                        if detected_lang == "ru" else
                        f"🎤 *Танылды:* {transcribed}"
                    )
                    await tg_client.send_message(chat_id, confirm_msg)
                else:
                    await tg_client.send_message(
                        chat_id,
                        content.LANG_DETECT_FAILED_RU if session.get("lang", "ru") == "ru" else content.LANG_DETECT_FAILED_KK
                    )
                    return
    
    if not text:
        return
    
    text_stripped = text.strip()
    
    lang = session.get("lang", "ru")
    
    # Helper to send with keyboard
    async def send_with_keyboard(message: str, keyboard: Dict | None = None):
        await tg_client.send_message(chat_id, message, reply_markup=keyboard)
    
    # Handle /start or menu return (already handled above, but catch duplicates from session-loaded path)
    if text_stripped in ["/start", "/menu", "меню", "главное меню", "басты мәзір"]:
        return
    
    # Handle WhatsApp menu digits (1-7) or AI response for any text
    if session.get("platform") == "wa" and session.get("state") == "idle":
        # Check if it's a menu digit
        wa_menu_map = {
            "1": "personal_credit",
            "2": "business_credit",
            "3": "damu",
            "4": "mortgage",
            "5": "refinancing",
            "6": "complex_case",
            "7": "operator",
        }
        
        if text_stripped in wa_menu_map:
            product_key = wa_menu_map[text_stripped]
            if product_key == "operator":
                session["state"] = "handoff"
                session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
                await tg_client.send_message(chat_id, content.get_operator_message(lang))
                await _notify_manager(
                    f"🚨 *Запрос оператора*\nChat: `{chat_id}`\nПлатформа: WhatsApp",
                    chat_id,
                    "telegram",
                    session=session
                )
            else:
                await _start_product_flow(chat_id, product_key, session, lambda m: tg_client.send_message(chat_id, m))
            return
        
        # Check if user asked for menu
        menu_keywords = ["меню", "menu", "мәзір", "список", "варианты", "нұсқалар"]
        if any(w in text_stripped.lower() for w in menu_keywords):
            await tg_client.send_message(chat_id, content.get_wa_menu(lang))
            return
        
        # Otherwise — detect language from text and answer via AI (no menu)
        kk_chars = set('әіңғүұқөһ')
        if any(c in text_stripped.lower() for c in kk_chars):
            session["lang"] = "kk"
            lang = "kk"
        else:
            if not session.get("lang"):
                session["lang"] = "ru"
                lang = "ru"
        
        session["conversation_history"].append({
            "role": "user",
            "text": text_stripped,
            "timestamp": time.time()
        })
        ai_response = await _handle_ai_response_with_context(text_stripped, session, groq)
        if ai_response:
            session["conversation_history"].append({
                "role": "assistant",
                "text": ai_response,
                "timestamp": time.time()
            })
            await tg_client.send_message(chat_id, ai_response)
        else:
            await tg_client.send_message(chat_id, content.get_unknown_message(lang))
        await save_session(chat_id, session)
        return
    
    # Handle operator request
    if any(word in text_stripped.lower() for word in ["оператор", "менеджер", "человек", "маман", "админ"]):
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await tg_client.send_message(chat_id, content.get_operator_message(lang))
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
    
    # Increment message count for auto-handoff
    session["message_count"] = session.get("message_count", 0) + 1
    platform = session.get("platform", "tg")
    
    # Auto-handoff to manager after 2-3 messages (if not in flow)
    if session["message_count"] >= 3 and session.get("state") == "idle" and not callback_id:
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await tg_client.send_message(chat_id, content.get_operator_message(lang))
        await _notify_manager(
            f"🚨 *Авто-передача менеджеру (3 сообщения)*\nЧат: `{chat_id}`\nПлатформа: {platform}\nПоследнее сообщение: {text_stripped[:100]}...",
            chat_id,
            "telegram",
            session=session
        )
        await save_session(chat_id, session)
        return
    
    # Check if user asked for menu (any platform)
    menu_keywords = ["меню", "menu", "мәзір", "список", "варианты", "нұсқалар", "/menu"]
    if any(w in text_stripped.lower() for w in menu_keywords) and session.get("state") == "idle":
        lang = session.get("lang", "ru")
        if session.get("platform") == "wa":
            await tg_client.send_message(chat_id, content.get_wa_menu(lang))
        else:
            await send_with_keyboard(content.get_greeting(lang), content.get_menu_keyboard(lang))
        return

    # Log message to database
    await log_message(chat_id, platform, "user", text_stripped, lang)
    
    # Check for small talk (random responses)
    small_talk_intent = detect_small_talk_intent(text_stripped)
    if small_talk_intent and session.get("state") == "idle":
        response = get_random_response(small_talk_intent, lang)
        await tg_client.send_message(chat_id, response)
        return
    
    # AI response for any text (when not in flow)
    if session.get("state") == "idle" and not callback_id:
        # AI response — no flows, just conversation
        ai_response = await _handle_ai_response_with_context(text_stripped, session, groq)
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
            await tg_client.send_message(chat_id, content.get_unknown_message(lang))
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
            await send_with_keyboard(
                "Выберите тип ипотеки / Ипотека түрін таңдаңыз:",
                content.get_mortgage_menu(lang)
            )
            return
        
        elif text_stripped == "menu:main":
            await send_with_keyboard(
                content.get_greeting(lang),
                content.get_menu_keyboard(lang)
            )
            return
        
        elif text_stripped == "action:operator":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await tg_client.send_message(chat_id, content.get_operator_message(lang))
            return
        
        elif text_stripped == "demo:whatsapp":
            await tg_client.send_message(chat_id, content.get_whatsapp_demo(lang))
            return
    
    # Handle active flow
    if session.get("state") == "in_flow" and session.get("product"):
        await _process_flow_step(
            chat_id, text_stripped, session,
            lambda m: tg_client.send_message(chat_id, m),
            groq
        )
        return
    
    # Try to detect intent and start flow
    intent = detect_intent(text_stripped)
    if intent:
        await _start_product_flow(
            chat_id, intent, session,
            lambda m: tg_client.send_message(chat_id, m)
        )
        return
    
    # FAQ detection (simple keyword matching)
    faq_keywords = {
        "адрес": "address", "мекенжай": "address", "где": "address",
        "график": "work_hours", "жұмыс уақыты": "work_hours", "время": "work_hours",
        "платно": "consultation_free", "бесплатно": "consultation_free", "тегін": "consultation_free",
        "сколько времени": "how_long", "когда": "how_long", "қашан": "how_long",
    }
    
    text_lower = text_stripped.lower()
    for keyword, faq_key in faq_keywords.items():
        if keyword in text_lower:
            answer = get_faq_answer(faq_key, lang)
            await tg_client.send_message(chat_id, answer)
            return
    
    # AI response for unrecognized text with context
    ai_response = await _handle_ai_response_with_context(text_stripped, session, groq)
    if ai_response:
        # Store bot response in history
        session["conversation_history"].append({
            "role": "assistant",
            "text": ai_response,
            "timestamp": time.time()
        })
        # Send AI response with menu keyboard for Telegram
        if session.get("platform") == "tg":
            await send_with_keyboard(ai_response, content.get_menu_keyboard(lang))
        else:
            await tg_client.send_message(chat_id, ai_response)
    else:
        # Random response for unknown
        random_fallback = get_random_response("unknown", lang)
        if session.get("platform") == "tg":
            await send_with_keyboard(random_fallback + "\n\n" + content.get_unknown_message(lang), content.get_menu_keyboard(lang))
        else:
            await tg_client.send_message(chat_id, random_fallback + "\n\n" + content.get_unknown_message(lang))


async def handle_whatsapp_update(
    body: Dict[str, Any],
    wa_client,
    groq: GroqClient,
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
        if settings.is_groq_configured and settings.is_whatsapp_configured:
            # Download and transcribe
            audio_bytes = await wa_client.download_file(media_url)
            if audio_bytes:
                transcribed, detected_lang = await _transcribe_voice(
                    audio_bytes, groq, session.get("lang")
                )
                if transcribed:
                    session["lang"] = detected_lang
                    text = transcribed
                    # Send confirmation
                    confirm_msg = (
                        f"🎤 Распознано: {transcribed}"
                        if detected_lang == "ru" else
                        f"🎤 Танылды: {transcribed}"
                    )
                    await wa_client.send_message(chat_id, confirm_msg)
    
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
        await send_wa_with_hint(content.get_operator_message(lang))
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
            await send_wa_with_hint(content.get_operator_message(lang))
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
            groq
        )
        return
    
    # Intent detection for free text
    intent = detect_intent(text_stripped)
    if intent:
        await _start_product_flow(
            chat_id, intent, session,
            lambda m: send_wa_with_hint(m)
        )
        return
    
    # Unknown - send menu
    await send_wa_with_hint(content.get_wa_menu(lang))
