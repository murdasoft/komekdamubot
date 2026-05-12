"""
Knowledge Base for KOMEK DAMU financial products.
Supports Russian and Kazakh languages.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProductInfo:
    key: str
    name_ru: str
    name_kk: str
    description_ru: str
    description_kk: str
    conditions_ru: str
    conditions_kk: str
    required_docs_ru: List[str] = field(default_factory=list)
    required_docs_kk: List[str] = field(default_factory=list)


# Financial products knowledge base
PRODUCTS: Dict[str, ProductInfo] = {
    "personal_credit": ProductInfo(
        key="personal_credit",
        name_ru="Кредит для физического лица",
        name_kk="Жеке несие",
        description_ru="Потребительский кредит на любые цели без залога",
        description_kk="Кепілдіксіз кез келген мақсатқа жеке несие",
        conditions_ru=(
            "Ставка: от 18% годовых\\n"
            "Сумма: до 10 000 000 тенге\\n"
            "Срок: до 5 лет\\n"
            "Возраст: 21-65 лет"
        ),
        conditions_kk=(
            "Мөлшерлеме: жылына 18%-дан\\n"
            "Сома: 10 000 000 теңгеге дейін\\n"
            "Мерзім: 5 жылға дейін\\n"
            "Жас: 21-65 жас"
        ),
        required_docs_ru=["Удостоверение личности", "Подтверждение дохода", "Документы по запросу"],
        required_docs_kk=["Жеке куәлік", "Табысты растайтын құжат", "Қосымша құжаттар"],
    ),
    
    "business_credit": ProductInfo(
        key="business_credit",
        name_ru="Кредит для бизнеса",
        name_kk="Бизнес несиесі",
        description_ru="Финансирование бизнеса для ТОО, ИП, КХ",
        description_kk="ТОО, ЖК, КХ үшін бизнес қаржыландыру",
        conditions_ru=(
            "Ставка: от 16% годовых\\n"
            "Сумма: до 100 000 000 тенге\\n"
            "Срок: до 5 лет\\n"
            "Требования: бизнес от 6 месяцев, оборот, без просрочек"
        ),
        conditions_kk=(
            "Мөлшерлеме: жылына 16%-дан\\n"
            "Сома: 100 000 000 теңгеге дейін\\n"
            "Мерзім: 5 жылға дейін\\n"
            "Талаптар: 6 айлық бизнес, айналым, кешігу жоқ"
        ),
        required_docs_ru=["Удостоверение", "Регистрация бизнеса", "Финансовая отчетность"],
        required_docs_kk=["Куәлік", "Бизнес тіркеу", "Қаржылық есептілік"],
    ),
    
    "damu": ProductInfo(
        key="damu",
        name_ru="DAMU 12,6%",
        name_kk="DAMU 12,6%",
        description_ru="Государственная программа поддержки бизнеса",
        description_kk="Мемлекеттік бизнес қолдау бағдарламасы",
        conditions_ru=(
            "Ставка: 12,6% годовых (субсидированная)\\n"
            "Сумма: до 80 000 000 тенге\\n"
            "Срок: до 3 лет\\n"
            "Условия: ТОО/ИП/КХ от 6 мес, оборот, без просрочек"
        ),
        conditions_kk=(
            "Мөлшерлеме: 12,6% (субсидияланған)\\n"
            "Сома: 80 000 000 теңгеге дейін\\n"
            "Мерзім: 3 жылға дейін\\n"
            "Шарттар: 6 айлық ТОО/ЖК/КХ, айналым, кешігу жоқ"
        ),
        required_docs_ru=["Бизнес регистрация", "Финансовый план", "Справка об обороте"],
        required_docs_kk=["Бизнес тіркеу", "Қаржы жоспары", "Айналым туралы анықтама"],
    ),
    
    "mortgage_gov": ProductInfo(
        key="mortgage_gov",
        name_ru="Ипотека по госпрограмме",
        name_kk="Мемлекеттік ипотека",
        description_ru="Ипотека по программам 2-9% (Сбербанк, БВУ и др.)",
        description_kk="2-9% бағдарламалар бойынша ипотека",
        conditions_ru=(
            "Ставка: 2-9% годовых (зависит от программы)\\n"
            "Первый взнос: 10-20%\\n"
            "Срок: до 20-25 лет\\n"
            "Требуется полная консультация в офисе"
        ),
        conditions_kk=(
            "Мөлшерлеме: 2-9% (бағдарламаға байланысты)\\n"
            "Алдын ала төлем: 10-20%\\n"
            "Мерзім: 20-25 жылға дейін\\n"
            "Толық кеңес беру керек"
        ),
        required_docs_ru=["Удостоверение", "Справка о доходах", "Договор на недвижимость"],
        required_docs_kk=["Куәлік", "Табыс туралы анықтама", "Мүлік келісім-шарты"],
    ),
    
    "mortgage_standard": ProductInfo(
        key="mortgage_standard",
        name_ru="Обычная ипотека",
        name_kk="Қарапайым ипотека",
        description_ru="Ипотека на первичное и вторичное жильё",
        description_kk="Бастапқы және қайталама тұрғын үйге ипотека",
        conditions_ru=(
            "Ставка: 18-22% годовых\\n"
            "Первый взнос: от 20%\\n"
            "Срок: до 20 лет\\n"
            "Первичка и вторичка"
        ),
        conditions_kk=(
            "Мөлшерлеме: 18-22%\\n"
            "Алдын ала төлем: 20%-дан\\n"
            "Мерзім: 20 жылға дейін\\n"
            "Бастапқы және қайталама"
        ),
        required_docs_ru=["Удостоверение", "Справка о доходах", "Документы на недвижимость"],
        required_docs_kk=["Куәлік", "Табыс анықтамасы", "Мүлік құжаттары"],
    ),
    
    "refinancing": ProductInfo(
        key="refinancing",
        name_ru="Рефинансирование",
        name_kk="Қайта қаржыландыру",
        description_ru="Снижение ставки по действующим кредитам",
        description_kk="Ағымдағы несиелер бойынша мөлшерлемені төмендету",
        conditions_ru=(
            "Снижение ставки до 16-18%\\n"
            "Объединение нескольких кредитов\\n"
            "Без открытых просрочек"
        ),
        conditions_kk=(
            "Мөлшерлемені 16-18%-ға дейін төмендету\\n"
            "Бірнеше несиені біріктіру\\n"
            "Ашық кешігу жоқ"
        ),
        required_docs_ru=["Удостоверение", "Договоры текущих кредитов", "Справка о платежах"],
        required_docs_kk=["Куәлік", "Ағымдағы несие шарттары", "Төлемдер туралы анықтама"],
    ),
}


def get_product_info(key: str, lang: str = "ru") -> Optional[Dict]:
    """Get product info in specified language."""
    product = PRODUCTS.get(key)
    if not product:
        return None
    
    if lang == "kk":
        return {
            "key": product.key,
            "name": product.name_kk,
            "description": product.description_kk,
            "conditions": product.conditions_kk,
            "docs": product.required_docs_kk,
        }
    return {
        "key": product.key,
        "name": product.name_ru,
        "description": product.description_ru,
        "conditions": product.conditions_ru,
        "docs": product.required_docs_ru,
    }


# Intent detection keywords
INTENT_KEYWORDS = {
    "personal_credit": {
        "ru": ["кредит для себя", "потребительский", "нужен кредит", "взять кредит", "деньги", "наличными"],
        "kk": ["жеке несие", "несие", "қаржы", "ақша", "алғым келеді"],
    },
    "business_credit": {
        "ru": ["кредит на бизнес", "бизнес кредит", "тово", "ип", "кх", "развитие бизнеса"],
        "kk": ["бизнес несиесі", "тово", "жк", "кәсіп", "бизнес"],
    },
    "damu": {
        "ru": ["даму", "damu", "12,6", "12.6", "госпрограмма бизнес"],
        "kk": ["даму", "damu", "12,6", "мәселе бағдарлама"],
    },
    "mortgage_gov": {
        "ru": ["гос ипотека", "ипотека 2%", "ипотека 9%", "сбер ипотека", "бву", "госпрограмма жилье"],
        "kk": ["мемлекеттік ипотека", "2% ипотека", "үй бағдарламасы"],
    },
    "mortgage_standard": {
        "ru": ["ипотека", "квартира в кредит", "первичка", "вторичка", "жилье"],
        "kk": ["ипотека", "пәтер несие", "бастапқы нарық", "үй"],
    },
    "refinancing": {
        "ru": ["рефинансирование", "перекрыть кредит", "снизить ставку", "перекредитовать"],
        "kk": ["қайта қаржыландыру", "мөлшерлемені төмендету", "несие толықтыру"],
    },
}


def detect_intent(text: str) -> Optional[str]:
    """Detect product intent from text."""
    text_lower = text.lower()
    
    for intent, keywords in INTENT_KEYWORDS.items():
        for lang, words in keywords.items():
            for word in words:
                if word in text_lower:
                    return intent
    return None


# FAQ answers
FAQ_ANSWERS = {
    "address": {
        "ru": "Наш офис находится в городе Алматы. Точный адрес уточняйте у менеджера после оформления заявки.",
        "kk": "Біздің кеңсесі Алматы қаласында орналасқан. Нақты мекенжайды менеджерден сұраңыз.",
    },
    "work_hours": {
        "ru": "Мы работаем с понедельника по пятницу с 9:00 до 18:00. Суббота с 10:00 до 14:00.",
        "kk": "Дүйсенбіден жұмаға дейін 9:00-ден 18:00-ге дейін. Сенбі 10:00-ден 14:00-ге дейін.",
    },
    "consultation_free": {
        "ru": "Консультация абсолютно бесплатная. Никакой предоплаты не требуется.",
        "kk": "Кеңес беру толығымен тегін. Алдын ала төлем талап етілмейді.",
    },
    "how_long": {
        "ru": "Рассмотрение заявки обычно занимает 1-3 рабочих дня. Менеджер свяжется с вами в течение 24 часов.",
        "kk": "Өтінішті қарау әдетте 1-3 жұмыс күні. Менеджер 24 сағат ішінде хабарласады.",
    },
}


def get_faq_answer(key: str, lang: str = "ru") -> str:
    """Get FAQ answer by key."""
    answer = FAQ_ANSWERS.get(key, {})
    return answer.get(lang, answer.get("ru", ""))
