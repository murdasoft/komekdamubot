#!/bin/bash
# Full bootstrap for fresh Hetzner CX33 Helsinki
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
NEW_IP="${1:-204.168.223.9}"
SSLIP_HOST="${NEW_IP//./-}.sslip.io"

echo "=== Base packages ==="
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx certbot python3-certbot-nginx ffmpeg curl git

echo "=== Ollama ==="
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment=OLLAMA_KEEP_ALIVE=5m
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_MAX_LOADED_MODELS=1
EOF
systemctl daemon-reload
systemctl enable ollama
systemctl start ollama
sleep 2
ollama pull qwen2.5:3b

echo "=== Whisper API ==="
python3 -m venv /opt/whisper-env
/opt/whisper-env/bin/pip install -q fastapi uvicorn openai-whisper

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
        return JSONResponse({"text": text, "language": result.get("language") or lang or "ru"})
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

cat > /etc/systemd/system/whisper-api.service << 'EOF'
[Unit]
Description=Whisper Transcription API
After=network.target

[Service]
Type=simple
Environment=WHISPER_MODEL=small
ExecStart=/opt/whisper-env/bin/python /opt/whisper-api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable whisper-api
systemctl start whisper-api

echo "=== Firewall ==="
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp

echo "=== Bot venv ==="
cd /opt/komek-damu-bot
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

cat > /etc/systemd/system/komek-damu-bot.service << 'EOF'
[Unit]
Description=KOMEK DAMU Bot
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=/opt/komek-damu-bot
EnvironmentFile=/opt/komek-damu-bot/.env
ExecStart=/opt/komek-damu-bot/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "=== Nginx ==="
cat > /etc/nginx/sites-available/komek-damu-bot << EOF
server {
    listen 80;
    server_name ${SSLIP_HOST};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 180s;
    }
}
EOF
ln -sf /etc/nginx/sites-available/komek-damu-bot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "${SSLIP_HOST}" --non-interactive --agree-tos --register-unsafely-without-email --redirect || true

systemctl daemon-reload
systemctl enable komek-damu-bot
systemctl restart komek-damu-bot

echo "=== Done: https://${SSLIP_HOST} ==="
free -h | head -2
systemctl is-active ollama whisper-api komek-damu-bot nginx
curl -s http://127.0.0.1:8000/health; echo
