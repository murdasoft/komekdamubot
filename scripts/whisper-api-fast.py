"""Fast Whisper API using faster-whisper (4x faster than openai-whisper on CPU)."""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uvicorn
import os
import tempfile

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
INITIAL_PROMPT = (
    "KOMEK DAMU. Кредит, ипотека, рефинансирование, DAMU 12,6%, госипотека 2%, "
    "бизнес кредит, потребительский, тенге, ставка, консультация бесплатная. "
    "Несие, ипотека, қайта қаржыландыру, мемлекеттік ипотека, бизнес несиесі."
)

app = FastAPI(title="Fast Whisper API")
_model = None


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = Form(None)):
    suffix = ".ogg"
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        temp_path = tmp.name
    try:
        lang = language if language in ("ru", "kk", "en") else None
        segments, info = get_model().transcribe(
            temp_path,
            language=lang,
            initial_prompt=INITIAL_PROMPT,
            beam_size=1,
            best_of=1,
        )
        text = "".join(s.text for s in segments).strip()
        return JSONResponse({
            "text": text,
            "language": info.language or lang or "ru",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
async def health():
    return {"status": "ok", "model": f"faster-whisper-{WHISPER_MODEL}"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11435)
