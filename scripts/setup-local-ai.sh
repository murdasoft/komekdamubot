#!/bin/bash
# Run on Hetzner as root after resize to CX33 (8GB) recommended; works on CX23 with swap
set -euo pipefail

echo "=== Swap 4GB ==="
if [ ! -f /swapfile ] || [ "$(stat -c%s /swapfile 2>/dev/null || echo 0)" -lt 4000000000 ]; then
  swapoff /swapfile 2>/dev/null || true
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "=== Ollama tuning ==="
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment=OLLAMA_KEEP_ALIVE=3m
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_MAX_LOADED_MODELS=1
EOF

echo "=== Whisper API (small, lazy load) ==="
cat > /opt/whisper-api.py << 'EOF'
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import whisper
import uvicorn
import os

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
INITIAL_PROMPT = (
    "Кредит, ипотека, ДАМУ, несие. Несие, ипотека, кредит, консультация. "
    "Сәлем, несие, ипотека."
)

app = FastAPI(title="Whisper Transcription API")
_model = None


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(WHISPER_MODEL, device="cpu")
    return _model


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = Form(None)):
    ext = ".ogg"
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    temp_path = f"/tmp/whisper_{os.getpid()}{ext}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        lang = language if language in ("ru", "kk", "en") else None
        result = get_model().transcribe(
            temp_path, language=lang, fp16=False, initial_prompt=INITIAL_PROMPT
        )
        text = (result.get("text") or "").strip()
        return JSONResponse({
            "text": text,
            "language": result.get("language") or lang or "ru",
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
async def health():
    return {"status": "ok", "model": f"whisper-{WHISPER_MODEL}"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11435)
EOF

mkdir -p /etc/systemd/system/whisper-api.service.d
cat > /etc/systemd/system/whisper-api.service.d/override.conf << 'EOF'
[Service]
Environment=WHISPER_MODEL=small
ExecStart=
ExecStart=/opt/whisper-env/bin/python /opt/whisper-api.py
EOF

systemctl daemon-reload
systemctl enable ollama whisper-api
systemctl restart ollama
sleep 3
systemctl restart whisper-api
sleep 5

if [ -f /opt/komek-damu-bot/.env ]; then
  sed -i 's/^AI_PROVIDER=.*/AI_PROVIDER=local/' /opt/komek-damu-bot/.env
  grep -q '^LOCAL_LLM_BASE_URL=' /opt/komek-damu-bot/.env || echo 'LOCAL_LLM_BASE_URL=http://127.0.0.1:11434' >> /opt/komek-damu-bot/.env
  grep -q '^LOCAL_WHISPER_URL=' /opt/komek-damu-bot/.env || echo 'LOCAL_WHISPER_URL=http://127.0.0.1:11435' >> /opt/komek-damu-bot/.env
  systemctl restart komek-damu-bot
fi

echo "=== Status ==="
free -h | head -2
systemctl is-active ollama whisper-api komek-damu-bot
curl -s http://127.0.0.1:11434/api/tags | head -c 120; echo
curl -s http://127.0.0.1:11435/health; echo
curl -s http://127.0.0.1:8000/health; echo
