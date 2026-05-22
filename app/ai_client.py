"""AI client factory: local Ollama/Whisper or Groq."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from app.groq_client import GroqClient
from app.local_ai_client import LocalAIClient

if TYPE_CHECKING:
    from app.config import Settings

AIClient = Union[GroqClient, LocalAIClient]


def create_ai_client(settings: "Settings") -> AIClient | None:
    if settings.effective_ai_provider == "local" and settings.local_llm_base_url:
        if not settings.local_whisper_url:
            raise ValueError("LOCAL_WHISPER_URL is required when AI_PROVIDER=local")
        return LocalAIClient(
            llm_base_url=settings.local_llm_base_url,
            llm_model=settings.local_llm_model,
            whisper_url=settings.local_whisper_url,
            api_key=settings.local_llm_api_key,
            num_ctx=settings.local_llm_num_ctx,
            keep_alive=settings.local_llm_keep_alive,
        )
    if settings.is_groq_configured:
        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            stt_model=settings.groq_stt_model,
        )
    return None
