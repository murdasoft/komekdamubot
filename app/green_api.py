"""
Green API (WhatsApp) client.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GreenApiClient:
    def __init__(self, instance_id: str, token: str):
        self.instance_id = instance_id
        self.token = token
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def send_message(self, phone: str, message: str) -> dict[str, Any] | None:
        """Send text message to WhatsApp number."""
        url = f"{self.base_url}/sendMessage/{self.token}"
        # Normalize phone
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        payload = {
            "chatId": f"{phone_clean}@c.us",
            "message": message,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload, headers=self._auth())
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.exception("Green API send error: %s", e)
            return None

    async def send_buttons(self, phone: str, message: str, buttons: list[dict]) -> dict[str, Any] | None:
        """Send message with reply buttons (template buttons)."""
        url = f"{self.base_url}/sendTemplateButtons/{self.token}"
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        payload = {
            "chatId": f"{phone_clean}@c.us",
            "message": message,
            "templateButtons": buttons,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload, headers=self._auth())
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.exception("Green API buttons error: %s", e)
            return None

    async def download_file(self, url: str) -> bytes | None:
        """Download media file by URL from webhook."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.content
        except Exception as e:
            logger.exception("Green API download error: %s", e)
            return None


# Helpers to extract info from Green API webhook body
def extract_green_info(body: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract (chat_id, text, sender_name, media_url) from Green API webhook.
    Returns chat_id as phone number without @c.us.
    """
    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "").replace("@c.us", "").replace("@g.us", "")
    sender_name = sender_data.get("senderName") or sender_data.get("chatName")
    
    message_data = body.get("messageData", {})
    text = None
    media_url = None
    
    if message_data.get("typeMessage") == "extendedTextMessage":
        text = message_data.get("extendedTextMessageData", {}).get("text", "")
    elif message_data.get("typeMessage") == "textMessage":
        text = message_data.get("textMessageData", {}).get("text", "")
    elif message_data.get("typeMessage") == "voiceMessage":
        # Voice message - return download URL
        media_url = message_data.get("downloadUrl")
        text = "[голосовое сообщение]"
    
    return chat_id, text, sender_name, media_url


def is_voice_message(body: dict[str, Any]) -> bool:
    return body.get("messageData", {}).get("typeMessage") == "voiceMessage"
