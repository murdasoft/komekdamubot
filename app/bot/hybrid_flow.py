"""
Гибридный ответ (FAQ + AI) во время мастера и в свободном диалоге.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from app.bot.chatbot_ux import parse_lang_digit
from app.bot.lang_policy import is_explicit_lang_message
from app.bot.wizard import resolve_city_digit
from app.offices import detect_city

if TYPE_CHECKING:
    from app.ai_client import AIClient


def is_wizard_nav_input(text: str, session: dict) -> bool:
    """Цифры/команды мастера — не отправлять в AI."""
    t = (text or "").strip()
    if not t:
        return False
    if t in ("0", "98", "99", "7"):
        return True
    state = session.get("state")
    if state == "selecting_lang":
        if parse_lang_digit(t) in ("1", "2"):
            return True
        if is_explicit_lang_message(t):
            return True
    if state == "selecting_city":
        if resolve_city_digit(t):
            return True
        if detect_city(t):
            return True
    return False


def looks_like_free_question(text: str, session: dict) -> bool:
    """Любой не-навигационный текст → AI-агент."""
    t = (text or "").strip()
    if len(t) < 2:
        return False
    if is_wizard_nav_input(t, session):
        return False
    return True


async def send_hybrid_reply(
    text: str,
    session: dict,
    ai: Optional["AIClient"],
    send_fn: Callable[[str], Awaitable[None]],
    *,
    get_reply,
) -> bool:
    """
    FAQ → AI → гид. True если ответ отправлен.
    get_reply — app.bot.handlers._get_bot_reply (инъекция без циклического импорта).
    """
    if not looks_like_free_question(text, session):
        return False

    reply = await get_reply(text, session, ai)
    if not reply:
        return False

    history = session.setdefault("conversation_history", [])
    history.append({"role": "user", "text": text, "timestamp": time.time()})
    history.append({"role": "assistant", "text": reply, "timestamp": time.time()})
    session["conversation_history"] = history[-10:]

    await send_fn(reply)
    return True
