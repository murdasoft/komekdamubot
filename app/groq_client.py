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
        "ru": "📍 Алматы: ул. Муратбаева 134, каб. 311, тел: 8 707 339 10 39",
        "kk": "📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39",
    },
    "astana": {
        "ru": "📍 Астана: ул. Сыганак 47, каб. 433, тел: 8 702 187 97 26",
        "kk": "📍 Астана: Сығанақ 47, 433 каб, тел: 8 702 187 97 26",
    },
    "shymkent": {
        "ru": "📍 Шымкент: ул. Мадели Кожа 45, каб. 7, тел: 8 705 810 28 81",
        "kk": "📍 Шымкент: Мадели Кожа 45, 7 каб, тел: 8 705 810 28 81",
    },
    "atyrau": {
        "ru": "📍 Атырау: ул. Досмухамедова 139а, каб. 9, тел: 8 706 686 83 00",
        "kk": "📍 Атырау: Досмухамедова 139а, 9 каб, тел: 8 706 686 83 00",
    },
}

CITY_KEYWORDS = {
    "almaty":   ["алматы", "алма-ата", "алмата", "almaty"],
    "astana":   ["астана", "нур-султан", "нурсултан", "astana"],
    "shymkent": ["шымкент", "шимкент", "шымкент", "shymkent"],
    "atyrau":   ["атырау", "atyrau"],
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
        "ЯЗЫК ОТВЕТА: Пользователь общается на КАЗАХСКОМ языке. Отвечай ТОЛЬКО на казахском. Никогда не переключайся на русский."
        if lang == "kk" else
        "ЯЗЫК ОТВЕТА: Пользователь общается на РУССКОМ языке. Отвечай ТОЛЬКО на русском. Никогда не переключайся на казахский."
    )
    office_block = get_office_block(city, lang)
    city_note = (
        "" if city else
        ("ВАЖНО: если клиент не называл город — спроси 'Из какого вы города?' и запомни ответ. Потом давай только его офис.\n\n"
         if lang == "ru" else
         "МАҢЫЗДЫ: клиент қала атамаса — 'Қай қаладасыз?' деп сұра және жауапты есте сақта. Содан кейін тек оның қаласын бер.\n\n")
    )
    return (
        f"{lang_instruction}\n\n"
        "Ты — консультант KOMEK DAMU. Одно короткое сообщение — и всё.\n\n"
        f"{city_note}"
        "СХЕМА ОТВЕТА:\n"
        "1. Одна фраза по теме из базы знаний.\n"
        "2. Скажи что онлайн-консультации нет — только офис.\n"
        "3. Укажи адрес офиса клиента (ниже).\n"
        "4. Добавь тег [DONE] в конце — диалог завершён.\n\n"
        f"ОФИС КЛИЕНТА:\n{office_block}\n\n"
        "ЕСЛИ НЕ ЗНАЕШЬ ОТВЕТА:\n"
        f"  Скажи что менеджер ответит подробнее, укажи офис: {office_block} [NOTIFY_MANAGER][DONE]\n\n"
        "ПРИМЕРЫ:\n"
        f"— Кредит: 'Кредит оформим. Ставка от 21%, до 25 млн. Деньги вперёд не берём.\n{office_block} [DONE]'\n"
        f"— DAMU: 'Ставка 12,6%, без залога до 40 млн, ИП/ТОО от 6 мес, без просрочек.\n{office_block} [DONE]'\n"
        f"— Ипотека: 'Гос.программа от 2%, взнос от 10%. Консультация только в офисе.\n{office_block} [DONE]'\n"
        f"— Просрочки: 'С открытыми просрочками не получится. Закройте и приходите.\n{office_block} [DONE]'\n\n"
        "БАЗА ЗНАНИЙ:\n"
        "— Бизнес (ИП/ТОО/КХ): без залога до 40 млн, с залогом до 500 млн, ТОО без залога до 200 млн, ставка 12,6%, от 6 мес работы, без открытых просрочек\n"
        "— Физлицо: до 25 млн, ставка от 21%, без открытых просрочек\n"
        "— Ипотека: гос.программа от 2–9%, взнос от 10–20%, срок до 25 лет, первичка/вторичка/частный дом, только офлайн\n"
        "— Предоплату не берём. Консультация бесплатная. Работаем по договору.\n\n"
        "ВАЖНО: всегда пиши 'ставка ОТ 21%' (не 'ставка 21%'), 'ОТ 2%' (не '2%'). Для казахского: 'стаука 21%-ДАН' (не '21%').\n\n"
        "ЗАПРЕЩЕНО: задавать лишние вопросы, давать онлайн-консультации по ипотеке, писать длинно."
    )
