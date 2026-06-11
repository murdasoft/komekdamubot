"""
Telegram: тот же текстовый UX, что WhatsApp (цифры 1–7, 0/98/99, без inline-кнопок).
"""

from __future__ import annotations

from typing import Any

from app.bot import content
from app.bot.wizard import (
    get_city_step_help,
    get_city_step_text,
    get_lang_step_text,
    get_welcome_with_menu,
)


def nav_step_from_session(session: dict) -> str | None:
    st = session.get("state")
    if st == "selecting_lang":
        return "lang"
    if st == "selecting_city":
        return "city"
    return "main"


async def send_tg_with_hint(
    tg_client: Any,
    chat_id: str,
    session: dict,
    message: str,
    *,
    reply_lang: str | None = None,
    nav_step: str | None = None,
) -> None:
    lang = reply_lang or session.get("lang", "kk")
    step = nav_step if nav_step is not None else nav_step_from_session(session)
    text = content.add_wa_back_hint(message, lang, step=step)
    await tg_client.send_message(chat_id, text)


async def send_tg_lang_step(tg_client: Any, chat_id: str, session: dict) -> None:
    await send_tg_with_hint(
        tg_client,
        chat_id,
        session,
        get_lang_step_text(),
        reply_lang="kk",
        nav_step="lang",
    )


async def send_tg_city_step(tg_client: Any, chat_id: str, session: dict) -> None:
    lang = session.get("lang", "kk")
    await send_tg_with_hint(
        tg_client,
        chat_id,
        session,
        get_city_step_text(lang),
        reply_lang=lang,
        nav_step="city",
    )


async def send_tg_main_menu(tg_client: Any, chat_id: str, session: dict) -> None:
    lang = session.get("lang", "kk")
    city = session.get("city") or "almaty"
    await send_tg_with_hint(
        tg_client,
        chat_id,
        session,
        get_welcome_with_menu(lang, city, "telegram"),
        reply_lang=lang,
        nav_step="main",
    )


async def send_tg_city_help(tg_client: Any, chat_id: str, session: dict) -> None:
    lang = session.get("lang", "kk")
    await send_tg_with_hint(
        tg_client,
        chat_id,
        session,
        get_city_step_help(lang),
        reply_lang=lang,
        nav_step="city",
    )
