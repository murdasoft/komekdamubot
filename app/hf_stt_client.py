"""
Hugging Face Inference — казахские Whisper-модели (опционально).
Модели: abilmansplus/whisper-turbo-kaz-rus-v1, shyngys879/kazakh-whisper-large-v3-turbo, …
Требует HUGGINGFACE_API_KEY и кредиты HF Inference (или dedicated endpoint).
"""

from __future__ import annotations

import io
import logging
import os

import httpx

logger = logging.getLogger(__name__)

HF_ROUTER = "https://router.huggingface.co/hf-inference/models"

# Приоритет: дообученные kk/ru модели → generic whisper
DEFAULT_KK_MODELS = (
    "abilmansplus/whisper-turbo-kaz-rus-v1",
    "openai/whisper-large-v3",
)


def _mime_for(filename: str) -> tuple[str, str]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".ogg", ".oga"):
        return "audio.opus", "audio/opus"
    if ext == ".mp3":
        return "audio.mp3", "audio/mpeg"
    if ext == ".wav":
        return "audio.wav", "audio/wav"
    return filename or "audio.ogg", "audio/ogg"


class HuggingFaceSTTClient:
    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        *,
        language: str | None = "kk",
        prompt: str | None = None,
    ) -> tuple[str | None, str | None]:
        models = [self.model] if self.model else list(DEFAULT_KK_MODELS)
        upload_name, mime = _mime_for(filename)
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for model_id in models:
            if not model_id:
                continue
            url = f"{HF_ROUTER}/{model_id}"
            files = {"file": (upload_name, io.BytesIO(audio_bytes), mime)}
            data: dict[str, str] = {}
            if language:
                data["language"] = language
            if prompt:
                data["prompt"] = prompt[:2200]

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.post(url, headers=headers, files=files, data=data)
                    if r.status_code in (503, 429):
                        logger.warning("HF STT %s warming up (%s)", model_id, r.status_code)
                        continue
                    if r.status_code >= 400:
                        logger.warning(
                            "HF STT %s HTTP %s: %s",
                            model_id,
                            r.status_code,
                            r.text[:200],
                        )
                        continue
                    body = r.json()
                    if isinstance(body, dict):
                        text = (body.get("text") or body.get("generated_text") or "").strip()
                    else:
                        text = str(body).strip()
                    if text:
                        logger.info("HF STT OK model=%s text=%s", model_id, text[:60])
                        return text, None
            except Exception:
                logger.exception("HF STT exception model=%s", model_id)

        return None, "hf_stt_all_models_failed"
