"""LLM service wrapper (spec §10, Phase 8).

Wraps the Groq SDK. Retries on 429 / 5xx (up to llm_max_retries).
Returns a structured LLMResponse with token counts.
Raises LLMUnavailableError on hard failure so callers can return 503.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM cannot be reached after retries."""


@dataclass
class LLMResponse:
    content: str
    token_in: int
    token_out: int


def call_llm(system: str, user: str) -> LLMResponse:
    """Call the LLM and return the response.

    Raises LLMUnavailableError if LLM_EXTERNAL_ALLOWED=false or after
    exhausting retries on 429/5xx.
    """
    if not settings.llm_external_allowed:
        raise LLMUnavailableError("LLM_EXTERNAL_ALLOWED is false")

    last_exc: Exception | None = None
    for attempt in range(max(1, settings.llm_max_retries + 1)):
        try:
            return _call(system, user)
        except Exception as exc:
            last_exc = exc
            if _is_retryable(exc) and attempt < settings.llm_max_retries:
                wait = 2 ** attempt
                logger.warning("LLM attempt %d failed (%s), retrying in %ds", attempt + 1, exc, wait)
                time.sleep(wait)
            else:
                break

    raise LLMUnavailableError(f"LLM unavailable after retries: {last_exc}") from last_exc


def _call(system: str, user: str) -> LLMResponse:
    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=settings.llm_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_output_tokens,
        timeout=settings.llm_timeout_seconds,
    )
    content = (response.choices[0].message.content or "").strip()
    usage = response.usage
    token_in = usage.prompt_tokens if usage else 0
    token_out = usage.completion_tokens if usage else 0
    return LLMResponse(content=content, token_in=token_in, token_out=token_out)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate" in msg or "500" in msg or "502" in msg or "503" in msg or "504" in msg
