"""
FastAPI application for KOMEK DAMU Bot.
Handles webhooks for Telegram and WhatsApp (Green API).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, Response, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.ai_client import AIClient, create_ai_client
from app.telegram_api import TelegramClient
from app.green_api import GreenApiClient
from app.bot.handlers import handle_telegram_update, handle_whatsapp_update
from app.storage.db import store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global clients
ai_client: Optional[AIClient] = None
tg_client: Optional[TelegramClient] = None
wa_client: Optional[GreenApiClient] = None
_clients_ready = False


async def ensure_clients() -> None:
    """Lazy init for Vercel serverless (lifespan may be off)."""
    global ai_client, tg_client, wa_client, _clients_ready
    if _clients_ready:
        return
    settings = get_settings()
    ai_client = create_ai_client(settings)
    if settings.is_telegram_configured:
        tg_client = TelegramClient(settings.telegram_bot_token)
    if settings.is_whatsapp_configured:
        wa_client = GreenApiClient(
            instance_id=settings.green_api_instance_id,
            token=settings.green_api_token,
            api_url=settings.green_api_url,
        )
    _clients_ready = True
    logger.info(
        "Clients ready: ai=%s provider=%s tg=%s wa=%s",
        ai_client is not None,
        settings.effective_ai_provider,
        tg_client is not None,
        wa_client is not None,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global ai_client, tg_client, wa_client
    
    await ensure_clients()
    settings = get_settings()
    if settings.local_llm_base_url and settings.effective_ai_provider == "local":
        import httpx
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                await client.post(
                    f"{settings.local_llm_base_url.rstrip('/')}/api/chat",
                    json={
                        "model": settings.local_llm_model,
                        "messages": [{"role": "user", "content": "да"}],
                        "stream": False,
                        "keep_alive": settings.local_llm_keep_alive,
                        "options": {
                            "num_predict": 16,
                            "num_ctx": settings.local_llm_num_ctx,
                        },
                    },
                )
            logger.info("Ollama model warmed up")
        except Exception as e:
            logger.warning("Ollama warmup failed: %s", e)
    if tg_client and settings.webhook_base_url:
        result = await tg_client.set_webhook(
            settings.telegram_webhook_url,
            settings.telegram_webhook_secret,
        )
        logger.info("Telegram webhook set: %s", result)
    yield
    
    # Note: do NOT delete webhook on shutdown — Vercel serverless restarts frequently


app = FastAPI(
    title="KOMEK DAMU Bot",
    description="AI Chatbot for financial services - loans, mortgages, DAMU",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "ok",
        "telegram_configured": settings.is_telegram_configured,
        "whatsapp_configured": settings.is_whatsapp_configured,
        "ai_configured": settings.is_ai_configured,
        "ai_provider": settings.effective_ai_provider,
        "groq_configured": settings.is_groq_configured,
        "bitrix_configured": bool(settings.bitrix24_webhook_url),
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "ai": ai_client is not None,
        "ai_provider": get_settings().effective_ai_provider,
        "telegram": tg_client is not None,
        "whatsapp": wa_client is not None,
    }


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=None),
):
    """Handle Telegram webhook updates."""
    await ensure_clients()
    settings = get_settings()
    
    # Rate limiting check
    from app.rate_limiter import is_rate_limited
    is_limited, reason = is_rate_limited("telegram_webhook")
    if is_limited:
        logger.warning(f"Rate limit exceeded for Telegram webhook: {reason}")
        raise HTTPException(status_code=429, detail=reason)
    
    # Verify secret token (optional security)
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid secret")
    
    if not tg_client:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    body = await request.json()
    logger.debug(f"Telegram update: {body}")
    
    try:
        await handle_telegram_update(body, tg_client, ai_client)
    except Exception as e:
        logger.exception("Error handling Telegram update")
        # Still return 200 to avoid retries
    
    return Response(status_code=200)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    authorization: str = Header(default=""),
    x_webhook_token: str = Header(default=""),
):
    """Handle WhatsApp (Green API) webhook updates."""
    await ensure_clients()
    settings = get_settings()
    
    # Rate limiting check
    from app.rate_limiter import is_rate_limited
    is_limited, reason = is_rate_limited("whatsapp_webhook")
    if is_limited:
        logger.warning(f"Rate limit exceeded for WhatsApp webhook: {reason}")
        raise HTTPException(status_code=429, detail=reason)
    
    # Security: verify webhook token (Green API uses Authorization header)
    if settings.green_api_webhook_token:
        from app.webhook_security import verify_whatsapp_webhook
        if not verify_whatsapp_webhook(settings.green_api_webhook_token, authorization):
            logger.warning(f"Invalid authorization: {authorization[:20] if authorization else 'None'}...")
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not wa_client:
        raise HTTPException(status_code=503, detail="WhatsApp not configured")
    
    body = await request.json()
    logger.info(f"WhatsApp body: {body}")
    
    # Extract sender info for debugging
    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "unknown")
    sender_name = sender_data.get("senderName", "unknown")
    logger.info(f"Message from: {chat_id} ({sender_name})")
    
    # Green API sends different event types
    # We only care about incoming messages
    msg_type = body.get("typeWebhook", "")
    
    if msg_type not in ["incomingMessageReceived", "incomingMessageText", "incomingMessageVoice"]:
        return Response(status_code=200)
    
    try:
        await handle_whatsapp_update(body, wa_client, ai_client)
    except Exception as e:
        logger.exception("Error handling WhatsApp update")
    
    return Response(status_code=200)


@app.get("/admin/stats")
async def admin_stats():
    """Admin dashboard statistics."""
    from app.analytics import get_dashboard_stats
    stats = await get_dashboard_stats()
    return stats


@app.get("/admin/leads")
async def admin_leads(days: int = 7):
    """Get leads report."""
    from app.analytics import get_leads_report
    leads = await get_leads_report(days)
    return {"leads": leads, "count": len(leads)}


@app.get("/setup")
async def setup_webhooks():
    """Manually setup webhooks (useful for testing)."""
    await ensure_clients()
    settings = get_settings()
    results = {}
    
    if tg_client and settings.webhook_base_url:
        result = await tg_client.set_webhook(
            settings.telegram_webhook_url,
            settings.telegram_webhook_secret
        )
        results["telegram"] = result
    
    return {
        "telegram_webhook_url": settings.telegram_webhook_url if settings.is_telegram_configured else None,
        "whatsapp_webhook_url": settings.green_api_webhook_url if settings.is_whatsapp_configured else None,
        "results": results,
    }


@app.get("/debug/session/{chat_id}")
async def debug_session(chat_id: str):
    """Debug endpoint to view session (remove in production)."""
    session = await store.get_session(chat_id)
    messages = await store.get_recent_messages(chat_id, limit=10)
    return {
        "session": session,
        "recent_messages": messages,
    }


# Vercel handler
from mangum import Mangum
handler = Mangum(app)
