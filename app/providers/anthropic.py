from typing import AsyncGenerator
import httpx
import time
import structlog
from app.providers.base import TimeoutError, map_httpx_error

logger = structlog.get_logger(__name__)

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
                    provider="anthropic",
                    model=model,
                    prompt_tokens=usage.get("input_tokens"),
                    completion_tokens=usage.get("output_tokens"),
                    latency_ms=latency_ms,
                    status="success"
                )
                return data, data["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="anthropic", model=model, latency_ms=latency_ms, status="error", error=e.response.text)
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="anthropic", model=model, latency_ms=latency_ms, status="timeout")
                raise ProviderTimeout("Anthropic API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": 1024,
            "messages": messages,
            "stream": True,
        }

        start_time = time.time()
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=None)) as client:
            try:
                async with client.stream("POST", self.url, json=body, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str != "[DONE]":
                                try:
                                    data = json.loads(data_str)
                                    if data.get("type") == "content_block_delta":
                                        yield data["delta"]["text"]
                                except json.JSONDecodeError:
                                    pass
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info("provider_call", provider="anthropic", model=model, latency_ms=latency_ms, status="success")
            except httpx.HTTPStatusError as e:
                await e.response.aread()
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="anthropic", model=model, latency_ms=latency_ms, status="error", error=e.response.text)
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="anthropic", model=model, latency_ms=latency_ms, status="timeout")
                raise ProviderTimeout("Anthropic API timeout")
