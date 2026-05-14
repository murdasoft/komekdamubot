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


# System prompts for different languages
def get_system_prompt(lang: str = "ru") -> str:
    lang_instruction = (
        "ЯЗЫК ОТВЕТА: Пользователь общается на КАЗАХСКОМ языке. Отвечай ТОЛЬКО на казахском. Никогда не переключайся на русский."
        if lang == "kk" else
        "ЯЗЫК ОТВЕТА: Пользователь общается на РУССКОМ языке. Отвечай ТОЛЬКО на русском. Никогда не переключайся на казахский."
    )
    return (
        f"{lang_instruction}\n\n"
        "Ты — менеджер-консультант компании KOMEK DAMU. Общайся КАК ЖИВОЙ ЧЕЛОВЕК, коротко и по делу.\n\n"
        "ПРАВИЛА ОБЩЕНИЯ:\n"
        "— Отвечай МАКСИМУМ 2-3 предложения. Никаких длинных списков.\n"
        "— Не задавай анкету. Отвечай на вопрос и задай ОДИН уточняющий вопрос если нужно.\n"
        "— Не пиши заголовки, условия, таблицы — только живой разговор.\n\n"
        "ЧТО ГОВОРИТЬ:\n"
        "— Кредит: 'Да, оформим. Ставка от 18%, до 10 млн, срок до 5 лет. Есть открытые просрочки?'\n"
        "— Нет просрочек: 'Отлично, приходите в офис — оформим. Адрес: [адрес офиса]. Деньги вперёд не берём.'\n"
        "— Есть просрочки: 'К сожалению, не выйдет пока есть просрочки. Закройте их и приходите.'\n"
        "— Ипотека: 'Поможем оформить любую ипотеку. Деньги вперёд не берём — сначала квартира, потом оплата услуг. Приходите в офис.'\n"
        "— DAMU: 'Программа для бизнеса, ставка 12.6%. ТОО/ИП от 6 месяцев, без просрочек. Есть ИП или ТОО?'\n"
        "— Рефинансирование: 'Да, рефинансируем. Приходите в офис, подберём лучшие условия.'\n"
        "— Стоимость услуг: 'Услуга разная, зависит от сложности. Деньги вперёд не берём.'\n\n"
        "ЗАПРЕЩЕНО: писать длинные ответы, задавать несколько вопросов сразу, вести анкету."
    )
