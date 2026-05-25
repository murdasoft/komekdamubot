#!/usr/bin/env python3
"""Sync production env vars on Vercel for komek-damu-bot."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN = os.environ.get("VERCEL_TOKEN", "")
if not TOKEN:
    print("Set VERCEL_TOKEN", file=sys.stderr)
    sys.exit(1)

REMOVE = [
    "LOCAL_LLM_BASE_URL",
    "LOCAL_LLM_MODEL",
    "LOCAL_LLM_API_KEY",
    "LOCAL_WHISPER_URL",
    "LOCAL_LLM_NUM_CTX",
    "LOCAL_LLM_KEEP_ALIVE",
    "BITRIX24_WEBHOOK_URL",
    "TELEGRAM_ALERT_CHAT_ID",
    "IGNORED_CHAT_IDS",
    "GOOGLE_API_KEY",
]

SET: dict[str, str] = {
    "WEBHOOK_BASE_URL": "https://komek-damu-bot.vercel.app",
    "AI_PROVIDER": "groq",
    "GROQ_ENABLED": "true",
    "GROQ_MODEL": "openai/gpt-oss-120b",
    "GROQ_STT_MODEL": "whisper-large-v3",
    "GROQ_VOICE_STT": "true",
    "GROQ_VOICE_INTENT": "false",
    "FAST_FAQ": "true",
    "GREEN_API_URL": "https://7107.api.greenapi.com",
    "REMINDER_DELAY_SECONDS": "3600",
    "ORDER_ABANDON_NUDGE_SECONDS": "1800",
    "HANDOFF_TIMEOUT_HOURS": "24",
    "LOCAL_LLM_MAX_TOKENS": "256",
}


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out


def load_supabase_from_transcript() -> dict[str, str]:
    transcript = Path(
        os.environ.get(
            "TRANSCRIPT",
            "/Users/aleksandr/.cursor/projects/Users-aleksandr-Project-bots-for-business-komek-damu-bot/agent-transcripts/d9935c60-8eba-4700-8618-4f4ff350db4b/d9935c60-8eba-4700-8618-4f4ff350db4b.jsonl",
        )
    )
    if not transcript.exists():
        return {}
    for line in transcript.read_text().splitlines():
        obj = json.loads(line)
        if obj.get("role") != "user":
            continue
        content = obj.get("message", {}).get("content", [])
        text = content if isinstance(content, str) else ""
        if not text:
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text += part.get("text", "")
        if "SUPABASE_SERVICE_ROLE_KEY" not in text:
            continue
        out: dict[str, str] = {}
        for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
            m = re.search(rf'{key}="([^"]+)"', text)
            if m:
                out[key] = m.group(1)
        return out
    return {}


def vercel(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "vercel",
        *args,
        "--token",
        TOKEN,
        "--yes",
    ]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def rm(name: str) -> None:
    for env in ("production", "preview"):
        r = vercel("env", "rm", name, env)
        if r.returncode == 0:
            print(f"removed {name} ({env})")


def add(name: str, value: str) -> None:
    for env in ("production", "preview"):
        r = vercel(
            "env",
            "add",
            name,
            env,
            "--value",
            value,
            "--force",
            "--non-interactive",
        )
        if r.returncode != 0:
            print(f"FAIL {name} ({env}): {r.stderr.strip() or r.stdout.strip()}")
            sys.exit(1)
        print(f"set {name} ({env})")


def main() -> None:
    local = load_dotenv(ROOT / ".env")
    supabase = load_supabase_from_transcript()

    for key in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "GREEN_API_INSTANCE_ID",
        "GREEN_API_TOKEN",
        "GREEN_API_WEBHOOK_TOKEN",
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GROQ_STT_MODEL",
        "TOGETHER_API_KEY",
    ):
        if local.get(key):
            SET[key] = local[key]

    SET.update({k: v for k, v in supabase.items() if v})

    missing = [k for k, v in SET.items() if not v]
    if missing:
        print("Missing required values:", ", ".join(missing))
        if "GROQ_API_KEY" in missing:
            print("WARNING: GROQ_API_KEY missing — voice and AI will not work")

    for name in REMOVE:
        rm(name)

    for name, value in sorted(SET.items()):
        if not value:
            continue
        add(name, value)

    print("done")


if __name__ == "__main__":
    main()
