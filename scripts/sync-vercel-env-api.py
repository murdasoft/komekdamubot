#!/usr/bin/env python3
"""Fix Vercel production env via REST API (fast batch)."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = __import__("os").environ.get("VERCEL_TOKEN", "")
PROJECT = "prj_be5ygUibloHeEdRtyWuBHEOWPagY"
ROOT = Path(__file__).resolve().parents[1]

REMOVE = {
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
}


def api(method: str, path: str, data: dict | None = None) -> tuple[int, dict | str]:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        f"https://api.vercel.com{path}",
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out


def load_supabase() -> dict[str, str]:
    transcript = Path(
        "/Users/aleksandr/.cursor/projects/Users-aleksandr-Project-bots-for-business-komek-damu-bot/agent-transcripts/d9935c60-8eba-4700-8618-4f4ff350db4b/d9935c60-8eba-4700-8618-4f4ff350db4b.jsonl"
    )
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


def main() -> None:
    if not TOKEN:
        print("VERCEL_TOKEN required", file=sys.stderr)
        sys.exit(1)

    local = load_dotenv(ROOT / ".env")
    supabase = load_supabase()

    desired: dict[str, str] = {
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
        "TELEGRAM_BOT_TOKEN": local.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_WEBHOOK_SECRET": local.get("TELEGRAM_WEBHOOK_SECRET", ""),
        "GREEN_API_INSTANCE_ID": local.get("GREEN_API_INSTANCE_ID", ""),
        "GREEN_API_TOKEN": local.get("GREEN_API_TOKEN", ""),
        "GREEN_API_WEBHOOK_TOKEN": local.get("GREEN_API_WEBHOOK_TOKEN", ""),
        "GROQ_API_KEY": local.get("GROQ_API_KEY", ""),
        "GROQ_MODEL": local.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        "GROQ_STT_MODEL": local.get("GROQ_STT_MODEL", "whisper-large-v3"),
        "SUPABASE_URL": supabase.get("SUPABASE_URL", ""),
        "SUPABASE_SERVICE_ROLE_KEY": supabase.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    }
    if local.get("TOGETHER_API_KEY"):
        desired["TOGETHER_API_KEY"] = local["TOGETHER_API_KEY"]

    _, data = api("GET", f"/v9/projects/{PROJECT}/env")
    existing = {e["key"]: e for e in data.get("envs", [])}

    for key in list(existing):
        if key in REMOVE:
            eid = existing[key]["id"]
            code, _ = api("DELETE", f"/v9/projects/{PROJECT}/env/{eid}")
            print(f"DELETE {key}: {code}")
            existing.pop(key, None)

    for key, value in sorted(desired.items()):
        if not value:
            print(f"SKIP {key}: no value")
            continue
        if key in existing:
            eid = existing[key]["id"]
            code, resp = api("DELETE", f"/v9/projects/{PROJECT}/env/{eid}")
            print(f"DELETE old {key}: {code}")
            if code >= 400:
                print(resp)
                sys.exit(1)
        code, resp = api(
            "POST",
            f"/v10/projects/{PROJECT}/env",
            {
                "key": key,
                "value": value,
                "type": "encrypted",
                "target": ["production", "preview"],
            },
        )
        print(f"POST {key}: {code}")
        if code >= 400:
            print(resp)
            sys.exit(1)

    print("env sync ok")


if __name__ == "__main__":
    main()
