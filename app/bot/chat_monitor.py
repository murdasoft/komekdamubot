"""Мониторинг всех диалогов: входящие + ответы бота → один Telegram-чат."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFAULT_MONITOR_CHAT_ID = "5450018125"


def monitor_recipient(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    if not settings.chat_monitor_enabled:
        return None
    rid = (settings.chat_monitor_chat_id or DEFAULT_MONITOR_CHAT_ID).strip()
    return rid or None


def should_monitor_chat(
    source_chat_id: str,
    platform: str,
    settings: Settings | None = None,
) -> bool:
    """Не мониторим свой чат (TG) и ops-чат менеджера."""
    settings = settings or get_settings()
    recipient = monitor_recipient(settings)
    if not recipient:
        return False
    src = str(source_chat_id)
    if platform == "telegram" and src == str(recipient):
        return False
    alert = (settings.telegram_alert_chat_id or "").strip()
    if alert and src == alert:
        return False
    return True


def _parse_tg_incoming(body: dict[str, Any]) -> tuple[str, str | None]:
    """kind, preview text."""
    cq = body.get("callback_query")
    if cq:
        data = (cq.get("data") or "").strip()
        return "callback", data or None

    msg = body.get("message") or body.get("edited_message") or {}
    if msg.get("voice") or msg.get("audio"):
        return "voice", None
    if msg.get("photo"):
        return "photo", "[фото]"
    if msg.get("document"):
        return "document", "[документ]"
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if text:
        return "text", text
    return "other", None


def _parse_wa_incoming(body: dict[str, Any], text: str | None) -> str:
    from app.green_api import is_image_message, is_voice_message

    if is_voice_message(body):
        return "voice"
    if is_image_message(body):
        return "image"
    if text and text.strip():
        return "text"
    return "other"


def _build_report(
    *,
    platform: str,
    sender_name: str | None,
    source_chat_id: str,
    incoming_kind: str,
    incoming_text: str | None,
    stt_raw: str | None = None,
    stt_routed: str | None = None,
    stt_error: str | None = None,
    duration_sec: float | None = None,
    bot_replies: list[str],
) -> str:
    plat = "Telegram" if platform == "telegram" else "WhatsApp"
    lines = [
        f"📡 *Монитор* ({plat})",
        f"👤 {sender_name or '—'}",
        f"💬 `{source_chat_id}`",
    ]

    if incoming_kind == "voice":
        lines.append("📥 Голосовое")
        if duration_sec:
            lines.append(f"⏱ {duration_sec:.0f} с")
    elif incoming_kind in ("photo", "image"):
        lines.append("📥 Фото")
    elif incoming_kind == "document":
        lines.append("📥 Документ")
    elif incoming_kind == "callback":
        lines.append("📥 Кнопка")
    elif incoming_text:
        lines.append(f"📥 «{incoming_text[:800]}»")
    else:
        lines.append(f"📥 ({incoming_kind})")

    if stt_error:
        lines.append(f"❌ STT: {stt_error}")
    elif stt_raw:
        lines.append(f"📝 STT: «{stt_raw[:500]}»")
    if stt_routed and stt_routed != stt_raw:
        lines.append(f"🔀 Routed: «{stt_routed[:300]}»")

    if bot_replies:
        combined = "\n---\n".join(r[:600] for r in bot_replies[:5])
        if len(bot_replies) > 5:
            combined += f"\n\n_(+ ещё {len(bot_replies) - 5} ответов)_"
        lines.append(f"🤖 Bot:\n{combined[:2000]}")
    else:
        lines.append("🤖 Bot: _(нет ответа)_")

    return "\n".join(lines)


async def _send_report(tg_client: Any, recipient: str, report: str) -> None:
    try:
        await tg_client.send_message(recipient, report)
    except Exception:
        logger.exception("Chat monitor report failed recipient=%s", recipient)


class ChatMonitor:
    """Прокси TelegramClient: ловит ответы бота и шлёт отчёт оператору."""

    def __init__(
        self,
        client: Any,
        *,
        recipient: str,
        body: dict[str, Any],
        source_chat_id: str,
        sender_name: str | None,
        platform: str = "telegram",
    ):
        self._client = client
        self._recipient = recipient
        self._body = body
        self._source_chat_id = source_chat_id
        self._sender_name = sender_name or "—"
        self._platform = platform
        self._incoming_kind, self._incoming_text = _parse_tg_incoming(body)
        self._stt_raw: str | None = None
        self._stt_routed: str | None = None
        self._stt_error: str | None = None
        self._duration_sec: float | None = None
        self._bot_replies: list[str] = []

    @property
    def client(self) -> ChatMonitor:
        return self

    def note_incoming_text(self, text: str) -> None:
        if text and text.strip():
            self._incoming_text = text.strip()
            if self._incoming_kind == "other":
                self._incoming_kind = "text"

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
        if self._duration_sec is None and voice.get("duration"):
            try:
                self._duration_sec = float(voice["duration"])
            except (TypeError, ValueError):
                pass

        report = _build_report(
            platform=self._platform,
            sender_name=self._sender_name,
            source_chat_id=self._source_chat_id,
            incoming_kind=self._incoming_kind,
            incoming_text=self._incoming_text,
            stt_raw=self._stt_raw,
            stt_routed=self._stt_routed,
            stt_error=self._stt_error,
            duration_sec=self._duration_sec,
            bot_replies=self._bot_replies,
        )

        try:
            if msg_id and self._incoming_kind != "callback":
                await self._client.forward_message(
                    self._recipient,
                    self._source_chat_id,
                    msg_id,
                )
        except Exception:
            logger.debug(
                "Chat monitor forward skipped src=%s msg=%s",
                self._source_chat_id,
                msg_id,
            )

        await _send_report(self._client, self._recipient, report)


class WaChatMonitor:
    """Прокси GreenApiClient + отчёт в Telegram."""

    def __init__(
        self,
        wa_client: Any,
        tg_client: Any,
        *,
        recipient: str,
        body: dict[str, Any],
        source_chat_id: str,
        sender_name: str | None,
        initial_text: str | None,
    ):
        self._wa = wa_client
        self._tg = tg_client
        self._recipient = recipient
        self._body = body
        self._source_chat_id = source_chat_id
        self._sender_name = sender_name or "—"
        self._incoming_kind = _parse_wa_incoming(body, initial_text)
        self._incoming_text = (initial_text or "").strip() or None
        self._stt_raw: str | None = None
        self._stt_routed: str | None = None
        self._stt_error: str | None = None
        self._bot_replies: list[str] = []

    @property
    def client(self) -> WaChatMonitor:
        return self

    def note_incoming_text(self, text: str) -> None:
        if text and text.strip():
            self._incoming_text = text.strip()
            self._incoming_kind = "text"

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

    async def send_message(self, phone: str, message: str) -> dict[str, Any] | None:
        result = await self._wa.send_message(phone, message)
        phone_clean = str(phone).replace("@c.us", "")
        if phone_clean == str(self._source_chat_id) and message and message.strip():
            self._bot_replies.append(message.strip())
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wa, name)

    async def flush(self) -> None:
        report = _build_report(
            platform="whatsapp",
            sender_name=self._sender_name,
            source_chat_id=self._source_chat_id,
            incoming_kind=self._incoming_kind,
            incoming_text=self._incoming_text,
            stt_raw=self._stt_raw,
            stt_routed=self._stt_routed,
            stt_error=self._stt_error,
            bot_replies=self._bot_replies,
        )
        await _send_report(self._tg, self._recipient, report)


def create_tg_chat_monitor(
    tg_client: Any,
    *,
    body: dict[str, Any],
    source_chat_id: str,
    sender_name: str | None,
    settings: Settings | None = None,
) -> ChatMonitor | None:
    settings = settings or get_settings()
    if not should_monitor_chat(source_chat_id, "telegram", settings):
        return None
    recipient = monitor_recipient(settings)
    if not recipient:
        return None
    return ChatMonitor(
        tg_client,
        recipient=recipient,
        body=body,
        source_chat_id=source_chat_id,
        sender_name=sender_name,
        platform="telegram",
    )


def create_wa_chat_monitor(
    wa_client: Any,
    tg_client: Any | None,
    *,
    body: dict[str, Any],
    source_chat_id: str,
    sender_name: str | None,
    initial_text: str | None,
    settings: Settings | None = None,
) -> WaChatMonitor | None:
    settings = settings or get_settings()
    if not should_monitor_chat(source_chat_id, "whatsapp", settings):
        return None
    recipient = monitor_recipient(settings)
    if not recipient or not tg_client:
        return None
    return WaChatMonitor(
        wa_client,
        tg_client,
        recipient=recipient,
        body=body,
        source_chat_id=source_chat_id,
        sender_name=sender_name,
        initial_text=initial_text,
    )
