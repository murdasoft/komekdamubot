"""
Pytest configuration and fixtures for KOMEK DAMU Bot tests.
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set mock environment variables for testing."""
    env_vars = {
        "GROQ_API_KEY": "test_groq_key",
        "GROQ_MODEL": "llama3-70b-8192",
        "TELEGRAM_BOT_TOKEN": "test_telegram_token",
        "TELEGRAM_WEBHOOK_SECRET": "test_secret",
        "WEBHOOK_BASE_URL": "https://test.vercel.app",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def sample_telegram_update():
    """Sample Telegram update payload."""
    return {
        "update_id": 123456,
        "message": {
            "message_id": 1,
            "from": {"id": 123, "first_name": "Test", "last_name": "User"},
            "chat": {"id": 123, "type": "private"},
            "text": "Привет, нужен кредит",
            "date": 1234567890,
        }
    }


@pytest.fixture
def sample_telegram_callback():
    """Sample Telegram callback query."""
    return {
        "update_id": 123457,
        "callback_query": {
            "id": "callback_123",
            "from": {"id": 123, "first_name": "Test"},
            "message": {
                "message_id": 2,
                "chat": {"id": 123, "type": "private"},
            },
            "data": "product:personal_credit",
        }
    }


@pytest.fixture
def sample_whatsapp_update():
    """Sample WhatsApp (Green API) update."""
    return {
        "typeWebhook": "incomingMessageReceived",
        "instanceData": {"idInstance": 123},
        "senderData": {
            "chatId": "77001234567@c.us",
            "sender": "77001234567@c.us",
            "senderName": "Test User",
        },
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"text": "Нужен кредит для бизнеса"},
        },
        "timestamp": 1234567890,
    }


@pytest.fixture
def mock_session():
    """Mock user session."""
    return {
        "state": "idle",
        "lang": "ru",
        "product": None,
        "flow_step": None,
        "data": {},
        "contact_name": "Test User",
    }
