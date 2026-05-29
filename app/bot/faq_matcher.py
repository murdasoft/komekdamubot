"""
Fast FAQ / product matching — ответ без LLM (<50 ms).
Покрывает типовые вопросы KOMEK DAMU (RU + KK).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.bot.knowledge_base import (
    PRODUCTS,
    detect_business_entity,
    detect_intent,
    format_clarify_borrower_type,
    format_ip_credit_answer,
    format_mortgage_programs_answer,
    format_personal_credit_answer,
    get_faq_answer,
    get_product_info,
    is_ip_credit_question,
    is_personal_credit_question,
    mentions_ip,
    mentions_mortgage,
    mentions_too,
)
from app.bot.text_utils import is_pure_greeting, strip_leading_greeting
from app.offices import get_contact_footer, city_for_contacts

_WORD = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)


@dataclass(frozen=True)
class _Pattern:
    """keywords (substring), faq_key or None, product boost."""
    keywords: tuple[str, ...]
    faq_key: str | None = None
    product_key: str | None = None
    weight: int = 2


# Чем длиннее фраза — тем выше приоритет (сортировка по длине при матче)
FAQ_PATTERNS: list[_Pattern] = [
    # Общие
    _Pattern(("предоплат", "аванс", "заранее плат", "алдын ала төлем"), "prepayment", weight=3),
    _Pattern(("бесплатн", "тегін кеңес", "платная консульта", "консультация бесплат"), "consultation_free", weight=3),
    _Pattern(("сколько времени", "как долго", "срок рассмотр", "когда ответ", "қашан", "неше күн"), "how_long", weight=3),
    _Pattern(("график работ", "рабочие часы", "во сколько работ", "жұмыс уақыты", "режим работ"), "work_hours", weight=3),
    _Pattern(("адрес", "мекенжай", "где офис", "где находит", "қайда"), "address", weight=3),
    _Pattern(("онлайн ипотек", "ипотека онлайн", "консультация по ипотек"), "mortgage_office", weight=3),
    _Pattern(("визит в офис", "приехать в офис", "офиске"), "mortgage_office", weight=2),
    # Продукты (ключевые фразы → карточка продукта)
    _Pattern(("даму 12", "12,6", "12.6", "программа даму", "damu 12"), product_key="damu", weight=4),
    _Pattern(("госпрограмм", "гос программ", "2% и 9", "2%/9", "18-22", "18 22", "15-22", "15 22", "партнерск ипотек", "диапазон"), faq_key="mortgage_programs", weight=5),
    _Pattern(("гос ипотек", "ипотека 2%", "ипотека 9%", "мемлекеттік ипотека", "2% ипотека"), product_key="mortgage_gov", weight=4),
    _Pattern(("рефинанс", "перекрыть кредит", "снизить ставку", "қайта қаржыландыру"), product_key="refinancing", weight=4),
    _Pattern(("кредит на бизнес", "бизнес кредит", "бизнес несиесі", "для ип", "для тоо"), product_key="business_credit", weight=4),
    _Pattern(("потребительск", "кредит для себя", "жеке несие", "взять кредит", "нужен кредит"), product_key="personal_credit", weight=3),
    _Pattern(("лимит на физ", "лимит физ", "физлиц", "физическ", "жеке тұлға"), product_key="personal_credit", weight=5),
    _Pattern(("ипотек", "пәтер", "квартир", "жилье", "үй сатып"), product_key="mortgage_standard", weight=2),
    _Pattern(("даму", "damu"), product_key="damu", weight=2),
    # Приветствия — короткий ответ без LLM
    _Pattern(("здравствуй", "добрый день", "добрый вечер", "привет", "салем", "сәлем", "салам", "саламатсыз"), faq_key="greeting", weight=2),
    _Pattern(
        ("кепілсіз", "тиімді несие", "35 млн", "500 млн", "25 млн", "200 млн", "komek damu"),
        faq_key="company_info",
        weight=3,
    ),
    _Pattern(("спасибо", "рахмет", "thanks"), faq_key="thanks", weight=2),
    _Pattern(("оператор", "менеджер", "человек", "маман", "связаться с"), faq_key="operator_hint", weight=2),
    _Pattern(("чёрный список", "черный список", "черном списке", "қара тізім"), faq_key="blacklist", weight=4),
    _Pattern(("просрочк", "кешігу", "задолжал"), faq_key="overdue", weight=4),
    # TODO: auto-expand from chat analysis: "гарантия", "процент", "ставка",
    # "млн", "миллион", "сома", "кредит аламын", "бересіздер", "көмек"
    # Реальные фразы клиентов
    _Pattern(("онлайн", "онлайн тапсыр", "онлайн оформ", "онлайн консульта"), faq_key="online_service", weight=4),
    _Pattern(("пенсионк", "пенсия", "зейнеткер", "зейнет", "пенсион"), faq_key="pension_info", weight=3),
    _Pattern(("нагрузк", "жүктеме", "қаржыл", "кредитная нагрузка"), faq_key="credit_load", weight=3),
    _Pattern(("скорбал", "скоринг", "балл", "скор"), faq_key="scoring_info", weight=3),
    _Pattern(("кредит ала", "берес", "қайда", "кредит бер", "кредит алу"), faq_key="credit_howto", weight=3),
    _Pattern(("кешігу жоқ", "просрочк жоқ", "без просрочек", "кешігу", "просрочк"), faq_key="overdue", weight=4),
    _Pattern(("жұмыс уақыты", "график", "сағат", "нешеғе дейін", "во сколько", "режим"), faq_key="work_hours", weight=3),
    _Pattern(("тарих", "история", "кредитная история", "қарайсыз", "қараймыз"), faq_key="credit_history", weight=3),
    _Pattern(
        ("ип без залог", "беззалогов", "даму ип", "жк даму", "даму для ип", "ип даму"),
        faq_key="damu_ip",
        weight=4,
    ),
]

# Доп. ответы (не в knowledge_base FAQ_ANSWERS)
EXTRA_FAQ = {
    "greeting": {
        "ru": (
            "Здравствуйте! KOMEK DAMU — кредиты, ипотека, DAMU 12,6%, рефинансирование.\n"
            "Напишите сумму и цель (например: «кредит 1 млн») или /start."
        ),
        "kk": (
            "Сәлеметсіз бе! KOMEK DAMU — несие, ипотека, DAMU 12,6%.\n"
            "Сома мен мақсатыңызды жазыңыз немесе /start."
        ),
    },
    "blacklist": {
        "ru": "Чёрного списка нет. Портится кредитная история — это можно улучшить. Нужна консультация в офисе.",
        "kk": "Қара тізім жоқ. Несие тарихы бұзылуы мүмкін — жөнделеді. Офисте кеңес керек.",
    },
    "overdue": {
        "ru": "С открытыми просрочками кредит не одобряем. Закройте просрочку и приходите в офис — подберём вариант.",
        "kk": "Ашық кешігумен несие берілмейді. Кешігуін жойып, офиске келіңіз.",
    },
    "thanks": {
        "ru": "Пожалуйста! Если появятся вопросы — пишите.",
        "kk": "Рахмет! Сұрақтар болса — жазыңыз.",
    },
    "operator_hint": {
        "ru": "Чтобы связаться с менеджером, напишите «оператор» или нажмите кнопку в меню.",
        "kk": "Менеджермен байланысу үшін «оператор» деп жазыңыз.",
    },
    "online_service": {
        "ru": "Полное оформление онлайн нет — нужен визит в офис. Предварительную консультацию можно получить по телефону.",
        "kk": "Толық онлайн рәсімдеу жоқ — офиске келу керек. Алдын ала кеңес телефон арқылы.",
    },
    "pension_info": {
        "ru": "С пенсионкой проще, но без неё тоже возможно. Подробности в офисе — консультация бесплатная.",
        "kk": "Зейнеткерлік куәлігімен оңайырақ, бірақ онсыз да болады. Толығы офисте — кеңес тегін.",
    },
    "credit_load": {
        "ru": "На кредитную нагрузку не смотрим. Главное — нет открытых просрочек.",
        "kk": "Несие жүктемесіне қарамаймыз. Бастысы — ашық кешігу болмауы керек.",
    },
    "scoring_info": {
        "ru": "Скоринг не единственный критерий. Приходите в офис — рассмотрим индивидуально.",
        "kk": "Скоринг бұл жалғыз критерий емес. Офиске келіңіз — жеке қараймыз.",
    },
    "credit_howto": {
        "ru": "Чтобы узнать шансы — выберите раздел меню (1–7) или напишите сумму и цель.",
        "kk": "Мүмкіндігін білу үшін мәзірден бөлімді таңдаңыз (1–7) немесе сома мен мақсатыңызды жазыңыз.",
    },
    "credit_history": {
        "ru": "Кредитную историю смотрим, но можно улучшить. Без открытых просрочек — шанс есть. Консультация в офисе бесплатная.",
        "kk": "Несие тарихын қараймыз, бірақ жөнделеді. Ашық кешігу болмаған жағдайда — мүмкіндік бар. Офисте кеңес тегін.",
    },
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _has_business_content(text: str) -> bool:
    norm = _normalize(text)
    if any(
        w in norm
        for w in (
            "кредит", "ипотек", "несие", "даму", "рефинанс", "млн", "миллион",
            "тенге", "взять", "займ", "сумм", "лимит", "процент", "ставк",
            "физлиц", "физическ", "срок", "пенси", "жеке",
        )
    ):
        return True
    digits = re.sub(r"\D", "", norm)
    return len(digits) >= 5


def parse_amount_tenge(text: str) -> int | None:
    """Извлечь сумму: 1 000 000, 1000000, 1 млн."""
    low = text.lower()
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*млн", low)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)
    collapsed = re.sub(r"(?<=\d)[\s\u00a0]+(?=\d)", "", text)
    amounts: list[int] = []
    for part in re.findall(r"\d+", collapsed):
        n = int(part)
        if n >= 50_000:
            amounts.append(n)
    if not amounts:
        return None
    return max(amounts)


def wants_payment_calculation(text: str) -> bool:
    """Расчёт только если явно просят посчитать платёж."""
    low = text.lower()
    markers = (
        "посчитай", "рассчитай", "сколько платить", "сколько будет",
        "ежемесяч", "платёж", "платеж", "калькулятор", "аннуитет", "переплат",
        "есепте", "айлық төлем", "ай сайын",
    )
    return any(m in low for m in markers)


def format_loan_offer(
    product_key: str,
    amount: int,
    lang: str,
    *,
    with_calc: bool = False,
    city: str | None = None,
) -> str:
    """Короткий ответ на «хочу кредит N» — без расчёта, если не просили."""
    info = get_product_info(product_key, lang)
    if not info:
        return format_product_card(product_key, lang)

    amount_str = f"{amount:,}".replace(",", " ")
    if city:
        body = f"📋 *{info['name']}*\n💰 {amount_str} ₸"
    elif lang == "kk":
        body = f"📋 *{info['name']}*\n💰 {amount_str} ₸\n\n❓ Қай қаладасыз?"
    else:
        body = f"📋 *{info['name']}*\n💰 {amount_str} ₸\n\n❓ Из какого вы города?"

    if not with_calc:
        return body

    from app.bot.loan_calc import format_calculator_result

    defaults = {
        "personal_credit": (21.0, 5),
        "business_credit": (21.0, 5),
        "damu": (12.6, 10),
        "mortgage_standard": (12.0, 20),
        "mortgage_gov": (7.0, 20),
        "refinancing": (18.0, 5),
    }
    rate, years = defaults.get(product_key, (21.0, 5))
    calc = format_calculator_result(
        {"amount": amount, "rate": rate, "years": years, "product": "personal"},
        lang,
    )
    return f"{body}\n\n{calc}"


def _score_pattern(text: str, pattern: _Pattern) -> int:
    score = 0
    for kw in pattern.keywords:
        if kw in text:
            score += pattern.weight + min(len(kw) // 4, 3)
    return score


def format_product_card(product_key: str, lang: str) -> str:
    info = get_product_info(product_key, lang)
    if not info:
        return ""
    if product_key == "personal_credit":
        return format_personal_credit_answer(lang)
    return f"📋 *{info['name']}*\n{info['description']}\n\n{info['conditions']}"


from app.bot.formatting import has_city_question, has_contact_block


def _attach_contacts(
    answer: str,
    lang: str,
    city: str | None,
    *,
    force_all_cities: bool = False,
    platform: str = "telegram",
) -> str:
    """Контакты: один город, если назван; иначе все 5 или вопрос про город."""
    if has_contact_block(answer) and not force_all_cities:
        return answer
    if city:
        return f"{answer}\n\n{get_contact_footer(city, lang, all_cities=False, platform=platform)}"  # type: ignore[arg-type]
    if force_all_cities:
        if has_contact_block(answer):
            return answer
        return f"{answer}\n\n{get_contact_footer(None, lang, all_cities=True, platform=platform)}"  # type: ignore[arg-type]
    if has_city_question(answer):
        return answer
    if lang == "kk":
        return f"{answer}\n\n❓ *Қай қаладасыз?*"
    return f"{answer}\n\n❓ *Из какого вы города?*"


def try_fast_response(
    text: str,
    lang: str = "ru",
    session_city: str | None = None,
    platform: str = "telegram",
    *,
    city_confirmed: bool = False,
    session: dict | None = None,
) -> Optional[str]:
    """
    Подбор готового ответа по ключевым словам и продуктам.
    Возвращает текст или None (тогда вызываем LLM).
    """
    if not text or len(text.strip()) < 2:
        return None

    if is_pure_greeting(text):
        from app.bot.formatting import format_welcome

        return _attach_contacts(
            format_welcome(lang, platform),  # type: ignore[arg-type]
            lang,
            session_city,
            platform=platform,
        )

    norm = _normalize(strip_leading_greeting(text))
    city = city_for_contacts(text, session_city, city_confirmed=city_confirmed)
    if len(norm) > 500:
        return None

    session = session or {}

    # Город после вопроса про физлицо — не адрес, а условия + офис
    if (
        city
        and len(_WORD.findall(norm)) <= 2
        and session.get("last_intent") == "personal_credit"
        and not any(w in norm for w in ("адрес", "офис", "телефон", "қайда", "мекен"))
    ):
        return _attach_contacts(
            format_personal_credit_answer(lang, text),
            lang,
            city,
            platform=platform,
        )

    if (mentions_ip(norm) or detect_business_entity(text) == "ip") and is_ip_credit_question(norm):
        return _attach_contacts(
            format_ip_credit_answer(lang), lang, city, platform=platform
        )

    if is_personal_credit_question(text, session):
        return _attach_contacts(
            format_personal_credit_answer(lang, text),
            lang,
            city,
            platform=platform,
        )

    business = _has_business_content(text)
    amount = parse_amount_tenge(text) if business else None
    entity = detect_business_entity(text)
    intent = detect_intent(text)

    if entity and not business and len(_WORD.findall(norm)) <= 3:
        if entity == "ip":
            return _attach_contacts(
                format_ip_credit_answer(lang)
                if is_ip_credit_question(norm)
                else format_product_card("business_credit", lang),
                lang,
                city,
                platform=platform,
            )
        if entity == "too":
            return _attach_contacts(
                format_product_card("business_credit", lang), lang, city, platform=platform
            )
        if entity == "personal":
            return _attach_contacts(
                format_personal_credit_answer(lang, text), lang, city, platform=platform
            )

    if (mentions_ip(norm) or entity == "ip") and is_ip_credit_question(norm):
        return _attach_contacts(
            format_ip_credit_answer(lang), lang, city, platform=platform
        )

    calc = wants_payment_calculation(text)
    if business and amount and intent:
        return _attach_contacts(
            format_loan_offer(intent, amount, lang, with_calc=calc, city=city),
            lang,
            city,
            platform=platform,
        )
    if business and amount and ("кредит" in norm or "несие" in norm):
        if not intent:
            return _attach_contacts(format_clarify_borrower_type(lang), lang, city, platform=platform)
        key = intent
        return _attach_contacts(
            format_loan_offer(key, amount, lang, with_calc=calc, city=city),
            lang,
            city,
            platform=platform,
        )
    if (
        business
        and ("кредит" in norm or "несие" in norm)
        and not entity
        and not mentions_ip(norm)
        and not mentions_too(norm)
        and not mentions_mortgage(norm)
        and intent not in ("mortgage_gov", "mortgage_standard")
    ):
        return _attach_contacts(format_clarify_borrower_type(lang), lang, city, platform=platform)
    if business and intent:
        if intent == "business_credit" and mentions_ip(norm) and not is_ip_credit_question(norm):
            intent = None
        if intent in ("mortgage_gov", "mortgage_standard"):
            return _attach_contacts(
                format_mortgage_programs_answer(lang), lang, city, platform=platform
            )
        if intent == "personal_credit":
            return _attach_contacts(
                format_personal_credit_answer(lang, text), lang, city, platform=platform
            )
        if intent:
            return _attach_contacts(format_product_card(intent, lang), lang, city, platform=platform)

    best_score = 0
    best_faq: str | None = None
    best_product: str | None = None

    for pat in FAQ_PATTERNS:
        if business and pat.faq_key == "greeting":
            continue
        if pat.product_key in ("mortgage_gov", "mortgage_standard") and mentions_ip(norm):
            continue
        s = _score_pattern(norm, pat)
        if s <= 0:
            continue
        if s > best_score:
            best_score = s
            best_faq = pat.faq_key
            best_product = pat.product_key
        elif s == best_score and pat.product_key:
            best_product = pat.product_key

    if best_score < 2:
        return None

    if best_product:
        if best_product in ("mortgage_gov", "mortgage_standard"):
            return _attach_contacts(
                format_mortgage_programs_answer(lang), lang, city, platform=platform
            )
        if best_product == "personal_credit":
            return _attach_contacts(
                format_personal_credit_answer(lang, text), lang, city, platform=platform
            )
        if amount:
            return _attach_contacts(
                format_loan_offer(
                    best_product, amount, lang, with_calc=calc, city=city
                ),
                lang,
                city,
                platform=platform,
            )
        return _attach_contacts(format_product_card(best_product, lang), lang, city, platform=platform)

    if best_faq and best_faq != "greeting":
        if best_faq == "mortgage_programs":
            return _attach_contacts(
                format_mortgage_programs_answer(lang), lang, city, platform=platform
            )
        if best_faq in EXTRA_FAQ:
            ans = EXTRA_FAQ[best_faq].get(lang) or EXTRA_FAQ[best_faq]["ru"]
            need_all = best_faq in ("blacklist", "overdue", "address") and not city
            return _attach_contacts(
                ans, lang, city, force_all_cities=need_all, platform=platform
            )
        if best_faq == "company_info":
            from app.bot.formatting import format_company_offer

            ans = format_company_offer(lang, platform)  # type: ignore[arg-type]
            return _attach_contacts(
                ans, lang, city, force_all_cities=not bool(city), platform=platform
            )
        ans = get_faq_answer(best_faq, lang)
        if ans:
            need_all = best_faq in ("blacklist", "overdue", "damu_ip", "address") and not city
            return _attach_contacts(ans, lang, city, force_all_cities=need_all, platform=platform)

    return None
