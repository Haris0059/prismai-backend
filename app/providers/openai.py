from typing import AsyncGenerator
import httpx
from app.providers.base import TimeoutError, map_httpx_error

class OpenAIAdapter:
    def __init__(self, api_key: str | None):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        self.api_key = api_key
        self.url = "https://api.openai.com/v1/chat/completions"

    async def complete(self, model: str, messages: list[dict]) -> tuple[dict, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data, data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                raise TimeoutError("OpenAI API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        # Placeholder for Phase 5
        yield ""
