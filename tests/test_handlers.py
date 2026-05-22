"""
Tests for handlers module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bot.handlers import _detect_language, _build_summary, _reset_session


class TestLanguageDetection:
    """Test language detection."""
    
    def test_detect_kazakh_by_chars(self):
        """Test detecting Kazakh by specific characters."""
        assert _detect_language("Сәлеметсіз бе") == "kk"
        assert _detect_language("Қазақ тілі") == "kk"
        assert _detect_language("несие керек") == "kk"  # kk word, not ambiguous alone
    
    def test_detect_kazakh_by_words(self):
        """Test detecting Kazakh by common words."""
        assert _detect_language("сіз қалайсыз") == "kk"
        assert _detect_language("біз қазақпыз") == "kk"
    
    def test_detect_russian(self):
        """Test detecting Russian."""
        assert _detect_language("Привет, как дела") == "ru"
        assert _detect_language("Нужен кредит") == "ru"
        assert _detect_language("ипотека") == "ru"
    
    def test_detect_russian_default(self):
        """Test Russian is default for unknown text."""
        assert _detect_language("hello world") == "ru"
        assert _detect_language("12345") == "ru"


class TestSummaryBuilder:
    """Test summary builder."""
    
    def test_build_summary_ru(self):
        """Test building summary in Russian."""
        data = {
            "city": "Алматы",
            "phone": "77001234567",
            "amount": "5000000",
        }
        summary = _build_summary(data, "personal_credit", "ru")
        
        assert "Новая заявка" in summary
        assert "Кредит для физического лица" in summary
        assert "Алматы" in summary
        assert "77001234567" in summary
    
    def test_build_summary_kk(self):
        """Test building summary in Kazakh."""
        data = {
            "city": "Алматы",
            "phone": "77001234567",
        }
        summary = _build_summary(data, "damu", "kk")
        
        assert "Жаңа өтініш" in summary
        assert "Қазақша" in summary
    
    def test_build_summary_with_empty_data(self):
        """Test building summary with minimal data."""
        summary = _build_summary({}, "business_credit", "ru")
        
        assert "Новая заявка" in summary
        assert "Кредит для бизнеса" in summary


class TestSessionManagement:
    """Test session management."""
    
    def test_reset_session(self):
        """Test session reset."""
        _reset_session("test_chat_123", "telegram")
        
        from app.bot.handlers import _get_session
        session = _get_session("test_chat_123")
        
        assert session["state"] == "idle"
        assert session["lang"] == "ru"
        assert session["product"] is None
        assert session["platform"] == "telegram"
    
    def test_reset_session_whatsapp(self):
        """Test session reset for WhatsApp."""
        _reset_session("77001234567", "whatsapp")
        
        from app.bot.handlers import _get_session
        session = _get_session("77001234567")
        
        assert session["platform"] == "whatsapp"


class TestTelegramHandlers:
    """Test Telegram-specific handlers."""
    
    @pytest.mark.asyncio
    async def test_handle_start_command(self, sample_telegram_update, mock_env_vars):
        """Test handling /start command."""
        from app.bot.handlers import handle_telegram_update
        
        update = sample_telegram_update
        update["message"]["text"] = "/start"
        
        mock_tg = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_telegram_update(update, mock_tg, mock_groq)
        
        # Should send greeting with menu
        assert mock_tg.send_message.called
        call_args = mock_tg.send_message.call_args
        assert "KOMEK DAMU" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_handle_operator_request(self, sample_telegram_update, mock_env_vars):
        """Test handling operator request."""
        from app.bot.handlers import handle_telegram_update
        
        update = sample_telegram_update
        update["message"]["text"] = "оператор"
        
        mock_tg = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_telegram_update(update, mock_tg, mock_groq)
        
        # Should send operator message
        assert mock_tg.send_message.called
        call_args = mock_tg.send_message.call_args
        assert "менеджер" in call_args[0][1].lower() or "менеджеру" in call_args[0][1].lower()
    
    @pytest.mark.asyncio
    async def test_handle_product_callback(self, sample_telegram_callback, mock_env_vars):
        """Test handling product selection callback."""
        from app.bot.handlers import handle_telegram_update
        
        mock_tg = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_telegram_update(sample_telegram_callback, mock_tg, mock_groq)
        
        # Should answer callback and start product flow
        assert mock_tg.answer_callback_query.called
        assert mock_tg.send_message.called


class TestWhatsAppHandlers:
    """Test WhatsApp-specific handlers."""
    
    @pytest.mark.asyncio
    async def test_handle_wa_start(self, sample_whatsapp_update, mock_env_vars):
        """Test handling WhatsApp start command."""
        from app.bot.handlers import handle_whatsapp_update
        
        update = sample_whatsapp_update
        update["messageData"]["textMessageData"]["text"] = "/start"
        
        mock_wa = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_whatsapp_update(update, mock_wa, mock_groq)
        
        # Should send menu
        assert mock_wa.send_message.called
        call_args = mock_wa.send_message.call_args
        # Should contain menu options (digits 1-7)
        assert "1" in call_args[0][1]
    
    @pytest.mark.asyncio
    async def test_handle_wa_menu_digit(self, sample_whatsapp_update, mock_env_vars):
        """Test handling WhatsApp menu digit selection."""
        from app.bot.handlers import handle_whatsapp_update
        
        update = sample_whatsapp_update
        update["messageData"]["textMessageData"]["text"] = "1"
        
        mock_wa = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_whatsapp_update(update, mock_wa, mock_groq)
        
        # Should start personal credit flow
        assert mock_wa.send_message.called


class TestIntentHandling:
    """Test intent-based routing."""
    
    @pytest.mark.asyncio
    async def test_intent_detection_triggers_flow(self, sample_telegram_update, mock_env_vars):
        """Test that intent detection triggers product flow."""
        from app.bot.handlers import handle_telegram_update
        
        update = sample_telegram_update
        update["message"]["text"] = "нужен кредит на бизнес"
        
        mock_tg = AsyncMock()
        mock_groq = MagicMock()
        
        await handle_telegram_update(update, mock_tg, mock_groq)
        
        # Should start business credit flow with product info
        calls = mock_tg.send_message.call_args_list
        texts = [call[0][1] for call in calls]
        
        # Should contain business credit info
        assert any("бизнес" in text.lower() for text in texts)
