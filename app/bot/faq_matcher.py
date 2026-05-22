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
    detect_intent,
    get_faq_answer,
    get_product_info,
    is_damu_ip_question,
)
from app.bot.text_utils import is_pure_greeting, strip_leading_greeting
from app.offices import get_contact_footer, resolve_city

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
    _Pattern(("гос ипотек", "ипотека 2%", "ипотека 9%", "мемлекеттік ипотека", "2% ипотека"), product_key="mortgage_gov", weight=4),
    _Pattern(("рефинанс", "перекрыть кредит", "снизить ставку", "қайта қаржыландыру"), product_key="refinancing", weight=4),
    _Pattern(("кредит на бизнес", "бизнес кредит", "бизнес несиесі", "для ип", "для тоо"), product_key="business_credit", weight=4),
    _Pattern(("потребительск", "кредит для себя", "жеке несие", "взять кредит", "нужен кредит"), product_key="personal_credit", weight=3),
    _Pattern(("ипотек", "пәтер", "квартир", "жилье", "үй сатып"), product_key="mortgage_standard", weight=2),
    _Pattern(("даму", "damu"), product_key="damu", weight=2),
    # Приветствия — короткий ответ без LLM
    _Pattern(("здравствуй", "добрый день", "добрый вечер", "привет", "салем", "сәлем", "салам"), faq_key="greeting", weight=2),
    _Pattern(("спасибо", "рахмет", "thanks"), faq_key="thanks", weight=2),
    _Pattern(("оператор", "менеджер", "человек", "маман", "связаться с"), faq_key="operator_hint", weight=2),
    _Pattern(("чёрный список", "черный список", "черном списке", "қара тізім"), faq_key="blacklist", weight=4),
    _Pattern(("просрочк", "кешігу", "задолжал"), faq_key="overdue", weight=4),
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
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _has_business_content(text: str) -> bool:
    norm = _normalize(text)
    if any(
        w in norm
        for w in (
            "кредит", "ипотек", "несие", "даму", "рефинанс", "млн", "миллион",
            "тенге", "взять", "займ", "сумм",
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
        body = f"*{info['name']}* — {amount_str} ₸."
    elif lang == "kk":
        body = f"*{info['name']}* — {amount_str} ₸.\nҚай қаладасыз?"
    else:
        body = f"*{info['name']}* — сумма {amount_str} ₸.\nИз какого вы города?"

    if not with_calc:
        return body

    from app.bot.loan_calc import format_calculator_result

    defaults = {
        "personal_credit": (18.0, 5),
        "business_credit": (23.0, 5),
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
    if lang == "kk":
        return f"*{info['name']}* — {info['description']}"
    return f"*{info['name']}* — {info['description']}"


def _attach_contacts(
    answer: str,
    lang: str,
    city: str | None,
    *,
    force_all_cities: bool = False,
) -> str:
    """Контакты: один город, если назван; иначе все 5 или вопрос про город."""
    if "8 7" in answer and not force_all_cities:
        return answer
    if city:
        return f"{answer}\n\n{get_contact_footer(city, lang, all_cities=False)}"
    if force_all_cities:
        return f"{answer}\n\n{get_contact_footer(None, lang, all_cities=True)}"
    if lang == "kk" and "қала" not in answer.lower():
        return f"{answer}\n\nҚай қаладасыз? Офис пен телефон жібереміз."
    if lang != "kk" and "город" not in answer.lower():
        return f"{answer}\n\nИз какого вы города? Подскажу офис и телефон."
    return answer


def try_fast_response(
    text: str, lang: str = "ru", session_city: str | None = None
) -> Optional[str]:
    """
    Подбор готового ответа по ключевым словам и продуктам.
    Возвращает текст или None (тогда вызываем LLM).
    """
    if not text or len(text.strip()) < 2:
        return None

    if is_pure_greeting(text):
        g = EXTRA_FAQ["greeting"].get(lang) or EXTRA_FAQ["greeting"]["ru"]
        return _attach_contacts(g, lang, session_city)

    norm = _normalize(strip_leading_greeting(text))
    city = resolve_city(text, session_city)
    if len(norm) > 500:
        return None

    business = _has_business_content(text)
    amount = parse_amount_tenge(text) if business else None
    intent = detect_intent(text)

    if business and is_damu_ip_question(norm):
        ans = get_faq_answer("damu_ip", lang)
        if ans:
            return _attach_contacts(
                ans, lang, city, force_all_cities=not bool(city)
            )

    calc = wants_payment_calculation(text)
    if business and amount and intent:
        return _attach_contacts(
            format_loan_offer(intent, amount, lang, with_calc=calc, city=city),
            lang,
            city,
        )
    if business and amount and ("кредит" in norm or "несие" in norm):
        key = intent or "personal_credit"
        return _attach_contacts(
            format_loan_offer(key, amount, lang, with_calc=calc, city=city),
            lang,
            city,
        )
    if business and intent:
        return _attach_contacts(format_product_card(intent, lang), lang, city)

    best_score = 0
    best_faq: str | None = None
    best_product: str | None = None

    for pat in FAQ_PATTERNS:
        if business and pat.faq_key == "greeting":
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
        if amount:
            return _attach_contacts(
                format_loan_offer(
                    best_product, amount, lang, with_calc=calc, city=city
                ),
                lang,
                city,
            )
        return _attach_contacts(format_product_card(best_product, lang), lang, city)

    if best_faq and best_faq != "greeting":
        if best_faq in EXTRA_FAQ:
            ans = EXTRA_FAQ[best_faq].get(lang) or EXTRA_FAQ[best_faq]["ru"]
            need_all = best_faq in ("blacklist", "overdue", "address") and not city
            return _attach_contacts(
                ans, lang, city, force_all_cities=need_all
            )
        ans = get_faq_answer(best_faq, lang)
        if ans:
            need_all = best_faq in ("blacklist", "overdue", "damu_ip", "address") and not city
            return _attach_contacts(ans, lang, city, force_all_cities=need_all)

    return None
