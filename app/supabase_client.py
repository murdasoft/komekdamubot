"""
Supabase client for Komek Damu Bot.
Stores sessions, conversation logs, and analytics.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from supabase import create_client, Client
except ImportError:
    Client = None
    create_client = None

logger = logging.getLogger(__name__)

# Global client
_supabase: Optional[Client] = None


def get_supabase() -> Optional[Client]:
    """Get or create Supabase client."""
    global _supabase
    
    if _supabase is not None:
        return _supabase
    
    if Client is None:
        logger.warning("Supabase not installed, using memory storage")
        return None
    
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        logger.warning("Supabase credentials not found, using memory storage")
        return None
    
    try:
        _supabase = create_client(url, key)
        logger.info("Supabase client initialized")
        return _supabase
    except Exception as e:
        logger.error(f"Failed to initialize Supabase: {e}")
        return None


async def save_session(chat_id: str, session_data: Dict[str, Any]) -> bool:
    """Save user session to database."""
    sb = get_supabase()
    if not sb:
        return False
    
    try:
        data = {
            "chat_id": chat_id,
            "platform": session_data.get("platform", "telegram"),
            "lang": session_data.get("lang", "ru"),
            "state": session_data.get("state", "idle"),
            "product": session_data.get("product"),
            "data": json.dumps(session_data.get("data", {})),
            "conversation_history": json.dumps(session_data.get("conversation_history", [])),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        sb.table("sessions").upsert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save session: {e}")
        return False


async def load_session(chat_id: str) -> Optional[Dict[str, Any]]:
    """Load user session from database."""
    sb = get_supabase()
    if not sb:
        return None
    
    try:
        result = sb.table("sessions").select("*").eq("chat_id", chat_id).execute()
        if result.data:
            row = result.data[0]
            return {
                "platform": row.get("platform", "telegram"),
                "lang": row.get("lang", "ru"),
                "state": row.get("state", "idle"),
                "product": row.get("product"),
                "data": json.loads(row.get("data", "{}")),
                "conversation_history": json.loads(row.get("conversation_history", "[]")),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to load session: {e}")
        return None


async def log_message(chat_id: str, platform: str, role: str, text: str, lang: str = "ru") -> bool:
    """Log message to conversation history."""
    sb = get_supabase()
    if not sb:
        return False
    
    try:
        data = {
            "chat_id": chat_id,
            "platform": platform,
            "role": role,  # 'user' or 'assistant'
            "text": text,
            "lang": lang,
            "created_at": datetime.utcnow().isoformat(),
        }
        sb.table("messages").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to log message: {e}")
        return False


async def create_lead(chat_id: str, platform: str, product: str, data: Dict, lang: str = "ru") -> bool:
    """Create lead in database."""
    sb = get_supabase()
    if not sb:
        return False
    
    try:
        lead_data = {
            "chat_id": chat_id,
            "platform": platform,
            "product": product,
            "lang": lang,
            "data": json.dumps(data),
            "status": "new",
            "created_at": datetime.utcnow().isoformat(),
        }
        sb.table("leads").insert(lead_data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to create lead: {e}")
        return False


async def get_stats(days: int = 7) -> Dict[str, Any]:
    """Get bot usage statistics."""
    sb = get_supabase()
    if not sb:
        return {}
    
    try:
        # Total messages
        messages_result = sb.table("messages").select("*", count="exact").gte(
            "created_at", (datetime.utcnow().replace(day=datetime.utcnow().day - days)).isoformat()
        ).execute()
        
        # Total leads
        leads_result = sb.table("leads").select("*", count="exact").execute()
        
        # Active users
        users_result = sb.table("sessions").select("chat_id", count="exact").execute()
        
        return {
            "total_messages": messages_result.count if hasattr(messages_result, 'count') else 0,
            "total_leads": leads_result.count if hasattr(leads_result, 'count') else 0,
            "active_users": users_result.count if hasattr(users_result, 'count') else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}
