"""
Tests for configuration module.
"""

import pytest
from app.config import Settings, get_settings


class TestSettings:
    """Test Settings dataclass."""
    
    def test_default_values(self, mock_env_vars):
        """Test default configuration values."""
        settings = Settings()
        
        assert settings.groq_model == "llama3-70b-8192"
        assert settings.groq_stt_model == "whisper-large-v3"
        assert settings.reminder_delay_seconds == 3600
        assert settings.handoff_timeout_hours == 24
    
    def test_telegram_configured(self, mock_env_vars):
        """Test Telegram configuration detection."""
        settings = Settings()
        assert settings.is_telegram_configured is True
        assert settings.telegram_bot_token == "test_telegram_token"
    
    def test_groq_configured(self, mock_env_vars):
        """Test Groq configuration detection."""
        settings = Settings()
        assert settings.is_groq_configured is True
    
    def test_whatsapp_not_configured(self, mock_env_vars):
        """Test WhatsApp not configured without credentials."""
        settings = Settings()
        assert settings.is_whatsapp_configured is False
    
    def test_webhook_urls(self, mock_env_vars):
        """Test webhook URL generation."""
        settings = Settings()
        
        assert settings.telegram_webhook_url == "https://test.vercel.app/webhook/telegram"
        assert settings.green_api_webhook_url == "https://test.vercel.app/webhook/whatsapp"
    
    def test_ignored_chat_ids(self, mock_env_vars):
        """Test parsing ignored chat IDs."""
        import os
        os.environ["IGNORED_CHAT_IDS"] = "123,456, 789 "
        
        settings = Settings()
        ignored = settings.get_ignored_chat_ids()
        
        assert ignored == ["123", "456", "789"]
    
    def test_singleton_behavior(self, mock_env_vars):
        """Test that get_settings returns singleton."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2


class TestMissingConfig:
    """Test behavior with missing configuration."""
    
    def test_no_telegram_token(self, monkeypatch):
        """Test Telegram not configured without token."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        
        from app.config import Settings
        settings = Settings()
        
        assert settings.is_telegram_configured is False
    
    def test_no_groq_key(self, monkeypatch):
        """Test Groq not configured without API key."""
        monkeypatch.setenv("GROQ_API_KEY", "")
        
        from app.config import Settings
        settings = Settings()
        
        assert settings.is_groq_configured is False
