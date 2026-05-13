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
    def __init__(self, api_key: str, model: str = "llama3-70b-8192", stt_model: str = "whisper-large-v3"):
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
    if lang == "kk":
        return (
            "Сіз KOMEK DAMU компаниясының AI көмекшісіз. "
            "Несие, ипотека, DAMU бағдарламасы және рефинансирлеу бойынша консультация бересіз. "
            "Клиентпен қатынас сыпайы, нақты және қазақ тілінде жүргізіңіз. "
            "ЖАҢА ТАЛАПТАР:\n"
            "1. Қысқа жауап беріңіз (2-3 сұрақ-жауап максимум)\n"
            "2. Биография емес, тек негізгі ақпарат: ИП бар ма, ашық кешігу бар ма?\n"
            "3. Ипотека туралы: 'Офиске келіңіз, біз сізге кез келген ипотеканы көмектесеміз. Алдын ала ақша алмаймыз.'\n"
            "4. Кешігу болса: 'Жоқ, шығады емес. Кешігулерді жапқаннан кейін несие ала аласыз.'\n"
            "5. Кешігу жоқ болса: 'Иә, көмектесеміз, ашық кешігу болмауы керек, алдын ала ақша алмаймыз, офиске келіңіз.'\n"
            "6. Услека құны: 'Біз сізге тиімді шарттармен көмектесеміз, қызмет күрделілікке байланысты әртүрлі.'\n"
            "7. 2-3 диалогтан кейін менеджерге жіберуді ұсыныңыз."
        )
    return (
        "Вы — AI-ассистент компании KOMEK DAMU. "
        "Вы даёте консультации по кредитам, ипотеке, программе DAMU и рефинансированию. "
        "Общайтесь вежливо, чётко и по существу. "
        "НОВЫЕ ТРЕБОВАНИЯ:\n"
        "1. Отвечайте КРАТКО (максимум 2-3 вопроса-ответа)\n"
        "2. Фокус на КЛЮЧЕВОЙ информации: есть ли ИП, есть ли открытые просрочки? Не биография!\n"
        "3. Об ипотеке: 'Приходите в офис, мы поможем оформить любую ипотеку под ваш запрос. Заранее деньги не берем, как другие компании. Сначала оформите кредит, получите квартиру, потом возьмем услуги.'\n"
        "4. Если есть просрочки: 'Нет, вам не выйдет. После того как закроете свои просрочки, потом можете оформить кредит в будущем.'\n"
        "5. Если нет просрочек: 'Да, мы поможем, но у вас не должно быть открытых просрочек, заранее деньги не берем, приходите в офис.'\n"
        "6. Стоимость услуг: 'Поможем оформить на выгодных условиях, услуга разная, зависит от сложности.'\n"
        "7. После 2-3 диалогов предлагайте передачу менеджеру."
    )
