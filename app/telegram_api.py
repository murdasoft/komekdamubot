"""
Telegram Bot API client.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        url = f"{self.base_url}/{method}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            logger.exception("Telegram API error: %s", e)
            return None

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
    ) -> dict[str, Any] | None:
        if parse_mode:
            from app.bot.formatting import sanitize_for_telegram

            text = sanitize_for_telegram(text)
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = await self._post("sendMessage", payload)
        # If failed due to parse error, retry without parse_mode
        if result is None and parse_mode:
            payload.pop("parse_mode", None)
            result = await self._post("sendMessage", payload)
        return result

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self._post("answerCallbackQuery", payload)

    async def set_webhook(self, url: str, secret_token: str = "") -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        }
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._post("setWebhook", payload)

    async def delete_webhook(self) -> dict[str, Any] | None:
        return await self._post("deleteWebhook", {})

    async def send_dice(self, chat_id: str | int, emoji: str = "🎲") -> dict[str, Any] | None:
        return await self._post("sendDice", {"chat_id": chat_id, "emoji": emoji})

    async def set_message_reaction(
        self, chat_id: str | int, message_id: int, emoji: str = "👍"
    ) -> None:
        await self._post("setMessageReaction", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
        })

    async def get_file(self, file_id: str) -> dict[str, Any] | None:
        return await self._post("getFile", {"file_id": file_id})


# Helpers to extract info from Telegram update
def extract_update_info(body: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract (chat_id, text, sender_name, callback_query_id) from update."""
    if "callback_query" in body:
        cq = body["callback_query"]
        msg = cq.get("message", {})
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = cq.get("data", "")
        user = cq.get("from", {})
        name = user.get("first_name", "") or ""
        if user.get("last_name"):
            name += " " + user.get("last_name")
        return chat_id, text, name.strip() or None, cq.get("id")

    msg = body.get("message", {})
    if not msg:
        return None, None, None, None

    chat = msg.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = msg.get("text", "")
    user = msg.get("from", {})
    name = user.get("first_name", "") or ""
    if user.get("last_name"):
        name += " " + user.get("last_name")
    return chat_id, text, name.strip() or None, None


def get_message_id(body: dict[str, Any]) -> int | None:
    msg = body.get("message") or body.get("callback_query", {}).get("message")
    if msg:
        return msg.get("message_id")
    return None


def is_voice_message(body: dict[str, Any]) -> bool:
    msg = body.get("message", {})
    return "voice" in msg


def get_voice_file_id(body: dict[str, Any]) -> str | None:
    msg = body.get("message", {})
    voice = msg.get("voice", {})
    return voice.get("file_id")


def get_file_url(token: str, file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{token}/{file_path}"
