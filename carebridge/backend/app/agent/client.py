import logging
import asyncio
from typing import List, Dict, Any, Optional
from groq import AsyncGroq, RateLimitError, APIConnectionError, APIStatusError
from app.core.config import settings

logger = logging.getLogger("carebridge.agent.client")

PRIMARY_MODEL = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

_client: Optional[AsyncGroq] = None


def get_groq_client() -> Optional[AsyncGroq]:
    global _client
    if _client is not None:
        return _client
    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("GROQ_API_KEY not configured. Running agent in fallback/mock mode.")
        return None
    _client = AsyncGroq(api_key=api_key)
    return _client


async def chat_completion_with_fallback(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto",
    temperature: float = 0.1,
) -> Any:
    """Executes a chat completion call with automatic primary -> fallback model switching on rate limits."""
    client = get_groq_client()
    if not client:
        raise RuntimeError("GROQ_CLIENT_UNAVAILABLE: No API key configured.")

    kwargs: Dict[str, Any] = {
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    # Attempt 1: Primary Model (llama-3.3-70b-versatile)
    try:
        response = await client.chat.completions.create(
            model=PRIMARY_MODEL,
            **kwargs,
        )
        return response
    except RateLimitError as e:
        logger.warning(f"Groq RateLimit on primary model '{PRIMARY_MODEL}': {e}. Switching to fallback '{FALLBACK_MODEL}'.")
    except APIStatusError as e:
        if e.status_code == 429:
            logger.warning(f"Groq 429 status on primary model. Switching to fallback '{FALLBACK_MODEL}'.")
        else:
            logger.error(f"Groq API error on primary model: {e}")
            raise
    except APIConnectionError as e:
        logger.warning(f"Groq connection error on primary model: {e}. Retrying with fallback model.")

    # Attempt 2: Fallback Model (llama-3.1-8b-instant)
    try:
        response = await client.chat.completions.create(
            model=FALLBACK_MODEL,
            **kwargs,
        )
        return response
    except Exception as e:
        logger.error(f"Groq fallback model '{FALLBACK_MODEL}' also failed: {e}")
        raise
