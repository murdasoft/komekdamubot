"""STT: қазақша — приоритет."""

from app.bot.voice_stt import (
    _pick_best_candidate,
    _score_transcript,
    _stt_prefer_kk,
)


def test_prefer_kk_by_default():
    assert _stt_prefer_kk({}) is True
    assert _stt_prefer_kk({"lang": "kk", "lang_locked": False}) is True


def test_prefer_ru_only_when_locked():
    assert _stt_prefer_kk({"lang": "ru", "lang_locked": True}) is False


def test_score_favors_kk_hint():
    kk_score = _score_transcript("несие керек", "kk", prefer_kk=True)
    ru_score = _score_transcript("нужен кредит", "ru", prefer_kk=True)
    assert kk_score >= ru_score - 5


def test_pick_kk_on_close_scores():
    candidates = [
        ("раз два три", "ru", 40),
        ("несие керек", "kk", 38),
    ]
    text, lang = _pick_best_candidate(candidates, "kk", prefer_kk=True)
    assert text == "несие керек"
    assert lang == "kk"
