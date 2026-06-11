#!/usr/bin/env python3
"""
Залить казахские JSON-корпуса в Vercel Blob (private store).

Нужно в .env:
  BLOB_READ_WRITE_TOKEN=...   (из Vercel → Storage → Blob → Settings)
  BLOB_STORE_ID=store_OTuiNVlUkxdaNaAx   (опционально, для URL)

Запуск: python scripts/upload_kk_corpus_blob.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "bot" / "data"

FILES = (
    "kk_stt_vocab.json",
    "kk_phrases_top10k.json",
    "kk_dictionary.json",
)


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def main() -> int:
    _load_env()
    if not os.getenv("BLOB_READ_WRITE_TOKEN"):
        print("BLOB_READ_WRITE_TOKEN missing — возьмите в Vercel → Storage → komek-damu-bot-blob → Settings")
        return 1

    sys.path.insert(0, str(ROOT))
    from app.blob_store import KK_CORPUS_PREFIX, blob_put_bytes

    manifest: dict = {"files": {}, "prefix": KK_CORPUS_PREFIX}
    for name in FILES:
        path = DATA / name
        if not path.is_file():
            print(f"SKIP missing: {path}")
            continue
        raw = path.read_bytes()
        result = await blob_put_bytes(
            f"{KK_CORPUS_PREFIX}{name}",
            raw,
            content_type="application/json; charset=utf-8",
        )
        if not result:
            print(f"FAIL upload: {name}")
            return 1
        manifest["files"][name] = {
            "url": result.get("url"),
            "size": len(raw),
            "pathname": result.get("pathname"),
        }
        print(f"OK {name} → {result.get('url', '')[:70]}…")

    meta = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    await blob_put_bytes(f"{KK_CORPUS_PREFIX}manifest.json", meta)
    print("Done. Set KK_CORPUS_USE_BLOB=true on Vercel and redeploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
