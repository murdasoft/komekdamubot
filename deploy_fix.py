#!/usr/bin/env python3
import os
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

TOKEN = "vcp_2BD1BHAeiK1ptIorJ30XP0VAo2pswVSblnmyGoE0Bl7SjRyI4H3USa38"
PROJECT_ID = "prj_m1mEnj8dwl0kk0g9spQEoXNgimkJ"

def collect_files():
    files = {}
    for pattern in ["api/*.py", "app/**/*.py", "requirements.txt", "vercel.json", "pytest.ini", "README.md"]:
        for file in Path(".").glob(pattern):
            if "__pycache__" not in str(file) and ".pyc" not in str(file) and ".git" not in str(file):
                try:
                    content = file.read_bytes()
                    files[str(file)] = base64.b64encode(content).decode()
                except Exception as e:
                    print(f"Skip {file}: {e}")
    return files

def deploy():
    files = collect_files()
    print(f"Deploying {len(files)} files...")
    
    env_list = [
        {"key": "GROQ_API_KEY", "value": "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", "type": "plain", "target": ["production"]},
        {"key": "TELEGRAM_BOT_TOKEN", "value": "8747075596:AAEu-Ni-ZzcVGflZW0E9Lm2bv8nf8llezR8", "type": "plain", "target": ["production"]},
        {"key": "TELEGRAM_WEBHOOK_SECRET", "value": "vcp_7iU3jVDFxx9mmSQKph0Ic58Y2qaM6h51owoUmnxBtcFMcMCIMb3Q2hYT", "type": "plain", "target": ["production"]},
        {"key": "GREEN_API_INSTANCE_ID", "value": "7107617125", "type": "plain", "target": ["production"]},
        {"key": "GREEN_API_TOKEN", "value": "808a69bc97f840e9af41e271cec089d49b50fc127b93491597", "type": "plain", "target": ["production"]},
        {"key": "WEBHOOK_BASE_URL", "value": "https://komek-damu-ipu6n4hk7-murdasoft-9183s-projects.vercel.app", "type": "plain", "target": ["production"]},
        {"key": "PYTHONPATH", "value": ".", "type": "plain", "target": ["production"]},
    ]
    
    payload = {
        "name": "komek-damu-bot",
        "project": PROJECT_ID,
        "target": "production",
        "files": [{"file": k, "data": v} for k, v in files.items()],
    }
    
    req = urllib.request.Request(
        "https://api.vercel.com/v13/deployments",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            print(f"✅ Deployment created!")
            print(f"   URL: {data.get('url')}")
            print(f"   ID: {data.get('id')}")
            return data.get('url')
    except urllib.error.HTTPError as e:
        print(f"❌ Error: {e.read().decode()}")
        return None

if __name__ == "__main__":
    deploy()
