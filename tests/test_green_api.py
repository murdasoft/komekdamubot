from app.green_api import (
    extract_green_info,
    extract_media_download_url,
    get_audio_filename,
    is_voice_message,
)


def test_audio_message_webhook():
    body = {
        "typeWebhook": "incomingMessageReceived",
        "idMessage": "ABC123",
        "senderData": {"chatId": "77001234567@c.us", "senderName": "Test"},
        "messageData": {
            "typeMessage": "audioMessage",
            "fileMessageData": {
                "downloadUrl": "https://example.com/voice.ogg",
                "fileName": "voice.ogg",
                "mimeType": "audio/ogg",
            },
        },
    }
    assert is_voice_message(body)
    assert extract_media_download_url(body) == "https://example.com/voice.ogg"
    chat_id, text, _, media = extract_green_info(body)
    assert chat_id == "77001234567"
    assert text is None
    assert media == "https://example.com/voice.ogg"
    assert get_audio_filename(body) == "voice.ogg"
