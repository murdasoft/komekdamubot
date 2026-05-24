"""
Supabase client for Komek Damu Bot.
Stores clients, sessions, conversation logs, and leads.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from supabase import Client, create_client
except ImportError:
    Client = None  # type: ignore[misc, assignment]
    create_client = None  # type: ignore[misc, assignment]

from app.bot.content import DEFAULT_LANG

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None

SESSION_PERSIST_KEYS = (
    "state",
    "lang",
    "lang_locked",
    "product",
    "flow_step",
    "data",
    "last_message_id",
    "contact_name",
    "handoff_until",
    "conversation_history",
    "context_topic",
    "message_count",
    "platform",
    "city",
    "city_confirmed",
    "submenu",
    "last_intent",
    "awaiting_borrower_type",
)


def _first_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def get_supabase_url() -> str:
    return _first_env(
        "SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_URL",
        "NEXT_PUBLIC_komek_SUPABASE_URL",
    )


def get_supabase_service_key() -> str:
    return _first_env(
        "SUPABASE_SERVICE_ROLE_KEY",
        "komek_SUPABASE_SERVICE_ROLE_KEY",
    )


def get_supabase() -> Optional[Client]:
    """Get or create Supabase client (service role for server-side writes)."""
    global _supabase

    if _supabase is not None:
        return _supabase

    if Client is None or create_client is None:
        logger.warning("Supabase package not installed, using memory storage")
        return None

    url = get_supabase_url()
    key = get_supabase_service_key()

    if not url or not key:
        logger.warning("Supabase credentials not found, using memory storage")
        return None

    try:
        _supabase = create_client(url, key)
        logger.info("Supabase client initialized: %s", url)
        return _supabase
    except Exception as e:
        logger.error("Failed to initialize Supabase: %s", e)
        return None


def is_supabase_configured() -> bool:
    return bool(get_supabase_url() and get_supabase_service_key())


def _normalize_platform(platform: str | None) -> str:
    p = (platform or "telegram").strip().lower()
    if p in ("tg", "telegram"):
        return "telegram"
    if p in ("wa", "whatsapp"):
        return "whatsapp"
    return p or "telegram"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_field(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _session_snapshot(session_data: dict[str, Any]) -> dict[str, Any]:
    return {k: session_data[k] for k in SESSION_PERSIST_KEYS if k in session_data}


def _row_to_session(row: dict[str, Any]) -> dict[str, Any]:
    session = _session_snapshot(_json_field(row.get("session_json"), {}))
    session.update(
        {
            "platform": _normalize_platform(row.get("platform")),
            "lang": row.get("lang") or DEFAULT_LANG,
            "lang_locked": bool(row.get("lang_locked", False)),
            "state": row.get("state") or "idle",
            "product": row.get("product"),
            "contact_name": row.get("contact_name"),
            "city": row.get("city"),
            "city_confirmed": bool(row.get("city_confirmed", False)),
            "context_topic": row.get("context_topic"),
            "flow_step": row.get("flow_step"),
            "handoff_until": row.get("handoff_until") or 0,
            "submenu": row.get("submenu"),
            "data": _json_field(row.get("data"), {}),
            "conversation_history": _json_field(row.get("conversation_history"), []),
        }
    )
    # session_json wins for keys stored only there
    extra = _json_field(row.get("session_json"), {})
    for key, value in extra.items():
        if key not in session or session.get(key) in (None, {}, []):
            session[key] = value
    return session


async def upsert_client(chat_id: str, session_data: dict[str, Any]) -> bool:
    sb = get_supabase()
    if not sb:
        return False

    platform = _normalize_platform(session_data.get("platform"))
    phone = chat_id if platform == "whatsapp" and chat_id.isdigit() else session_data.get("phone")

    row = {
        "chat_id": chat_id,
        "platform": platform,
        "contact_name": session_data.get("contact_name"),
        "phone": phone,
        "city": session_data.get("city"),
        "city_confirmed": bool(session_data.get("city_confirmed", False)),
        "lang": session_data.get("lang") or DEFAULT_LANG,
        "lang_locked": bool(session_data.get("lang_locked", False)),
        "last_product": session_data.get("product"),
        "last_state": session_data.get("state") or "idle",
        "context_topic": session_data.get("context_topic"),
        "metadata": {
            "message_count": session_data.get("message_count", 0),
            "handoff_until": session_data.get("handoff_until", 0),
            "flow_step": session_data.get("flow_step"),
            "submenu": session_data.get("submenu"),
            "data": session_data.get("data", {}),
        },
        "last_seen_at": _utc_now(),
        "updated_at": _utc_now(),
    }

    try:
        sb.table("clients").upsert(row, on_conflict="chat_id").execute()
        return True
    except Exception as e:
        logger.error("Failed to upsert client chat=%s: %s", chat_id, e)
        return False


async def save_session(chat_id: str, session_data: dict[str, Any]) -> bool:
    """Save full user session + client profile."""
    sb = get_supabase()
    if not sb:
        return False

    platform = _normalize_platform(session_data.get("platform"))
    snapshot = _session_snapshot(session_data)
    snapshot["platform"] = platform

    row = {
        "chat_id": chat_id,
        "platform": platform,
        "lang": session_data.get("lang") or DEFAULT_LANG,
        "lang_locked": bool(session_data.get("lang_locked", False)),
        "state": session_data.get("state") or "idle",
        "product": session_data.get("product"),
        "contact_name": session_data.get("contact_name"),
        "city": session_data.get("city"),
        "city_confirmed": bool(session_data.get("city_confirmed", False)),
        "context_topic": session_data.get("context_topic"),
        "flow_step": session_data.get("flow_step"),
        "handoff_until": session_data.get("handoff_until") or 0,
        "submenu": session_data.get("submenu"),
        "data": session_data.get("data") or {},
        "conversation_history": session_data.get("conversation_history") or [],
        "session_json": snapshot,
        "updated_at": _utc_now(),
    }

    try:
        sb.table("sessions").upsert(row, on_conflict="chat_id").execute()
        await upsert_client(chat_id, session_data)
        return True
    except Exception as e:
        logger.error("Failed to save session chat=%s: %s", chat_id, e)
        return False


async def load_session(chat_id: str) -> Optional[dict[str, Any]]:
    """Load user session from database."""
    sb = get_supabase()
    if not sb:
        return None

    try:
        result = sb.table("sessions").select("*").eq("chat_id", chat_id).execute()
        if result.data:
            return _row_to_session(result.data[0])
        return None
    except Exception as e:
        logger.error("Failed to load session chat=%s: %s", chat_id, e)
        return None


async def log_message(
    chat_id: str,
    platform: str,
    role: str,
    text: str,
    lang: str = DEFAULT_LANG,
) -> bool:
    """Log message to conversation history."""
    sb = get_supabase()
    if not sb:
        return False

    try:
        data = {
            "chat_id": chat_id,
            "platform": _normalize_platform(platform),
            "role": role,
            "text": text[:8000],
            "lang": lang or DEFAULT_LANG,
            "created_at": _utc_now(),
        }
        sb.table("messages").insert(data).execute()
        return True
    except Exception as e:
        logger.error("Failed to log message chat=%s: %s", chat_id, e)
        return False


async def create_lead(
    chat_id: str,
    platform: str,
    product: str,
    data: dict[str, Any],
    lang: str = DEFAULT_LANG,
) -> bool:
    """Create lead in database."""
    sb = get_supabase()
    if not sb:
        return False

    try:
        lead_data = {
            "chat_id": chat_id,
            "platform": _normalize_platform(platform),
            "product": product,
            "lang": lang or DEFAULT_LANG,
            "data": data or {},
            "status": "new",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        sb.table("leads").insert(lead_data).execute()
        return True
    except Exception as e:
        logger.error("Failed to create lead chat=%s: %s", chat_id, e)
        return False


async def get_client(chat_id: str) -> Optional[dict[str, Any]]:
    sb = get_supabase()
    if not sb:
        return None
    try:
        result = sb.table("clients").select("*").eq("chat_id", chat_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to get client chat=%s: %s", chat_id, e)
        return None


async def get_stats(days: int = 7) -> dict[str, Any]:
    """Get bot usage statistics."""
    sb = get_supabase()
    if not sb:
        return {}

    try:
        since = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        _ = since  # placeholder if date filter added later
        messages_result = sb.table("messages").select("id", count="exact").execute()
        leads_result = sb.table("leads").select("id", count="exact").execute()
        users_result = sb.table("clients").select("chat_id", count="exact").execute()

        return {
            "total_messages": getattr(messages_result, "count", 0) or 0,
            "total_leads": getattr(leads_result, "count", 0) or 0,
            "active_users": getattr(users_result, "count", 0) or 0,
            "days": days,
        }
    except Exception as e:
        logger.error("Failed to get stats: %s", e)
        return {}
