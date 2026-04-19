from typing import AsyncGenerator
import httpx
import time
import structlog
from app.providers.base import TimeoutError, map_httpx_error

logger = structlog.get_logger(__name__)

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

        start_time = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
                latency_ms = int((time.time() - start_time) * 1000)
                usage = data.get("usage", {})
                logger.info(
                    "provider_call",
                    provider="openai",
                    model=model,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    latency_ms=latency_ms,
                    status="success"
                )
                return data, data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="openai", model=model, latency_ms=latency_ms, status="error", error=e.response.text)
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="openai", model=model, latency_ms=latency_ms, status="timeout")
                raise TimeoutError("OpenAI API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        start_time = time.time()
        # Placeholder for Phase 5
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info("provider_call", provider="openai", model=model, latency_ms=latency_ms, status="success")
        yield ""
