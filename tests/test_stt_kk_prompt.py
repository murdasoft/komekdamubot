from app.bot.kk_stt_lexicon import build_kk_whisper_prompt, get_finance_words


def test_prompt_contains_kazakh_phrases():
    p = build_kk_whisper_prompt()
    assert "несие" in p
    assert "KOMEK DAMU" in p
    assert len(p) <= 2200
    assert len(get_finance_words(10)) >= 5


def test_prompt_variants_differ():
    a = build_kk_whisper_prompt(variant=0)
    b = build_kk_whisper_prompt(variant=1)
    assert a != b or "Сөздер" in a


def test_prompt_session_borrower_hint():
    session = {"awaiting_borrower_type": True}
    p = build_kk_whisper_prompt(session)
    assert "ЖК" in p or "ИП" in p
