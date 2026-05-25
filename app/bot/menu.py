"""
Главное меню: выбор цифрой (WhatsApp) или кнопкой (Telegram).
"""

from __future__ import annotations

from app.bot.knowledge_base import (
    format_ip_credit_answer,
    format_mortgage_programs_answer,
    format_personal_credit_answer,
    format_too_credit_answer,
    get_product_info,
)

# 1 — ИП, 2 — ТОО, 3 — физлицо, 4 — ипотека, 5 — DAMU, 6 — рефинанс, 7 — менеджер
MAIN_MENU_DIGIT_MAP: dict[str, str] = {
    "1": "ip_business",
    "2": "too_business",
    "3": "personal_credit",
    "4": "mortgage_menu",
    "5": "damu",
    "6": "refinancing",
    "7": "operator",
}

MAIN_MENU_RU = (
    "📋 *Меню KOMEK DAMU*\n\n"
    "*Шаг 3* — напишите цифру:\n\n"
    "1️⃣ ИП / ЖК (бизнес)\n"
    "2️⃣ ТОО\n"
    "3️⃣ Кредит для себя (физлицо)\n"
    "4️⃣ Ипотека\n"
    "5️⃣ DAMU 12,6%\n"
    "6️⃣ Рефинансирование\n"
    "7️⃣ Связаться с менеджером\n\n"
    "0 — главное меню · 99 — язык"
)

MAIN_MENU_KK = (
    "📋 *KOMEK DAMU мәзірі*\n\n"
    "*3-ші қадам* — санын жазыңыз:\n\n"
    "1️⃣ ЖК / ИП (бизнес)\n"
    "2️⃣ ТОО\n"
    "3️⃣ Жеке тұлға (өзіне)\n"
    "4️⃣ Ипотека\n"
    "5️⃣ DAMU 12,6%\n"
    "6️⃣ Қайта қаржыландыру\n"
    "7️⃣ Менеджермен байланысу\n\n"
    "0 — негізгі мәзір · 99 — тіл"
)

MEDIA_MENU_RU = (
    "📷 Фото и документы бот не разбирает.\n\n"
    "Выберите нужный раздел цифрой из меню ниже 👇"
)

MEDIA_MENU_KK = (
    "📷 Фото мен құжатты бот оқымайды.\n\n"
    "Төмендегі мәзірден сан таңдаңыз 👇"
)


def get_main_menu_text(lang: str) -> str:
    return MAIN_MENU_KK if lang == "kk" else MAIN_MENU_RU


def get_media_menu_reply(lang: str) -> str:
    return MEDIA_MENU_KK if lang == "kk" else MEDIA_MENU_RU


def get_telegram_main_menu_keyboard(lang: str) -> dict:
    """Inline-кнопки: callback menu:1 … menu:7."""
    if lang == "kk":
        rows = [
            [
                {"text": "1 ЖК / ИП", "callback_data": "menu:1"},
                {"text": "2 ТОО", "callback_data": "menu:2"},
            ],
            [
                {"text": "3 Жеке тұлға", "callback_data": "menu:3"},
                {"text": "4 Ипотека", "callback_data": "menu:4"},
            ],
            [
                {"text": "5 DAMU", "callback_data": "menu:5"},
                {"text": "6 Рефинанс", "callback_data": "menu:6"},
            ],
            [{"text": "7 Менеджер", "callback_data": "menu:7"}],
        ]
    else:
        rows = [
            [
                {"text": "1 ИП / ЖК", "callback_data": "menu:1"},
                {"text": "2 ТОО", "callback_data": "menu:2"},
            ],
            [
                {"text": "3 Физлицо", "callback_data": "menu:3"},
                {"text": "4 Ипотека", "callback_data": "menu:4"},
            ],
            [
                {"text": "5 DAMU", "callback_data": "menu:5"},
                {"text": "6 Рефинанс", "callback_data": "menu:6"},
            ],
            [{"text": "7 Менеджер", "callback_data": "menu:7"}],
        ]
    return {"inline_keyboard": rows}


def resolve_menu_digit(digit: str) -> str | None:
    d = digit.strip()
    if d in MAIN_MENU_DIGIT_MAP:
        return MAIN_MENU_DIGIT_MAP[d]
    return None


def menu_choice_body(choice_key: str, lang: str) -> str | None:
    """Готовый ответ по выбору из меню (без сценария с вопросами)."""
    if choice_key == "ip_business":
        return format_ip_credit_answer(lang)
    if choice_key == "too_business":
        return format_too_credit_answer(lang)
    if choice_key == "personal_credit":
        return format_personal_credit_answer(lang)
    if choice_key == "mortgage_menu":
        return format_mortgage_programs_answer(lang)
    if choice_key == "damu":
        return format_damu_menu_answer(lang)
    if choice_key in ("refinancing", "mortgage_gov", "mortgage_standard"):
        info = get_product_info(choice_key, lang)
        if not info:
            return None
        cond = info["conditions"].replace("\\n", "\n")
        return f"📋 *{info['name']}*\n\n{info['description']}\n\n{cond}"
    return None


def get_text_fallback_reply(lang: str) -> str:
    """Нет совпадения в FAQ — меню и менеджер, без нейросети."""
    menu = get_main_menu_text(lang)
    if lang == "kk":
        return (
            "ℹ️ Бұл сұраққа дайын жауап жоқ.\n"
            "Төмендегі мәзірден сан таңдаңыз немесе *7* — менеджер.\n\n"
            f"{menu}"
        )
    return (
        "ℹ️ На этот вопрос нет готового ответа.\n"
        "Выберите раздел цифрой из меню или *7* — менеджер.\n\n"
        f"{menu}"
    )


def format_damu_menu_answer(lang: str) -> str:
    if lang == "kk":
        return (
            "📋 *DAMU 12,6%*\n\n"
            "*ТОО:*\n"
            "• Кепілдіксіз DAMU — *200 млн ₸* дейін, *12,6%*, *3 жыл* (ТОО 1 жыл + айналым)\n"
            "• Кепілді DAMU — *7 млрд ₸* дейін, *12,6%*, *10 жыл*\n\n"
            "*ЖК / ИП:*\n"
            "• Кепілдіксіз DAMU *жоқ*\n"
            "• Кепілді DAMU — *12,6%*, *10 жыл* (ЖК 6 ай + айналым)\n\n"
            "Несие жүктемесіне қарамаймыз. Ашық кешігу болмауы керек.\n"
            "Нақты есеп — офисте, кеңес *тегін*"
        )
    return (
        "📋 *DAMU 12,6%*\n\n"
        "*ТОО:*\n"
        "• Беззалоговый DAMU — до *200 млн ₸*, *12,6%*, до *3 лет* (ТОО от 1 года + обороты)\n"
        "• Залоговый DAMU — до *7 млрд ₸*, *12,6%*, до *10 лет*\n\n"
        "*ИП / ЖК:*\n"
        "• Беззалогового DAMU *нет*\n"
        "• Залоговый DAMU — *12,6%*, до *10 лет* (ИП от 6 мес + обороты)\n\n"
        "На кредитную нагрузку не смотрим. Без открытых просрочек.\n"
        "Точный расчёт — в офисе, консультация *бесплатная*"
    )
