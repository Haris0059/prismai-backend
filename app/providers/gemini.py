from typing import AsyncGenerator
import httpx
import time
import json
import structlog
from app.providers.base import ProviderTimeout, map_httpx_error

logger = structlog.get_logger(__name__)

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

        start_time = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()
                latency_ms = int((time.time() - start_time) * 1000)
                usage = data.get("usageMetadata", {})
                logger.info(
                    "provider_call",
                    provider="gemini",
                    model=model,
                    prompt_tokens=usage.get("promptTokenCount"),
                    completion_tokens=usage.get("candidatesTokenCount"),
                    latency_ms=latency_ms,
                    status="success"
                )
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return data, text
            except httpx.HTTPStatusError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="gemini", model=model, latency_ms=latency_ms, status="error", error=e.response.text)
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="gemini", model=model, latency_ms=latency_ms, status="timeout")
                raise TimeoutError("Gemini API timeout")

    async def stream(self, model: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/{model}:streamGenerateContent?alt=sse&key={self.api_key}"
        
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

        start_time = time.time()
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=None)) as client:
            try:
                async with client.stream("POST", url, json=body) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("candidates") and len(data["candidates"]) > 0:
                                    candidate = data["candidates"][0]
                                    if "content" in candidate and "parts" in candidate["content"]:
                                        yield candidate["content"]["parts"][0]["text"]
                            except json.JSONDecodeError:
                                pass
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info("provider_call", provider="gemini", model=model, latency_ms=latency_ms, status="success")
            except httpx.HTTPStatusError as e:
                await e.response.aread()
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="gemini", model=model, latency_ms=latency_ms, status="error", error=e.response.text)
                raise map_httpx_error(e)
            except httpx.TimeoutException:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("provider_call", provider="gemini", model=model, latency_ms=latency_ms, status="timeout")
                raise ProviderTimeout("Gemini API timeout")
