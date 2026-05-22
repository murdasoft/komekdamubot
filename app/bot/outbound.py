"""Отправка ответов пользователю с учётом платформы."""

from __future__ import annotations

import re
from typing import Any

from app.bot.formatting import Platform, sanitize_for_telegram


def adapt_message_for_platform(text: str, platform: Platform) -> str:
    """Telegram: `код`; WhatsApp: ```код```."""
    if platform != "whatsapp":
        return text
    return re.sub(r"`([^`]+)`", r"```\1```", text)


async def send_to_user(
    api: Any,
    chat_id: str,
    text: str,
    platform: Platform,
) -> None:
    text = adapt_message_for_platform(text, platform)
    if platform == "whatsapp":
        await api.send_message(chat_id, text)
        return
    safe = sanitize_for_telegram(text)
    await api.send_message(chat_id, safe, parse_mode="Markdown")
