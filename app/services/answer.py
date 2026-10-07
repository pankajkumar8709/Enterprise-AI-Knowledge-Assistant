"""Answer generation pipeline (spec §10, Phase 8).

generate_answer():
  1. Build prompt from context items.
  2. Call LLM (or return fallback if no context / LLM disabled).
  3. Parse [S#] citation markers.
  4. Compute confidence.
  5. Persist user message + assistant message + message_sources.
  6. Audit chat.query.
  7. Return ChatAnswerOut.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.conversation import ChatRoute, Message, MessageRole, MessageSource
from app.models.user import User
from app.services.audit import record_audit
from app.services.confidence import compute_confidence, confidence_label
from app.services.llm import LLMUnavailableError, call_llm
from app.services.prompts import ANSWER_SYSTEM, build_user_message
from app.services.retrieval.merger import ContextItem
from app.services.retrieval.orchestrator import RetrievalResult

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "I couldn't find this in the company knowledge I have access to. "
    "Try rephrasing, or contact the relevant department."
)
_CITATION_RE = re.compile(r"(?:\[S(\d+)\]|【S(\d+)】)")


@dataclass
class SourceOut:
    ref: str
    kind: str
    score: float
    cited: bool
    title: str
    snippet: str | None
    # chunk-specific
    chunk_id: int | None = None
    document_id: int | None = None
    section_title: str | None = None
    page: int | None = None
    # okf-specific
    okf_object_id: int | None = None
    okf_type: str | None = None
    facts: dict = field(default_factory=dict)
    origin: dict | None = None


@dataclass
class ChatAnswerOut:
    message_id: int
    conversation_id: int
    answer: str
    answerable: bool
    route: str
    confidence: float
    confidence_label: str
    sources: list[SourceOut]
    latency_ms: int


def generate_answer(
    db: Session,
    user: User,
    conversation_id: int,
    user_content: str,
    retrieval: RetrievalResult,
    ip: str | None = None,
) -> ChatAnswerOut:
    t0 = time.monotonic()

    context = retrieval.context
    rewritten = retrieval.rewritten_query

    # --- Persist user message ---
    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=user_content,
    )
    db.add(user_msg)
    db.flush()

    # --- No context → immediate fallback ---
    if not context:
        return _persist_and_return(
            db=db,
            user=user,
            conversation_id=conversation_id,
            user_msg_id=user_msg.id,
            answer=_FALLBACK_ANSWER,
            answerable=False,
            route=retrieval.route,
            confidence=0.0,
            conf_label="low",
            sources=[],
            rewritten=rewritten,
            token_in=0,
            token_out=0,
            latency_ms=int((time.monotonic() - t0) * 1000),
            ip=ip,
            original_query=user_content,
        )

    # --- Build prompt and call LLM ---
    user_msg_text = build_user_message(rewritten, context)
    token_in = token_out = 0
    raw_answer = ""

    try:
        llm_resp = call_llm(ANSWER_SYSTEM, user_msg_text)
        raw_answer = llm_resp.content
        token_in = llm_resp.token_in
        token_out = llm_resp.token_out
    except LLMUnavailableError:
        raise  # caller converts to 503
    except Exception as exc:
        logger.error("LLM call failed unexpectedly: %s", exc)
        raise LLMUnavailableError(str(exc)) from exc

    # --- Post-process ---
    answerable = raw_answer.strip() != "INSUFFICIENT_CONTEXT"
    if not answerable:
        answer_text = _FALLBACK_ANSWER
        cited_refs: set[str] = set()
    else:
        answer_text, cited_refs = _clean_citations(raw_answer, {item.ref for item in context})

    # --- Build source list ---
    sources = _build_sources(context, cited_refs)

    # --- Confidence ---
    cited_scores = [s.score for s in sources if s.cited]
    conf = compute_confidence(cited_scores, len(cited_refs)) if answerable else 0.0
    conf_label = confidence_label(conf)

    latency_ms = int((time.monotonic() - t0) * 1000)

    return _persist_and_return(
        db=db,
        user=user,
        conversation_id=conversation_id,
        user_msg_id=user_msg.id,
        answer=answer_text,
        answerable=answerable,
        route=retrieval.route,
        confidence=conf,
        conf_label=conf_label,
        sources=sources,
        rewritten=rewritten,
        token_in=token_in,
        token_out=token_out,
        latency_ms=latency_ms,
        ip=ip,
        original_query=user_content,
    )


def _clean_citations(text: str, valid_refs: set[str]) -> tuple[str, set[str]]:
    """Remove markers referencing absent sources; collect cited refs."""
    cited: set[str] = set()

    def replace(m: re.Match) -> str:
        ref = f"S{m.group(1) or m.group(2)}"
        if ref in valid_refs:
            cited.add(ref)
            return f"[{ref}]"
        return ""

    cleaned = _CITATION_RE.sub(replace, text)
    return cleaned.strip(), cited


def _build_sources(context: list[ContextItem], cited_refs: set[str]) -> list[SourceOut]:
    sources: list[SourceOut] = []
    for item in context:
        cited = item.ref in cited_refs
        if item.kind == "okf" and item.okf_result:
            r = item.okf_result
            origin = None
            if r.source_document_id:
                origin = {"document_id": r.source_document_id, "document_title": item.title, "page": item.page}
            sources.append(
                SourceOut(
                    ref=item.ref,
                    kind="okf",
                    score=item.score,
                    cited=cited,
                    title=item.title,
                    snippet=None,
                    okf_object_id=r.okf_id,
                    okf_type=r.object_type,
                    facts=r.attributes or {},
                    origin=origin,
                )
            )
        else:
            cr = item.chunk_result
            snippet = (item.text[:300] + "…") if item.text and len(item.text) > 300 else item.text
            sources.append(
                SourceOut(
                    ref=item.ref,
                    kind="chunk",
                    score=item.score,
                    cited=cited,
                    title=item.title,
                    snippet=snippet,
                    chunk_id=item.id,
                    document_id=item.document_id,
                    section_title=cr.section_title if cr else None,
                    page=item.page,
                )
            )
    return sources


def _persist_and_return(
    *,
    db: Session,
    user: User,
    conversation_id: int,
    user_msg_id: int,
    answer: str,
    answerable: bool,
    route: str,
    confidence: float,
    conf_label: str,
    sources: list[SourceOut],
    rewritten: str,
    token_in: int,
    token_out: int,
    latency_ms: int,
    ip: str | None,
    original_query: str,
) -> ChatAnswerOut:
    try:
        route_enum = ChatRoute(route)
    except ValueError:
        route_enum = ChatRoute.MIXED

    asst_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=answer,
        route=route_enum,
        confidence=confidence,
        confidence_label=conf_label,
        answerable=answerable,
        rewritten_query=rewritten,
        latency_ms=latency_ms,
        token_in=token_in,
        token_out=token_out,
    )
    db.add(asst_msg)
    db.flush()

    for src in sources:
        extra: dict = {}
        if src.kind == "okf":
            extra = {"okf_type": src.okf_type, "facts": src.facts, "origin": src.origin}
        else:
            extra = {"section_title": src.section_title}

        db.add(
            MessageSource(
                message_id=asst_msg.id,
                ref=src.ref,
                kind=src.kind,
                chunk_id=src.chunk_id,
                okf_object_id=src.okf_object_id,
                document_id=src.document_id,
                score=src.score,
                snippet=src.snippet,
                cited=src.cited,
                extra=extra,
            )
        )

    record_audit(
        db,
        action="chat.query",
        entity_type="conversation",
        entity_id=str(conversation_id),
        user_id=user.id,
        metadata={
            "query": original_query[:500],
            "route": route,
            "answerable": answerable,
            "latency_ms": latency_ms,
        },
        ip=ip,
        commit=False,
    )

    db.commit()
    db.refresh(asst_msg)

    return ChatAnswerOut(
        message_id=asst_msg.id,
        conversation_id=conversation_id,
        answer=answer,
        answerable=answerable,
        route=route,
        confidence=confidence,
        confidence_label=conf_label,
        sources=sources,
        latency_ms=latency_ms,
    )
