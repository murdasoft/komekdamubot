"""Chat monitor tests."""

import asyncio

from app.bot.chat_monitor import (
    ChatMonitor,
    create_tg_chat_monitor,
    monitor_recipient,
    should_monitor_chat,
)


def test_monitor_recipient_default(monkeypatch):
    monkeypatch.delenv("CHAT_MONITOR_CHAT_ID", raising=False)
    monkeypatch.setenv("CHAT_MONITOR_ENABLED", "true")
    import app.config as cfg

    cfg._settings = None
    assert monitor_recipient() == "5450018125"
    assert should_monitor_chat("8741719713", "telegram") is True
    assert should_monitor_chat("5450018125", "telegram") is False


def test_monitor_disabled(monkeypatch):
    monkeypatch.setenv("CHAT_MONITOR_ENABLED", "false")
    import app.config as cfg

    cfg._settings = None
    assert monitor_recipient() is None


def test_tg_monitor_text_message():
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
    body = {
        "message": {
            "message_id": 99,
            "text": "Сәлем",
            "from": {"id": 8741719713},
        }
    }
    mon = ChatMonitor(
        client,
        recipient="5450018125",
        body=body,
        source_chat_id="8741719713",
        sender_name="Айгүл",
        platform="telegram",
    )

    async def run():
        await mon.send_message("8741719713", "Қайырлы күн!")
        await mon.flush()

    asyncio.run(run())

    assert client.forwards == [("5450018125", "8741719713", 99)]
    report = [m[1] for m in client.messages if m[0] == "5450018125"][0]
    assert "Сәлем" in report
    assert "Қайырлы күн" in report
    assert "Telegram" in report


def test_create_tg_monitor_skips_recipient(monkeypatch):
    monkeypatch.setenv("CHAT_MONITOR_ENABLED", "true")
    monkeypatch.setenv("CHAT_MONITOR_CHAT_ID", "5450018125")
    import app.config as cfg

    cfg._settings = None
    assert create_tg_chat_monitor(
        object(),
        body={},
        source_chat_id="5450018125",
        sender_name="Me",
    ) is None
