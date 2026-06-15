"""Обратная совместимость: voice debug → chat monitor."""

from app.bot.chat_monitor import (
    ChatMonitor,
    ChatMonitor as VoiceDebugMonitor,
    create_tg_chat_monitor,
    monitor_recipient,
    should_monitor_chat,
)

DEFAULT_VOICE_DEBUG_CHAT_ID = "5450018125"


def voice_debug_recipient(settings=None):
    return monitor_recipient(settings)


def should_monitor_voice(source_chat_id: str, settings=None) -> bool:
    return should_monitor_chat(source_chat_id, "telegram", settings)


def create_voice_debug_monitor(
    tg_client,
    *,
    body,
    source_chat_id: str,
    sender_name: str | None,
    settings=None,
):
    return create_tg_chat_monitor(
        tg_client,
        body=body,
        source_chat_id=source_chat_id,
        sender_name=sender_name,
        settings=settings,
    )
