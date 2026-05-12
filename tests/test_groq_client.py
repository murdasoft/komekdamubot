"""
Tests for Groq API client module.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.groq_client import GroqClient, get_system_prompt


class TestGroqClientInit:
    """Test GroqClient initialization."""
    
    def test_init_with_defaults(self):
        """Test client initialization with default values."""
        client = GroqClient("test_key")
        
        assert client.api_key == "test_key"
        assert client.model == "llama3-70b-8192"
        assert client.stt_model == "whisper-large-v3"
        assert "Authorization" in client.headers
    
    def test_init_with_custom_values(self):
        """Test client initialization with custom values."""
        client = GroqClient("test_key", model="mixtral-8x7b", stt_model="whisper-v3-turbo")
        
        assert client.model == "mixtral-8x7b"
        assert client.stt_model == "whisper-v3-turbo"


class TestLanguageDetection:
    """Test language detection."""
    
    def test_detect_kazakh_by_chars(self):
        """Test detecting Kazakh by specific characters."""
        client = GroqClient("test_key")
        
        assert client.detect_language_simple("Сәлеметсіз") == "kk"
        assert client.detect_language_simple("Қазақстан") == "kk"
        assert client.detect_language_simple("әіңғү") == "kk"
    
    def test_detect_kazakh_by_words(self):
        """Test detecting Kazakh by common words."""
        client = GroqClient("test_key")
        
        assert client.detect_language_simple("сіз және мен") == "kk"
        assert client.detect_language_simple("біз қазақпыз") == "kk"
    
    def test_detect_russian_default(self):
        """Test Russian is default."""
        client = GroqClient("test_key")
        
        assert client.detect_language_simple("Привет мир") == "ru"
        assert client.detect_language_simple("hello world") == "ru"


class TestSystemPrompt:
    """Test system prompts."""
    
    def test_system_prompt_ru(self):
        """Test Russian system prompt."""
        prompt = get_system_prompt("ru")
        
        assert "KOMEK DAMU" in prompt
        assert "кредит" in prompt.lower()
    
    def test_system_prompt_kk(self):
        """Test Kazakh system prompt."""
        prompt = get_system_prompt("kk")
        
        assert "KOMEK DAMU" in prompt
        assert "несие" in prompt.lower()
    
    def test_system_prompt_default(self):
        """Test default system prompt."""
        prompt = get_system_prompt("unknown")
        
        assert "KOMEK DAMU" in prompt


class TestChatMock:
    """Test chat completion with mocks."""
    
    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Test successful chat completion."""
        client = GroqClient("test_key")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={
                    "choices": [{"message": {"content": "Test response"}}]
                }),
                raise_for_status=MagicMock()
            )
            
            messages = [{"role": "user", "content": "Hello"}]
            response, error = await client.chat(messages)
            
            assert response == "Test response"
            assert error is None
    
    @pytest.mark.asyncio
    async def test_chat_error(self):
        """Test chat completion with error."""
        client = GroqClient("test_key")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=429,
                text="Rate limit exceeded",
                raise_for_status=MagicMock(side_effect=Exception("HTTP Error"))
            )
            
            messages = [{"role": "user", "content": "Hello"}]
            response, error = await client.chat(messages)
            
            assert response is None
            assert error is not None


class TestTranscribeMock:
    """Test STT transcription with mocks."""
    
    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        """Test successful transcription."""
        client = GroqClient("test_key")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={"text": "Hello world"}),
                raise_for_status=MagicMock()
            )
            
            audio_bytes = b"fake_audio_data"
            text, error = await client.transcribe(audio_bytes, language="ru")
            
            assert text == "Hello world"
            assert error is None
    
    @pytest.mark.asyncio
    async def test_transcribe_auto_language(self):
        """Test transcription with auto language detection."""
        client = GroqClient("test_key")
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                json=AsyncMock(return_value={"text": "Привет мир"}),
                raise_for_status=MagicMock()
            )
            
            audio_bytes = b"fake_audio_data"
            text, error = await client.transcribe(audio_bytes, language=None)
            
            assert text == "Привет мир"
