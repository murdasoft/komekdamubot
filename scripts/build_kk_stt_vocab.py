#!/usr/bin/env python3
"""
Собрать казахский словарь и top-10k фраз для STT/бота.

Источники (локальные zip + data/kk_datasets/ после download_kk_datasets.py):
  - kazakh_words, apertium-kaz, KazQAD
  - KazNERD, chatgpt-paraphrases-kz, KazParC (если скачан)

Запуск:
  python scripts/download_kk_datasets.py   # один раз
  python scripts/build_kk_stt_vocab.py

→ app/bot/data/kk_dictionary.json
→ app/bot/data/kk_phrases_top10k.json
→ app/bot/data/kk_stt_vocab.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kk_corpus_utils import (  # noqa: E402
    FINANCE_RE,
    chunk_texts,
    from_apertium_zip,
    from_kazparc_csv,
    from_kazqad_zip,
    from_paraphrases_jsonl,
    is_clean_phrase,
    is_clean_word,
    parse_conll_sentences,
    rank_top_phrases,
    read_csv_file,
    read_zip_csv,
)

DATA_DIR = ROOT / "data" / "kk_datasets"
OUT_DIR = ROOT / "app" / "bot" / "data"
DICT_OUT = OUT_DIR / "kk_dictionary.json"
PHRASES_OUT = OUT_DIR / "kk_phrases_top10k.json"
VOCAB_OUT = OUT_DIR / "kk_stt_vocab.json"

BUILTIN_PHRASES = [
    "Сәлеметсіз бе, мен несие алғым келеді",
    "Несие керек па",
    "Жеке несие алу",
    "Ипотека керек",
    "Кәсіпкерге кредит",
    "DAMU 12,6 пайызы",
    "Қайта қаржыландыру",
    "Банктен несие",
    "Ақша керек",
    "Зейнетақымен несие",
    "Мен несие алғым келеді",
    "Қанша пайызбен бересіз",
    "Ипотека бойынша несие",
    "Кәсіп ашуға кредит керек",
    "Рефинансирование жасау керек",
]


def _collect_words() -> tuple[list[str], list[str], dict]:
    sources: dict = {}

    # kazakh_words: zip или скачанный CSV
    zip_words = read_zip_csv(ROOT / "kazakh_words-master.zip", "kazakh_words-master/words.csv")
    csv_words = read_csv_file(DATA_DIR / "kazakh_words" / "words.csv")
    raw_words = zip_words or csv_words
    sources["kazakh_words"] = len(raw_words)

    all_words: set[str] = {w for w in raw_words if is_clean_word(w)}
    finance_words: set[str] = {w for w in all_words if FINANCE_RE.search(w)}

    apertium_words, _ = from_apertium_zip(ROOT / "apertium-kaz-main.zip")
    sources["apertium"] = len(apertium_words)
    all_words |= apertium_words
    finance_words |= {w for w in apertium_words if FINANCE_RE.search(w)}

    return sorted(all_words), sorted(finance_words), sources


def _collect_phrase_buckets() -> list[tuple[str, list[str], bool]]:
    buckets: list[tuple[str, list[str], bool]] = []

    buckets.append(("builtin", BUILTIN_PHRASES, True))

    try:
        from app.bot.kazakh_phrases import KK_PHRASES_EXTENDED

        buckets.append(("kazakh_dict", list(KK_PHRASES_EXTENDED), True))
    except ImportError:
        pass

    kazqad = from_kazqad_zip(ROOT / "KazQAD-main.zip")
    buckets.append(("kazqad", kazqad, False))

    kaznerd_dir = DATA_DIR / "kaznerd"
    kaznerd_phrases: list[str] = []
    for name in ("IOB2_train.txt", "IOB2_valid.txt", "IOB2_test.txt"):
        for sent in parse_conll_sentences(kaznerd_dir / name):
            if is_clean_phrase(sent, min_len=8):
                kaznerd_phrases.append(sent)
    buckets.append(("kaznerd", kaznerd_phrases, False))

    para = from_paraphrases_jsonl(DATA_DIR / "paraphrases" / "train_sample.jsonl")
    buckets.append(("paraphrases_kz", para, False))

    kazparc = from_kazparc_csv(DATA_DIR / "kazparc" / "01_kazparc_all_entries.csv")
    buckets.append(("kazparc", kazparc, False))

    return buckets


def main() -> None:
    all_words, finance_words, word_sources = _collect_words()
    buckets = _collect_phrase_buckets()
    top_phrases = rank_top_phrases(buckets, limit=10_000)

    finance_phrases = [p["text"] for p in top_phrases if p["finance"]]
    general_phrases = [p["text"] for p in top_phrases if not p["finance"]]

    # STT: приоритет финансовым словам + коротким леммам
    priority_finance = [
        w for w in finance_words if 3 <= len(w) <= 24 and FINANCE_RE.search(w)
    ][:2000]
    extra_finance = [w for w in finance_words if w not in priority_finance][:800]
    stt_words = priority_finance + extra_finance

    stt_phrases = (finance_phrases[:120] + general_phrases[:80])[:200]
    if len(stt_phrases) < 50:
        stt_phrases = [p["text"] for p in top_phrases[:200]]

    phrase_texts = [p["text"] for p in top_phrases]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    DICT_OUT.write_text(
        json.dumps(
            {
                "version": 1,
                "word_count": len(all_words),
                "finance_word_count": len(finance_words),
                "sources": word_sources,
                "words": all_words,
                "finance_words": finance_words,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    PHRASES_OUT.write_text(
        json.dumps(
            {
                "version": 1,
                "phrase_count": len(top_phrases),
                "sources": {name: len(phrs) for name, phrs, _ in buckets},
                "phrases": top_phrases,
                "phrase_chunks": chunk_texts(phrase_texts, max_len=350),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    vocab = {
        "version": 3,
        "sources": [
            "kazakh_words",
            "apertium-kaz",
            "KazQAD",
            "KazNERD",
            "paraphrases-kz",
            "kazparc (optional)",
        ],
        "dictionary_words": len(all_words),
        "finance_word_count": len(stt_words),
        "phrase_count": len(stt_phrases),
        "top_phrases_total": len(top_phrases),
        "finance_words": stt_words[:2000],
        "phrases": stt_phrases,
        "prompt_chunks": chunk_texts(stt_words[:1200], max_len=400),
        "phrase_chunks": chunk_texts(stt_phrases, max_len=350),
        "top_phrase_chunks": chunk_texts(phrase_texts[:3000], max_len=380),
    }
    VOCAB_OUT.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Dictionary: {DICT_OUT} ({len(all_words)} words, {len(finance_words)} finance)")
    print(f"Top phrases: {PHRASES_OUT} ({len(top_phrases)} phrases)")
    print(f"STT vocab: {VOCAB_OUT} ({len(stt_words)} words, {len(stt_phrases)} STT phrases)")


if __name__ == "__main__":
    main()
