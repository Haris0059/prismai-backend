from app.core.settings import settings
from app.providers.base import LLMProvider
from app.providers.anthropic import AnthropicAdapter
from app.providers.openai import OpenAIAdapter
from app.providers.gemini import GeminiAdapter
import structlog

logger = structlog.get_logger(__name__)

PROVIDERS: dict[str, LLMProvider] = {}

try:
    PROVIDERS["anthropic"] = AnthropicAdapter(settings.anthropic_api_key)
except ValueError as e:
    logger.warning("Failed to initialize AnthropicAdapter", error=str(e))

try:
    PROVIDERS["openai"] = OpenAIAdapter(settings.openai_api_key)
except ValueError as e:
    logger.warning("Failed to initialize OpenAIAdapter", error=str(e))

try:
    PROVIDERS["gemini"] = GeminiAdapter(settings.gemini_api_key)
except ValueError as e:
    logger.warning("Failed to initialize GeminiAdapter", error=str(e))
