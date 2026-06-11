"""Общие утилиты для сборки казахского корпуса (слова + фразы)."""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

KK_CHARS = set("әіңғүұқөһ")
FINANCE_RE = re.compile(
    r"несие|кредит|қарыз|карыз|банк|ақша|акша|ипотек|ипота|даму|зейнет|пенси|"
    r"кәсіп|касип|төлем|толем|сома|пайыз|млн|тенге|рефинанс|"
    r"кепіл|кепил|жеке|бизнес|залог|қарыз",
    re.IGNORECASE,
)
JUNK_PREFIX = re.compile(r"^іздеу", re.I)
LEMMA_LINE = re.compile(r"^([^:;\s!<>]+):")
WORD_RE = re.compile(r"[\wа-яёәіңғүұқөһ]+", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-zA-Z]{3,}")
DIGIT_HEAVY = re.compile(r"\d{4,}")


def normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def phrase_key(text: str) -> str:
    return normalize_phrase(text).lower()


def is_clean_word(word: str) -> bool:
    if len(word) < 2 or len(word) > 45:
        return False
    if JUNK_PREFIX.match(word):
        return False
    if DIGIT_HEAVY.search(word):
        return False
    if LATIN_RE.search(word) and not FINANCE_RE.search(word):
        return False
    lower = word.lower()
    if any(c in KK_CHARS for c in lower):
        return True
    return bool(FINANCE_RE.search(word))


def is_clean_phrase(text: str, *, min_len: int = 12, max_len: int = 180) -> bool:
    t = normalize_phrase(text)
    if not (min_len <= len(t) <= max_len):
        return False
    if not any(c in KK_CHARS for c in t.lower()):
        return False
    if t.count("?") > 3 or t.count("!") > 3:
        return False
    kk_tokens = WORD_RE.findall(t)
    if not kk_tokens:
        return False
    latin_tokens = sum(1 for w in kk_tokens if LATIN_RE.fullmatch(w))
    if latin_tokens > max(2, len(kk_tokens) // 3):
        return False
    if "«" in t or "»" in t:
        return False
    title_tokens = sum(1 for w in kk_tokens if len(w) > 2 and w[0].isupper())
    if title_tokens > 3 or t.count(",") > 3:
        return False
    return True


def score_phrase(text: str, freq: int = 1, *, finance: bool = False, source: str = "") -> float:
    t = normalize_phrase(text)
    score = float(freq)
    n = len(t)
    if 25 <= n <= 90:
        score += 2.0
    elif 15 <= n < 25:
        score += 1.0
    if finance or FINANCE_RE.search(t):
        score += 8.0
    if "?" in t:
        score += 0.5
    if source in {"kazqad", "builtin", "kazakh_dict"}:
        score += 1.5
    if source == "kazparc":
        score += 2.0
    return score


def read_zip_csv(zpath: Path, inner: str) -> list[str]:
    if not zpath.is_file():
        return []
    with zipfile.ZipFile(zpath) as zf:
        raw = zf.read(inner).decode("utf-8", errors="replace")
    rows = csv.reader(io.StringIO(raw))
    return [r[0].strip() for r in rows if r and r[0].strip()]


def read_csv_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8", errors="replace")
    rows = csv.reader(io.StringIO(raw))
    return [r[0].strip() for r in rows if r and r[0].strip()]


def parse_conll_sentences(path: Path) -> list[str]:
    if not path.is_file():
        return []
    sentences: list[str] = []
    tokens: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            if tokens:
                sentences.append(" ".join(tokens))
                tokens = []
            continue
        parts = line.split()
        if parts:
            tokens.append(parts[0])
    if tokens:
        sentences.append(" ".join(tokens))
    return sentences


def from_kazqad_zip(zpath: Path) -> list[str]:
    if not zpath.is_file():
        return []
    out: list[str] = []
    with zipfile.ZipFile(zpath) as zf:
        for name in zf.namelist():
            if "/topics/" not in name or not name.endswith(".tsv") or "kk" not in name:
                continue
            data = zf.read(name).decode("utf-8", errors="replace")
            for line in data.splitlines():
                if "\t" not in line:
                    continue
                q = line.split("\t", 1)[1].strip()
                if is_clean_phrase(q, min_len=8):
                    out.append(normalize_phrase(q))
    return out


def from_apertium_zip(zpath: Path) -> tuple[set[str], list[str]]:
    words: set[str] = set()
    if not zpath.is_file():
        return words, []
    with zipfile.ZipFile(zpath) as zf:
        data = zf.read("apertium-kaz-main/apertium-kaz.kaz.lexc").decode("utf-8", errors="replace")
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("!") or line.startswith("<"):
            continue
        m = LEMMA_LINE.match(line)
        if not m:
            continue
        w = m.group(1)
        if is_clean_word(w):
            words.add(w)
    return words, []


def from_paraphrases_jsonl(path: Path) -> list[str]:
    if not path.is_file():
        return []
    phrases: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("src", "trg"):
            val = row.get(key)
            if isinstance(val, str) and is_clean_phrase(val):
                phrases.append(normalize_phrase(val))
    return phrases


def from_kazparc_csv(path: Path) -> list[str]:
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8", errors="replace")
    rows = csv.DictReader(io.StringIO(raw))
    out: list[str] = []
    kk_col = None
    if rows.fieldnames:
        for col in rows.fieldnames:
            if col and col.lower() in {"kk", "kazakh", "source_lang"}:
                kk_col = col
                break
        if kk_col is None:
            for col in rows.fieldnames:
                if "kk" in col.lower():
                    kk_col = col
                    break
    if kk_col is None:
        # fallback: second column often kk in 01_kazparc_all_entries
        reader = csv.reader(io.StringIO(raw))
        header = next(reader, None)
        idx = 2 if header and len(header) > 2 else 1
        for row in reader:
            if len(row) > idx:
                t = row[idx].strip()
                if is_clean_phrase(t, min_len=8):
                    out.append(normalize_phrase(t))
        return out

    for row in rows:
        t = (row.get(kk_col) or "").strip()
        if is_clean_phrase(t, min_len=8):
            out.append(normalize_phrase(t))
    return out


def rank_top_phrases(
    buckets: list[tuple[str, list[str], bool]],
    *,
    limit: int = 10_000,
) -> list[dict]:
    """Собрать top-N фраз с приоритетом частоты и домена."""
    freq: Counter[str] = Counter()
    meta: dict[str, dict] = {}

    for source, phrases, finance_boost in buckets:
        for p in phrases:
            key = phrase_key(p)
            if not key:
                continue
            freq[key] += 1
            entry = meta.get(key)
            if entry is None:
                meta[key] = {
                    "text": normalize_phrase(p),
                    "sources": {source},
                    "finance": finance_boost or bool(FINANCE_RE.search(p)),
                }
            else:
                entry["sources"].add(source)
                if finance_boost or FINANCE_RE.search(p):
                    entry["finance"] = True

    scored: list[tuple[float, str]] = []
    for key, count in freq.items():
        m = meta[key]
        src = next(iter(m["sources"]))
        scored.append(
            (
                score_phrase(
                    m["text"],
                    count,
                    finance=m["finance"],
                    source=src,
                ),
                key,
            )
        )

    scored.sort(key=lambda x: (-x[0], x[1]))
    result: list[dict] = []
    seen: set[str] = set()
    for _, key in scored:
        if key in seen:
            continue
        seen.add(key)
        m = meta[key]
        result.append(
            {
                "text": m["text"],
                "freq": freq[key],
                "finance": m["finance"],
                "sources": sorted(m["sources"]),
            }
        )
        if len(result) >= limit:
            break
    return result


def chunk_texts(items: list[str], max_len: int = 350) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    n = 0
    for item in items:
        add = len(item) + 2
        if buf and n + add > max_len:
            chunks.append("; ".join(buf))
            buf, n = [], 0
        buf.append(item)
        n += add
    if buf:
        chunks.append("; ".join(buf))
    return chunks
