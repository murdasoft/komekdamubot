from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.green_api import (
    GreenApiClient,
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


def test_text_message_green_api_field():
    body = {
        "typeWebhook": "incomingMessageReceived",
        "senderData": {"chatId": "77012117340@c.us", "senderName": "Test"},
        "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": "салеметсезбе"},
        },
    }
    chat_id, text, name, media = extract_green_info(body)
    assert chat_id == "77012117340"
    assert text == "салеметсезбе"
    assert name == "Test"
    assert media is None


@pytest.mark.asyncio
async def test_fetch_media_bytes_without_bearer_on_signed_url():
    """Green API signed URLs break with Authorization: Bearer (400)."""
    client = GreenApiClient("7107624359", "test-token")
    url = "https://do-media-7107.fra1.digitaloceanspaces.com/voice.oga"
    audio = b"x" * 128

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = audio

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.green_api.httpx.AsyncClient", return_value=mock_http):
        data = await client._fetch_media_bytes(url)

    assert data == audio
    mock_http.get.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_download_incoming_file_prefers_webhook_url():
    client = GreenApiClient("7107624359", "test-token")
    audio = b"voice-bytes" * 20
    signed_url = "https://do-media-7107.fra1.digitaloceanspaces.com/voice.oga"

    with patch.object(
        client, "_fetch_media_bytes", AsyncMock(return_value=audio)
    ) as fetch, patch.object(
        client, "resolve_download_url", AsyncMock()
    ) as resolve:
        data = await client.download_incoming_file(
            "77001234567", "MSG123", signed_url
        )

    assert data == audio
    fetch.assert_called_once_with(signed_url)
    resolve.assert_not_called()
