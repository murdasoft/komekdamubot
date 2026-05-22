"""
Green API (WhatsApp) client.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# WhatsApp voice notes приходят как audioMessage + fileMessageData
AUDIO_MESSAGE_TYPES = frozenset({"audioMessage", "voiceMessage"})


class GreenApiClient:
    def __init__(self, instance_id: str, token: str, api_url: str = "https://7107.api.greenapi.com"):
        self.instance_id = instance_id
        self.token = token
        root = api_url.rstrip("/")
        self.base_url = f"{root}/waInstance{instance_id}"

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def send_message(self, phone: str, message: str) -> dict[str, Any] | None:
        """Send text message to WhatsApp number."""
        from app.bot.outbound import adapt_message_for_platform

        message = adapt_message_for_platform(message, "whatsapp")
        url = f"{self.base_url}/sendMessage/{self.token}"
        phone_clean = phone.replace("+", "").replace(" ", "").replace("-", "")
        chat_id = f"{phone_clean}@c.us"
        payload = {
            "chatId": chat_id,
            "message": message,
        }
        logger.info(f"Sending WhatsApp message to: {chat_id}")
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
        """Download media by URL from webhook."""
        if not url:
            return None
        try:
            async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
                r = await client.get(url, headers=self._auth())
                r.raise_for_status()
                if r.content:
                    return r.content
        except Exception as e:
            logger.warning("Green API direct download failed: %s", e)
        return None

    async def download_incoming_file(
        self,
        chat_id: str,
        id_message: str,
        download_url: str | None = None,
    ) -> bytes | None:
        """Скачать входящий файл: URL из вебхука или downloadFile API."""
        if download_url:
            data = await self.download_file(download_url)
            if data:
                return data

        if not id_message:
            return None

        phone_clean = chat_id.replace("@c.us", "").replace("@g.us", "")
        wa_chat = chat_id if "@" in chat_id else f"{phone_clean}@c.us"
        api_url = f"{self.base_url}/downloadFile/{self.token}"
        payload = {"chatId": wa_chat, "idMessage": id_message}
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.post(
                    api_url, json=payload, headers=self._auth()
                )
                r.raise_for_status()
                fresh_url = (r.json() or {}).get("downloadUrl")
                if fresh_url:
                    return await self.download_file(fresh_url)
        except Exception as e:
            logger.exception("Green API downloadFile failed: %s", e)
        return None


def _message_data(body: dict[str, Any]) -> dict[str, Any]:
    return body.get("messageData") or {}


def _file_message_data(body: dict[str, Any]) -> dict[str, Any]:
    md = _message_data(body)
    return (
        md.get("fileMessageData")
        or md.get("voiceMessageData")
        or md.get("audioMessageData")
        or {}
    )


def get_audio_filename(body: dict[str, Any]) -> str:
    fmd = _file_message_data(body)
    name = (fmd.get("fileName") or "").strip()
    if name:
        return name
    mime = (fmd.get("mimeType") or "").lower()
    if "ogg" in mime:
        return "voice.ogg"
    if "mpeg" in mime or "mp3" in mime:
        return "voice.mp3"
    return "voice.ogg"


def extract_media_download_url(body: dict[str, Any]) -> str | None:
    fmd = _file_message_data(body)
    url = fmd.get("downloadUrl")
    if url:
        return url
    return _message_data(body).get("downloadUrl")


def extract_green_info(body: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Extract (chat_id, text, sender_name, media_url) from Green API webhook.
    """
    sender_data = body.get("senderData", {})
    chat_id = sender_data.get("chatId", "").replace("@c.us", "").replace("@g.us", "")
    sender_name = sender_data.get("senderName") or sender_data.get("chatName")

    md = _message_data(body)
    type_message = md.get("typeMessage", "")
    text = None
    media_url = None

    if type_message == "extendedTextMessage":
        text = md.get("extendedTextMessageData", {}).get("text", "")
    elif type_message == "textMessage":
        text = md.get("textMessageData", {}).get("text", "")
    elif type_message in AUDIO_MESSAGE_TYPES:
        media_url = extract_media_download_url(body)
        # text остаётся None — обработчик распознаёт голос отдельно

    return chat_id, text, sender_name, media_url


def is_voice_message(body: dict[str, Any]) -> bool:
    return _message_data(body).get("typeMessage") in AUDIO_MESSAGE_TYPES
