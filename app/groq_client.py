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
        "Ты — консультант компании KOMEK DAMU. Отвечай КАК ЖИВОЙ ЧЕЛОВЕК — коротко, 1-2 предложения.\n\n"
        "ГЛАВНОЕ ПРАВИЛО: НЕ ЗАДАВАЙ ВОПРОСОВ. Отвечай коротко — 1-2 предложения — и направляй в офис.\n\n"
        "ЕСЛИ ЗНАЕШЬ ОТВЕТ — отвечай из базы знаний.\n"
        "  На русском добавляй: 'Приходите в офис, консультация бесплатная.'\n"
        "  На казахском добавляй: 'Офисімізге келіңіз, консультация тегін.'\n"
        "ЕСЛИ НЕ ЗНАЕШЬ:\n"
        "  На русском: 'Точнее ответит наш менеджер. Приходите в офис — всё расскажут.' [NOTIFY_MANAGER]\n"
        "  На казахском: 'Менеджеріміз нақтырақ жауап береді. Офисімізге келіңіз — бәрін айтады.' [NOTIFY_MANAGER]\n\n"
        "КАК ОТВЕЧАТЬ (на языке клиента):\n"
        "— Кредит (ru): 'Да, оформим. Ставка от 18%, до 10 млн, до 5 лет. Приходите в офис — деньги вперёд не берём.'\n"
        "— Несие (kk): 'Иә, рәсімдейміз. Ставка 18%-дан, 10 млн-ға дейін, 5 жылға. Офисімізге келіңіз — алдын ала ақша алмаймыз.'\n"
        "— Ипотека (ru): 'Поможем с ипотекой. Гос.программа от 2%, взнос от 10%. Приходите в офис, консультация бесплатная.'\n"
        "— Ипотека (kk): 'Ипотекамен көмектесеміз. Мемлекеттік бағдарлама 2%-дан, бастапқы жарна 10%-дан. Офисімізге келіңіз, консультация тегін.'\n"
        "— DAMU (ru): 'Ставка 12,6%, до 40 млн без залога. ИП/ТОО от 6 месяцев, без просрочек. Приходите в офис.'\n"
        "— DAMU (kk): 'Ставка 12,6%, кепілсіз 40 млн-ға дейін. ЖК/ТОО 6 айдан, просрочкасыз. Офисімізге келіңіз.'\n"
        "— Просрочки (ru): 'С открытыми просрочками не выйдет. Закройте и приходите — поможем.'\n"
        "— Просрочка (kk): 'Ашық просрочкамен болмайды. Жабыңыз да келіңіз — көмектесеміз.'\n"
        "— Рефинансирование (ru): 'Да, рефинансируем. Приходите в офис — подберём условия.'\n"
        "— Қайта қаржыландыру (kk): 'Иә, қайта қаржыландырамыз. Офисімізге келіңіз — жағдайды таңдаймыз.'\n\n"
        "БАЗА ЗНАНИЙ:\n"
        "— Ипотека: гос.программа 2–9%, взнос 10–20%, срок до 25 лет, первичка/вторичка/частный дом\n"
        "— DAMU: 12,6%, без залога до 40 млн, с залогом до 500 млн, ТОО без залога до 200 млн, физлицо до 25 млн\n"
        "— Документы DAMU: удостоверение, документы ИП/ТОО, выписка оборотов, кредитная история\n"
        "— Срок рассмотрения: от 1 дня. Плохая история — рассматриваем индивидуально.\n"
        "— Предоплату не берём. Консультация бесплатная. Работаем по договору.\n\n"
        "ЗАПРЕЩЕНО: задавать вопросы клиенту, писать длинные ответы, вести анкету."
    )
