"""Загрузка казахских корпусов: Vercel Blob → локальный файл (fallback)."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.blob_store import blob_auth_headers, corpus_blob_url, is_blob_configured

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent / "bot" / "data"

ASSETS: dict[str, str] = {
    "stt_vocab": "kk_stt_vocab.json",
    "phrases_top10k": "kk_phrases_top10k.json",
    "dictionary": "kk_dictionary.json",
}


@lru_cache(maxsize=1)
def _use_blob() -> bool:
    if os.getenv("KK_CORPUS_USE_BLOB", "true").lower() in ("0", "false", "no"):
        return False
    return is_blob_configured() and bool(corpus_blob_url("probe.json"))


def _read_local(filename: str) -> dict[str, Any] | None:
    path = _DATA_DIR / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read local corpus %s", path)
        return None


def _read_blob_sync(filename: str) -> dict[str, Any] | None:
    url = corpus_blob_url(filename)
    if not url:
        return None
    try:
        with httpx.Client(timeout=45.0) as client:
            r = client.get(url, headers=blob_auth_headers())
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except Exception:
        logger.exception("Blob load failed for %s", filename)
        return None


def load_corpus(asset_key: str) -> dict[str, Any]:
    """stt_vocab | phrases_top10k | dictionary"""
    filename = ASSETS.get(asset_key)
    if not filename:
        return {}

    data: dict[str, Any] | None = None
    if _use_blob():
        data = _read_blob_sync(filename)
        if data:
            logger.info("KK corpus %s from Blob", asset_key)

    if not data:
        data = _read_local(filename)
        if data:
            logger.info("KK corpus %s from local file", asset_key)

    return data or {}


@lru_cache(maxsize=1)
def get_stt_vocab() -> dict:
    return load_corpus("stt_vocab")


@lru_cache(maxsize=1)
def get_phrases_top10k() -> dict:
    return load_corpus("phrases_top10k")
