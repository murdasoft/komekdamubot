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

# Try to load full app
try:
    from app.main import app as main_app
    app = main_app
except Exception as e:
    @app.get("/")
    async def root():
        return {"status": "loading", "error": str(e)[:100]}
    
    @app.get("/health")
    async def health():
        return {"status": "loading", "error": str(e)[:100]}

# Create handler for Vercel
handler = Mangum(app, lifespan="off")
