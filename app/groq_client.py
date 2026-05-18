"""
Groq API client for LLM chat and Speech-to-Text (STT).
Supports: LLaMA 3.1, Whisper for Russian and Kazakh voice messages.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_API_BASE = "https://api.groq.com/openai/v1"


class GroqClient:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", stt_model: str = "whisper-large-v3"):
        self.api_key = api_key
        self.model = model
        self.stt_model = stt_model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> tuple[str | None, str | None]:
        """
        Send chat completion request to Groq.
        Returns (content, error).
        """
        url = f"{GROQ_API_BASE}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, json=payload, headers=self.headers)
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                return content.strip() if content else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("Groq chat error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Groq chat exception")
            return None, str(e)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        language: str | None = None,  # "ru", "kk", or None for auto
    ) -> tuple[str | None, str | None]:
        """
        Transcribe audio using Groq Whisper.
        Supports Russian (ru) and Kazakh (kk).
        Returns (transcript, error).
        """
        url = f"{GROQ_API_BASE}/audio/transcriptions"
        
        files = {
            "file": (filename, io.BytesIO(audio_bytes), "audio/ogg"),
        }
        data = {
            "model": self.stt_model,
        }
        if language:
            data["language"] = language
        
        # Use multipart form data
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                )
                r.raise_for_status()
                result = r.json()
                text = result.get("text", "").strip()
                return text if text else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("Groq STT error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Groq STT exception")
            return None, str(e)

    def detect_language_simple(self, text: str) -> str:
        """
        Simple heuristic to detect if text is Kazakh or Russian.
        Returns 'kk' for Kazakh, 'ru' for Russian.
        """
        # Kazakh-specific characters
        kazakh_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
        text_sample = text[:200]
        
        for char in kazakh_chars:
            if char in text_sample:
                return "kk"
        
        # Common Kazakh words
        kazakh_words = ["сіз", "мен", "біз", "немесе", "және", "болды", "қазақстан", "қазақ"]
        text_lower = text.lower()
        kazakh_score = sum(1 for w in kazakh_words if w in text_lower)
        
        if kazakh_score >= 2:
            return "kk"
        
        return "ru"


OFFICES = {
    "almaty": {
        "ru": "📍 Алматы, ул. Муратбаева 134, каб. 311\n\n📞 Телефон: `8 707 339 10 39`\n💬 WhatsApp: `7 707 339 10 39`",
        "kk": "📍 Алматы, Муратбаева 134, 311 каб\n\n📞 Телефон: `8 707 339 10 39`\n💬 WhatsApp: `7 707 339 10 39`",
    },
    "astana": {
        "ru": "📍 Астана, ул. Сыганак 47, каб. 433\n\n📞 Телефон: `8 702 187 97 26`\n💬 WhatsApp: `7 702 187 97 26`",
        "kk": "📍 Астана, Сығанақ 47, 433 каб\n\n📞 Телефон: `8 702 187 97 26`\n💬 WhatsApp: `7 702 187 97 26`",
    },
    "shymkent": {
        "ru": "📍 Шымкент, ул. Мадели Кожа 45, каб. 7\n\n📞 Телефон: `8 705 810 28 81`\n💬 WhatsApp: `7 705 810 28 81`",
        "kk": "📍 Шымкент, Мадели Кожа 45, 7 каб\n\n📞 Телефон: `8 705 810 28 81`\n💬 WhatsApp: `7 705 810 28 81`",
    },
    "atyrau": {
        "ru": "📍 Атырау, ул. Досмухамедова 139а, каб. 9\n\n📞 Телефон: `8 706 686 83 00`\n💬 WhatsApp: `7 706 686 83 00`",
        "kk": "📍 Атырау, Досмухамедова 139а, 9 каб\n\n📞 Телефон: `8 706 686 83 00`\n💬 WhatsApp: `7 706 686 83 00`",
    },
    "aktau": {
        "ru": "📍 Актау\n\n📞 Телефон: `8 705 112 99 22`\n💬 WhatsApp: `7 705 112 99 22`",
        "kk": "📍 Ақтау\n\n📞 Телефон: `8 705 112 99 22`\n💬 WhatsApp: `7 705 112 99 22`",
    },
}

CITY_KEYWORDS = {
    "almaty":   ["алматы", "алма-ата", "алмата", "almaty"],
    "astana":   ["астана", "нур-султан", "нурсултан", "astana"],
    "shymkent": ["шымкент", "шимкент", "шымкент", "shymkent"],
    "atyrau":   ["атырау", "atyrau"],
    "aktau":    ["актау", "ақтау", "aktau"],
}


def detect_city(text: str) -> str | None:
    """Return city key if mentioned in text, else None."""
    lower = text.lower()
    for city, keywords in CITY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return city
    return None


def get_office_block(city: str | None, lang: str) -> str:
    """Return office line(s) for given city, or all offices if city unknown."""
    if city and city in OFFICES:
        return OFFICES[city][lang]
    lines = [OFFICES[c][lang] for c in OFFICES]
    return "\n".join(lines)


# System prompts for different languages
def get_system_prompt(lang: str = "ru", city: str | None = None) -> str:
    lang_instruction = (
        "ЯЗЫК: КАЗАХСКИЙ. Отвечай ТОЛЬКО на казахском."
        if lang == "kk" else
        "ЯЗЫК: РУССКИЙ. Отвечай ТОЛЬКО на русском."
    )
    office_block = get_office_block(city, lang)
    city_note = (
        "" if city else
        ("Если город неизвестен — спроси 'Из какого вы города?'\n\n" if lang == "ru" else "Қала белгісіз болса — 'Қай қаладасыз?' деп сұра\n\n")
    )
    
    # Examples are CRITICAL for AI to understand format
    if lang == "kk":
        examples = (
            "МИСАЛДАР (осы форматты қолдан):\n"
            "— Ипотека: 'Ипотекамен көмектесеміз. Мемлекеттік бағдарлама 2%-дан, алдын ала 10%-20%. Онлайн кеңес бермейміз — офисімізге келіңіз.\\n{office} [DONE]'\n"
            "— Несие жеке тұлғаға: 'Несие береміз. Пенсионкамен 10-15 млн, пенсионкасыз 8 млн-ға дейін. Офиске келіңіз.\\n{office} [DONE]'\n"
            "— ИП: 'ИП-ге несие: 35 млн-ға дейін, 3 жылға. ИП кемінде 6 ай жұмыс істеген болуы керек. Келіңіз.\\n{office} [DONE]'\n"
            "— ИП залог: 'ИП-ге кепілдік несие 500 млн-ға дейін, 12,6%, 10 жылға. Офиске келіңіз.\\n{office} [DONE]'\n"
            "— ТОО: 'ТОО-ға несие: 200 млн-ға дейін, 12,6%, 1 жыл жұмыс. Келіңіз.\\n{office} [DONE]'\n"
            "— Просрочка: 'Ашық просрочкамен несие бермейміз. Жабыңыз да келіңіз.\\n{office} [DONE]'\n"
            "— Белгісіз сұрақ: 'Менеджер толығырақ түсіндіреді. Келіңіз.\\n{office} [NOTIFY_MANAGER][DONE]'\n\n"
            "БАЗА:\n"
            "— Ипотека: 2-9%, 10-20% алдын ала, 25 жыл\n"
            "— ИП: 35 млн, ОТ 21%, 3 жыл, 6 ай жұмыс\n"
            "— ТОО: 200 млн, 12,6%, 1 жыл жұмыс\n"
            "— ИП залог: 500 млн, 12,6%, 10 жыл\n"
            "— Жеке тұлға: 10-15 млн (пенсионкамен), 8 млн (пенсионкасыз)\n"
            "— Ставканы СҰРАМАСАН айтпа — тек офиске кел деп жауап бер\n"
            "— Предоплата жоқ, кеңес тегін"
        ).format(office=office_block)
        unknown = "Менеджер толығырақ түсіндіреді. Келіңіз."
    else:
        examples = (
            "ПРИМЕРЫ (используй этот формат):\n"
            "— Ипотека: 'Поможем с ипотекой. Гос.программа от 2%, взнос от 10-20%. Онлайн-консультации не даём — приходите в офис.\\n{office} [DONE]'\n"
            "— Физлицо: 'Кредит оформим. С пенсионкой 10–15 млн, без пенсионки до 8 млн. Ждём вас.\\n{office} [DONE]'\n"
            "— ИП: 'Кредит для ИП: до 35 млн, до 3 лет. ИП должен работать от 6 месяцев. Приглашаем в офис.\\n{office} [DONE]'\n"
            "— ИП залог: 'Залоговый кредит для ИП до 500 млн, 12,6%, до 10 лет. Приходите.\\n{office} [DONE]'\n"
            "— ТОО: 'Кредит для ТОО: до 200 млн, 12,6%, от 1 года работы. Приглашаем.\\n{office} [DONE]'\n"
            "— Просрочка: 'С открытыми просрочками не получится. Закройте и приходите.\\n{office} [DONE]'\n"
            "— Не знаешь ответ: 'Менеджер ответит подробнее. Приходите.\\n{office} [NOTIFY_MANAGER][DONE]'\n\n"
            "БАЗА ЗНАНИЙ:\n"
            "— Ипотека: от 2-9%, взнос 10-20%, до 25 лет\n"
            "— ИП: до 35 млн, ОТ 21%, до 3 лет, от 6 мес работы\n"
            "— ТОО: до 200 млн, 12,6%, от 1 года работы\n"
            "— ИП залоговый: до 500 млн, 12,6%, до 10 лет\n"
            "— Физлицо: 10-15 млн (с пенсионкой), до 8 млн (без)\n"
            "— НЕ называй ставку если НЕ спрашивали — просто пригласи в офис\n"
            "— Предоплаты нет, консультация бесплатна"
        ).format(office=office_block)
        unknown = "Менеджер ответит подробнее. Приходите."
    
    return (
        f"{lang_instruction}\n\n"
        f"{city_note}"
        "Ты — консультант KOMEK DAMU. Одно короткое сообщение.\n\n"
        "СХЕМА:\n"
        "1. Одна фраза по теме\n"
        "2. Онлайн-консультации нет — только офис\n"
        "3. Адрес офиса ниже\n"
        "4. Тег [DONE] в конце\n\n"
        f"ОФИС:\n{office_block}\n\n"
        "ЕСЛИ НЕ ЗНАЕШЬ ОТВЕТ:\n"
        f"  {unknown} {office_block} [NOTIFY_MANAGER][DONE]\n\n"
        f"{examples}\n\n"
        "ЗАПРЕТ: ставки без вопроса, лишние вопросы, длинные ответы, DAMU беззалоговый для ИП — НЕТ"
    )
