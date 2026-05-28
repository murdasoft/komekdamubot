"""
Green API (WhatsApp) client.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# WhatsApp voice notes приходят как audioMessage + fileMessageData
AUDIO_MESSAGE_TYPES = frozenset({"audioMessage", "voiceMessage", "pttMessage"})


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

    @staticmethod
    def normalize_chat_id(chat_id: str) -> str:
        """77001234567 → 77001234567@c.us"""
        c = (chat_id or "").strip()
        if "@" in c:
            return c
        phone = c.replace("+", "").replace(" ", "").replace("-", "")
        return f"{phone}@c.us"

    async def _fetch_media_bytes(self, url: str) -> bytes | None:
        """
        Скачать файл по ссылке Green API.
        Подписанные URL (do-media-*.digitaloceanspaces.com) — без Authorization.
        """
        if not url:
            return None
        min_size = 64
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            try:
                r = await client.get(url)
                if r.status_code == 200 and len(r.content) >= min_size:
                    return r.content
                logger.warning(
                    "Media GET %s status=%s len=%s",
                    url[:60],
                    r.status_code,
                    len(r.content),
                )
            except Exception as e:
                logger.warning("Media GET plain failed: %s", e)
            try:
                r = await client.get(url, headers=self._auth())
                if r.status_code == 200 and len(r.content) >= min_size:
                    return r.content
            except Exception as e:
                logger.warning("Media GET with Bearer failed: %s", e)
        return None

    async def resolve_download_url(self, chat_id: str, id_message: str) -> str | None:
        """Свежая ссылка через downloadFile API."""
        if not id_message:
            return None
        wa_chat = self.normalize_chat_id(chat_id)
        api_url = f"{self.base_url}/downloadFile/{self.token}"
        payload = {"chatId": wa_chat, "idMessage": id_message}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(api_url, json=payload, headers=self._auth())
                r.raise_for_status()
                data = r.json() or {}
                return (
                    data.get("downloadUrl")
                    or data.get("urlFile")
                    or data.get("link")
                )
        except Exception as e:
            logger.warning(
                "downloadFile API chat=%s msg=%s: %s", wa_chat, id_message, e
            )
        return None

    async def download_file(self, url: str) -> bytes | None:
        """Download media by URL from webhook or downloadFile."""
        return await self._fetch_media_bytes(url)

    async def download_incoming_file(
        self,
        chat_id: str,
        id_message: str,
        download_url: str | None = None,
    ) -> bytes | None:
        """Скачать голосовое: сначала URL из вебхука, затем downloadFile API."""
        wa_chat = self.normalize_chat_id(chat_id)

        if download_url:
            data = await self._fetch_media_bytes(download_url)
            if data:
                logger.info(
                    "WA media OK (webhook url) chat=%s msg=%s bytes=%s",
                    wa_chat,
                    id_message,
                    len(data),
                )
                return data

        for attempt in range(2):
            fresh = await self.resolve_download_url(wa_chat, id_message)
            if fresh:
                data = await self._fetch_media_bytes(fresh)
                if data:
                    logger.info(
                        "WA media OK (downloadFile) chat=%s msg=%s bytes=%s attempt=%s",
                        wa_chat,
                        id_message,
                        len(data),
                        attempt + 1,
                    )
                    return data
            if attempt < 1:
                await asyncio.sleep(0.5)

        logger.error(
            "WA media download failed chat=%s msg=%s webhook_url=%s",
            wa_chat,
            id_message,
            bool(download_url),
        )
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
        etd = md.get("extendedTextMessageData", {})
        text = etd.get("text") or etd.get("textMessage") or ""
    elif type_message == "textMessage":
        tmd = md.get("textMessageData", {})
        text = tmd.get("text") or tmd.get("textMessage") or ""
    elif type_message in AUDIO_MESSAGE_TYPES:
        media_url = extract_media_download_url(body)
        # text остаётся None — обработчик распознаёт голос отдельно

    return chat_id, text, sender_name, media_url


def is_voice_message(body: dict[str, Any]) -> bool:
    return _message_data(body).get("typeMessage") in AUDIO_MESSAGE_TYPES


IMAGE_MESSAGE_TYPES = frozenset({"imageMessage", "documentMessage"})


def is_image_message(body: dict[str, Any]) -> bool:
    return _message_data(body).get("typeMessage") in IMAGE_MESSAGE_TYPES
