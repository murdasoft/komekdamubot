from app.bot.kk_stt_lexicon import (
    build_kk_whisper_prompt_compact,
    build_kk_whisper_prompt_for_duration,
    build_kk_whisper_prompt_standard,
    pick_stt_prompt_profile,
)


def test_profile_by_duration():
    assert pick_stt_prompt_profile(2.0, 0) == "compact"
    assert pick_stt_prompt_profile(3.9, 0) == "compact"
    assert pick_stt_prompt_profile(6.0, 0) == "standard"
    assert pick_stt_prompt_profile(14.0, 0) == "standard"
    assert pick_stt_prompt_profile(20.0, 0) == "rich"
    assert pick_stt_prompt_profile(45.0, 0) == "rich"


def test_profile_from_bytes_when_no_duration():
    assert pick_stt_prompt_profile(None, 4000) == "compact"
    assert pick_stt_prompt_profile(None, 20000) == "standard"
    assert pick_stt_prompt_profile(None, 60000) == "rich"


def test_prompt_lengths_scale_with_profile():
    short = build_kk_whisper_prompt_for_duration(duration_sec=2.0)
    mid = build_kk_whisper_prompt_for_duration(duration_sec=8.0)
    long = build_kk_whisper_prompt_for_duration(duration_sec=30.0)
    assert len(short) <= 750
    assert 850 <= len(mid) <= 1250
    assert len(long) >= 1300
    assert len(long) <= 2200


def test_standard_between_compact_and_full():
    c = build_kk_whisper_prompt_compact()
    s = build_kk_whisper_prompt_standard()
    assert len(s) > len(c)
    assert "несие" in s
