"""Тестовый мониторинг голосовых: пересылка STT и ответа бота одному получателю."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_VOICE_DEBUG_CHAT_ID = "5450018125"


def voice_debug_recipient(settings: Settings | None = None) -> str | None:
    """Chat ID, куда слать отчёты (только этот человек)."""
    settings = settings or get_settings()
    if not settings.voice_debug_enabled:
        return None
    rid = (settings.voice_debug_chat_id or DEFAULT_VOICE_DEBUG_CHAT_ID).strip()
    return rid or None


def should_monitor_voice(source_chat_id: str, settings: Settings | None = None) -> bool:
    """Мониторим чужие чаты; не шлём отчёт, если голос от самого получателя."""
    recipient = voice_debug_recipient(settings)
    if not recipient:
        return False
    return str(source_chat_id) != str(recipient)


def create_voice_debug_monitor(
    tg_client: Any,
    *,
    body: dict[str, Any],
    source_chat_id: str,
    sender_name: str | None,
    settings: Settings | None = None,
) -> VoiceDebugMonitor | None:
    settings = settings or get_settings()
    if not should_monitor_voice(source_chat_id, settings):
        return None
    recipient = voice_debug_recipient(settings)
    if not recipient:
        return None
    return VoiceDebugMonitor(
        tg_client,
        recipient=recipient,
        body=body,
        source_chat_id=source_chat_id,
        sender_name=sender_name,
    )


class VoiceDebugMonitor:
    """Прокси TelegramClient: перехватывает ответы бота и шлёт отчёт получателю."""

    def __init__(
        self,
        client: Any,
        *,
        recipient: str,
        body: dict[str, Any],
        source_chat_id: str,
        sender_name: str | None,
    ):
        self._client = client
        self._recipient = recipient
        self._body = body
        self._source_chat_id = source_chat_id
        self._sender_name = sender_name or "—"
        self._stt_raw: str | None = None
        self._stt_routed: str | None = None
        self._stt_error: str | None = None
        self._duration_sec: float | None = None
        self._bot_replies: list[str] = []

    @property
    def client(self) -> VoiceDebugMonitor:
        return self

    def note_stt(
        self,
        *,
        raw: str | None = None,
        routed: str | None = None,
        error: str | None = None,
        duration_sec: float | None = None,
    ) -> None:
        self._stt_raw = raw
        self._stt_routed = routed
        self._stt_error = error
        self._duration_sec = duration_sec

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict | None = None,
    ) -> dict[str, Any] | None:
        result = await self._client.send_message(
            chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup
        )
        if str(chat_id) == str(self._source_chat_id) and text and text.strip():
            self._bot_replies.append(text.strip())
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def flush(self) -> None:
        msg = self._body.get("message") or {}
        msg_id = msg.get("message_id")
        voice = msg.get("voice") or msg.get("audio") or {}
        dur = self._duration_sec
        if dur is None and voice.get("duration"):
            try:
                dur = float(voice["duration"])
            except (TypeError, ValueError):
                dur = None

        lines = [
            "🎤 *Voice debug* (тест)",
            f"👤 {self._sender_name}",
            f"💬 chat `{self._source_chat_id}`",
        ]
        user = (self._body.get("message") or {}).get("from") or {}
        if user.get("id"):
            lines.append(f"🆔 user `{user['id']}`")
        if dur:
            lines.append(f"⏱ {dur:.0f} с")

        if self._stt_error:
            lines.append(f"❌ STT: {self._stt_error}")
        elif self._stt_raw:
            lines.append(f"📝 STT: «{self._stt_raw[:500]}»")
        else:
            lines.append("📝 STT: (пусто)")

        if self._stt_routed and self._stt_routed != self._stt_raw:
            lines.append(f"🔀 Routed: «{self._stt_routed[:300]}»")

        if self._bot_replies:
            reply = self._bot_replies[0]
            if len(self._bot_replies) > 1:
                extra = len(self._bot_replies) - 1
                reply += f"\n\n_(+ ещё {extra} сообщ.)_"
            lines.append(f"🤖 Bot:\n{reply[:1200]}")
        else:
            lines.append("🤖 Bot: _(нет ответа)_")

        report = "\n".join(lines)

        try:
            if msg_id:
                await self._client.forward_message(
                    self._recipient,
                    self._source_chat_id,
                    msg_id,
                )
            await self._client.send_message(self._recipient, report)
        except Exception:
            logger.exception(
                "Voice debug report failed src=%s recipient=%s",
                self._source_chat_id,
                self._recipient,
            )
