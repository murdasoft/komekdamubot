"""Google Gemini client for AI responses - fallback when Groq rate limited."""

import os
import json
from typing import Optional, List, Dict
import httpx

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBX5nT6ytAK7BlfCH_wqB0idWOSE90i7dA")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class GeminiClient:
    """Simple Gemini client for chat completions."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.api_url = f"{GEMINI_API_URL}?key={self.api_key}"
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Send chat messages to Gemini.
        Returns (response_text, error).
        """
        try:
            # Convert messages to Gemini format
            # System prompt goes into system_instruction field
            system_content = ""
            conversation = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                elif msg["role"] == "user":
                    conversation.append({
                        "role": "user",
                        "parts": [{"text": msg["content"]}]
                    })
                elif msg["role"] == "assistant":
                    conversation.append({
                        "role": "model",
                        "parts": [{"text": msg["content"]}]
                    })
            
            # Build request
            payload = {
                "contents": conversation,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 800,
                }
            }
            
            if system_content:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_content}]
                }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                r.raise_for_status()
                result = r.json()
                
                # Extract text
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        return text if text else None, None
                
                return None, "Empty response from Gemini"
                
        except httpx.HTTPStatusError as e:
            err_body = e.response.text
            return None, f"HTTP {e.response.status_code}: {err_body}"
        except Exception as e:
            return None, str(e)


# Singleton instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create Gemini client singleton."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
