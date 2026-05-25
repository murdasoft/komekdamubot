"""
UI Content for KOMEK DAMU bot.
Russian and Kazakh languages supported.
"""

# Қазақша — негізгі тіл; орысша — 99 арқылы таңдау
DEFAULT_LANG = "kk"

WA_NAV_HINT = (
    "0 — Назад в главное меню / Бас мәзірге қайту\n"
    "99 — Сменить язык / Тілді ауыстыру"
)

# Platform selection
PLATFORM_PROMPT_RU = "📱 *Выберите мессенджер / Мессенджерді таңдаңыз:*"
PLATFORM_PROMPT_KK = "📱 *Выберите мессенджер / Мессенджерді таңдаңыз:*"

PLATFORM_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "✈️ Telegram (кнопки)", "callback_data": "platform:tg"}],
        [{"text": "💬 WhatsApp (текст+цифры)", "callback_data": "platform:wa"}],
    ]
}

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

# City phones
CITY_PHONES = {
    "almaty":   "8 707 339 10 39",
    "astana":   "8 702 187 97 26",
    "shymkent": "8 705 810 28 81",
    "atyrau":   "8 706 686 83 00",
    "aktau":    "8 705 112 99 22",
}

DEFAULT_PHONE = "8 707 339 10 39"


def get_city_phone(city: str | None) -> str:
    return CITY_PHONES.get(city, DEFAULT_PHONE) if city else DEFAULT_PHONE


# Operator/handoff messages
OPERATOR_RU = "Передаю диалог менеджеру. Совсем скоро с вами свяжется человек."
OPERATOR_KK = "Диалогты менеджерге беремін. Жақын арада сізбен адам байланысады."


def get_operator_message_with_phone(
    lang: str, city: str | None = None, platform: str = "telegram"
) -> str:
    from app.bot.formatting import mono

    phone = get_city_phone(city)
    p = mono(phone, platform)  # type: ignore[arg-type]
    if lang == "kk":
        return (
            f"👨‍💼 *Менеджерге қосылдым.*\n"
            f"Жақын арада хабарласады.\n\n"
            f"📞 Тездету: {p}"
        )
    return (
        f"👨‍💼 *Передаю менеджеру.*\n"
        f"Скоро с вами свяжутся.\n\n"
        f"📞 Срочно: {p}"
    )

HANDOFF_RELEASED_RU = "Возвращаю бота в диалог. Напишите /start для главного меню."
HANDOFF_RELEASED_KK = "Ботты диалогқа қайтарып аламын. Негізгі мәзір үшін /start жазыңыз."

# Error / unknown message
def get_unknown_message_with_phone(lang: str, city: str | None = None) -> str:
    phone = get_city_phone(city)
    if lang == "kk":
        return (f"Кешіріңіз, сұрауыңызды толық түсінбедім.\n\nСіз:\n• Қоңырау шала аласыз: {phone}\n• Негізгі мәзірге оралу үшін /start жазыңыз")
    return (f"Извините, не совсем понял ваш запрос.\n\nВы можете:\n• Позвонить: {phone}\n• Написать /start для возврата в меню")


def get_ai_fallback_message(
    lang: str, city: str | None = None, platform: str = "telegram"
) -> str:
    """Used when AI service fails — invite to office with phone."""
    from app.offices import get_contact_footer

    if lang == "kk":
        lead = "⚠️ *Қазір жүйе бос емес.*\nТолық кеңес — офисте:"
    else:
        lead = "⚠️ *Сейчас не могу ответить онлайн.*\nКонсультация в офисе:"
    footer = get_contact_footer(
        city, lang, all_cities=not bool(city), platform=platform  # type: ignore[arg-type]
    )
    return f"{lead}\n\n{footer}\n\n/start"


UNKNOWN_RU = get_unknown_message_with_phone("ru")
UNKNOWN_KK = get_unknown_message_with_phone("kk")

# Language detection failed
LANG_DETECT_FAILED_RU = "Извините, не удалось определить язык. Пожалуйста, напишите текстом."
LANG_DETECT_FAILED_KK = "Кешіріңіз, тілді анықтау мүмкін болмады. Мәтінмен жазыңыз."
VOICE_STT_FAILED_RU = "Не расслышал. Повторите голосом или напишите текстом."
VOICE_STT_FAILED_KK = "Естіген жоқпын. Дауыспен қайта жіберіңіз немесе мәтінмен жазыңыз."

# WhatsApp demo for Telegram users
WHATSAPP_DEMO_RU = """📱 *Как выглядит этот бот в WhatsApp*

В WhatsApp интерфейс другой — там нет красивых кнопок как здесь.

Вместо этого бот показывает *текстовое меню с цифрами*:

```
📋 Меню KOMEK DAMU

Выберите цифру нужного раздела:

1️⃣ ИП / ЖК
2️⃣ ТОО
3️⃣ Кредит для себя
4️⃣ Ипотека
5️⃣ DAMU 12,6%
6️⃣ Рефинансирование
7️⃣ Менеджер

Напишите цифру от 1 до 7
```

🔹 Вы просто пишете число — и бот понимает что вам нужно
🔹 Голосовые сообщения тоже работают
🔹 Тот же AI и тот же функционал

*WhatsApp номер бота:* `+7 701 2117340`"""

WHATSAPP_DEMO_KK = """📱 *Бұл бот WhatsApp-та қалай көрінеді*

WhatsApp-та интерфейс басқа — мұндағы сияқты әдемі түймелер жоқ.

Оның орнына бот *сандармен мәтіндік мәзір* көрсетеді:

```
📋 KOMEK DAMU мәзірі

Қажетті бөлімнің санын жазыңыз:

1️⃣ ЖК / ИП
2️⃣ ТОО
3️⃣ Жеке несие
4️⃣ Ипотека
5️⃣ DAMU 12,6%
6️⃣ Қайта қаржыландыру
7️⃣ Менеджер

1-ден 7-ге дейін сан жазыңыз
```

🔹 Сіз тек сан жазасыз — бот сіздің не қажет екенін түсінеді
🔹 Дауыстық хабарламалар да жұмыс істейді
🔹 Сол AI және сол функционал

*WhatsApp бот нөмірі:* `+7 701 2117340`"""

from app.bot.menu import MAIN_MENU_DIGIT_MAP, get_main_menu_text

WA_MORTGAGE_MENU_RU = (
    "🏠 *Ипотека*\n\n"
    "1️⃣ Госпрограмма (2–9%, до 25 лет)\n"
    "2️⃣ Партнёрская (15–22%, до 25 лет)\n"
    "0️⃣ Назад в главное меню\n\n"
    "Консультация только в офисе. Напишите цифру:"
)

WA_MORTGAGE_MENU_KK = (
    "🏠 Ипотека мәзірі\n\n"
    "1️⃣ Мемлекеттік (2–9%, 25 жылға дейін)\n"
    "2️⃣ Серіктес (15–22%, 25 жылға дейін)\n"
    "0️⃣ Негізгі мәзірге оралу\n\n"
    "Кеңес тек офисте. Санды жазыңыз:"
)

WA_INTRO_RU = (
    "📱 *WhatsApp режим*\n\n"
    "В WhatsApp используется текстовое меню с цифрами:\n\n"
)

WA_INTRO_KK = (
    "📱 *WhatsApp режим*\n\n"
    "WhatsApp мәтіндік мәзір қолданады:\n\n"
)

WA_FOOTER_RU = (
    "*Напишите цифру от 1 до 7* или *отправьте голосовое сообщение*\n\n"
    "0 — Назад в главное меню\n\n"
    "Перейти в WhatsApp:\n"
    "📞 `+7 701 2117340`"
)

WA_FOOTER_KK = (
    "*1-ден 7-ге дейінгі санды жазыңыз* немесе *дауыстық хабарлама жіберіңіз*\n\n"
    "0 — Негізгі мәзірге оралу\n\n"
    "WhatsApp-қа өту:\n"
    "📞 `+7 701 2117340`"
)

# Map WA digits → menu choice (см. app.bot.menu)
WA_DIGIT_MAP = MAIN_MENU_DIGIT_MAP

WA_MORTGAGE_DIGIT_MAP = {
    "1": "mortgage_gov",
    "2": "mortgage_standard",
    "0": "back_to_main",
}


def get_platform_prompt(lang: str = "ru") -> str:
    return PLATFORM_PROMPT_RU if lang == "ru" else PLATFORM_PROMPT_KK


def get_platform_keyboard() -> dict:
    return PLATFORM_KEYBOARD


def get_language_prompt(lang: str = "ru") -> str:
    return LANGUAGE_PROMPT_RU if lang == "ru" else LANGUAGE_PROMPT_KK


def get_language_keyboard() -> dict:
    return LANGUAGE_KEYBOARD


def get_greeting(lang: str = "ru", platform: str = "telegram") -> str:
    from app.bot.formatting import format_welcome

    return format_welcome(lang, platform)  # type: ignore[arg-type]


def get_wa_intro(lang: str = "ru") -> str:
    return WA_INTRO_RU if lang == "ru" else WA_INTRO_KK


def get_wa_footer(lang: str = "ru") -> str:
    return WA_FOOTER_RU if lang == "ru" else WA_FOOTER_KK


def get_wa_mortgage_menu(lang: str = "ru") -> str:
    return WA_MORTGAGE_MENU_RU if lang == "ru" else WA_MORTGAGE_MENU_KK


def get_operator_message(lang: str = "ru") -> str:
    return OPERATOR_RU if lang == "ru" else OPERATOR_KK


def get_unknown_message(lang: str = "ru") -> str:
    return UNKNOWN_RU if lang == "ru" else UNKNOWN_KK


def get_wa_menu(lang: str = DEFAULT_LANG) -> str:
    return get_main_menu_text(lang)


def get_whatsapp_demo(lang: str = "ru") -> str:
    return WHATSAPP_DEMO_KK if lang == "kk" else WHATSAPP_DEMO_RU


def add_wa_back_hint(message: str, lang: str = DEFAULT_LANG) -> str:
    """Добавить подсказки 0/99 на двух языках (lang — только для текста ответа)."""
    _ = lang  # ответ уже на выбранном языке; навигация всегда двуязычная
    return f"{message}\n\n{WA_NAV_HINT}"
