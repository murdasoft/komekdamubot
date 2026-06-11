"""Together AI — chat + Whisper STT (OpenAI-compatible API)."""

from __future__ import annotations

import io
import os
import logging

import httpx

from app.ai_utils import detect_language_simple

logger = logging.getLogger(__name__)

TOGETHER_API_BASE = "https://api.together.xyz/v1"

_together_cache: dict[tuple[str, str, str], "TogetherClient"] = {}


def get_together_client(settings) -> "TogetherClient":
    """Reuse client per API key + models (serverless warm instances)."""
    key = (
        settings.together_api_key,
        settings.together_model,
        settings.together_stt_model,
    )
    client = _together_cache.get(key)
    if client is None:
        client = TogetherClient(*key)
        _together_cache[key] = client
    return client


class TogetherClient:
    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        stt_model: str = "openai/whisper-large-v3",
    ):
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
        temperature: float = 0.5,
        max_tokens: int = 280,
    ) -> tuple[str | None, str | None]:
        url = f"{TOGETHER_API_BASE}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload, headers=self.headers)
                r.raise_for_status()
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                return content.strip() if content else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            logger.error("Together chat error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Together chat exception")
            return None, str(e)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        language: str | None = None,
        prompt: str | None = None,
        *,
        temperature: float = 0.0,
    ) -> tuple[str | None, str | None]:
        url = f"{TOGETHER_API_BASE}/audio/transcriptions"
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".ogg", ".oga"):
            upload_name = "audio.opus"
            mime = "audio/opus"
        elif ext == ".mp3":
            upload_name = "audio.mp3"
            mime = "audio/mpeg"
        elif ext == ".wav":
            upload_name = "audio.wav"
            mime = "audio/wav"
        else:
            upload_name = filename or "audio.ogg"
            mime = "audio/ogg"

        logger.info(
            "Together STT: file=%s upload=%s mime=%s lang=%s bytes=%s",
            filename,
            upload_name,
            mime,
            language,
            len(audio_bytes),
        )
        files = {"file": (upload_name, io.BytesIO(audio_bytes), mime)}
        data: dict[str, str] = {
            "model": self.stt_model,
            "response_format": "json",
            "temperature": str(temperature),
        }
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt[:2200]
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, headers=headers, files=files, data=data)
                r.raise_for_status()
                result = r.json()
                text = (result.get("text") or "").strip()
                return text if text else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            logger.error("Together STT error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Together STT exception")
            return None, str(e)

    def detect_language_simple(self, text: str) -> str:
        return detect_language_simple(text)
