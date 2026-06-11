"""
Telegram: навигация как в WhatsApp (текст + цифры).
Старые inline-callback обрабатываются как выбор цифрой.
"""

from __future__ import annotations

import logging
from typing import Any

from app.bot.formatting import format_office_city
from app.bot.menu import menu_choice_body, resolve_menu_digit
from app.bot.tg_wa_ui import (
    send_tg_city_step,
    send_tg_lang_step,
    send_tg_main_menu,
    send_tg_with_hint,
)
from app.bot import content
from app.offices import get_contact_footer

logger = logging.getLogger(__name__)


def _set_menu_intent_session(choice_key: str, session: dict) -> None:
    mapping = {
        "ip_business": ("business_credit", "ip"),
        "too_business": ("business_credit", "too"),
        "personal_credit": ("personal_credit", "personal"),
        "mortgage_menu": ("mortgage_standard", None),
        "damu": ("damu", None),
        "refinancing": ("refinancing", None),
    }
    intent, entity = mapping.get(choice_key, (choice_key, None))
    session["last_intent"] = intent
    if entity:
        session["last_entity"] = entity
    session["state"] = "idle"
    session["product"] = None
    session["flow_step"] = None


async def _send_product_answer(
    tg_client: Any,
    chat_id: str,
    session: dict,
    choice_key: str,
) -> bool:
    lang = session.get("lang", "kk")
    city = session.get("city")
    body = menu_choice_body(choice_key, lang)
    if not body:
        return False
    if city:
        body = f"{body}\n\n{get_contact_footer(city, lang, all_cities=False, platform='telegram')}"  # type: ignore[arg-type]
    _set_menu_intent_session(choice_key, session)
    await send_tg_with_hint(tg_client, chat_id, session, body, nav_step="main")
    if choice_key == "mortgage_menu":
        session["submenu"] = "mortgage"
        await send_tg_with_hint(
            tg_client,
            chat_id,
            session,
            content.get_wa_mortgage_menu(lang),
            nav_step="main",
        )
    return True


async def handle_nav_callback(
    data: str,
    session: dict,
    tg_client: Any,
    chat_id: str,
    message_id: int,
) -> str | None:
    """nav:* / menu:* / mort:* — тот же результат, что цифры в WhatsApp."""
    _ = message_id
    lang = session.get("lang", "kk")
    city = session.get("city")

    if data.startswith("nav:lang:"):
        code = data.split(":")[-1]
        session["lang"] = code
        session["lang_locked"] = True
        session["state"] = "selecting_city"
        await send_tg_city_step(tg_client, chat_id, session)
        return None

    if data.startswith("nav:city:"):
        session["city"] = data.split(":")[-1]
        session["city_confirmed"] = True
        session["state"] = "idle"
        await send_tg_main_menu(tg_client, chat_id, session)
        return None

    if data == "nav:back:lang":
        session["state"] = "selecting_lang"
        session.pop("city_confirmed", None)
        await send_tg_lang_step(tg_client, chat_id, session)
        return None

    if data == "nav:back:city":
        session["state"] = "selecting_city"
        session.pop("city_confirmed", None)
        await send_tg_city_step(tg_client, chat_id, session)
        return None

    if data == "nav:back:main":
        if city:
            await send_tg_main_menu(tg_client, chat_id, session)
        else:
            await send_tg_city_step(tg_client, chat_id, session)
        return None

    if data.startswith("menu:"):
        digit = data.split(":")[1]
        if digit == "7":
            return "operator"
        if not city:
            return None
        choice = resolve_menu_digit(digit)
        if choice:
            await _send_product_answer(tg_client, chat_id, session, choice)
        return None

    if data.startswith("mort:"):
        if not city:
            return None
        key = "mortgage_gov" if data.endswith(":1") else "mortgage_standard"
        from app.bot.knowledge_base import get_product_info

        info = get_product_info(key, lang)
        if info:
            text = (
                f"📋 *{info['name']}*\n\n{info['conditions']}\n\n"
                f"{format_office_city(city, lang, 'telegram')}"
            )
            session["submenu"] = None
            _set_menu_intent_session(key, session)
            await send_tg_with_hint(tg_client, chat_id, session, text, nav_step="main")
        return None

    return None


# Совместимость: старый код мог импортировать render_screen
async def render_screen(*_args, **_kwargs):
    logger.warning("render_screen deprecated — use tg_wa_ui helpers")


async def send_main_menu_message(tg_client: Any, chat_id: str, session: dict, **kwargs) -> None:
    _ = kwargs
    await send_tg_main_menu(tg_client, chat_id, session)


def use_buttons_hint(lang: str) -> str:
    if lang == "kk":
        return "🤖 *1–7* санын жазыңыз немесе /start"
    return "🤖 Напишите цифру *1–7* или /start"
