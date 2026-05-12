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
from app.groq_client import GroqClient
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
groq_client: Optional[GroqClient] = None
tg_client: Optional[TelegramClient] = None
wa_client: Optional[GreenApiClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global groq_client, tg_client, wa_client
    
    settings = get_settings()
    
    # Initialize Groq
    if settings.is_groq_configured:
        groq_client = GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            stt_model=settings.groq_stt_model,
        )
        logger.info("Groq client initialized")
    else:
        logger.warning("Groq API key not configured")
    
    # Initialize Telegram
    if settings.is_telegram_configured:
        tg_client = TelegramClient(settings.telegram_bot_token)
        logger.info("Telegram client initialized")
        
        # Set webhook
        if settings.webhook_base_url:
            result = await tg_client.set_webhook(
                settings.telegram_webhook_url,
                settings.telegram_webhook_secret
            )
            logger.info(f"Telegram webhook set: {result}")
    else:
        logger.warning("Telegram bot token not configured")
    
    # Initialize WhatsApp
    if settings.is_whatsapp_configured:
        wa_client = GreenApiClient(
            instance_id=settings.green_api_instance_id,
            token=settings.green_api_token,
        )
        logger.info("WhatsApp (Green API) client initialized")
    else:
        logger.warning("Green API credentials not configured")
    
    yield
    
    # Cleanup
    if tg_client:
        await tg_client.delete_webhook()
        logger.info("Telegram webhook deleted")


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
        "groq_configured": settings.is_groq_configured,
        "bitrix_configured": bool(settings.bitrix24_webhook_url),
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=None),
):
    """Handle Telegram webhook updates."""
    settings = get_settings()
    
    # Verify secret token (optional security)
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid secret")
    
    if not tg_client:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    
    body = await request.json()
    logger.debug(f"Telegram update: {body}")
    
    try:
        await handle_telegram_update(body, tg_client, groq_client)
    except Exception as e:
        logger.exception("Error handling Telegram update")
        # Still return 200 to avoid retries
    
    return Response(status_code=200)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_webhook_token: str = Header(default=""),
):
    """Handle WhatsApp (Green API) webhook updates."""
    settings = get_settings()
    
    # Verify webhook token
    if settings.green_api_webhook_token:
        if x_webhook_token != settings.green_api_webhook_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
    
    if not wa_client:
        raise HTTPException(status_code=503, detail="WhatsApp not configured")
    
    body = await request.json()
    logger.debug(f"WhatsApp update: {body}")
    
    # Green API sends different event types
    # We only care about incoming messages
    msg_type = body.get("typeWebhook", "")
    
    if msg_type not in ["incomingMessageReceived", "incomingMessageText", "incomingMessageVoice"]:
        return Response(status_code=200)
    
    try:
        await handle_whatsapp_update(body, wa_client, groq_client)
    except Exception as e:
        logger.exception("Error handling WhatsApp update")
    
    return Response(status_code=200)


@app.get("/setup")
async def setup_webhooks():
    """Manually setup webhooks (useful for testing)."""
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
