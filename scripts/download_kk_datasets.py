#!/usr/bin/env python3
"""
Скачать открытые казахские датасеты в data/kk_datasets/.

Источники:
  - KazNERD (GitHub, IOB2 — ~112k предложений)
  - CCRss/chatgpt-paraphrases-kz (HF, sample jsonl)
  - issai/kazparc (HF, если токен одобрен)
  - Epimetheus84/kazakh_words (GitHub CSV, если нет локального zip)

Запуск: python scripts/download_kk_datasets.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "kk_datasets"
MANIFEST = OUT / "manifest.json"

KAZNERD_FILES = (
    "KazNERD/IOB2_train.txt",
    "KazNERD/IOB2_valid.txt",
    "KazNERD/IOB2_test.txt",
)
KAZNERD_BASE = "https://raw.githubusercontent.com/IS2AI/KazNERD/main"
PARAPHRASES_URL = (
    "https://huggingface.co/datasets/CCRss/chatgpt-paraphrases-kz/resolve/main/train.jsonl"
)
KAZPARC_FILE = "kazparc/01_kazparc_all_entries.csv"
KAZPARC_URL = f"https://huggingface.co/datasets/issai/kazparc/resolve/main/{KAZPARC_FILE}"
KAZAKH_WORDS_URL = (
    "https://raw.githubusercontent.com/Epimetheus84/kazakh_words/master/words.csv"
)


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _hf_token() -> str:
    return os.environ.get("HUGGINGFACE_API_KEY", "") or os.environ.get("HF_TOKEN", "")


def _download(url: str, dest: Path, *, token: str = "") -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"  skip (exists): {dest.name}")
        return True

    headers = {"User-Agent": "komek-damu-bot/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", errors="replace")
        print(f"  FAIL {dest.name}: HTTP {exc.code} — {body[:200]}")
        return False

    if b"restricted" in data[:400].lower() or b"authorized list" in data[:400].lower():
        print(f"  FAIL {dest.name}: gated dataset — запросите доступ на HuggingFace")
        return False

    dest.write_bytes(data)
    print(f"  saved {dest.name} ({len(data) // 1024} KB)")
    return True


def _download_paraphrases_sample(dest: Path, *, max_lines: int = 120_000, token: str = "") -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 50_000:
        print(f"  skip (exists): {dest.name}")
        return True

    headers = {"User-Agent": "komek-damu-bot/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(PARAPHRASES_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            with dest.open("w", encoding="utf-8") as out:
                for i, raw in enumerate(resp):
                    if i >= max_lines:
                        break
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        out.write(line + "\n")
    except urllib.error.HTTPError as exc:
        print(f"  FAIL paraphrases sample: HTTP {exc.code}")
        return False

    size_kb = dest.stat().st_size // 1024
    print(f"  saved {dest.name} ({size_kb} KB, up to {max_lines} lines)")
    return True


def main() -> int:
    _load_env()
    token = _hf_token()
    OUT.mkdir(parents=True, exist_ok=True)

    manifest: dict = {"sources": {}, "notes": []}

    print("KazNERD …")
    kaznerd_ok = True
    for rel in KAZNERD_FILES:
        dest = OUT / "kaznerd" / Path(rel).name
        ok = _download(f"{KAZNERD_BASE}/{rel}", dest)
        kaznerd_ok = kaznerd_ok and ok
    manifest["sources"]["kaznerd"] = {"ok": kaznerd_ok, "files": list(KAZNERD_FILES)}

    print("chatgpt-paraphrases-kz (sample) …")
    para_ok = _download_paraphrases_sample(
        OUT / "paraphrases" / "train_sample.jsonl",
        token=token,
    )
    manifest["sources"]["paraphrases_kz"] = {"ok": para_ok, "file": "paraphrases/train_sample.jsonl"}

    print("kazakh_words (GitHub) …")
    words_dest = OUT / "kazakh_words" / "words.csv"
    words_ok = _download(KAZAKH_WORDS_URL, words_dest)
    manifest["sources"]["kazakh_words"] = {"ok": words_ok}

    print("KazParC (HF, optional) …")
    kazparc_dest = OUT / "kazparc" / "01_kazparc_all_entries.csv"
    kazparc_ok = _download(KAZPARC_URL, kazparc_dest, token=token)
    manifest["sources"]["kazparc"] = {
        "ok": kazparc_ok,
        "note": "Требует принятия условий на https://huggingface.co/datasets/issai/kazparc",
    }
    if not kazparc_ok:
        manifest["notes"].append(
            "KazParC недоступен: примите условия на HF и перезапустите скрипт."
        )

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nManifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
