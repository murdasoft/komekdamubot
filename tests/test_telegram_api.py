"""
Tests for Telegram API module.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.telegram_api import (
    TelegramClient, extract_update_info, get_message_id,
    is_voice_message, get_voice_file_id, get_file_url
)


class TestExtractUpdateInfo:
    """Test extracting info from Telegram updates."""
    
    def test_extract_message_update(self):
        """Test extracting info from regular message."""
        update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "from": {"id": 123, "first_name": "Test", "last_name": "User"},
                "chat": {"id": 456, "type": "private"},
                "text": "Hello",
                "date": 1234567890,
            }
        }
        
        chat_id, text, sender_name, callback_id = extract_update_info(update)
        
        assert chat_id == "456"
        assert text == "Hello"
        assert sender_name == "Test User"
        assert callback_id is None
    
    def test_extract_callback_update(self):
        """Test extracting info from callback query."""
        update = {
            "update_id": 124,
            "callback_query": {
                "id": "cb_123",
                "from": {"id": 123, "first_name": "Test"},
                "message": {
                    "message_id": 2,
                    "chat": {"id": 456, "type": "private"},
                },
                "data": "product:personal_credit",
            }
        }
        
        chat_id, text, sender_name, callback_id = extract_update_info(update)
        
        assert chat_id == "456"
        assert text == "product:personal_credit"
        assert sender_name == "Test"
        assert callback_id == "cb_123"
    
    def test_extract_empty_update(self):
        """Test extracting info from empty update."""
        update = {}
        
        chat_id, text, sender_name, callback_id = extract_update_info(update)
        
        assert chat_id is None
        assert text is None


class TestGetMessageId:
    """Test getting message ID."""
    
    def test_get_message_id_from_message(self):
        """Test getting ID from regular message."""
        update = {
            "message": {"message_id": 42, "text": "Hello"}
        }
        assert get_message_id(update) == 42
    
    def test_get_message_id_from_callback(self):
        """Test getting ID from callback query."""
        update = {
            "callback_query": {
                "message": {"message_id": 43, "chat": {"id": 123}}
            }
        }
        assert get_message_id(update) == 43
    
    def test_get_message_id_none(self):
        """Test getting ID from empty update."""
        assert get_message_id({}) is None


class TestVoiceMessage:
    """Test voice message detection."""
    
    def test_is_voice_message_true(self):
        """Test detecting voice message."""
        update = {
            "message": {
                "message_id": 1,
                "voice": {"file_id": "voice_123", "duration": 10}
            }
        }
        assert is_voice_message(update) is True
    
    def test_is_voice_message_false(self):
        """Test detecting non-voice message."""
        update = {
            "message": {"message_id": 1, "text": "Hello"}
        }
        assert is_voice_message(update) is False
    
    def test_get_voice_file_id(self):
        """Test getting voice file ID."""
        update = {
            "message": {
                "voice": {"file_id": "voice_123", "duration": 10}
            }
        }
        assert get_voice_file_id(update) == "voice_123"
    
    def test_get_file_url(self):
        """Test generating file URL."""
        url = get_file_url("test_token", "path/to/file.ogg")
        assert "api.telegram.org" in url
        assert "test_token" in url
        assert "path/to/file.ogg" in url


class TestTelegramClient:
    """Test TelegramClient class."""
    
    def test_client_init(self):
        """Test client initialization."""
        client = TelegramClient("test_token")
        assert client.token == "test_token"
        assert "test_token" in client.base_url
    
    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending message."""
        client = TelegramClient("test_token")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={"ok": True, "result": {"message_id": 1}}),
                raise_for_status=MagicMock()
            )
            
            result = await client.send_message("123", "Hello", parse_mode="Markdown")
            
            assert mock_post.called
            call_args = mock_post.call_args
            assert "sendMessage" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_set_webhook(self):
        """Test setting webhook."""
        client = TelegramClient("test_token")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={"ok": True, "result": True}),
                raise_for_status=MagicMock()
            )
            
            result = await client.set_webhook("https://example.com/webhook", "secret")
            
            assert mock_post.called
            call_args = mock_post.call_args
            assert "setWebhook" in call_args[0][0]
