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
    groq_model: str = field(default_factory=lambda: _getenv("GROQ_MODEL", "llama3-70b-8192"))
    groq_stt_model: str = field(default_factory=lambda: _getenv("GROQ_STT_MODEL", "whisper-large-v3"))
    
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
