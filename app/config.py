"""
Configuration for Komek Damu Bot.
Supports: Telegram, WhatsApp (Green API), Groq AI, Bitrix24
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _getenv(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Settings:
    # Telegram Bot
    telegram_bot_token: str = field(default_factory=lambda: _getenv("TELEGRAM_BOT_TOKEN"))
    telegram_webhook_secret: str = field(default_factory=lambda: _getenv("TELEGRAM_WEBHOOK_SECRET", "changeme"))
    telegram_alert_chat_id: str = field(default_factory=lambda: _getenv("TELEGRAM_ALERT_CHAT_ID"))
    
    # WhatsApp (Green API)
    green_api_instance_id: str = field(default_factory=lambda: _getenv("GREEN_API_INSTANCE_ID"))
    green_api_token: str = field(default_factory=lambda: _getenv("GREEN_API_TOKEN"))
    green_api_webhook_token: str = field(default_factory=lambda: _getenv("GREEN_API_WEBHOOK_TOKEN", "changeme"))
    
    # Groq AI
    groq_api_key: str = field(default_factory=lambda: _getenv("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_stt_model: str = field(default_factory=lambda: _getenv("GROQ_STT_MODEL", "whisper-large-v3"))

    # Local AI (Ollama + Whisper on Hetzner)
    ai_provider: str = field(default_factory=lambda: _getenv("AI_PROVIDER", ""))
    local_llm_base_url: str = field(default_factory=lambda: _getenv("LOCAL_LLM_BASE_URL", ""))
    local_llm_model: str = field(
        default_factory=lambda: _getenv("LOCAL_LLM_MODEL", "qwen2.5:3b")
    )
    local_llm_api_key: str = field(default_factory=lambda: _getenv("LOCAL_LLM_API_KEY", ""))
    local_whisper_url: str = field(default_factory=lambda: _getenv("LOCAL_WHISPER_URL", ""))

    # Groq только если явно включён (лимит ~50 req/day на free tier)
    groq_enabled: bool = field(
        default_factory=lambda: _getenv("GROQ_ENABLED", "false").lower() in ("1", "true", "yes")
    )

    # Мгновенные ответы из базы FAQ без вызова LLM
    fast_faq_enabled: bool = field(
        default_factory=lambda: _getenv("FAST_FAQ", "true").lower() in ("1", "true", "yes")
    )
    local_llm_max_tokens: int = field(
        default_factory=lambda: int(_getenv("LOCAL_LLM_MAX_TOKENS", "256"))
    )
    local_llm_num_ctx: int = field(
        default_factory=lambda: int(_getenv("LOCAL_LLM_NUM_CTX", "2048"))
    )
    local_llm_keep_alive: str = field(
        default_factory=lambda: _getenv("LOCAL_LLM_KEEP_ALIVE", "30m")
    )
    
    # Bitrix24
    bitrix24_webhook_url: str = field(default_factory=lambda: _getenv("BITRIX24_WEBHOOK_URL"))
    
    # Security
    ignored_chat_ids: str = field(default_factory=lambda: _getenv("IGNORED_CHAT_IDS", ""))
    
    # Timing
    reminder_delay_seconds: int = field(default_factory=lambda: int(_getenv("REMINDER_DELAY_SECONDS", "3600")))
    order_abandon_nudge_seconds: int = field(default_factory=lambda: int(_getenv("ORDER_ABANDON_NUDGE_SECONDS", "1800")))
    handoff_timeout_hours: int = field(default_factory=lambda: int(_getenv("HANDOFF_TIMEOUT_HOURS", "24")))
    
    # URLs
    webhook_base_url: str = field(default_factory=lambda: _getenv("WEBHOOK_BASE_URL", ""))
    
    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}/webhook/telegram"
    
    @property
    def green_api_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}/webhook/whatsapp"
    
    @property
    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)
    
    @property
    def is_whatsapp_configured(self) -> bool:
        return bool(self.green_api_instance_id and self.green_api_token)
    
    @property
    def is_groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def effective_ai_provider(self) -> str:
        provider = (self.ai_provider or "").lower()
        if provider == "local" and self.is_local_ai_configured:
            return "local"
        if provider == "groq" or (not provider and self.is_groq_configured):
            return "groq"
        if self.is_local_ai_configured:
            return "local"
        if self.is_groq_configured:
            return "groq"
        return provider or "none"

    @property
    def is_local_ai_configured(self) -> bool:
        return bool(self.local_llm_base_url and self.local_whisper_url)

    @property
    def is_ai_configured(self) -> bool:
        if self.effective_ai_provider == "local":
            return self.is_local_ai_configured
        if self.effective_ai_provider == "groq":
            return self.is_groq_configured
        return False
    
    def get_ignored_chat_ids(self) -> List[str]:
        raw = self.ignored_chat_ids.strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]


# Global singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
