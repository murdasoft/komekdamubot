"""
Flow definitions for KOMEK DAMU bot.
Each product has its own data collection flow.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any


@dataclass
class FlowStep:
    key: str
    question_ru: str
    question_kk: str
    validate: Optional[Callable[[str], tuple[bool, str]]] = None
    next_step: Optional[str] = None
    is_final: bool = False


# Validation helpers
def validate_phone(value: str) -> tuple[bool, str]:
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) >= 10:
        return True, digits
    return False, ""


def validate_number(value: str) -> tuple[bool, str]:
    digits = "".join(c for c in value if c.isdigit())
    if digits:
        return True, digits
    return False, ""


def validate_yes_no(value: str) -> tuple[bool, str]:
    yes_words = ["да", "yes", "есть", "бар", "иә", "true", "1"]
    no_words = ["нет", "no", "жоқ", " Yok", "false", "0"]
    val = value.lower().strip()
    if any(y in val for y in yes_words):
        return True, "да"
    if any(n in val for n in no_words):
        return True, "нет"
    return False, ""


# Common steps
PERSONAL_CREDIT_FLOW: Dict[str, FlowStep] = {
    "city": FlowStep(
        key="city",
        question_ru="В каком городе вы находитесь?",
        question_kk="Қай қалада тұрасыз?",
        next_step="age",
    ),
    "age": FlowStep(
        key="age",
        question_ru="Укажите ваш возраст (полных лет):",
        question_kk="Жасыңызды көрсетіңіз:",
        validate=validate_number,
        next_step="gender",
    ),
    "gender": FlowStep(
        key="gender",
        question_ru="Укажите пол (мужской/женский):",
        question_kk="Жынысыңызды көрсетіңіз:",
        next_step="amount",
    ),
    "amount": FlowStep(
        key="amount",
        question_ru="Какая сумма кредита вас интересует (в тенге)?",
        question_kk="Қандай сома қызықтырады (теңгеде)?",
        validate=validate_number,
        next_step="credit_history",
    ),
    "credit_history": FlowStep(
        key="credit_history",
        question_ru="Какая у вас кредитная история? (хорошая/средняя/плохая/нет кредитов)",
        question_kk="Несие тарихыңыз қалай? (жақсы/орташа/нашар/несие жоқ)",
        next_step="has_delays",
    ),
    "has_delays": FlowStep(
        key="has_delays",
        question_ru="Есть ли у вас открытые просрочки по кредитам? (да/нет)",
        question_kk="Ағымдағы кешігу бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Укажите ваш номер телефона для связи:",
        question_kk="Байланыс үшін телефон нөміріңіз:",
        validate=validate_phone,
        next_step="comment",
    ),
    "comment": FlowStep(
        key="comment",
        question_ru="Дополнительная информация (можно пропустить, написав 'нет'):",
        question_kk="Қосымша ақпарат ('жоқ' деп жіберсеңіз болады):",
        next_step="done",
    ),
}


BUSINESS_CREDIT_FLOW: Dict[str, FlowStep] = {
    "city": FlowStep(
        key="city",
        question_ru="В каком городе находится бизнес?",
        question_kk="Бизнес қай қалада орналасқан?",
        next_step="business_form",
    ),
    "business_form": FlowStep(
        key="business_form",
        question_ru="Форма бизнеса? (ТОО/ИП/КХ)",
        question_kk="Бизнес нысаны? (ТОО/ЖК/КХ)",
        next_step="business_age",
    ),
    "business_age": FlowStep(
        key="business_age",
        question_ru="Сколько месяцев работает бизнес?",
        question_kk="Бизнес неше ай жұмыс істейді?",
        validate=validate_number,
        next_step="has_turnover",
    ),
    "has_turnover": FlowStep(
        key="has_turnover",
        question_ru="Есть ли оборот по счетам? (да/нет)",
        question_kk="Есептер бойынша айналым бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="has_delays",
    ),
    "has_delays": FlowStep(
        key="has_delays",
        question_ru="Есть ли открытые просрочки? (да/нет)",
        question_kk="Ашық кешігу бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="amount",
    ),
    "amount": FlowStep(
        key="amount",
        question_ru="Требуемая сумма финансирования (тенге):",
        question_kk="Қажетті қаржы сомасы (теңге):",
        validate=validate_number,
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Контактный телефон:",
        question_kk="Байланыс телефоны:",
        validate=validate_phone,
        next_step="done",
    ),
}


DAMU_FLOW: Dict[str, FlowStep] = {
    "city": FlowStep(
        key="city",
        question_ru="Город регистрации бизнеса?",
        question_kk="Бизнес тіркелген қала?",
        next_step="business_form",
    ),
    "business_form": FlowStep(
        key="business_form",
        question_ru="Статус: ТОО / ИП / КХ?",
        question_kk="Мәртебе: ТОО / ЖК / КХ?",
        next_step="business_age",
    ),
    "business_age": FlowStep(
        key="business_age",
        question_ru="Сколько месяцев работает? (нужно минимум 6)",
        question_kk="Небір ай жұмыс істейді? (минимум 6 керек)",
        validate=validate_number,
        next_step="has_turnover",
    ),
    "has_turnover": FlowStep(
        key="has_turnover",
        question_ru="Есть ли оборот? (да/нет)",
        question_kk="Айналым бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="has_delays",
    ),
    "has_delays": FlowStep(
        key="has_delays",
        question_ru="Есть просрочки? (да/нет)",
        question_kk="Кешігу бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="amount",
    ),
    "amount": FlowStep(
        key="amount",
        question_ru="Желаемая сумма по программе DAMU:",
        question_kk="DAMU бағдарламасы бойынша қалайтын сома:",
        validate=validate_number,
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Телефон для связи:",
        question_kk="Байланыс телефоны:",
        validate=validate_phone,
        next_step="done",
    ),
}


MORTGAGE_FLOW: Dict[str, FlowStep] = {
    "mortgage_type": FlowStep(
        key="mortgage_type",
        question_ru="Какая ипотека интересует? (госпрограмма/обычная/первичка/вторичка)",
        question_kk="Қандай ипотека қызықтырады? (мәселе/қарапайым/бастапқы/қайталама)",
        next_step="city",
    ),
    "city": FlowStep(
        key="city",
        question_ru="Город покупки недвижимости?",
        question_kk="Мүлік сатып алатын қала?",
        next_step="property_type",
    ),
    "property_type": FlowStep(
        key="property_type",
        question_ru="Тип недвижимости? (квартира/дом/коммерция)",
        question_kk="Мүлік түрі? (пәтер/үй/коммерция)",
        next_step="property_price",
    ),
    "property_price": FlowStep(
        key="property_price",
        question_ru="Примерная стоимость (тенге):",
        question_kk="Шамамен құны (теңге):",
        validate=validate_number,
        next_step="down_payment",
    ),
    "down_payment": FlowStep(
        key="down_payment",
        question_ru="Первоначальный взнос, который готовы внести:",
        question_kk="Алдын ала төлемге дайын сома:",
        validate=validate_number,
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Телефон для консультации:",
        question_kk="Кеңес беру үшін телефон:",
        validate=validate_phone,
        next_step="done",
    ),
}


REFINANCING_FLOW: Dict[str, FlowStep] = {
    "client_type": FlowStep(
        key="client_type",
        question_ru="Кто вы? (физлицо/ИП/ТОО)",
        question_kk="Сіз кімсіз? (жеке тұлға/ЖК/ТОО)",
        next_step="current_loan_amount",
    ),
    "current_loan_amount": FlowStep(
        key="current_loan_amount",
        question_ru="Сумма текущего кредита (тенге):",
        question_kk="Ағымдағы несие сомасы (теңге):",
        validate=validate_number,
        next_step="current_rate",
    ),
    "current_rate": FlowStep(
        key="current_rate",
        question_ru="Текущая ставка (примерно):",
        question_kk="Ағымдағы мөлшерлеме (шамамен):",
        next_step="has_delays",
    ),
    "has_delays": FlowStep(
        key="has_delays",
        question_ru="Есть просрочки сейчас? (да/нет)",
        question_kk="Қазір кешігу бар ма? (иә/жоқ)",
        validate=validate_yes_no,
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Телефон для расчета:",
        question_kk="Есептесу үшін телефон:",
        validate=validate_phone,
        next_step="done",
    ),
}


COMPLEX_CASE_FLOW: Dict[str, FlowStep] = {
    "city": FlowStep(
        key="city",
        question_ru="Ваш город?",
        question_kk="Сіздің қалаңыз?",
        next_step="client_type",
    ),
    "client_type": FlowStep(
        key="client_type",
        question_ru="Кто вы? (физлицо/ИП/ТОО/КХ)",
        question_kk="Сіз кімсіз? (жеке тұлға/ЖК/ТОО/КХ)",
        next_step="amount",
    ),
    "amount": FlowStep(
        key="amount",
        question_ru="Какая сумма нужна?",
        question_kk="Қандай сома керек?",
        validate=validate_number,
        next_step="problem_description",
    ),
    "problem_description": FlowStep(
        key="problem_description",
        question_ru="Опишите ситуацию (плохая КИ, просрочки, отказы банков и т.д.):",
        question_kk="Жағдайды сипаттаңыз (нашар НТ, кешігу, банк бас тартуы т.б.):",
        next_step="phone",
    ),
    "phone": FlowStep(
        key="phone",
        question_ru="Телефон. Специалист разберет ваш кейс:",
        question_kk="Телефон. Маман сіздің жағдайды қарайды:",
        validate=validate_phone,
        next_step="done",
    ),
}


# Map product keys to their flows
PRODUCT_FLOWS = {
    "personal_credit": PERSONAL_CREDIT_FLOW,
    "business_credit": BUSINESS_CREDIT_FLOW,
    "damu": DAMU_FLOW,
    "mortgage_gov": MORTGAGE_FLOW,
    "mortgage_standard": MORTGAGE_FLOW,
    "refinancing": REFINANCING_FLOW,
    "complex_case": COMPLEX_CASE_FLOW,
}


def get_flow_for_product(product_key: str) -> Optional[Dict[str, FlowStep]]:
    """Get flow definition for a product."""
    return PRODUCT_FLOWS.get(product_key)


def get_first_step(flow: Dict[str, FlowStep]) -> Optional[str]:
    """Get first step key from flow."""
    if not flow:
        return None
    # Find step with no dependencies (entry point)
    all_next = {s.next_step for s in flow.values() if s.next_step}
    candidates = [k for k in flow.keys() if k not in all_next]
    return candidates[0] if candidates else list(flow.keys())[0]
