"""
Vercel serverless handler entry point.
"""

from app.main import handler

# Export the Mangum handler for Vercel
app = handler
