#!/usr/bin/env python3
"""
Deploy KOMEK DAMU Bot to Vercel using REST API.
"""

import os
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

TOKEN = "vcp_2BD1BHAeiK1ptIorJ30XP0VAo2pswVSblnmyGoE0Bl7SjRyI4H3USa38"
PROJECT_NAME = "clean-bot"

def get_project_id():
    """Get project ID by name."""
    req = urllib.request.Request(
        f"https://api.vercel.com/v9/projects/{PROJECT_NAME}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data.get("id")
    except urllib.error.HTTPError as e:
        print(f"Error getting project: {e.read().decode()}")
        return None

def create_deployment():
    """Create deployment with files."""
    # Collect files
    files = {}
    for pattern in ["api/*.py", "app/**/*.py", "requirements.txt", "vercel.json", "pytest.ini", "run_tests.sh", "README.md", "DEPLOY.md"]:
        for file in Path(".").glob(pattern):
            if "__pycache__" not in str(file) and ".pyc" not in str(file) and ".git" not in str(file):
                try:
                    content = file.read_bytes()
                    files[str(file)] = base64.b64encode(content).decode()
                except Exception as e:
                    print(f"Skip {file}: {e}")
    
    print(f"Files to deploy: {len(files)}")
    
    # Prepare payload
    payload = {
        "name": PROJECT_NAME,
        "project": PROJECT_NAME,
        "target": "production",
        "files": [{"file": k, "data": v} for k, v in files.items()],
        "env": {
            "GROQ_API_KEY": "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",
            "GROQ_MODEL": "llama3-70b-8192",
            "GROQ_STT_MODEL": "whisper-large-v3",
            "TELEGRAM_BOT_TOKEN": "8747075596:AAEu-Ni-ZzcVGflZW0E9Lm2bv8nf8llezR8",
            "TELEGRAM_WEBHOOK_SECRET": "vcp_7iU3jVDFxx9mmSQKph0Ic58Y2qaM6h51owoUmnxBtcFMcMCIMb3Q2hYT",
            "GREEN_API_INSTANCE_ID": "7107617125",
            "GREEN_API_TOKEN": "808a69bc97f840e9af41e271cec089d49b50fc127b93491597",
            "GREEN_API_WEBHOOK_TOKEN": "changeme",
            "WEBHOOK_BASE_URL": "https://clean-bot-omega.vercel.app",
            "PYTHONPATH": ".",
        }
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
            return data
    except urllib.error.HTTPError as e:
        print(f"Deploy error: {e.read().decode()}")
        return None

def main():
    print("=" * 50)
    print("KOMEK DAMU Bot - Vercel Deploy")
    print("=" * 50)
    print()
    
    result = create_deployment()
    
    if result:
        print(f"✅ Deployment created!")
        print(f"   ID: {result.get('id')}")
        print(f"   URL: {result.get('url')}")
        print(f"   State: {result.get('readyState')}")
        print()
        print("Check status at:")
        print(f"https://vercel.com/murdasoft-9183/clean-bot/deployments")
    else:
        print("❌ Deployment failed")

if __name__ == "__main__":
    main()
