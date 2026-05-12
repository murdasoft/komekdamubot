"""
Tests for knowledge base module.
"""

import pytest
from app.bot.knowledge_base import (
    detect_intent, get_product_info, get_faq_answer,
    PRODUCTS, INTENT_KEYWORDS
)


class TestIntentDetection:
    """Test intent detection from user messages."""
    
    def test_detect_personal_credit_ru(self):
        """Test detecting personal credit intent in Russian."""
        assert detect_intent("нужен кредит для себя") == "personal_credit"
        assert detect_intent("хочу взять потребительский кредит") == "personal_credit"
        assert detect_intent("деньги наличными") == "personal_credit"
    
    def test_detect_business_credit_ru(self):
        """Test detecting business credit intent in Russian."""
        assert detect_intent("кредит на бизнес") == "business_credit"
        assert detect_intent("ТОО кредит") == "business_credit"
        assert detect_intent("ИП кредит") == "business_credit"
    
    def test_detect_damu_ru(self):
        """Test detecting DAMU program intent in Russian."""
        assert detect_intent("даму 12,6%") == "damu"
        assert detect_intent("программа damu") == "damu"
    
    def test_detect_mortgage_ru(self):
        """Test detecting mortgage intent in Russian."""
        assert detect_intent("ипотека") == "mortgage_standard"
        assert detect_intent("гос ипотека 2%") == "mortgage_gov"
        assert detect_intent("квартира в кредит") == "mortgage_standard"
    
    def test_detect_refinancing_ru(self):
        """Test detecting refinancing intent in Russian."""
        assert detect_intent("рефинансирование") == "refinancing"
        assert detect_intent("снизить ставку") == "refinancing"
    
    def test_detect_kazakh(self):
        """Test detecting intents in Kazakh."""
        assert detect_intent("жеке несие") == "personal_credit"
        assert detect_intent("бизнес несиесі") == "business_credit"
        assert detect_intent("ипотека") == "mortgage_standard"
    
    def test_no_intent_detected(self):
        """Test when no intent is detected."""
        assert detect_intent("привет") is None
        assert detect_intent("спасибо") is None
        assert detect_intent("") is None


class TestProductInfo:
    """Test product information retrieval."""
    
    def test_get_personal_credit_ru(self):
        """Test getting personal credit info in Russian."""
        info = get_product_info("personal_credit", "ru")
        
        assert info is not None
        assert info["name"] == "Кредит для физического лица"
        assert "Ставка" in info["conditions"]
        assert len(info["docs"]) > 0
    
    def test_get_personal_credit_kk(self):
        """Test getting personal credit info in Kazakh."""
        info = get_product_info("personal_credit", "kk")
        
        assert info is not None
        assert info["name"] == "Жеке несие"
        assert "Мөлшерлеме" in info["conditions"]
    
    def test_get_damu_info(self):
        """Test getting DAMU program info."""
        info = get_product_info("damu", "ru")
        
        assert info is not None
        assert "12,6%" in info["conditions"]
        assert info["name"] == "DAMU 12,6%"
    
    def test_invalid_product(self):
        """Test getting info for invalid product."""
        assert get_product_info("invalid_product", "ru") is None


class TestFAQ:
    """Test FAQ answers."""
    
    def test_faq_address_ru(self):
        """Test address FAQ in Russian."""
        answer = get_faq_answer("address", "ru")
        assert "Алматы" in answer
    
    def test_faq_address_kk(self):
        """Test address FAQ in Kazakh."""
        answer = get_faq_answer("address", "kk")
        assert "Алматы" in answer
    
    def test_faq_free_consultation(self):
        """Test free consultation FAQ."""
        answer = get_faq_answer("consultation_free", "ru")
        assert "бесплатная" in answer.lower()
    
    def test_faq_fallback_to_ru(self):
        """Test FAQ falls back to Russian for unknown language."""
        answer = get_faq_answer("address", "unknown_lang")
        assert "Алматы" in answer


class TestProductsStructure:
    """Test products data structure."""
    
    def test_all_products_have_required_fields(self):
        """Test all products have required fields."""
        required_fields = ["key", "name_ru", "name_kk", "description_ru", 
                          "description_kk", "conditions_ru", "conditions_kk"]
        
        for key, product in PRODUCTS.items():
            for field in required_fields:
                assert hasattr(product, field), f"Product {key} missing field {field}"
    
    def test_intent_keywords_structure(self):
        """Test intent keywords have both languages."""
        for intent, langs in INTENT_KEYWORDS.items():
            assert "ru" in langs, f"Intent {intent} missing Russian keywords"
            assert isinstance(langs["ru"], list)
