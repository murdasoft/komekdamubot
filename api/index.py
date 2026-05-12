"""
Vercel serverless handler entry point.
"""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import handler
    app = handler
except Exception as e:
    import logging
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__name__)
    logger.error(f"Import error: {e}")
    
    # Fallback minimal handler
    from mangum import Mangum
    from fastapi import FastAPI
    
    fallback_app = FastAPI()
    
    @fallback_app.get("/")
    async def root():
        return {"status": "error", "message": str(e)}
    
    @fallback_app.get("/health")
    async def health():
        return {"status": "error", "message": str(e)}
    
    app = Mangum(fallback_app, lifespan="off")
