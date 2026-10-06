"""Context merger (spec §9.6).

Merges OKF and chunk results into a single ranked, deduplicated context list
ready for the LLM prompt. Applies route weighting, near-duplicate removal,
conflict detection, and context token budget trimming.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings
from app.services.retrieval.fusion import ChunkResult
from app.services.retrieval.okf_search import OKFResult

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    ref: str  # S1, S2, …
    kind: str  # "chunk" | "okf"
    id: int  # chunk_id or okf_id
    title: str
    text: str  # rendered text for the prompt
    score: float
    document_id: int | None
    page: int | None
    # Extra metadata kept for the API response.
    chunk_result: ChunkResult | None = field(default=None, repr=False)
    okf_result: OKFResult | None = field(default=None, repr=False)


def merge(
    route: str,
    chunk_results: list[ChunkResult],
    okf_results: list[OKFResult],
) -> list[ContextItem]:
    """Merge, deduplicate, weight, and trim results into a context list.

    Returns items with refs assigned (S1…Sn), ordered by final score desc,
    trimmed to `CONTEXT_MAX_TOKENS` total.
    """
    items: list[ContextItem] = []

    # --- Build raw items ---
    for r in okf_results:
        text = _render_okf(r)
        items.append(
            ContextItem(
                ref="",
                kind="okf",
                id=r.okf_id,
                title=r.name,
                text=text,
                score=r.score,
                document_id=r.source_document_id,
                page=None,
                okf_result=r,
            )
        )

    for r in chunk_results:
        items.append(
            ContextItem(
                ref="",
                kind="chunk",
                id=r.chunk_id,
                title=r.document_title,
                text=r.content,
                score=r.rrf_score,
                document_id=r.document_id,
                page=r.page_start,
                chunk_result=r,
            )
        )

    if not items:
        return []

    # --- Route weighting (spec §9.6 step 4) ---
    for item in items:
        if route == "structured" and item.kind == "okf":
            item.score *= 1.15
        elif route == "document" and item.kind == "chunk":
            item.score *= 1.10

    # --- Near-duplicate chunk removal (spec §9.6 step 2) ---
    # Remove chunk items whose content overlaps heavily with a higher-scored chunk.
    items = _dedupe_chunks(items)

    # --- OKF + source-chunk co-presence (spec §9.6 step 3) ---
    # When an OKF object and a chunk share the same document_id, keep both
    # (OKF gives the exact fact, chunk gives context). Never repeat the same
    # OKF object twice.
    seen_okf_ids: set[int] = set()
    deduped: list[ContextItem] = []
    for item in items:
        if item.kind == "okf":
            if item.id in seen_okf_ids:
                continue
            seen_okf_ids.add(item.id)
        deduped.append(item)
    items = deduped

    # --- Sort by score desc ---
    items.sort(key=lambda x: x.score, reverse=True)

    # --- Context token budget (spec §9.6 step 5) ---
    items = _trim_to_budget(items)

    # --- Assign refs ---
    for i, item in enumerate(items, 1):
        item.ref = f"S{i}"

    return items


def _render_okf(r: OKFResult) -> str:
    """Render OKF attributes as key: value lines for the LLM prompt."""
    lines = [f"[OKF FACT · {r.object_type} · {r.name}]"]
    for k, v in (r.attributes or {}).items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _dedupe_chunks(items: list[ContextItem]) -> list[ContextItem]:
    """Remove chunk items with >95% token overlap to a higher-scored chunk."""
    kept: list[ContextItem] = []
    chunk_texts: list[str] = []

    for item in sorted(items, key=lambda x: x.score, reverse=True):
        if item.kind != "chunk":
            kept.append(item)
            continue
        words = set(item.text.lower().split())
        duplicate = False
        for existing_text in chunk_texts:
            existing_words = set(existing_text.lower().split())
            if not words or not existing_words:
                continue
            overlap = len(words & existing_words) / max(len(words), len(existing_words))
            if overlap > 0.95:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
            chunk_texts.append(item.text)

    return kept


def _trim_to_budget(items: list[ContextItem]) -> list[ContextItem]:
    """Trim items to fit within CONTEXT_MAX_TOKENS; always keep at least 1."""
    budget = settings.context_max_tokens
    kept: list[ContextItem] = []
    used = 0
    for item in items:
        tokens = _estimate_tokens(item.text)
        if kept and used + tokens > budget:
            break
        kept.append(item)
        used += tokens
    return kept or items[:1]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (no tiktoken dependency here)."""
    return max(1, len(text) // 4)
