"""Query rewrite for follow-up questions (spec §9.4).

When a conversation has prior messages, the LLM rewrites the latest question
into a standalone query using the last `CHAT_HISTORY_TURNS` messages.
Falls back to the raw question on any error or when LLM is disabled.
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a query rewriter for an enterprise knowledge assistant.
Given a conversation history and a follow-up question, rewrite the question
into a fully self-contained standalone question that can be understood without
the conversation context.

Output ONLY valid JSON with a single key:
{"query": "<rewritten standalone question>"}

If the question is already standalone, return it unchanged.
"""


def rewrite_query(query: str, history: list[dict[str, str]]) -> str:
    """Return a standalone version of *query* given *history*.

    *history* is a list of ``{"role": "user"|"assistant", "content": "..."}``
    dicts, most-recent last. Returns the raw *query* on any failure.
    """
    if not history or not settings.llm_external_allowed:
        return query

    turns = history[-(settings.chat_history_turns * 2):]  # user+assistant pairs
    if not turns:
        return query

    try:
        return _call_llm(query, turns)
    except Exception as exc:
        logger.warning("query_rewrite error (%s), using raw query", exc)
        return query


def _call_llm(query: str, turns: list[dict[str, str]]) -> str:
    from groq import Groq  # noqa: PLC0415

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    messages.extend(turns)
    messages.append({"role": "user", "content": query})

    client = Groq(api_key=settings.llm_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=0.0,
        max_tokens=200,
        timeout=settings.llm_timeout_seconds,
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
        rewritten = str(data.get("query", query)).strip()
        return rewritten if rewritten else query
    except (json.JSONDecodeError, KeyError):
        return query
