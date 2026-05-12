#!/usr/bin/env python3
"""
Deploy KOMEK DAMU Bot to Vercel.
Uses Vercel REST API with deploy hook.
"""

import os
import sys
import json
import subprocess
import tempfile
import zipfile
import urllib.request
from pathlib import Path

# Vercel settings
VERCEL_TOKEN = os.getenv("VERCEL_TOKEN", "")  # Get from vercel.com/account/tokens
PROJECT_ID = "prj_xxxxxxxxxxxx"  # Replace with your Vercel project ID
DEPLOY_HOOK = "vcp_7iU3jVDFxx9mmSQKph0Ic58Y2qaM6h51owoUmnxBtcFMcMCIMb3Q2hYT"
WEBHOOK_URL = "https://clean-bot-omega.vercel.app"

def create_zip():
    """Create deployment archive."""
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    
    with zipfile.ZipFile(temp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add all Python files
        for pattern in ["api/*.py", "app/**/*.py", "requirements.txt", "vercel.json"]:
            for file in Path(".").glob(pattern):
                if "__pycache__" not in str(file):
                    arcname = str(file).replace("./", "")
                    zf.write(file, arcname)
                    print(f"Added: {arcname}")
    
    return temp.name

def deploy_with_hook():
    """Trigger deploy using deploy hook."""
    hook_url = f"{WEBHOOK_URL}/api/deploy-hook/{DEPLOY_HOOK}"
    
    print(f"Triggering deploy via hook...")
    try:
        req = urllib.request.Request(
            hook_url,
            data=b"",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            print(f"Hook response: {resp.status}")
            return True
    except Exception as e:
        print(f"Hook failed: {e}")
        return False

def set_env_vars():
    """Set environment variables via Vercel CLI or API."""
    env_vars = {
        "GROQ_API_KEY": "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",
        "TELEGRAM_BOT_TOKEN": "8747075596:AAEu-Ni-ZzcVGflZW0E9Lm2bv8nf8llezR8",
        "TELEGRAM_WEBHOOK_SECRET": DEPLOY_HOOK,
        "WEBHOOK_BASE_URL": WEBHOOK_URL,
    }
    
    print("\nSet these environment variables in Vercel Dashboard:")
    print("https://vercel.com/murdasoft-9183/clean-bot/settings/environment-variables")
    print()
    for key, value in env_vars.items():
        print(f"{key}={value}")
    print()

def main():
    print("=" * 50)
    print("KOMEK DAMU Bot - Vercel Deploy")
    print("=" * 50)
    print()
    
    # Check if we're in right directory
    if not Path("api/index.py").exists():
        print("ERROR: Run this script from komek-damu-bot directory")
        sys.exit(1)
    
    # Show instructions
    print("Deploy options:")
    print()
    print("1. AUTO DEPLOY (recommended):")
    print("   git push to GitHub → Vercel auto-deploys")
    print()
    print("2. MANUAL via Vercel CLI:")
    print("   npm i -g vercel")
    print("   vercel --prod")
    print()
    print("3. MANUAL via Dashboard:")
    print("   Upload to https://vercel.com/new")
    print()
    
    # Show env vars needed
    set_env_vars()
    
    print("After deploy, set webhook:")
    print(f"   GET {WEBHOOK_URL}/setup")
    print()
    print("Test bot:")
    print("   Write to @YourBot on Telegram")

if __name__ == "__main__":
    main()
