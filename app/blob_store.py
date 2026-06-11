"""Vercel Blob (private store) — REST без JS SDK."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BLOB_API = "https://blob.vercel-storage.com"
API_VERSION = "7"
KK_CORPUS_PREFIX = "kk-corpus/"


def _token() -> str:
    return os.getenv("BLOB_READ_WRITE_TOKEN", "").strip()


def _store_base_url() -> str:
    explicit = os.getenv("BLOB_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    store_id = os.getenv("BLOB_STORE_ID", "").strip()
    if store_id.startswith("store_"):
        slug = store_id[6:].lower()
        return f"https://{slug}.private.blob.vercel-storage.com"
    return ""


def is_blob_configured() -> bool:
    return bool(_token())


def corpus_blob_url(filename: str) -> str | None:
    base = _store_base_url()
    if not base:
        return None
    return f"{base}/{KK_CORPUS_PREFIX}{filename.lstrip('/')}"


def blob_auth_headers(*, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {_token()}",
        "x-api-version": API_VERSION,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def blob_get_bytes(url: str, *, timeout: float = 45.0) -> bytes | None:
    if not _token():
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=blob_auth_headers())
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
    except Exception:
        logger.exception("Blob GET failed: %s", url[:80])
        return None


async def blob_get_json(url: str) -> dict[str, Any] | None:
    raw = await blob_get_bytes(url)
    if not raw:
        return None
    try:
        import json

        return json.loads(raw.decode("utf-8"))
    except Exception:
        logger.exception("Blob JSON parse failed: %s", url[:80])
        return None


async def blob_put_bytes(
    pathname: str,
    data: bytes,
    *,
    content_type: str = "application/json",
) -> dict[str, Any] | None:
    if not _token():
        logger.warning("BLOB_READ_WRITE_TOKEN missing")
        return None
    path = pathname.lstrip("/")
    url = f"{BLOB_API}/{path}"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.put(url, headers=blob_auth_headers(content_type=content_type), content=data)
            r.raise_for_status()
            body = r.json()
            logger.info("Blob PUT ok pathname=%s size=%s", path, len(data))
            return body
    except Exception:
        logger.exception("Blob PUT failed pathname=%s", path)
        return None
