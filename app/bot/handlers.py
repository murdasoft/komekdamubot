"""
Main handler for KOMEK DAMU bot.
Supports: Telegram + WhatsApp, Russian + Kazakh, Voice messages.
"""

from __future__ import annotations

import asyncio
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
)
from app.bot.text_utils import strip_leading_greeting
from app.bot.response_builder import finalize_bot_response
from app.bot.stt_normalize import (
    is_borrower_clarify_message,
    normalize_stt_borrower_answer,
    stt_prompt_for_session,
)
from app.bot.voice_router import (
    prepare_voice_input,
    resolve_menu_digit_from_text,
)
from app.bot.voice_stt import transcribe_voice_message
from app.bot.chatbot_ux import (
    get_credit_choice_menu,
    get_lang_retry_message,
    is_vague_credit_request,
    parse_lang_digit,
    pick_voice_text_nudge,
    try_resolve_city_from_text,
)
from app.bot.faq_matcher import try_fast_response, is_pure_greeting
from app.bot.faq_guide import build_faq_guide_reply
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
from app.bot.telegram_nav import handle_nav_callback
from app.bot.hybrid_flow import is_wizard_nav_input, send_hybrid_reply
from app.bot.tg_wa_ui import (
    send_tg_city_help,
    send_tg_city_step,
    send_tg_lang_step,
    send_tg_main_menu,
    send_tg_with_hint,
    send_wa_city_help,
    send_wa_city_step,
    send_wa_lang_step,
    send_wa_main_menu,
    send_wa_with_hint,
)
from app.bot.wizard import (
    get_city_step_help,
    get_city_step_text,
    get_lang_step_text,
    get_welcome_with_menu,
    resolve_city_digit,
)
from app.offices import get_contact_footer
from app.bot.lang_detect import detect_message_lang
from app.bot.kazakh_phrases import KK_CHARS
from app.supabase_client import save_session, load_session, log_message, create_lead
from app.bot.business_hours import is_bot_active_now, get_human_hours_reply
from app.bot.ux_labels import (
    LIST_TRIGGER_EXACT,
    LIST_TRIGGER_KEYWORDS,
    normalize_list_trigger,
)

logger = logging.getLogger(__name__)

_HUMAN_HOURS_NOTICE_TTL = 4 * 3600

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
        "алғым", "алу", "келеді", "керек", "бересіз", "берес", "қажет",
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
    if "conversation_history" not in session or session.get("conversation_history") is None:
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
    duration_sec: float | None = None,
) -> tuple[str | None, str]:
    """STT: Together Whisper (kk) + ensemble, LLM refine."""
    settings = get_settings()
    return await transcribe_voice_message(
        audio_bytes,
        settings,
        ai=ai,
        lang_hint=lang_hint,
        filename=filename,
        session=session,
        duration_sec=duration_sec,
    )


async def _voice_text_for_handler(transcribed: str, session: Dict) -> str:
    """Голос → тот же текстовый пайплайн, что и при наборе."""
    from app.bot.stt_normalize import normalize_stt_voice_text
    from app.bot.voice_router import looks_like_credit_question

    normalized = normalize_stt_voice_text(transcribed, session)
    route = await prepare_voice_input(normalized, session)
    if looks_like_credit_question(normalized):
        logger.info("Voice credit question → raw text: %s", normalized[:60])
        return normalized
    logger.info("Voice route source=%s text=%s", route.source, route.text[:60])
    return route.text


async def _send_voice_text_nudge(
    session: Dict,
    chat_id: str,
    lang: str,
    send_fn,
) -> None:
    if not session.pop("from_voice", False):
        return
    try:
        await send_fn(pick_voice_text_nudge(lang, chat_id))
    except Exception:
        logger.exception("Voice text nudge failed chat=%s", chat_id)


def _ensure_session_defaults(session: Dict) -> None:
    if "conversation_history" not in session or session.get("conversation_history") is None:
        session["conversation_history"] = []
    if "message_count" not in session:
        session["message_count"] = 0


async def _try_hybrid_send(
    text: str,
    session: Dict,
    ai: AIClient | None,
    send_fn=None,
    *,
    tg_client=None,
    chat_id: str | None = None,
    nav_step: str | None = None,
) -> bool:
    if tg_client is not None and chat_id is not None:
        send_fn = _tg_send_bound(tg_client, chat_id, session, nav_step=nav_step)
    if send_fn is None:
        return False
    return await send_hybrid_reply(
        text,
        session,
        ai,
        send_fn,
        get_reply=_get_bot_reply,
    )


async def _tg_reply_credit_clarify(
    tg_client,
    chat_id: str,
    session: Dict,
    ai: AIClient | None,
    text: str,
) -> None:
    """FAQ/AI по кредиту, затем меню цифрами."""
    lang = session.get("lang", DEFAULT_LANG)
    _ensure_session_defaults(session)

    if not session.get("city_confirmed"):
        session["state"] = "selecting_city"

    nav = "city" if not session.get("city_confirmed") else "main"
    if await _try_hybrid_send(
        text,
        session,
        ai,
        None,
        tg_client=tg_client,
        chat_id=chat_id,
        nav_step=nav,
    ):
        pass
    elif session.get("city_confirmed"):
        await send_tg_with_hint(
            tg_client,
            chat_id,
            session,
            get_credit_choice_menu(lang),
            nav_step="main",
        )
    else:
        await send_tg_city_step(tg_client, chat_id, session)

    await _send_voice_text_nudge(session, chat_id, lang, tg_client.send_message)
    await _save_session_logged(chat_id, session)


def _tg_send_bound(tg_client, chat_id: str, session: Dict, *, nav_step: str | None = None):
    async def send_fn(message: str, reply_lang: str | None = None):
        await send_tg_with_hint(
            tg_client,
            chat_id,
            session,
            message,
            reply_lang=reply_lang,
            nav_step=nav_step,
        )

    return send_fn


async def _block_if_human_hours(chat_id: str, session: Dict, send_fn) -> bool:
    """True — стоп: будни 09–18, отвечает менеджер (бот молчит)."""
    if is_bot_active_now():
        return False
    now = time.time()
    if now - float(session.get("human_hours_notice_at") or 0) < _HUMAN_HOURS_NOTICE_TTL:
        return True
    session["human_hours_notice_at"] = now
    lang = session.get("lang", DEFAULT_LANG)
    await send_fn(get_human_hours_reply(lang))
    await _save_session_logged(chat_id, session)
    return True


async def _save_session_logged(chat_id: str, session: Dict) -> bool:
    ok = await save_session(chat_id, session)
    if ok:
        logger.info(
            "save_session OK chat=%s state=%s lang=%s city=%s",
            chat_id,
            session.get("state"),
            session.get("lang"),
            session.get("city"),
        )
    else:
        logger.warning("save_session FAILED chat=%s", chat_id)
    return ok


async def _process_tg_voice_message(
    body: Dict[str, Any],
    chat_id: str,
    session: Dict,
    tg_client,
    ai: AIClient | None,
) -> str | None:
    """
    Скачать аудио → STT (текст не показываем клиенту).
    Возвращает текст для дальнейшей обработки или None (ошибка уже отправлена).
    """
    from app.telegram_api import get_voice_duration_sec, get_voice_file_id, get_file_url

    settings = get_settings()
    lang_ui = session.get("lang", DEFAULT_LANG)

    if not settings.is_voice_stt_configured:
        await tg_client.send_message(
            chat_id,
            "🎤 Голосовые временно недоступны. Напишите текстом."
            if lang_ui == "ru"
            else "🎤 Дауыстық хабарлама уақытша жоқ. Мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None

    await tg_client.send_chat_action(
        chat_id,
        "record_voice" if lang_ui == "kk" else "upload_voice",
    )

    try:
        from app.kk_corpus_loader import get_stt_vocab

        corpus_warmup = asyncio.get_running_loop().run_in_executor(None, get_stt_vocab)

        file_id = get_voice_file_id(body)
        logger.info("Voice TG: file_id=%s chat=%s", file_id, chat_id)
        if not file_id:
            raise ValueError("No voice/audio file_id")

        file_info = await tg_client.get_file(file_id)
        if not file_info or not file_info.get("result", {}).get("file_path"):
            raise ValueError("Cannot get Telegram file path")
        file_path = file_info["result"]["file_path"]
        file_url = get_file_url(settings.telegram_bot_token, file_path)
        logger.info("Voice TG: downloading path=%s", file_path)

        import httpx

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(file_url)
            r.raise_for_status()
            audio_bytes = r.content
        logger.info("Voice TG: downloaded %s bytes chat=%s", len(audio_bytes), chat_id)
        await corpus_warmup

        if session.get("lang_locked") and session.get("lang") == "ru":
            lang_hint = "ru"
        else:
            lang_hint = "kk"
        duration_sec = get_voice_duration_sec(body)
        if hasattr(tg_client, "note_stt"):
            tg_client.note_stt(duration_sec=duration_sec)
        logger.info(
            "Voice TG: STT started chat=%s lang_hint=%s dur=%s",
            chat_id,
            lang_hint,
            duration_sec,
        )
        transcribed, detected_lang = await asyncio.wait_for(
            _transcribe_voice(
                audio_bytes,
                ai,
                lang_hint,
                filename="voice.ogg",
                session=session,
                duration_sec=duration_sec,
            ),
            timeout=55.0,
        )
        logger.info(
            "Voice TG: STT result chat=%s lang=%s text=%s",
            chat_id,
            detected_lang,
            (transcribed or "")[:80],
        )

        if not transcribed or not transcribed.strip():
            if hasattr(tg_client, "note_stt"):
                tg_client.note_stt(error="пустой транскрипт")
            await tg_client.send_message(
                chat_id,
                content.VOICE_STT_FAILED_RU
                if lang_ui == "ru"
                else content.VOICE_STT_FAILED_KK,
            )
            await _save_session_logged(chat_id, session)
            return None

        raw = transcribed.strip()
        from app.bot.lang_policy import resolve_voice_lang

        resolve_voice_lang(raw, session, stt_lang=detected_lang)

        cmd_text = await _voice_text_for_handler(raw, session)
        if hasattr(tg_client, "note_stt"):
            tg_client.note_stt(raw=raw, routed=cmd_text, duration_sec=duration_sec)
        logger.info("Voice TG: routed cmd=%s chat=%s", cmd_text[:60], chat_id)
        session["from_voice"] = True
        session["last_voice_raw"] = raw
        await _save_session_logged(chat_id, session)
        return cmd_text

    except asyncio.TimeoutError:
        logger.error("Voice TG: STT timeout chat=%s", chat_id)
        if hasattr(tg_client, "note_stt"):
            tg_client.note_stt(error="timeout 55s")
        await tg_client.send_message(
            chat_id,
            "Не удалось распознать голосовое вовремя. Попробуйте ещё раз или напишите текстом."
            if lang_ui == "ru"
            else "Дауыстықты уақытында тану мүмкін болмады. Қайта жіберіңіз немесе мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None
    except Exception:
        logger.exception("Voice TG: ERROR chat=%s", chat_id)
        if hasattr(tg_client, "note_stt"):
            tg_client.note_stt(error="exception")
        await tg_client.send_message(
            chat_id,
            "Не удалось распознать голосовое. Попробуйте ещё раз или напишите текстом."
            if lang_ui == "ru"
            else "Дауыстықты тану мүмкін болмады. Қайта жіберіңіз немесе мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None


async def _process_wa_voice_message(
    body: Dict[str, Any],
    chat_id: str,
    session: Dict,
    wa_client,
    ai: AIClient | None,
) -> str | None:
    """Скачать аудио из Green API → STT (как в Telegram)."""
    from app.green_api import (
        extract_media_download_url,
        get_audio_filename,
        is_voice_message,
    )

    settings = get_settings()
    lang_ui = session.get("lang", DEFAULT_LANG)
    md = body.get("messageData") or {}
    has_file_data = bool(md.get("fileMessageData"))
    if not is_voice_message(body) and not (has_file_data and not body.get("text")):
        return None

    if not settings.is_voice_stt_configured:
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            "🎤 Голосовые временно недоступны. Напишите текстом."
            if lang_ui == "ru"
            else "🎤 Дауыстық хабарлама уақытша жоқ. Мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None

    try:
        from app.kk_corpus_loader import get_stt_vocab

        corpus_warmup = asyncio.get_running_loop().run_in_executor(None, get_stt_vocab)

        id_message = body.get("idMessage", "")
        media_url = extract_media_download_url(body)
        if not media_url:
            qm = md.get("quotedMessage", {})
            if isinstance(qm, dict):
                qmd = qm.get("message", qm)
                if isinstance(qmd, dict):
                    fmd = qmd.get("fileMessageData", {})
                    media_url = fmd.get("downloadUrl") or fmd.get("url")

        logger.info("Voice WA: downloading chat=%s msg=%s", chat_id, id_message)
        audio_bytes = await wa_client.download_incoming_file(
            chat_id, id_message, media_url
        )
        if not audio_bytes:
            raise ValueError("Cannot download WhatsApp audio")

        await corpus_warmup
        logger.info("Voice WA: downloaded %s bytes chat=%s", len(audio_bytes), chat_id)

        if session.get("lang_locked") and session.get("lang") == "ru":
            lang_hint = "ru"
        else:
            lang_hint = "kk"
        fname = get_audio_filename(body)
        logger.info(
            "Voice WA: STT started chat=%s lang_hint=%s file=%s",
            chat_id,
            lang_hint,
            fname,
        )
        transcribed, detected_lang = await asyncio.wait_for(
            _transcribe_voice(
                audio_bytes,
                ai,
                lang_hint,
                filename=fname,
                session=session,
            ),
            timeout=55.0,
        )
        logger.info(
            "Voice WA: STT result chat=%s lang=%s text=%s",
            chat_id,
            detected_lang,
            (transcribed or "")[:80],
        )

        if not transcribed or not transcribed.strip():
            await send_wa_with_hint(
                wa_client,
                chat_id,
                session,
                content.VOICE_STT_FAILED_RU
                if lang_ui == "ru"
                else content.VOICE_STT_FAILED_KK,
            )
            await _save_session_logged(chat_id, session)
            return None

        raw = transcribed.strip()
        from app.bot.lang_policy import resolve_voice_lang

        resolve_voice_lang(raw, session, stt_lang=detected_lang)

        cmd_text = await _voice_text_for_handler(raw, session)
        if hasattr(wa_client, "note_stt"):
            wa_client.note_stt(raw=raw, routed=cmd_text)
        logger.info("Voice WA: routed cmd=%s chat=%s", cmd_text[:60], chat_id)
        session["from_voice"] = True
        session["last_voice_raw"] = raw
        await _save_session_logged(chat_id, session)
        return cmd_text

    except asyncio.TimeoutError:
        logger.error("Voice WA: STT timeout chat=%s", chat_id)
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            "Не удалось распознать голосовое вовремя. Попробуйте ещё раз или напишите текстом."
            if lang_ui == "ru"
            else "Дауыстықты уақытында тану мүмкін болмады. Қайта жіберіңіз немесе мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None
    except Exception:
        logger.exception("Voice WA: ERROR chat=%s", chat_id)
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            "Не удалось распознать голосовое. Попробуйте ещё раз или напишите текстом."
            if lang_ui == "ru"
            else "Дауыстықты тану мүмкін болмады. Қайта жіберіңіз немесе мәтінмен жазыңыз.",
        )
        await _save_session_logged(chat_id, session)
        return None


async def _wa_reply_credit_clarify(
    wa_client,
    chat_id: str,
    session: Dict,
    ai: AIClient | None,
    text: str,
) -> None:
    """FAQ/AI по кредиту, затем меню цифрами (как в Telegram)."""
    lang = session.get("lang", DEFAULT_LANG)
    _ensure_session_defaults(session)

    if not session.get("city_confirmed"):
        session["state"] = "selecting_city"

    nav = "city" if not session.get("city_confirmed") else "main"
    if await _try_hybrid_send(
        text,
        session,
        ai,
        lambda m: send_wa_with_hint(wa_client, chat_id, session, m, nav_step=nav),
    ):
        pass
    elif session.get("city_confirmed"):
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            get_credit_choice_menu(lang),
            nav_step="main",
        )
    else:
        await send_wa_city_step(wa_client, chat_id, session)

    await _send_voice_text_nudge(
        session,
        chat_id,
        lang,
        lambda m: send_wa_with_hint(wa_client, chat_id, session, m),
    )
    await _save_session_logged(chat_id, session)


def _wa_send_bound(wa_client, chat_id: str, session: Dict, *, nav_step: str | None = None):
    async def send_fn(message: str, reply_lang: str | None = None):
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            message,
            reply_lang=reply_lang,
            nav_step=nav_step,
        )

    return send_fn


async def _handle_manager_reply(
    manager_chat_id: str,
    text: str,
    tg_client,
    wa_client,
) -> None:
    """Прокси ответа менеджера пользователю (Telegram или WhatsApp)."""
    settings = get_settings()
    if str(manager_chat_id) != str(settings.telegram_alert_chat_id):
        return

    parts = text.strip().split(" ", 2)
    if len(parts) < 3:
        await tg_client.send_message(manager_chat_id, "Формат: /reply CHAT_ID текст")
        return

    target_chat_id = parts[1]
    reply_text = parts[2]
    session = await _get_session(target_chat_id)
    platform = session.get("platform", "telegram")

    try:
        if platform == "whatsapp" and wa_client:
            await wa_client.send_message(target_chat_id, f"👨‍💼 {reply_text}")
            label = f"WhatsApp {target_chat_id}"
        else:
            await tg_client.send_message(target_chat_id, f"👨‍💼 {reply_text}")
            label = f"Telegram {target_chat_id}"
        await tg_client.send_message(manager_chat_id, f"✅ Отправлено пользователю {label}")
        logger.info("Manager reply sent to %s (%s)", target_chat_id, platform)
    except Exception as e:
        await tg_client.send_message(manager_chat_id, f"❌ Ошибка: {e}")


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


def _detect_lang_from_free_text(text: str) -> str | None:
    from app.bot.lang_policy import detect_lang_from_free_text

    return detect_lang_from_free_text(text)


def _update_session_lang(text: str, session: Dict) -> str:
    from app.bot.lang_policy import resolve_reply_lang

    return resolve_reply_lang(text, session)


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
    """AI-агент (база знаний) → FAQ fallback → гид."""
    from app.bot.ai_agent import run_kb_agent
    from app.bot.lang_policy import attach_hybrid_footer
    from app.config import get_settings

    settings = get_settings()
    text = normalize_stt_borrower_answer(text, session)
    lang = _update_session_lang(text, session)
    found_city = detect_city(text)
    if found_city:
        session["city"] = found_city
        session["city_confirmed"] = True
    core = strip_leading_greeting(text)
    platform = session.get("platform", "telegram")
    hybrid = settings.hybrid_ai_enabled

    if hybrid and ai and settings.is_ai_configured:
        ai_resp = await run_kb_agent(core, session, ai)
        if ai_resp:
            clean = (
                ai_resp.replace("[NOTIFY_MANAGER]", "")
                .replace("[DONE]", "")
                .strip()
            )
            if clean:
                logger.info("KB agent reply for: %s", core[:40])
                session.pop("guide_attempts", None)
                _update_session_intent(core, session)
                return attach_hybrid_footer(clean, lang, session, enabled=hybrid)

    if settings.fast_faq_enabled:
        fast = try_fast_response(
            core,
            lang,
            session.get("city"),
            platform,
            city_confirmed=session.get("city_confirmed", False),
            session=session,
        )
        if fast:
            logger.info("Fast FAQ fallback for: %s", core[:40])
            session.pop("guide_attempts", None)
            _update_session_intent(core, session)
            if is_borrower_clarify_message(fast):
                session["awaiting_borrower_type"] = True
            elif session.get("awaiting_borrower_type"):
                from app.bot.knowledge_base import detect_business_entity

                if detect_business_entity(core):
                    session.pop("awaiting_borrower_type", None)
            return attach_hybrid_footer(fast, lang, session, enabled=hybrid)

    logger.info("AI/FAQ miss, FAQ guide: %s", core[:40])
    guide = await build_faq_guide_reply(core, lang, session, ai, platform=platform)
    return attach_hybrid_footer(guide, lang, session, enabled=hybrid)


async def _handle_ai_response_with_context(
    text: str,
    session: Dict,
    ai: AIClient | None,
) -> str | None:
    """Обратная совместимость — делегирует в KB-агента."""
    from app.bot.ai_agent import run_kb_agent

    return await run_kb_agent(text, session, ai)


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
            "Хорошо, анкета отменена. Напишите вопрос или *список* — покажу разделы."
            if lang == "ru" else
            "Жарайды, анкета тоқтатылды. Сұрағыңызды жазыңыз немесе *тізім* деп жазыңыз — бөлімдерді көрсетемін."
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

    if choice_key == "mortgage_menu":
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
    wa_client=None,
):
    """Handle Telegram webhook update."""
    from app.telegram_api import (
        extract_update_info, get_message_id,
        is_voice_message, get_voice_file_id, get_file_url
    )
    from app.bot.chat_monitor import create_tg_chat_monitor

    chat_id, text, sender_name, _ = extract_update_info(body)
    monitor = None
    client = tg_client
    if chat_id:
        monitor = create_tg_chat_monitor(
            tg_client,
            body=body,
            source_chat_id=chat_id,
            sender_name=sender_name,
        )
        if monitor:
            client = monitor.client

    try:
        return await _handle_telegram_update_inner(body, client, ai, wa_client)
    except Exception as exc:
        logger.exception("CRITICAL: handle_telegram_update crashed chat=%s: %s", chat_id, exc)
        if chat_id:
            try:
                from app.bot.city_routing import get_universal_fallback_reply
                lang = _sessions.get(str(chat_id), {}).get("lang", DEFAULT_LANG)
                await client.send_message(
                    chat_id,
                    get_universal_fallback_reply(lang, platform="telegram")
                )
            except Exception:
                pass
    finally:
        if monitor:
            await monitor.flush()


async def _handle_telegram_update_inner(
    body: Dict[str, Any],
    tg_client,
    ai: AIClient | None,
    wa_client=None,
):
    """Inner handler — all Telegram logic."""
    from app.telegram_api import (
        extract_update_info, get_message_id,
        is_voice_message, get_voice_file_id, get_file_url
    )

    chat_id, text, sender_name, callback_id = extract_update_info(body)
    if not chat_id:
        return

    text = normalize_list_trigger(text)
    
    msg_id = get_message_id(body)
    
    # Handle /reply command from manager (proxy reply to user)
    if text and text.strip().startswith("/reply "):
        await _handle_manager_reply(chat_id, text, tg_client, wa_client)
        return

    session = await _get_session(chat_id)
    restart = bool(text and text.strip() in LIST_TRIGGER_EXACT)
    if not restart and await _block_if_human_hours(chat_id, session, tg_client.send_message):
        return

    # /start и «список» — шаг 1: язык
    if restart:
        if not chat_id or chat_id == "None":
            logger.error(f"Invalid chat_id for /start: {chat_id}")
            return
        _reset_session(chat_id, "tg")
        _sessions[chat_id]["state"] = "selecting_lang"
        _sessions[chat_id]["platform"] = "tg"
        session = _sessions[chat_id]
        await save_session(chat_id, session)
        await send_tg_lang_step(tg_client, chat_id, session)
        return

    # Inline-кнопки (legacy): тот же результат, что цифры в WhatsApp
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

    if text and text.strip() == "99":
        session["state"] = "selecting_lang"
        session.pop("city_confirmed", None)
        await save_session(chat_id, session)
        await send_tg_lang_step(tg_client, chat_id, session)
        return

    if text and text.strip() == "98":
        if not session.get("lang_locked"):
            await send_tg_lang_step(tg_client, chat_id, session)
            return
        session["state"] = "selecting_city"
        await save_session(chat_id, session)
        await send_tg_city_step(tg_client, chat_id, session)
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
    
    # Handle voice message (voice + audio)
    if is_voice_message(body):
        voice_text = await _process_tg_voice_message(body, chat_id, session, tg_client, ai)
        if voice_text is None:
            return
        text = voice_text
        logger.info("Voice TG: dispatching text=%s chat=%s", text[:60], chat_id)
    
    msg = body.get("message") or {}
    if not text and msg and (msg.get("photo") or msg.get("document")):
        lang_ph = session.get("lang", DEFAULT_LANG)
        await tg_client.send_message(chat_id, get_media_menu_reply(lang_ph))
        if session.get("city_confirmed"):
            await send_tg_main_menu(tg_client, chat_id, session)
        elif session.get("state") == "selecting_city":
            await send_tg_city_step(tg_client, chat_id, session)
        else:
            await send_tg_lang_step(tg_client, chat_id, session)
        return

    if not text:
        return

    text_stripped = text.strip()
    lang = session.get("lang", DEFAULT_LANG)
    _ensure_session_defaults(session)

    # Голос/текст «хочу кредит» — сразу меню (до приветствий и small talk)
    if session.get("state") == "idle" and is_vague_credit_request(text_stripped):
        await _tg_reply_credit_clarify(tg_client, chat_id, session, ai, text_stripped)
        return

    # Явное «русский» / «қазақша» вне мастера — переключить без повторных вопросов
    from app.bot.lang_policy import (
        apply_lang_switch,
        is_explicit_lang_message,
        lang_switch_confirmation,
    )

    if apply_lang_switch(text_stripped, session) and is_explicit_lang_message(text_stripped):
        lang = session["lang"]
        await send_tg_with_hint(
            tg_client, chat_id, session, lang_switch_confirmation(lang), reply_lang=lang
        )
        if session.get("city_confirmed") and session.get("city"):
            await send_tg_main_menu(tg_client, chat_id, session)
        elif session.get("state") != "selecting_city":
            session["state"] = "selecting_city"
            await send_tg_city_step(tg_client, chat_id, session)
        await _save_session_logged(chat_id, session)
        return

    # Выбор языка: 1/2, слова, или сразу русский/казахский текст → город
    if session.get("state") == "selecting_lang":
        lang_digit = parse_lang_digit(text_stripped)
        if lang_digit:
            session["lang"] = "kk" if lang_digit == "1" else "ru"
            session["lang_locked"] = True
            session["state"] = "selecting_city"
            session.pop("lang_retry", None)
            await _save_session_logged(chat_id, session)
            await send_tg_city_step(tg_client, chat_id, session)
            return
        if not is_explicit_lang_message(text_stripped):
            session["lang"] = _detect_lang_from_free_text(text_stripped) or DEFAULT_LANG
            session["lang_locked"] = True
            session.pop("lang_retry", None)
            found_city = try_resolve_city_from_text(text_stripped)
            if found_city:
                session["city"] = found_city
                session["city_confirmed"] = True
                session["state"] = "idle"
                await _save_session_logged(chat_id, session)
                await send_tg_main_menu(tg_client, chat_id, session)
                return
            session["state"] = "selecting_city"
            if await _try_hybrid_send(
                text_stripped,
                session,
                ai,
                None,
                tg_client=tg_client,
                chat_id=chat_id,
                nav_step="city",
            ):
                await _save_session_logged(chat_id, session)
                return
            if is_vague_credit_request(text_stripped):
                await _tg_reply_credit_clarify(
                    tg_client, chat_id, session, ai, text_stripped
                )
                return
            await _save_session_logged(chat_id, session)
            await send_tg_city_step(tg_client, chat_id, session)
            return
        attempt = session.get("lang_retry", 0)
        session["lang_retry"] = attempt + 1
        await send_tg_with_hint(
            tg_client,
            chat_id,
            session,
            get_lang_retry_message(lang, attempt),
            nav_step="lang",
        )
        await _save_session_logged(chat_id, session)
        return

    if session.get("state") == "selecting_city":
        if text_stripped == "7":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await send_tg_with_hint(
                tg_client,
                chat_id,
                session,
                content.get_operator_message_with_phone(lang, None, "telegram"),
                nav_step="main",
            )
            await _notify_manager(
                f"🚨 *Менеджер на шаге города (Telegram)*\nChat: `{chat_id}`",
                chat_id,
                "telegram",
                session=session,
            )
            await save_session(chat_id, session)
            return

        if await _try_hybrid_send(
            text_stripped,
            session,
            ai,
            None,
            tg_client=tg_client,
            chat_id=chat_id,
            nav_step="city",
        ):
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
            await send_tg_main_menu(tg_client, chat_id, session)
            return

        if not is_wizard_nav_input(text_stripped, session):
            reply = await _get_bot_reply(text_stripped, session, ai)
            if reply:
                await send_tg_with_hint(
                    tg_client, chat_id, session, reply, nav_step="city"
                )
                await save_session(chat_id, session)
                return
        await send_tg_city_step(tg_client, chat_id, session)
        await save_session(chat_id, session)
        return

    if text_stripped == "0":
        if session.get("city_confirmed") and session.get("city"):
            await send_tg_main_menu(tg_client, chat_id, session)
        elif session.get("state") == "selecting_city":
            await send_tg_city_help(tg_client, chat_id, session)
        elif session.get("lang_locked"):
            session["state"] = "selecting_city"
            await send_tg_city_step(tg_client, chat_id, session)
        else:
            session["state"] = "selecting_lang"
            await send_tg_lang_step(tg_client, chat_id, session)
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
    
    session["conversation_history"].append({
        "role": "user",
        "text": text_stripped,
        "timestamp": time.time(),
    })
    session["conversation_history"] = session["conversation_history"][-10:]
    session["message_count"] = session.get("message_count", 0) + 1
    platform = session.get("platform", "tg")
    
    # Check if user asked for menu (any platform)
    if any(w in text_stripped.lower() for w in LIST_TRIGGER_KEYWORDS) and session.get("state") == "idle":
        if session.get("city_confirmed"):
            await send_tg_main_menu(tg_client, chat_id, session)
        else:
            await send_tg_lang_step(tg_client, chat_id, session)
        return

    if (
        session.get("state") == "idle"
        and not session.get("city_confirmed")
        and not session.get("lang_locked")
        and is_pure_greeting(text_stripped)
    ):
        await send_tg_lang_step(tg_client, chat_id, session)
        await _save_session_logged(chat_id, session)
        return

    # Log message to database
    await log_message(chat_id, platform, "user", text_stripped, lang)
    
    # Check for small talk (не перехватывать «салам, хочу кредит»)
    if session.get("state") == "idle" and not is_vague_credit_request(text_stripped) and (
        is_pure_greeting(text_stripped) or detect_small_talk_intent(text_stripped) == "greeting"
    ):
        if not session.get("lang_locked"):
            await send_tg_lang_step(tg_client, chat_id, session)
        elif not session.get("city_confirmed"):
            await send_tg_city_step(tg_client, chat_id, session)
        else:
            await send_tg_main_menu(tg_client, chat_id, session)
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
                await send_tg_main_menu(tg_client, chat_id, session)
                await save_session(chat_id, session)
                return
            session.pop("nearby_pick", None)

        found_city = detect_city(text_stripped)
        if found_city:
            session["city"] = found_city
            session["city_confirmed"] = True
            session.pop("nearby_pick", None)
            await send_tg_main_menu(tg_client, chat_id, session)
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
            await send_tg_main_menu(tg_client, chat_id, session)
            await _save_session_logged(chat_id, session)
            return

        from app.bot.voice_router import extract_spoken_digit, map_menu_phrase

        _maybe_digit = text_stripped
        phrase_digit = map_menu_phrase(_maybe_digit)
        if phrase_digit and phrase_digit not in ("0", "98", "99"):
            _maybe_digit = phrase_digit
        else:
            spoken = extract_spoken_digit(_maybe_digit)
            if spoken and spoken not in ("0", "98", "99"):
                _maybe_digit = spoken

        if session.get("submenu") == "mortgage":
            mapped_mort = content.WA_MORTGAGE_DIGIT_MAP.get(_maybe_digit)
            if mapped_mort == "back_to_main":
                session["submenu"] = None
                await send_tg_main_menu(tg_client, chat_id, session)
                await _save_session_logged(chat_id, session)
                return
            if mapped_mort:
                session["submenu"] = None
                if await _try_handle_menu_digit(
                    mapped_mort,
                    session,
                    _tg_send_bound(tg_client, chat_id, session, nav_step="main"),
                    platform="telegram",
                ):
                    await _save_session_logged(chat_id, session)
                    return

        if _maybe_digit in content.WA_DIGIT_MAP and session.get("state") != "selecting_lang":
            mapped = content.WA_DIGIT_MAP.get(_maybe_digit)
            if mapped == "operator":
                session["state"] = "handoff"
                session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
                await send_tg_with_hint(
                    tg_client,
                    chat_id,
                    session,
                    content.get_operator_message_with_phone(lang, session.get("city"), "telegram"),
                )
                await _notify_manager(
                    f"🚨 *Меню → менеджер (Telegram)*\nChat: `{chat_id}`",
                    chat_id,
                    "telegram",
                    session=session,
                )
                await _save_session_logged(chat_id, session)
                return
            if mapped and await _try_handle_menu_digit(
                mapped,
                session,
                _tg_send_bound(tg_client, chat_id, session, nav_step="main"),
                platform="telegram",
            ):
                await _save_session_logged(chat_id, session)
                return

        menu_digit = resolve_menu_digit_from_text(text_stripped, session)
        if menu_digit and menu_digit not in ("0", "98", "99") and session.get("city_confirmed"):
            if menu_digit == "7":
                session["state"] = "handoff"
                session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
                await tg_client.send_message(
                    chat_id,
                    content.get_operator_message_with_phone(lang, session.get("city")),
                )
                await _notify_manager(
                    f"🚨 *Голос/текст → менеджер*\nChat: `{chat_id}`\nСообщение: {text_stripped}",
                    chat_id,
                    "telegram",
                    session=session,
                )
                await _send_voice_text_nudge(session, chat_id, lang, tg_client.send_message)
                await _save_session_logged(chat_id, session)
                return
            if await _try_handle_menu_digit(
                menu_digit,
                session,
                _tg_send_bound(tg_client, chat_id, session, nav_step="main"),
                platform="telegram",
            ):
                await _send_voice_text_nudge(session, chat_id, lang, tg_client.send_message)
                await _save_session_logged(chat_id, session)
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
            await _send_voice_text_nudge(session, chat_id, lang, tg_client.send_message)
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
            await send_tg_with_hint(
                tg_client,
                chat_id,
                session,
                get_text_fallback_reply(lang, platform="telegram"),
                nav_step="main",
            )
            await _send_voice_text_nudge(
                session, chat_id, lang, _tg_send_bound(tg_client, chat_id, session)
            )
        await _save_session_logged(chat_id, session)
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

    # Умный маппинг фраз → цифры (как в WhatsApp): "ипотека" → "4"
    from app.bot.voice_router import map_menu_phrase
    phrase_digit = map_menu_phrase(text_stripped)
    word_count = len(text_stripped.split())
    if (
        phrase_digit
        and phrase_digit not in ("0", "98", "99")
        and session.get("city_confirmed")
        and word_count <= 6
    ):
        ai_response = await _get_bot_reply(phrase_digit, session, ai)
        if ai_response:
            session["conversation_history"].append({
                "role": "assistant",
                "text": ai_response,
                "timestamp": time.time()
            })
            await tg_client.send_message(chat_id, ai_response)
            await save_session(chat_id, session)
            return

    ai_response = await _get_bot_reply(text_stripped, session, ai)
    if ai_response:
        session["conversation_history"].append({
            "role": "assistant",
            "text": ai_response,
            "timestamp": time.time()
        })
        await tg_client.send_message(chat_id, ai_response)
    else:
        # Универсальный fallback — бот НИКОГДА не молчит
        fallback = get_text_fallback_reply(lang, platform="telegram")
        await tg_client.send_message(chat_id, fallback)
    await save_session(chat_id, session)


async def handle_whatsapp_update(
    body: Dict[str, Any],
    wa_client,
    ai: AIClient | None,
    tg_client=None,
):
    """Handle WhatsApp (Green API) webhook update — crash-safe wrapper."""
    from app.green_api import extract_green_info
    from app.bot.chat_monitor import create_wa_chat_monitor

    chat_id, text, sender_name, _ = extract_green_info(body)
    monitor = None
    client = wa_client
    if chat_id:
        monitor = create_wa_chat_monitor(
            wa_client,
            tg_client,
            body=body,
            source_chat_id=chat_id,
            sender_name=sender_name,
            initial_text=text,
        )
        if monitor:
            client = monitor.client

    try:
        return await _handle_whatsapp_update_inner(body, client, ai)
    except Exception:
        logger.exception("CRITICAL: handle_whatsapp_update crashed chat=%s", chat_id)
        if chat_id:
            try:
                from app.bot.city_routing import get_universal_fallback_reply
                lang = _sessions.get(str(chat_id), {}).get("lang", DEFAULT_LANG)
                await client.send_message(
                    chat_id,
                    get_universal_fallback_reply(lang, platform="whatsapp"),
                )
            except Exception:
                pass
    finally:
        if monitor:
            await monitor.flush()


async def _handle_whatsapp_update_inner(
    body: Dict[str, Any],
    wa_client,
    ai: AIClient | None,
):
    """Inner WhatsApp handler — зеркало Telegram (цифры, wizard, голос, handoff, AI)."""
    from app.green_api import extract_green_info, is_image_message, is_voice_message

    chat_id, text, sender_name, _media_url = extract_green_info(body)
    if not chat_id:
        return

    text = normalize_list_trigger(text)
    session = await _get_session(chat_id)
    session["platform"] = "whatsapp"

    restart = bool(
        text
        and (text.strip() in LIST_TRIGGER_EXACT or text.strip().lower() == "start")
    )

    async def wa_send(
        message: str,
        reply_lang: str | None = None,
        *,
        nav_step: str | None = None,
    ) -> None:
        await send_wa_with_hint(
            wa_client,
            chat_id,
            session,
            message,
            reply_lang=reply_lang,
            nav_step=nav_step,
        )

    if not restart and await _block_if_human_hours(chat_id, session, wa_send):
        return

    if restart:
        _reset_session(chat_id, "whatsapp")
        session = await _get_session(chat_id)
        session["state"] = "selecting_lang"
        session["platform"] = "whatsapp"
        await save_session(chat_id, session)
        await send_wa_lang_step(wa_client, chat_id, session)
        return

    if text and text.strip() == "99":
        session["state"] = "selecting_lang"
        session.pop("city_confirmed", None)
        await save_session(chat_id, session)
        await send_wa_lang_step(wa_client, chat_id, session)
        return

    if text and text.strip() == "98":
        if not session.get("lang_locked"):
            await send_wa_lang_step(wa_client, chat_id, session)
            return
        session["state"] = "selecting_city"
        await save_session(chat_id, session)
        await send_wa_city_step(wa_client, chat_id, session)
        return

    if sender_name:
        session["contact_name"] = sender_name

    if session.get("state") == "office_directed" and (text or "").strip() not in LIST_TRIGGER_EXACT:
        session["state"] = "idle"

    if _is_handoff_active(session):
        if text and text.lower() in ["бот", "bot", "жүйе", "system"]:
            session["state"] = "idle"
            session["handoff_until"] = 0
            await wa_send(
                content.HANDOFF_RELEASED_RU
                if session.get("lang", DEFAULT_LANG) == "ru"
                else content.HANDOFF_RELEASED_KK
            )
            await save_session(chat_id, session)
            return
        if text:
            lang_h = session.get("lang", DEFAULT_LANG)
            note = (
                "Менеджер скоро ответит. Напишите *бот* чтобы вернуться к боту."
                if lang_h == "ru"
                else "Менеджер жақын арада жауап береді. Ботқа оралу үшін *бот* жазыңыз."
            )
            await wa_send(note)
        return

    md = body.get("messageData") or {}
    has_file_data = bool(md.get("fileMessageData"))
    is_voice = is_voice_message(body) or (has_file_data and not text)
    if is_voice:
        voice_text = await _process_wa_voice_message(
            body, chat_id, session, wa_client, ai
        )
        if voice_text is None:
            return
        text = voice_text
        logger.info("Voice WA: dispatching text=%s chat=%s", text[:60], chat_id)
        if hasattr(wa_client, "note_incoming_text"):
            wa_client.note_incoming_text(text)

    if is_image_message(body):
        lang_ph = session.get("lang", DEFAULT_LANG)
        await wa_send(get_media_menu_reply(lang_ph))
        if session.get("city_confirmed"):
            await send_wa_main_menu(wa_client, chat_id, session)
        elif session.get("state") == "selecting_city":
            await send_wa_city_step(wa_client, chat_id, session)
        else:
            await send_wa_lang_step(wa_client, chat_id, session)
        return

    if not text:
        return

    text_stripped = text.strip()
    lang = session.get("lang", DEFAULT_LANG)
    _ensure_session_defaults(session)

    if session.get("state") == "idle" and is_vague_credit_request(text_stripped):
        await _wa_reply_credit_clarify(wa_client, chat_id, session, ai, text_stripped)
        return

    from app.bot.lang_policy import (
        apply_lang_switch,
        is_explicit_lang_message,
        lang_switch_confirmation,
    )

    if apply_lang_switch(text_stripped, session) and is_explicit_lang_message(text_stripped):
        lang = session["lang"]
        await wa_send(lang_switch_confirmation(lang), reply_lang=lang)
        if session.get("city_confirmed") and session.get("city"):
            await send_wa_main_menu(wa_client, chat_id, session)
        elif session.get("state") != "selecting_city":
            session["state"] = "selecting_city"
            await send_wa_city_step(wa_client, chat_id, session)
        await _save_session_logged(chat_id, session)
        return

    if session.get("state") == "selecting_lang":
        lang_digit = parse_lang_digit(text_stripped)
        if lang_digit:
            session["lang"] = "kk" if lang_digit == "1" else "ru"
            session["lang_locked"] = True
            session["state"] = "selecting_city"
            session.pop("lang_retry", None)
            await _save_session_logged(chat_id, session)
            await send_wa_city_step(wa_client, chat_id, session)
            return
        if not is_explicit_lang_message(text_stripped):
            session["lang"] = _detect_lang_from_free_text(text_stripped) or DEFAULT_LANG
            session["lang_locked"] = True
            session.pop("lang_retry", None)
            found_city = try_resolve_city_from_text(text_stripped)
            if found_city:
                session["city"] = found_city
                session["city_confirmed"] = True
                session["state"] = "idle"
                await _save_session_logged(chat_id, session)
                await send_wa_main_menu(wa_client, chat_id, session)
                return
            session["state"] = "selecting_city"
            if await _try_hybrid_send(
                text_stripped,
                session,
                ai,
                lambda m: send_wa_with_hint(
                    wa_client, chat_id, session, m, nav_step="city"
                ),
            ):
                await _save_session_logged(chat_id, session)
                return
            if is_vague_credit_request(text_stripped):
                await _wa_reply_credit_clarify(
                    wa_client, chat_id, session, ai, text_stripped
                )
                return
            await _save_session_logged(chat_id, session)
            await send_wa_city_step(wa_client, chat_id, session)
            return
        attempt = session.get("lang_retry", 0)
        session["lang_retry"] = attempt + 1
        await wa_send(get_lang_retry_message(lang, attempt), nav_step="lang")
        await _save_session_logged(chat_id, session)
        return

    if session.get("state") == "selecting_city":
        if text_stripped == "7":
            session["state"] = "handoff"
            session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
            await wa_send(
                content.get_operator_message_with_phone(lang, None, "whatsapp"),
                nav_step="main",
            )
            await _notify_manager(
                f"🚨 *Менеджер на шаге города (WhatsApp)*\nPhone: `{chat_id}`",
                chat_id,
                "whatsapp",
                session=session,
            )
            await save_session(chat_id, session)
            return

        if await _try_hybrid_send(
            text_stripped,
            session,
            ai,
            lambda m: send_wa_with_hint(
                wa_client, chat_id, session, m, nav_step="city"
            ),
        ):
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
            await send_wa_main_menu(wa_client, chat_id, session)
            return

        if not is_wizard_nav_input(text_stripped, session):
            reply = await _get_bot_reply(text_stripped, session, ai)
            if reply:
                await wa_send(reply, nav_step="city")
                await save_session(chat_id, session)
                return
        await send_wa_city_step(wa_client, chat_id, session)
        await save_session(chat_id, session)
        return

    if text_stripped == "0":
        if session.get("city_confirmed") and session.get("city"):
            await send_wa_main_menu(wa_client, chat_id, session)
        elif session.get("state") == "selecting_city":
            await send_wa_city_help(wa_client, chat_id, session)
        elif session.get("lang_locked"):
            session["state"] = "selecting_city"
            await send_wa_city_step(wa_client, chat_id, session)
        else:
            session["state"] = "selecting_lang"
            await send_wa_lang_step(wa_client, chat_id, session)
        await save_session(chat_id, session)
        return

    if any(
        word in text_stripped.lower()
        for word in ["оператор", "менеджер", "человек", "маман", "админ"]
    ):
        session["state"] = "handoff"
        session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
        await wa_send(
            content.get_operator_message_with_phone(lang, session.get("city"), "whatsapp")
        )
        await _notify_manager(
            f"🚨 *Запрос оператора*\nPhone: `{chat_id}`\nСообщение: {text_stripped}",
            chat_id,
            "whatsapp",
            session=session,
        )
        await save_session(chat_id, session)
        return

    session["conversation_history"].append({
        "role": "user",
        "text": text_stripped,
        "timestamp": time.time(),
    })
    session["conversation_history"] = session["conversation_history"][-10:]
    session["message_count"] = session.get("message_count", 0) + 1
    platform = session.get("platform", "whatsapp")

    if (
        any(w in text_stripped.lower() for w in LIST_TRIGGER_KEYWORDS)
        and session.get("state") == "idle"
    ):
        if session.get("city_confirmed"):
            await send_wa_main_menu(wa_client, chat_id, session)
        else:
            await send_wa_lang_step(wa_client, chat_id, session)
        return

    if (
        session.get("state") == "idle"
        and not session.get("city_confirmed")
        and not session.get("lang_locked")
        and is_pure_greeting(text_stripped)
    ):
        await send_wa_lang_step(wa_client, chat_id, session)
        await _save_session_logged(chat_id, session)
        return

    await log_message(chat_id, platform, "user", text_stripped, lang)

    if session.get("state") == "idle" and not is_vague_credit_request(text_stripped) and (
        is_pure_greeting(text_stripped)
        or detect_small_talk_intent(text_stripped) == "greeting"
    ):
        if not session.get("lang_locked"):
            await send_wa_lang_step(wa_client, chat_id, session)
        elif not session.get("city_confirmed"):
            await send_wa_city_step(wa_client, chat_id, session)
        else:
            await send_wa_main_menu(wa_client, chat_id, session)
        await save_session(chat_id, session)
        return

    small_talk_intent = detect_small_talk_intent(text_stripped)
    if small_talk_intent and session.get("state") == "idle":
        await wa_send(get_small_talk_response(small_talk_intent, lang))
        return

    is_calc, calc_params = detect_calculator_intent(text_stripped)
    if is_calc and calc_params:
        calc_result = format_calculator_result(calc_params, lang)
        await wa_send(calc_result)
        session["conversation_history"].append({
            "role": "assistant",
            "text": calc_result,
            "timestamp": time.time(),
        })
        await log_message(chat_id, platform, "assistant", calc_result, lang)
        await save_session(chat_id, session)
        return

    if session.get("state") == "idle":
        if session.get("nearby_pick") and text_stripped.isdigit():
            opts = session.get("nearby_pick") or []
            idx = int(text_stripped) - 1
            if 0 <= idx < len(opts):
                session["city"] = opts[idx]
                session["city_confirmed"] = True
                session.pop("nearby_pick", None)
                await send_wa_main_menu(wa_client, chat_id, session)
                await save_session(chat_id, session)
                return
            session.pop("nearby_pick", None)

        found_city = detect_city(text_stripped)
        if found_city:
            session["city"] = found_city
            session["city_confirmed"] = True
            session.pop("nearby_pick", None)
            await send_wa_main_menu(wa_client, chat_id, session)
            await save_session(chat_id, session)
            return

        nearby = detect_nearby_offices(text_stripped, lang)
        if nearby:
            place, keys, _dists = nearby
            session["nearby_pick"] = keys
            await wa_send(format_nearby_offices_reply(place, keys, lang))
            await save_session(chat_id, session)
            return

    if session.get("state") == "idle":
        if is_pure_greeting(text_stripped):
            await send_wa_main_menu(wa_client, chat_id, session)
            await _save_session_logged(chat_id, session)
            return

        from app.bot.voice_router import extract_spoken_digit, map_menu_phrase

        _maybe_digit = text_stripped
        phrase_digit = map_menu_phrase(_maybe_digit)
        if phrase_digit and phrase_digit not in ("0", "98", "99"):
            _maybe_digit = phrase_digit
        else:
            spoken = extract_spoken_digit(_maybe_digit)
            if spoken and spoken not in ("0", "98", "99"):
                _maybe_digit = spoken

        if session.get("submenu") == "mortgage":
            mapped_mort = content.WA_MORTGAGE_DIGIT_MAP.get(_maybe_digit)
            if mapped_mort == "back_to_main":
                session["submenu"] = None
                await send_wa_main_menu(wa_client, chat_id, session)
                await _save_session_logged(chat_id, session)
                return
            if mapped_mort:
                session["submenu"] = None
                if await _try_handle_menu_digit(
                    mapped_mort,
                    session,
                    _wa_send_bound(wa_client, chat_id, session, nav_step="main"),
                    platform="whatsapp",
                ):
                    await _save_session_logged(chat_id, session)
                    return

        if _maybe_digit in content.WA_DIGIT_MAP and session.get("state") != "selecting_lang":
            mapped = content.WA_DIGIT_MAP.get(_maybe_digit)
            if mapped == "operator":
                session["state"] = "handoff"
                session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
                await wa_send(
                    content.get_operator_message_with_phone(
                        lang, session.get("city"), "whatsapp"
                    ),
                    nav_step="main",
                )
                await _notify_manager(
                    f"🚨 *Меню → менеджер (WhatsApp)*\nPhone: `{chat_id}`",
                    chat_id,
                    "whatsapp",
                    session=session,
                )
                await _save_session_logged(chat_id, session)
                return
            if mapped and await _try_handle_menu_digit(
                mapped,
                session,
                _wa_send_bound(wa_client, chat_id, session, nav_step="main"),
                platform="whatsapp",
            ):
                await _save_session_logged(chat_id, session)
                return

        menu_digit = resolve_menu_digit_from_text(text_stripped, session)
        if menu_digit and menu_digit not in ("0", "98", "99") and session.get("city_confirmed"):
            if menu_digit == "7":
                session["state"] = "handoff"
                session["handoff_until"] = time.time() + get_settings().handoff_timeout_hours * 3600
                await wa_send(
                    content.get_operator_message_with_phone(lang, session.get("city"), "whatsapp")
                )
                await _notify_manager(
                    f"🚨 *Голос/текст → менеджер*\nPhone: `{chat_id}`\nСообщение: {text_stripped}",
                    chat_id,
                    "whatsapp",
                    session=session,
                )
                await _send_voice_text_nudge(
                    session,
                    chat_id,
                    lang,
                    lambda m: send_wa_with_hint(wa_client, chat_id, session, m),
                )
                await _save_session_logged(chat_id, session)
                return
            if await _try_handle_menu_digit(
                menu_digit,
                session,
                _wa_send_bound(wa_client, chat_id, session, nav_step="main"),
                platform="whatsapp",
            ):
                await _send_voice_text_nudge(
                    session,
                    chat_id,
                    lang,
                    lambda m: send_wa_with_hint(wa_client, chat_id, session, m),
                )
                await _save_session_logged(chat_id, session)
                return

        ai_response = await _get_bot_reply(text_stripped, session, ai)
        if ai_response:
            notify_manager = "[NOTIFY_MANAGER]" in ai_response
            dialog_done = "[DONE]" in ai_response
            clean_response = (
                ai_response.replace("[NOTIFY_MANAGER]", "").replace("[DONE]", "").strip()
            )
            session["conversation_history"].append({
                "role": "assistant",
                "text": clean_response,
                "timestamp": time.time(),
            })
            await wa_send(clean_response)
            await _send_voice_text_nudge(
                session,
                chat_id,
                lang,
                lambda m: send_wa_with_hint(wa_client, chat_id, session, m),
            )
            await log_message(chat_id, platform, "assistant", clean_response, lang)
            if notify_manager:
                await _notify_manager(
                    f"❓ *Клиент задал вопрос вне базы знаний*\nВопрос: {text_stripped}",
                    chat_id,
                    platform,
                    session=session,
                )
            if dialog_done:
                session["state"] = "office_directed"
        else:
            await wa_send(
                get_text_fallback_reply(lang, platform="whatsapp"),
                nav_step="main",
            )
            await _send_voice_text_nudge(
                session,
                chat_id,
                lang,
                lambda m: send_wa_with_hint(wa_client, chat_id, session, m),
            )
        await _save_session_logged(chat_id, session)
        return

    if session.get("state") == "in_flow":
        session["state"] = "idle"
        session.pop("product", None)
        session.pop("flow_step", None)

    from app.bot.voice_router import map_menu_phrase

    phrase_digit = map_menu_phrase(text_stripped)
    word_count = len(text_stripped.split())
    if (
        phrase_digit
        and phrase_digit not in ("0", "98", "99")
        and session.get("city_confirmed")
        and word_count <= 6
    ):
        ai_response = await _get_bot_reply(phrase_digit, session, ai)
        if ai_response:
            session["conversation_history"].append({
                "role": "assistant",
                "text": ai_response,
                "timestamp": time.time(),
            })
            await wa_send(ai_response)
            await save_session(chat_id, session)
            return

    ai_response = await _get_bot_reply(text_stripped, session, ai)
    if ai_response:
        session["conversation_history"].append({
            "role": "assistant",
            "text": ai_response,
            "timestamp": time.time(),
        })
        await wa_send(ai_response)
    else:
        fallback = get_text_fallback_reply(lang, platform="whatsapp")
        await wa_send(fallback)
    await save_session(chat_id, session)
