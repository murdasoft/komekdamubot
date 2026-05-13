"""
Rate limiter for Komek Damu Bot.
Prevents spam and abuse.
"""

from __future__ import annotations

import time
import logging
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory storage for rate limiting
_request_counts: Dict[str, list] = defaultdict(list)
_blocked_users: Dict[str, float] = {}

# Config
MAX_REQUESTS_PER_MINUTE = 20
MAX_REQUESTS_PER_HOUR = 100
BLOCK_DURATION_SECONDS = 300  # 5 minutes


def is_rate_limited(chat_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if user is rate limited.
    Returns (is_limited, reason)
    """
    now = time.time()
    
    # Check if user is blocked
    if chat_id in _blocked_users:
        if now < _blocked_users[chat_id]:
            remaining = int(_blocked_users[chat_id] - now)
            return True, f"Слишком много сообщений. Подождите {remaining} секунд."
        else:
            del _blocked_users[chat_id]
    
    # Clean old requests
    _request_counts[chat_id] = [
        t for t in _request_counts[chat_id] 
        if now - t < 3600  # Keep last hour
    ]
    
    # Add current request
    _request_counts[chat_id].append(now)
    
    # Check limits
    requests_last_minute = len([t for t in _request_counts[chat_id] if now - t < 60])
    requests_last_hour = len(_request_counts[chat_id])
    
    if requests_last_minute > MAX_REQUESTS_PER_MINUTE:
        _blocked_users[chat_id] = now + BLOCK_DURATION_SECONDS
        logger.warning(f"Rate limit exceeded for {chat_id}: {requests_last_minute}/min")
        return True, "Слишком много сообщений. Подождите 5 минут."
    
    if requests_last_hour > MAX_REQUESTS_PER_HOUR:
        _blocked_users[chat_id] = now + BLOCK_DURATION_SECONDS
        logger.warning(f"Hourly rate limit exceeded for {chat_id}: {requests_last_hour}/hour")
        return True, "Превышен лимит сообщений на час. Попробуйте позже."
    
    return False, None


def get_remaining_quota(chat_id: str) -> Dict[str, int]:
    """Get remaining request quota for user."""
    now = time.time()
    
    if chat_id not in _request_counts:
        return {
            "per_minute": MAX_REQUESTS_PER_MINUTE,
            "per_hour": MAX_REQUESTS_PER_HOUR
        }
    
    requests_last_minute = len([t for t in _request_counts[chat_id] if now - t < 60])
    requests_last_hour = len(_request_counts[chat_id])
    
    return {
        "per_minute": max(0, MAX_REQUESTS_PER_MINUTE - requests_last_minute),
        "per_hour": max(0, MAX_REQUESTS_PER_HOUR - requests_last_hour)
    }
