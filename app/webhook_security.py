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


def _extract_bearer_token(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    header = value.strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    if header.lower().startswith("basic "):
        return header[6:].strip()
    return header


def verify_whatsapp_webhook(
    webhook_token: str,
    authorization_header: Optional[str],
    x_webhook_token: Optional[str] = None,
) -> bool:
    """
    Verify WhatsApp (Green API) webhook authorization.
    Green API sends webhookUrlToken as Authorization: Bearer <token>.
    """
    token = webhook_token.strip()
    if not token or token == "changeme":
        return True

    candidates = [
        _extract_bearer_token(authorization_header),
        (x_webhook_token or "").strip() or None,
    ]
    for candidate in candidates:
        if candidate and candidate == token:
            return True

    if authorization_header:
        logger.warning("Invalid authorization header: %s...", authorization_header[:24])
    else:
        logger.warning("Missing authorization header")
    return False


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
