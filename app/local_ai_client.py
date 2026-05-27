"""Local Ollama LLM + Whisper API client."""

from __future__ import annotations

import io
import logging

import httpx

from app.ai_utils import detect_language_simple

logger = logging.getLogger(__name__)


class LocalAIClient:
    def __init__(
        self,
        llm_base_url: str,
        llm_model: str,
        whisper_url: str,
        api_key: str = "",
        num_ctx: int = 2048,
        keep_alive: str = "30m",
    ):
        self.llm_base_url = llm_base_url.rstrip("/")
        self.llm_model = llm_model
        self.whisper_url = whisper_url.rstrip("/")
        self.api_key = api_key
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> tuple[str | None, str | None]:
        url = f"{self.llm_base_url}/api/chat"
        payload = {
            "model": self.llm_model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": self.num_ctx,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                content = data.get("message", {}).get("content")
                return content.strip() if content else None, None
        except httpx.HTTPStatusError as e:
            err = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error("Ollama chat error: %s", err)
            return None, err
        except Exception as e:
            logger.exception("Ollama chat exception")
            return None, str(e)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        language: str | None = None,
        prompt: str | None = None,
    ) -> tuple[str | None, str | None]:
        # Try OpenAI-compatible API first (/v1/audio/transcriptions)
        # Then fallback to custom /transcribe endpoint
        for endpoint in ("/v1/audio/transcriptions", "/transcribe"):
            url = f"{self.whisper_url}{endpoint}"
            files = {"file": (filename, io.BytesIO(audio_bytes), "application/octet-stream")}
            data: dict[str, str] = {}
            if language:
                data["language"] = language
            if prompt and endpoint == "/v1/audio/transcriptions":
                data["prompt"] = prompt
            if endpoint == "/v1/audio/transcriptions":
                data["model"] = "small"

            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    r = await client.post(url, files=files, data=data or None)
                    if r.status_code == 404 and endpoint == "/v1/audio/transcriptions":
                        continue
                    r.raise_for_status()
                    result = r.json()
                    text = result.get("text", "").strip()
                    logger.info("Local Whisper result: '%s...' lang=%s endpoint=%s", text[:50], language, endpoint)
                    return text if text else None, None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and endpoint == "/v1/audio/transcriptions":
                    continue
                err = f"HTTP {e.response.status_code}: {e.response.text}"
                logger.error("Local Whisper error: %s", err)
                return None, err
            except Exception as e:
                if endpoint == "/v1/audio/transcriptions":
                    logger.warning("Local Whisper OpenAI endpoint failed, trying /transcribe: %s", e)
                    continue
                logger.exception("Local Whisper exception")
                return None, str(e)
        return None, "All Whisper endpoints failed"

    def detect_language_simple(self, text: str) -> str:
        return detect_language_simple(text)
