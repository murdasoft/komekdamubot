#!/usr/bin/env python3
"""
Force deploy KOMEK DAMU Bot to Vercel.
Uses Vercel REST API with token.
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

# Configuration
TOKEN = os.getenv("VERCEL_TOKEN", "")
PROJECT_ID = "prj_xxxxxxxxxxxxx"  # Replace if known
WEBHOOK_URL = "https://clean-bot-omega.vercel.app"

# Environment variables to set
ENV_VARS = {
    "GROQ_API_KEY": "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",
    "GROQ_MODEL": "llama3-70b-8192",
    "GROQ_STT_MODEL": "whisper-large-v3",
    "TELEGRAM_BOT_TOKEN": "8747075596:AAEu-Ni-ZzcVGflZW0E9Lm2bv8nf8llezR8",
    "TELEGRAM_WEBHOOK_SECRET": "vcp_7iU3jVDFxx9mmSQKph0Ic58Y2qaM6h51owoUmnxBtcFMcMCIMb3Q2hYT",
    "WEBHOOK_BASE_URL": WEBHOOK_URL,
    "PYTHONPATH": ".",
}


def create_deployment():
    """Create deployment via Vercel API."""
    if not TOKEN:
        print("ERROR: Set VERCEL_TOKEN environment variable")
        print("Get token: https://vercel.com/account/tokens")
        return False
    
    # Build file list
    files = {}
    for pattern in ["api/*.py", "app/**/*.py", "requirements.txt", "vercel.json"]:
        for file in Path(".").glob(pattern):
            if "__pycache__" not in str(file) and ".pyc" not in str(file):
                try:
                    content = file.read_bytes()
                    files[str(file)] = base64.b64encode(content).decode()
                except Exception as e:
                    print(f"Skip {file}: {e}")
    
    # Deployment payload
    payload = {
        "name": "clean-bot",
        "project": "clean-bot",
        "target": "production",
        "files": [{"file": k, "data": v} for k, v in files.items()],
        "env": ENV_VARS,
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
            result = json.loads(resp.read())
            print(f"✅ Deployment created!")
            print(f"   URL: {result.get('url')}")
            print(f"   ID: {result.get('id')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ Deploy failed: {e.code}")
        print(e.read().decode())
        return False


def main():
    print("=" * 50)
    print("Force Deploy KOMEK DAMU Bot")
    print("=" * 50)
    print()
    
    if not TOKEN:
        print("Quick deploy options:")
        print()
        print("1. Git push to existing repo:")
        print("   cd komek-damu-bot")
        print("   git remote add origin https://github.com/murdasoft/clean-bot.git")
        print("   git push -f origin main")
        print()
        print("2. Vercel Dashboard:")
        print("   https://vercel.com/murdasoft-9183/clean-bot")
        print("   → Git → Select repo → Deploy")
        print()
        print("3. Set VERCEL_TOKEN and run:")
        print("   export VERCEL_TOKEN=your_token")
        print("   python3 force_deploy.py")
        print()
        
        # Print env vars for manual setup
        print("Required Environment Variables:")
        for k, v in ENV_VARS.items():
            print(f"  {k}={v}")
        return
    
    if create_deployment():
        print()
        print("Next steps:")
        print(f"  1. Visit {WEBHOOK_URL}")
        print(f"  2. Visit {WEBHOOK_URL}/setup to set webhook")
        print(f"  3. Test bot on Telegram")


if __name__ == "__main__":
    main()
