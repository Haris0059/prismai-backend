from typing import AsyncGenerator
import httpx
from app.providers.base import TimeoutError, map_httpx_error

class AnthropicAdapter:
    def __init__(self, api_key: str | None):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        self.api_key = api_key
        self.url = "https://api.anthropic.com/v1/messages"

    async def complete(self, model: str, messages: list[dict]) -> tuple[dict, str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 1024,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data, data["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                raise TimeoutError("Anthropic API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        # Placeholder for Phase 5
        yield ""
