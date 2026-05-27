#!/usr/bin/env python3
"""Локальный тест Groq STT на тестовых .ogg (без вывода ключей)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.groq_client import GroqClient


async def main() -> None:
    settings = get_settings()
    if not settings.is_groq_configured:
        print("GROQ_API_KEY not set in .env")
        sys.exit(1)

    audio_dir = ROOT.parent / "audio"
    files = sorted(audio_dir.glob("*.ogg"))[:3]
    if not files:
        print(f"No .ogg in {audio_dir}")
        sys.exit(1)

    client = GroqClient(settings.groq_api_key, stt_model=settings.groq_stt_model)
    for path in files:
        audio = path.read_bytes()
        text, err = await client.transcribe(audio, filename=path.name)
        print(f"{path.name}: text={text!r} err={err}")


if __name__ == "__main__":
    asyncio.run(main())
