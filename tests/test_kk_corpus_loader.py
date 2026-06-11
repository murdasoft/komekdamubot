"""KK corpus loader — local fallback."""

from app.kk_corpus_loader import load_corpus


def test_load_stt_vocab_local(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("KK_CORPUS_USE_BLOB", "false")
    data = load_corpus("stt_vocab")
    assert data.get("finance_words") or data.get("phrases")
