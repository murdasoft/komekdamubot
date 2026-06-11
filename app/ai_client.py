"""AI client factory: Groq (основной), local Ollama, Together (legacy)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from app.config import Settings
    from app.groq_client import GroqClient
    from app.local_ai_client import LocalAIClient
    from app.together_client import TogetherClient

AIClient = Union["GroqClient", "LocalAIClient", "TogetherClient"]


def create_ai_client(settings: "Settings") -> AIClient | None:
    provider = settings.effective_ai_provider

    if provider == "groq" and settings.is_groq_configured:
        from app.groq_client import GroqClient

        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            stt_model=settings.groq_stt_model,
        )
    if provider == "local" and settings.local_llm_base_url:
        from app.local_ai_client import LocalAIClient

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
    if provider == "together" and settings.is_together_configured:
        from app.together_client import TogetherClient

        return TogetherClient(
            api_key=settings.together_api_key,
            model=settings.together_model,
            stt_model=settings.together_stt_model,
        )
    if settings.is_groq_configured:
        from app.groq_client import GroqClient

        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            stt_model=settings.groq_stt_model,
        )
    return None
