from app.bot.stt_prompt_utils import GROQ_WHISPER_PROMPT_MAX_BYTES, truncate_whisper_prompt


def test_truncate_utf8_kazakh_bytes():
    text = "ә" * 500 + "несие алғым келеді"
    out = truncate_whisper_prompt(text, GROQ_WHISPER_PROMPT_MAX_BYTES)
    assert len(out.encode("utf-8")) <= GROQ_WHISPER_PROMPT_MAX_BYTES
    assert len(out) > 0
