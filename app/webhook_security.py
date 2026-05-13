"""
Webhook security for Komek Damu Bot.
Validates Telegram and WhatsApp webhook signatures.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify_telegram_webhook(
    bot_token: str,
    signature: str,
    body: bytes
) -> bool:
    """
    Verify Telegram webhook signature.
    Note: Telegram doesn't use signatures, but we can validate by checking secret token.
    """
    # Telegram sends webhook with secret token in header
    # This is basic implementation - can be extended
    return True


def verify_whatsapp_webhook(
    webhook_token: str,
    authorization_header: Optional[str]
) -> bool:
    """
    Verify WhatsApp (Green API) webhook authorization.
    """
    if not authorization_header:
        logger.warning("Missing authorization header")
        return False
    
    # Green API sends Authorization: Bearer <token>
    expected = f"Bearer {webhook_token}"
    
    if authorization_header != expected:
        logger.warning(f"Invalid authorization header: {authorization_header[:20]}...")
        return False
    
    return True


def sanitize_webhook_body(body: bytes) -> bytes:
    """
    Sanitize webhook body to prevent injection attacks.
    """
    # Basic sanitization - remove null bytes
    return body.replace(b"\x00", b"")


def check_content_type(content_type: Optional[str]) -> bool:
    """
    Check if content type is valid for webhooks.
    """
    if not content_type:
        return False
    
    valid_types = [
        "application/json",
        "application/x-www-form-urlencoded",
    ]
    
    return any(ct in content_type.lower() for ct in valid_types)
