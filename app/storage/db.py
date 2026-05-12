"""
Simple storage for KOMEK DAMU bot sessions.
Uses in-memory dict for MVP; upgrade to Redis/DB for production.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory storage
_sessions: Dict[str, Dict[str, Any]] = {}
_messages: Dict[str, list] = defaultdict(list)  # chat_id -> list of messages


class SessionStore:
    """Simple session storage."""
    
    async def get_session(self, chat_id: str) -> Dict[str, Any]:
        """Get or create session for chat."""
        if chat_id not in _sessions:
            _sessions[chat_id] = {
                "state": "idle",
                "lang": "ru",
                "product": None,
                "flow_step": None,
                "data": {},
                "contact_name": None,
                "created_at": None,
                "last_activity": None,
            }
        return _sessions[chat_id]
    
    async def save_session(self, chat_id: str, data: Dict[str, Any]):
        """Save session data."""
        _sessions[chat_id] = data
    
    async def log_message(self, chat_id: str, direction: str, text: str, meta: Optional[Dict] = None):
        """Log message to history."""
        import time
        entry = {
            "timestamp": time.time(),
            "direction": direction,  # 'in' or 'out'
            "text": text,
            "meta": meta or {},
        }
        _messages[chat_id].append(entry)
        # Keep only last 50 messages
        if len(_messages[chat_id]) > 50:
            _messages[chat_id] = _messages[chat_id][-50:]
    
    async def get_recent_messages(self, chat_id: str, limit: int = 5) -> list:
        """Get recent message history."""
        return _messages[chat_id][-limit:]
    
    async def clear_session(self, chat_id: str):
        """Clear session data."""
        if chat_id in _sessions:
            del _sessions[chat_id]


# Global instance
store = SessionStore()
