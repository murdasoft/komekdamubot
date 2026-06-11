"""
Telegram: одно сообщение + inline-кнопки и «Назад» (без цифр в чате).
"""

from __future__ import annotations

import logging
from typing import Any

from app.bot.formatting import CITY_OFFICES, format_office_city
from app.bot.ux_labels import SCREEN_MAIN_HEAD_KK, SCREEN_MAIN_HEAD_RU
from app.bot.menu import (
    format_damu_menu_answer,
    get_main_menu_text,
    menu_choice_body,
    resolve_menu_digit,
)
from app.bot.wizard import CITY_DIGIT_ORDER

logger = logging.getLogger(__name__)

BACK_RU = "◀️ Назад"
BACK_KK = "◀️ Артқа"


def _back(lang: str) -> dict[str, str]:
    return {"text": BACK_KK if lang == "kk" else BACK_RU, "callback_data": ""}


def _city_label(key: str, lang: str) -> str:
    o = CITY_OFFICES[key]
    return o["name_kk"] if lang == "kk" else o["name_ru"]


def screen_lang_text() -> str:
    return (
        "👋 *KOMEK DAMU*\n\n"
        "🌐 Выберите язык / Тілді таңдаңыз:"
    )


def screen_lang_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "🇰🇿 Қазақша", "callback_data": "nav:lang:kk"},
                {"text": "🇷🇺 Русский", "callback_data": "nav:lang:ru"},
            ],
        ]
    }


def screen_city_text(lang: str) -> str:
    if lang == "kk":
        return "📍 *Қалаңызды таңдаңыз:*"
    return "📍 *Выберите город:*"


def screen_city_keyboard(lang: str) -> dict:
    rows: list[list[dict[str, str]]] = []
    pair: list[dict[str, str]] = []
    for key in CITY_DIGIT_ORDER:
        pair.append({"text": _city_label(key, lang), "callback_data": f"nav:city:{key}"})
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([{**_back(lang), "callback_data": "nav:back:lang"}])
    return {"inline_keyboard": rows}


def screen_main_text(lang: str, city: str) -> str:
    office = format_office_city(city, lang, "telegram")
    head = SCREEN_MAIN_HEAD_KK if lang == "kk" else SCREEN_MAIN_HEAD_RU
    return f"{head}\n\n{office}"


def screen_main_keyboard(lang: str) -> dict:
    if lang == "kk":
        rows = [
            [
                {"text": "ЖК / ИП", "callback_data": "menu:1"},
                {"text": "ТОО", "callback_data": "menu:2"},
            ],
            [
                {"text": "Жеке тұлға", "callback_data": "menu:3"},
                {"text": "Ипотека", "callback_data": "menu:4"},
            ],
            [
                {"text": "DAMU", "callback_data": "menu:5"},
                {"text": "Рефинанс", "callback_data": "menu:6"},
            ],
            [{"text": "👨‍💼 Менеджер", "callback_data": "menu:7"}],
            [{**_back(lang), "callback_data": "nav:back:city"}],
        ]
    else:
        rows = [
            [
                {"text": "ИП / ЖК", "callback_data": "menu:1"},
                {"text": "ТОО", "callback_data": "menu:2"},
            ],
            [
                {"text": "Физлицо", "callback_data": "menu:3"},
                {"text": "Ипотека", "callback_data": "menu:4"},
            ],
            [
                {"text": "DAMU", "callback_data": "menu:5"},
                {"text": "Рефинанс", "callback_data": "menu:6"},
            ],
            [{"text": "👨‍💼 Менеджер", "callback_data": "menu:7"}],
            [{**_back(lang), "callback_data": "nav:back:city"}],
        ]
    return {"inline_keyboard": rows}


def screen_mortgage_keyboard(lang: str) -> dict:
    if lang == "kk":
        rows = [
            [
                {"text": "Мемлекеттік 2–9%", "callback_data": "mort:1"},
                {"text": "Серіктес 15–22%", "callback_data": "mort:2"},
            ],
            [{**_back(lang), "callback_data": "nav:back:main"}],
        ]
    else:
        rows = [
            [
                {"text": "Гос 2–9%", "callback_data": "mort:1"},
                {"text": "Партнёр 15–22%", "callback_data": "mort:2"},
            ],
            [{**_back(lang), "callback_data": "nav:back:main"}],
        ]
    return {"inline_keyboard": rows}


def screen_product_text(choice_key: str, lang: str, city: str) -> str | None:
    if choice_key == "mortgage_menu":
        body = menu_choice_body("mortgage_menu", lang)
        if not body:
            return None
        sub = (
            "\n\n🏠 *Тип ипотеки:*"
            if lang == "ru"
            else "\n\n🏠 *Ипотека түрі:*"
        )
        return body + sub
    body = menu_choice_body(choice_key, lang)
    if not body:
        return None
    office = format_office_city(city, lang, "telegram")
    return f"{body}\n\n{office}"


def screen_product_keyboard(lang: str, *, mortgage: bool = False) -> dict:
    if mortgage:
        return screen_mortgage_keyboard(lang)
    return {
        "inline_keyboard": [[{**_back(lang), "callback_data": "nav:back:main"}]],
    }


def get_screen(
    screen: str,
    lang: str,
    city: str | None,
) -> tuple[str, dict]:
    if screen == "lang":
        return screen_lang_text(), screen_lang_keyboard()
    if screen == "city":
        return screen_city_text(lang), screen_city_keyboard(lang)
    if screen == "main":
        use_city = city or "almaty"
        return screen_main_text(lang, use_city), screen_main_keyboard(lang)
    return screen_lang_text(), screen_lang_keyboard()


async def send_main_menu_message(
    tg_client: Any,
    chat_id: str,
    session: dict,
    *,
    lead: str | None = None,
    force_new: bool = False,
) -> int | None:
    """Главное меню с кнопками; одно сообщение (надёжно после голоса)."""
    lang = session.get("lang", "kk")
    city = session.get("city") or "almaty"
    body, markup = get_screen("main", lang, city)
    text = f"{lead}\n\n{body}" if lead else body
    mid = None if force_new else session.get("menu_message_id")
    if mid and not force_new:
        ok = await tg_client.edit_message(chat_id, mid, text, reply_markup=markup)
        if ok:
            session["menu_message_id"] = mid
            session["tg_screen"] = "main"
            return mid
    result = await tg_client.send_message(chat_id, text, reply_markup=markup)
    new_mid = None
    if result and result.get("ok") and result.get("result"):
        new_mid = result["result"].get("message_id")
    else:
        logger.error(
            "send_main_menu failed chat=%s ok=%s",
            chat_id,
            result.get("ok") if result else None,
        )
        plain = text.replace("*", "")
        result2 = await tg_client.send_message(
            chat_id, plain, parse_mode="", reply_markup=markup
        )
        if result2 and result2.get("ok") and result2.get("result"):
            new_mid = result2["result"]["message_id"]
    if new_mid:
        session["menu_message_id"] = new_mid
    session["tg_screen"] = "main"
    session["city"] = city
    return new_mid


async def render_screen(
    tg_client: Any,
    chat_id: str,
    session: dict,
    screen: str,
    *,
    message_id: int | None = None,
) -> int | None:
    """Показать или обновить одно навигационное сообщение."""
    lang = session.get("lang", "kk")
    city = session.get("city")
    text, markup = get_screen(screen, lang, city)

    if message_id:
        ok = await tg_client.edit_message(chat_id, message_id, text, reply_markup=markup)
        if ok:
            session["menu_message_id"] = message_id
            session["tg_screen"] = screen
            return message_id
    result = await tg_client.send_message(chat_id, text, reply_markup=markup)
    mid = None
    if result and result.get("ok") and result.get("result"):
        mid = result["result"].get("message_id")
    else:
        logger.error("render_screen send failed chat=%s screen=%s", chat_id, screen)
        plain = text.replace("*", "")
        result2 = await tg_client.send_message(
            chat_id, plain, parse_mode="", reply_markup=markup
        )
        if result2 and result2.get("ok") and result2.get("result"):
            mid = result2["result"].get("message_id")
    if mid:
        session["menu_message_id"] = mid
    session["tg_screen"] = screen
    return mid


async def handle_nav_callback(
    data: str,
    session: dict,
    tg_client: Any,
    chat_id: str,
    message_id: int,
) -> str | None:
    """
    Обработка nav:* / menu:* / mort:*.
    Возвращает 'operator' для передачи менеджеру, иначе None.
    """
    lang = session.get("lang", "kk")
    city = session.get("city")

    if data.startswith("nav:lang:"):
        session["lang"] = data.split(":")[-1]
        session["lang_locked"] = True
        session["state"] = "selecting_city"
        await render_screen(tg_client, chat_id, session, "city", message_id=message_id)
        return None

    if data.startswith("nav:city:"):
        session["city"] = data.split(":")[-1]
        session["city_confirmed"] = True
        session["state"] = "idle"
        await render_screen(tg_client, chat_id, session, "main", message_id=message_id)
        return None

    if data == "nav:back:lang":
        session["state"] = "selecting_lang"
        session.pop("city_confirmed", None)
        await render_screen(tg_client, chat_id, session, "lang", message_id=message_id)
        return None

    if data == "nav:back:city":
        session["state"] = "selecting_city"
        session.pop("city_confirmed", None)
        await render_screen(tg_client, chat_id, session, "city", message_id=message_id)
        return None

    if data == "nav:back:main":
        if city:
            await render_screen(tg_client, chat_id, session, "main", message_id=message_id)
        else:
            await render_screen(tg_client, chat_id, session, "city", message_id=message_id)
        return None

    if data.startswith("menu:"):
        digit = data.split(":")[1]
        if digit == "7":
            return "operator"
        choice = resolve_menu_digit(digit)
        if not choice or not city:
            return None
        if choice == "mortgage_menu":
            text = screen_product_text(choice, lang, city)
            if text:
                await tg_client.edit_message(
                    chat_id,
                    message_id,
                    text,
                    reply_markup=screen_product_keyboard(lang, mortgage=True),
                )
                session["tg_screen"] = "mortgage"
            return None
        text = screen_product_text(choice, lang, city)
        if text:
            await tg_client.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=screen_product_keyboard(lang),
            )
            session["tg_screen"] = "product"
            _set_menu_intent_session(choice, session)
        return None

    if data.startswith("mort:"):
        if not city:
            return None
        from app.bot.knowledge_base import get_product_info

        key = "mortgage_gov" if data.endswith(":1") else "mortgage_standard"
        info = get_product_info(key, lang)
        if info:
            text = f"📋 *{info['name']}*\n\n{info['conditions']}\n\n{format_office_city(city, lang, 'telegram')}"
            await tg_client.edit_message(
                chat_id,
                message_id,
                text,
                reply_markup=screen_product_keyboard(lang, mortgage=True),
            )
        return None

    return None


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


def use_buttons_hint(lang: str) -> str:
    if lang == "kk":
        return "Төмендегі *түймені* басыңыз 👇 /start — бөлімдер тізімі"
    return "Нажмите *кнопку* ниже 👇 /start — в начало"
