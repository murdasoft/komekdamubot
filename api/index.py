"""
Vercel serverless handler entry point.
"""

from fastapi import FastAPI
from mangum import Mangum
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create FastAPI app
app = FastAPI()
_load_error = None

# Try to load full app
try:
    from app.main import app as main_app
    app = main_app
except Exception as e:
    _load_error = e
    @app.get("/")
    async def root():
        return {"status": "loading", "error": str(_load_error)[:500] if _load_error else "unknown"}
    
    @app.get("/health")
    async def health():
        return {"status": "loading", "error": str(_load_error)[:500] if _load_error else "unknown"}

# Create handler for Vercel
handler = Mangum(app, lifespan="off")
