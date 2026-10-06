"""OKF validation helpers — spec §6.1/§7.4 (quote verification, predicate gate)."""

from __future__ import annotations

import re

from app.services.okf.schema import predicate_is_allowed

_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_for_quote_check(text: str) -> str:
    """Whitespace-normalize text for verbatim quote comparison (spec §7.4.4)."""

    return _WHITESPACE_RUN.sub(" ", text or "").strip()


def quote_is_verbatim(quote: str, chunk_text: str) -> bool:
    """True iff `quote` appears verbatim (whitespace-normalized) in `chunk_text`."""

    if not quote or not chunk_text:
        return False
    needle = normalize_for_quote_check(quote)
    haystack = normalize_for_quote_check(chunk_text)
    return needle in haystack


def find_quote_chunk(quote: str, chunks: list[tuple[int, str | None, str]]) -> tuple[int, str | None] | None:
    """Locate the first chunk whose text contains the quote verbatim.

    `chunks` is a list of (chunk_id, page, text). Returns (chunk_id, page) or
    None when the quote fails verification in every chunk (fact must be
    dropped — spec §7.4.4).
    """

    for chunk_id, page, text in chunks:
        if quote_is_verbatim(quote, text):
            return chunk_id, page
    return None


def validate_relations(relations: list[dict]) -> tuple[list[dict], list[str]]:
    """Filter relations to the closed predicate list (spec §6.2).

    Returns (valid_relations, rejected_predicates). Anything else is rejected
    by the validator.
    """

    valid: list[dict] = []
    rejected: list[str] = []
    for relation in relations or []:
        predicate = str(relation.get("predicate", ""))
        if predicate_is_allowed(predicate):
            valid.append(relation)
        else:
            rejected.append(predicate or "<empty>")
    return valid, rejected
