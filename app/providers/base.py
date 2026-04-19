from typing import Protocol, AsyncIterator
import httpx

class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class RateLimited(ProviderError):
    def __init__(self, message: str = "Rate limited"):
        super().__init__(message, status_code=429)

class BadRequest(ProviderError):
    def __init__(self, message: str = "Bad request"):
        super().__init__(message, status_code=400)

class UpstreamError(ProviderError):
    def __init__(self, message: str = "Upstream error", status_code: int = 502):
        super().__init__(message, status_code=status_code)

class ProviderTimeout(ProviderError):
    def __init__(self, message: str = "Timeout"):
        super().__init__(message, status_code=504)

def map_httpx_error(e: httpx.HTTPStatusError) -> ProviderError:
    status = e.response.status_code
    if status == 429:
        return RateLimited(e.response.text)
    elif 400 <= status < 500:
        return BadRequest(e.response.text)
    elif status == 504:
        return ProviderTimeout(e.response.text)
    else:
        return UpstreamError(e.response.text, status_code=status)

class LLMProvider(Protocol):
    async def complete(self, model: str, messages: list[dict]) -> tuple[dict, str]:
        ...
        
    def stream(self, model: str, messages: list[dict]) -> AsyncIterator[str]:
        ...
