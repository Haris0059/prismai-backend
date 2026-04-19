from typing import AsyncGenerator
import httpx
from app.providers.base import TimeoutError, map_httpx_error

class GeminiAdapter:
    def __init__(self, api_key: str | None):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(self, model: str, messages: list[dict]) -> tuple[dict, str]:
        # Google Gemini v1beta API format
        # Model needs to be something like "gemini-1.5-pro" or similar.
        url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
        
        # Transform standard role 'assistant' to 'model' for Gemini
        gemini_messages = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        body = {
            "contents": gemini_messages
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return data, text
            except httpx.HTTPStatusError as e:
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                raise TimeoutError("Gemini API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        # Placeholder for Phase 5
        yield ""
