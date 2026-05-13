"""
Analytics and statistics for Komek Damu Bot.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.supabase_client import get_supabase

logger = logging.getLogger(__name__)


async def get_dashboard_stats() -> Dict[str, Any]:
    """Get stats for admin dashboard."""
    sb = get_supabase()
    
    if not sb:
        return {
            "error": "Database not available",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    try:
        # Today's stats
        today = datetime.utcnow().date()
        
        # Messages today
        messages_today = sb.table("messages").select("*", count="exact").gte(
            "created_at", today.isoformat()
        ).execute()
        
        # Leads today
        leads_today = sb.table("leads").select("*", count="exact").gte(
            "created_at", today.isoformat()
        ).execute()
        
        # Total active users
        active_users = sb.table("sessions").select("chat_id", count="exact").execute()
        
        # Leads by status
        leads_by_status = sb.table("leads").select("status").execute()
        status_counts = {}
        for lead in leads_by_status.data:
            status = lead.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "today": {
                "messages": messages_today.count if hasattr(messages_today, 'count') else 0,
                "leads": leads_today.count if hasattr(leads_today, 'count') else 0,
            },
            "total": {
                "active_users": active_users.count if hasattr(active_users, 'count') else 0,
            },
            "leads_by_status": status_counts,
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": str(e)}


async def get_recent_conversations(limit: int = 10) -> list:
    """Get recent conversations for review."""
    sb = get_supabase()
    
    if not sb:
        return []
    
    try:
        result = sb.table("messages").select("*").order(
            "created_at", desc=True
        ).limit(limit).execute()
        
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        return []


async def get_leads_report(days: int = 7) -> list:
    """Get leads report for last N days."""
    sb = get_supabase()
    
    if not sb:
        return []
    
    try:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        result = sb.table("leads").select("*").gte(
            "created_at", since
        ).order("created_at", desc=True).execute()
        
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get leads report: {e}")
        return []
