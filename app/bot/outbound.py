"""Отправка ответов пользователю с учётом платформы."""

from __future__ import annotations

import re
from typing import Any

from app.bot.formatting import Platform, sanitize_for_telegram


def clean_whatsapp_text(text: str, lang: str = "kk") -> str:
    """Убрать битые backticks, markdown-ссылки и дубли вопроса про город."""
    from app.bot.formatting import strip_foreign_scripts

    text = strip_foreign_scripts(text, lang)
    text = text.replace("```", "").replace("`", "")
    # WhatsApp не понимает [текст](tel:+7...) — оставляем только номер/текст
    text = re.sub(r"\[([^\]]+)\]\((?:tel:|https?://)[^)]+\)", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # **жирный** → *жирный* (формат WhatsApp)
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [ln.rstrip() for ln in text.split("\n")]
    seen_city_q = False
    out: list[str] = []
    city_markers = (
        "из какого вы города",
        "подскажу офис",
        "қай қаладасыз",
        "офис пен телефон",
    )
    for ln in lines:
        low = ln.lower().strip()
        if any(m in low for m in city_markers):
            if seen_city_q:
                continue
            seen_city_q = True
        out.append(ln)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def adapt_message_for_platform(text: str, platform: Platform) -> str:
    """Telegram: Markdown; WhatsApp: *жирный*, без ` и ```."""
    if platform != "whatsapp":
        return text
    return clean_whatsapp_text(text)


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
