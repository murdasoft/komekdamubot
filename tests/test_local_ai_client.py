"""Tests for LocalAIClient."""

import pytest
from unittest.mock import AsyncMock, patch

from app.local_ai_client import LocalAIClient
from app.ai_utils import detect_language_simple


class TestDetectLanguage:
    def test_russian(self):
        assert detect_language_simple("Привет, нужен кредит") == "ru"

    def test_kazakh_chars(self):
        assert detect_language_simple("Сәлеметсіз бе") == "kk"


class TestLocalAIClient:
    @pytest.mark.asyncio
    async def test_chat_success(self):
        client = LocalAIClient(
            "http://localhost:11434",
            "qwen2.5:3b",
            "http://localhost:11435",
        )
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: {"message": {"content": "  Ответ  "}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            text, err = await client.chat([{"role": "user", "content": "test"}])
            assert text == "Ответ"
            assert err is None
