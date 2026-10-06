"""Query classifier (spec §9.5).

Calls the LLM (temperature 0) to classify a query as structured / document /
mixed. Falls back to `mixed` on any error, invalid JSON, or confidence below
`CLASSIFIER_MIN_CONFIDENCE`.

The LLM call is skipped entirely when `LLM_EXTERNAL_ALLOWED=false`; the
classifier returns `mixed` so the retrieval orchestrator runs both paths.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a query classifier for an enterprise knowledge assistant.
Classify the user question into exactly one route and output ONLY valid JSON.

Route definitions:
- "structured": asks for a specific fact, person, role, number, date, list of
  entities, or rule value. Examples: "Who is the HR manager?",
  "What is the carry-forward limit?"
- "document": asks to summarise, explain, describe a procedure, compare, or
  needs narrative. Example: "Summarise the leave policy."
- "mixed": needs both exact facts AND narrative explanation. Example:
  "Explain the leave policy and tell me the carry-forward limit."

Output schema (no other keys):
{
  "route": "structured" | "document" | "mixed",
  "confidence": <float 0-1>,
  "entity_hints": [<okf type strings from: policy, employee, department,
                    product, faq, business_rule, asset>],
  "reason": "<≤20 words>"
}
"""


@dataclass
class ClassifierResult:
    route: str  # "structured" | "document" | "mixed"
    confidence: float
    entity_hints: list[str] = field(default_factory=list)
    reason: str = ""


_FALLBACK = ClassifierResult(route="mixed", confidence=0.0, reason="fallback")


def classify_query(query: str) -> ClassifierResult:
    """Classify *query*. Always returns a valid result; never raises."""
    if not settings.llm_external_allowed:
        logger.debug("classifier: LLM_EXTERNAL_ALLOWED=false, returning mixed")
        return ClassifierResult(route="mixed", confidence=0.0, reason="llm_disabled")

    try:
        return _call_llm(query)
    except Exception as exc:
        logger.warning("classifier error (%s), falling back to mixed", exc)
        return _FALLBACK


def _call_llm(query: str) -> ClassifierResult:
    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=settings.llm_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.0,
        max_tokens=200,
        timeout=settings.llm_timeout_seconds,
    )
    raw = (response.choices[0].message.content or "").strip()
    return _parse(raw)


def _parse(raw: str) -> ClassifierResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code fences.
        import re  # noqa: PLC0415

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return _FALLBACK
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return _FALLBACK

    route = str(data.get("route", "mixed")).lower()
    if route not in {"structured", "document", "mixed"}:
        route = "mixed"

    confidence = float(data.get("confidence", 0.0))
    if confidence < settings.classifier_min_confidence:
        route = "mixed"

    hints = [str(h).lower() for h in data.get("entity_hints", []) if h]
    reason = str(data.get("reason", ""))[:100]

    return ClassifierResult(route=route, confidence=confidence, entity_hints=hints, reason=reason)
