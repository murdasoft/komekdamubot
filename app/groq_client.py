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
        "Ты — консультант KOMEK DAMU. Одно короткое сообщение — и всё.\n\n"
        "СХЕМА ОТВЕТА:\n"
        "1. Одна фраза по теме из базы знаний.\n"
        "2. Скажи что онлайн-консультации нет — только офис.\n"
        "3. Укажи адрес офиса.\n"
        "4. Добавь тег [DONE] в конце — диалог завершён.\n\n"
        "ОФИСЫ (ru):\n"
        "📍 Алматы: ул. Муратбаева 134, каб. 311, тел: 8 707 339 10 39\n"
        "📍 Астана: ул. Сыганак 47, каб. 433, тел: 8 702 187 97 26\n"
        "📍 Шымкент: ул. Мадели Кожа 45, каб. 7, тел: 8 705 810 28 81\n"
        "📍 Атырау: ул. Досмухамедова 139а, каб. 9, тел: 8 706 686 83 00\n\n"
        "ОФИСТЕР (kk):\n"
        "📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39\n"
        "📍 Астана: Сығанақ 47, 433 каб, тел: 8 702 187 97 26\n"
        "📍 Шымкент: Мадели Кожа 45, 7 каб, тел: 8 705 810 28 81\n"
        "📍 Атырау: Досмухамедова 139а, 9 каб, тел: 8 706 686 83 00\n\n"
        "ЕСЛИ НЕ ЗНАЕШЬ ОТВЕТА:\n"
        "  ru: 'Подробнее расскажет менеджер. Приходите в ближайший офис:\\n📍 Алматы: Муратбаева 134, каб.311, тел: 8 707 339 10 39\\n📍 Астана: Сыганак 47, каб.433, тел: 8 702 187 97 26' [NOTIFY_MANAGER][DONE]\n"
        "  kk: 'Менеджер толығырақ түсіндіреді. Жақын офисімізге келіңіз:\\n📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39\\n📍 Астана: Сығанақ 47, 433 каб, тел: 8 702 187 97 26' [NOTIFY_MANAGER][DONE]\n\n"
        "ПРИМЕРЫ (используй как шаблон, вставляй список офисов):\n"
        "— Кредит (ru): 'Кредит оформим. Ставка от 21%, до 25 млн. Деньги вперёд не берём.\\n📍 Алматы: Муратбаева 134, каб.311, тел: 8 707 339 10 39\\n📍 Астана: Сыганак 47, каб.433, тел: 8 702 187 97 26\\n📍 Шымкент: Мадели Кожа 45, каб.7, тел: 8 705 810 28 81\\n📍 Атырау: Досмухамедова 139а, каб.9, тел: 8 706 686 83 00 [DONE]'\n"
        "— Несие (kk): 'Несие рәсімдейміз. Ставка 21%-дан, 25 млн-ға дейін. Алдын ала ақша алмаймыз.\\n📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39\\n📍 Астана: Сығанақ 47, 433 каб, тел: 8 702 187 97 26\\n📍 Шымкент: Мадели Кожа 45, 7 каб, тел: 8 705 810 28 81\\n📍 Атырау: Досмухамедова 139а, 9 каб, тел: 8 706 686 83 00 [DONE]'\n"
        "— DAMU (ru): 'Программа DAMU — ставка 12,6%, без залога до 40 млн, ИП/ТОО от 6 мес, без просрочек.\\n📍 Алматы: Муратбаева 134, каб.311, тел: 8 707 339 10 39 [DONE]'\n"
        "— DAMU (kk): 'DAMU бағдарламасы — ставка 12,6%, кепілсіз 40 млн-ға дейін, ЖК/ТОО 6 айдан, просрочкасыз.\\n📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39 [DONE]'\n"
        "— Ипотека (ru): 'Поможем с ипотекой. Гос.программа от 2%, взнос от 10%. Консультация только в офисе.\\n📍 Алматы: Муратбаева 134, каб.311, тел: 8 707 339 10 39 [DONE]'\n"
        "— Ипотека (kk): 'Ипотекамен көмектесеміз. Мемлекеттік бағдарлама 2%-дан, бастапқы жарна 10%-дан. Тек офисте кеңес береміз.\\n📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39 [DONE]'\n"
        "— Просрочки (ru): 'С открытыми просрочками не получится. Закройте их и приходите — поможем.\\n📍 Алматы: Муратбаева 134, каб.311, тел: 8 707 339 10 39 [DONE]'\n"
        "— Просрочка (kk): 'Ашық просрочкамен болмайды. Жабыңыз да офисімізге келіңіз.\\n📍 Алматы: Муратбаева 134, 311 каб, тел: 8 707 339 10 39 [DONE]'\n\n"
        "БАЗА ЗНАНИЙ:\n"
        "— Бизнес (ИП/ТОО/КХ): без залога до 40 млн, с залогом до 500 млн, ТОО без залога до 200 млн, ставка 12,6%, от 6 мес работы, без открытых просрочек\n"
        "— Физлицо: до 25 млн, ставка от 21%, без открытых просрочек\n"
        "— Ипотека: гос.программа 2–9%, взнос 10–20%, срок до 25 лет, первичка/вторичка/частный дом, только офлайн\n"
        "— Предоплату не берём. Консультация бесплатная. Работаем по договору.\n\n"
        "ЗАПРЕЩЕНО: задавать вопросы, давать онлайн-консультации по ипотеке, писать длинно."
    )
