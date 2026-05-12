"""
Vercel serverless handler entry point.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Lazy import to avoid cold start errors
def get_app():
    from app.main import handler
    return handler

app = get_app()
