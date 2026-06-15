"""Voice debug monitor tests."""

from app.bot.voice_debug import (
    VoiceDebugMonitor,
    voice_debug_recipient,
    should_monitor_voice,
)


def test_default_recipient(monkeypatch):
    monkeypatch.delenv("VOICE_DEBUG_CHAT_ID", raising=False)
    monkeypatch.setenv("VOICE_DEBUG_ENABLED", "true")
    import app.config as cfg

    cfg._settings = None
    assert voice_debug_recipient() == "5450018125"
    assert should_monitor_voice("8741719713") is True
    assert should_monitor_voice("5450018125") is False


def test_disabled(monkeypatch):
    monkeypatch.setenv("VOICE_DEBUG_ENABLED", "false")
    import app.config as cfg

    cfg._settings = None
    assert voice_debug_recipient() is None


def test_monitor_captures_user_reply():
    class FakeClient:
        def __init__(self):
            self.forwards = []
            self.messages = []

        async def send_message(self, chat_id, text, parse_mode="Markdown", reply_markup=None):
            self.messages.append((str(chat_id), text))
            return {"ok": True}

        async def forward_message(self, to_chat_id, from_chat_id, message_id):
            self.forwards.append((str(to_chat_id), str(from_chat_id), message_id))
            return {"ok": True}

    client = FakeClient()
    body = {"message": {"message_id": 42, "from": {"id": 8741719713}}}
    mon = VoiceDebugMonitor(
        client,
        recipient="5450018125",
        body=body,
        source_chat_id="8741719713",
        sender_name="Test",
    )
    mon.note_stt(raw="мен несие алғым келеді", routed="мен несие алғым келеді", duration_sec=6.0)

    import asyncio

    async def run():
        await mon.send_message("8741719713", "Жауап бот")
        await mon.flush()

    asyncio.run(run())

    assert client.forwards == [("5450018125", "8741719713", 42)]
    assert any("5450018125" == m[0] for m in client.messages)
    report = [m[1] for m in client.messages if m[0] == "5450018125"][0]
    assert "мен несие" in report
    assert "Жауап бот" in report
