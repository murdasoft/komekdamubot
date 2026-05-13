"""
UI Content for KOMEK DAMU bot.
Russian and Kazakh languages supported.
"""

# Language selection
LANGUAGE_PROMPT_RU = "🌐 *Выберите язык / Тілді таңдаңыз:*"
LANGUAGE_PROMPT_KK = "🌐 *Выберите язык / Тілді таңдаңыз:*"

LANGUAGE_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "🇷🇺 Русский", "callback_data": "lang:ru"}],
        [{"text": "🇰🇿 Қазақша", "callback_data": "lang:kk"}],
    ]
}

# Greetings
GREETING_RU = (
    "Здравствуйте! Вас приветствует *KOMEK DAMU*\n\n"
    "Я помогу подобрать решение по кредиту, ипотеке или финансированию бизнеса.\n\n"
    "Вы можете:\n"
    "• написать, что вам нужно, своими словами\n"
    "• отправить голосовое сообщение\n"
    "• выбрать один из вариантов ниже"
)

GREETING_KK = (
    "Сәлеметсіз бе! *KOMEK DAMU* компаниясына қош келдіңіз\n\n"
    "Мен сізге несие, ипотека немесе бизнес қаржыландыру бойынша көмектесемін.\n\n"
    "Сіз:\n"
    "• өз сұрағыңызды еркін мәтінмен жаза аласыз\n"
    "• дауыстық хабарлама жібере аласыз\n"
    "• төмендегі нұсқалардың бірін таңдай аласыз"
)

# Menu buttons (Telegram inline)
MENU_KEYBOARD_RU = {
    "inline_keyboard": [
        [{"text": "💰 Кредит для себя", "callback_data": "product:personal_credit"}],
        [{"text": "🏢 Кредит для бизнеса", "callback_data": "product:business_credit"}],
        [{"text": "📊 DAMU 12,6%", "callback_data": "product:damu"}],
        [{"text": "🏠 Ипотека", "callback_data": "menu:mortgage"}],
        [{"text": "🔄 Рефинансирование", "callback_data": "product:refinancing"}],
        [{"text": "⚠️ Сложный случай", "callback_data": "product:complex_case"}],
        [{"text": "👨‍💼 Связаться с менеджером", "callback_data": "action:operator"}],
    ]
}

MENU_KEYBOARD_KK = {
    "inline_keyboard": [
        [{"text": "💰 Жеке несие", "callback_data": "product:personal_credit"}],
        [{"text": "🏢 Бизнес несиесі", "callback_data": "product:business_credit"}],
        [{"text": "📊 DAMU 12,6%", "callback_data": "product:damu"}],
        [{"text": "🏠 Ипотека", "callback_data": "menu:mortgage"}],
        [{"text": "🔄 Қайта қаржыландыру", "callback_data": "product:refinancing"}],
        [{"text": "⚠️ Қиын жағдай", "callback_data": "product:complex_case"}],
        [{"text": "👨‍💼 Менеджермен байланысу", "callback_data": "action:operator"}],
    ]
}

# Mortgage submenu
MORTGAGE_MENU_RU = {
    "inline_keyboard": [
        [{"text": "🏛️ Госпрограмма (2-9%)", "callback_data": "product:mortgage_gov"}],
        [{"text": "🏦 Обычная ипотека", "callback_data": "product:mortgage_standard"}],
        [{"text": "⬅️ Назад", "callback_data": "menu:main"}],
    ]
}

MORTGAGE_MENU_KK = {
    "inline_keyboard": [
        [{"text": "🏛️ Мемлекеттік (2-9%)", "callback_data": "product:mortgage_gov"}],
        [{"text": "🏦 Қарапайым ипотека", "callback_data": "product:mortgage_standard"}],
        [{"text": "⬅️ Артқа", "callback_data": "menu:main"}],
    ]
}

# Operator/handoff messages
OPERATOR_RU = (
    "Передаю диалог менеджеру. Совсем скоро с вами свяжется человек.\n"
    "Если срочно — позвоните: +7 (XXX) XXX-XX-XX"
)

OPERATOR_KK = (
    "Диалогты менеджерге беремін. Жақын арада сізбен адам байланысады.\n"
    "Тездету үшін қоңырау шалыңыз: +7 (XXX) XXX-XX-XX"
)

HANDOFF_RELEASED_RU = "Возвращаю бота в диалог. Напишите /start для главного меню."
HANDOFF_RELEASED_KK = "Ботты диалогқа қайтарып аламын. Негізгі мәзір үшін /start жазыңыз."

# Error / unknown message
UNKNOWN_RU = (
    "Извините, не совсем понял ваш запрос.\n\n"
    "Вы можете:\n"
    "• Позвонить: +7 (XXX) XXX-XX-XX\n"
    "• Написать /start для возврата в меню"
)

UNKNOWN_KK = (
    "Кешіріңіз, сұрауыңызды толық түсінбедім.\n\n"
    "Сіз:\n"
    "• Қоңырау шала аласыз: +7 (XXX) XXX-XX-XX\n"
    "• Негізгі мәзірге оралу үшін /start жазыңыз"
)

# Language detection failed
LANG_DETECT_FAILED_RU = "Извините, не удалось определить язык. Пожалуйста, напишите текстом."
LANG_DETECT_FAILED_KK = "Кешіріңіз, тілді анықтау мүмкін болмады. Мәтінмен жазыңыз."

# WhatsApp numeric menu (for WA users)
WA_MENU_RU = (
    "📋 *Меню KOMEK DAMU*\n\n"
    "Выберите цифру нужного раздела:\n\n"
    "1️⃣ Кредит для себя\n"
    "2️⃣ Кредит для бизнеса\n"
    "3️⃣ DAMU 12,6%\n"
    "4️⃣ Ипотека\n"
    "5️⃣ Рефинансирование\n"
    "6️⃣ Сложный случай\n"
    "7️⃣ Связаться с менеджером\n\n"
    "Напишите цифру от 1 до 7"
)

WA_MENU_KK = (
    "📋 *KOMEK DAMU мәзірі*\n\n"
    "Қажетті бөлімнің санын жазыңыз:\n\n"
    "1️⃣ Жеке несие\n"
    "2️⃣ Бизнес несиесі\n"
    "3️⃣ DAMU 12,6%\n"
    "4️⃣ Ипотека\n"
    "5️⃣ Қайта қаржыландыру\n"
    "6️⃣ Қиын жағдай\n"
    "7️⃣ Менеджермен байланысу\n\n"
    "1-ден 7-ге дейінгі санды жазыңыз"
)

WA_MORTGAGE_MENU_RU = (
    "🏠 *Ипотека*\n\n"
    "1️⃣ Госпрограмма (2-9%)\n"
    "2️⃣ Обычная ипотека\n"
    "0️⃣ Назад в главное меню\n\n"
    "Напишите цифру:"
)

WA_MORTGAGE_MENU_KK = (
    "🏠 *Ипотека*\n\n"
    "1️⃣ Мемлекеттік (2-9%)\n"
    "2️⃣ Қарапайым ипотека\n"
    "0️⃣ Негізгі мәзірге оралу\n\n"
    "Санды жазыңыз:"
)

# Map WA digits to product keys
WA_DIGIT_MAP = {
    "1": "personal_credit",
    "2": "business_credit",
    "3": "damu",
    "4": "mortgage_menu",  # Special submenu
    "5": "refinancing",
    "6": "complex_case",
    "7": "operator",
}

WA_MORTGAGE_DIGIT_MAP = {
    "1": "mortgage_gov",
    "2": "mortgage_standard",
    "0": "back_to_main",
}


def get_language_prompt(lang: str = "ru") -> str:
    return LANGUAGE_PROMPT_RU if lang == "ru" else LANGUAGE_PROMPT_KK


def get_language_keyboard() -> dict:
    return LANGUAGE_KEYBOARD


def get_greeting(lang: str = "ru") -> str:
    return GREETING_RU if lang == "ru" else GREETING_KK


def get_menu_keyboard(lang: str = "ru") -> dict:
    return MENU_KEYBOARD_RU if lang == "ru" else MENU_KEYBOARD_KK


def get_mortgage_menu(lang: str = "ru") -> dict:
    return MORTGAGE_MENU_RU if lang == "ru" else MORTGAGE_MENU_KK


def get_wa_menu(lang: str = "ru") -> str:
    return WA_MENU_RU if lang == "ru" else WA_MENU_KK


def get_wa_mortgage_menu(lang: str = "ru") -> str:
    return WA_MORTGAGE_MENU_RU if lang == "ru" else WA_MORTGAGE_MENU_KK


def get_operator_message(lang: str = "ru") -> str:
    return OPERATOR_RU if lang == "ru" else OPERATOR_KK


def get_unknown_message(lang: str = "ru") -> str:
    return UNKNOWN_RU if lang == "ru" else UNKNOWN_KK
