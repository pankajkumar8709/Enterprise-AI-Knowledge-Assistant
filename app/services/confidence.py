"""Confidence scoring (spec §10.3)."""

from __future__ import annotations


def compute_confidence(cited_scores: list[float], n_distinct_cited: int) -> float:
    """confidence = round(0.7*top_cited_score + 0.3*min(1, n_distinct_cited/2), 2)"""
    top = max(cited_scores) if cited_scores else 0.0
    return round(0.7 * top + 0.3 * min(1.0, n_distinct_cited / 2), 2)


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"
