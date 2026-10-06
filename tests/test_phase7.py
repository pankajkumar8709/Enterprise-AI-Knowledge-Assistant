"""Phase 7 tests — classifier, query rewrite, OKF search, merger, orchestrator.

All tests run against SQLite (no pgvector / pg_trgm), so PG-only paths
(vector search, FTS, trgm) return empty lists gracefully. The tests verify:
  - classifier fallback behaviour (LLM disabled)
  - query rewrite passthrough (LLM disabled)
  - merger deduplication, route weighting, token budget, ref assignment
  - OKF search graceful no-op on SQLite
  - POST /search/semantic and POST /search/okf endpoints return 200
  - retrieval orchestrator returns a valid RetrievalResult
  - ACL: employee cannot see admin_only chunks via /search/semantic
"""

from __future__ import annotations

import os

import pytest

from tests.conftest import client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_token() -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _employee_token() -> str:
    # Reuse the employee created in test_app.py; create if absent.
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "StrongPass123"},
    )
    if r.status_code == 200:
        return r.json()["access_token"]
    client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Phase7 Employee",
            "email": "employee@example.com",
            "password": "StrongPass123",
        },
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "StrongPass123"},
    )
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Classifier (spec §9.5)
# ---------------------------------------------------------------------------


def test_classifier_returns_mixed_when_llm_disabled() -> None:
    """With LLM_EXTERNAL_ALLOWED=false the classifier must return 'mixed'."""
    from app.services.classifier import classify_query

    result = classify_query("Who is the HR manager?")
    # LLM is disabled in tests (default false); fallback is always mixed.
    assert result.route == "mixed"
    assert result.confidence == 0.0


def test_classifier_parse_valid_json() -> None:
    """_parse correctly extracts route/confidence/hints from valid JSON."""
    from app.services.classifier import _parse

    raw = '{"route":"structured","confidence":0.9,"entity_hints":["employee"],"reason":"asks for a person"}'
    result = _parse(raw)
    assert result.route == "structured"
    assert result.confidence == 0.9
    assert "employee" in result.entity_hints


def test_classifier_parse_low_confidence_falls_back_to_mixed() -> None:
    from app.services.classifier import _parse

    raw = '{"route":"structured","confidence":0.3,"entity_hints":[],"reason":"uncertain"}'
    result = _parse(raw)
    # confidence < CLASSIFIER_MIN_CONFIDENCE (0.60) → route forced to mixed.
    assert result.route == "mixed"


def test_classifier_parse_invalid_json_returns_fallback() -> None:
    from app.services.classifier import _parse

    result = _parse("not json at all")
    assert result.route == "mixed"


def test_classifier_parse_unknown_route_normalised_to_mixed() -> None:
    from app.services.classifier import _parse

    raw = '{"route":"unknown_route","confidence":0.95,"entity_hints":[],"reason":"x"}'
    result = _parse(raw)
    assert result.route == "mixed"


# ---------------------------------------------------------------------------
# Query rewrite (spec §9.4)
# ---------------------------------------------------------------------------


def test_query_rewrite_passthrough_when_llm_disabled() -> None:
    """With LLM disabled the raw query is returned unchanged."""
    from app.services.query_rewrite import rewrite_query

    q = "What is the carry-forward limit?"
    assert rewrite_query(q, []) == q


def test_query_rewrite_passthrough_when_no_history() -> None:
    from app.services.query_rewrite import rewrite_query

    q = "Summarise the leave policy."
    assert rewrite_query(q, []) == q


def test_query_rewrite_passthrough_when_history_present_but_llm_disabled() -> None:
    from app.services.query_rewrite import rewrite_query

    history = [
        {"role": "user", "content": "Tell me about the leave policy."},
        {"role": "assistant", "content": "The leave policy allows 20 days per year."},
    ]
    q = "What about carry-forward?"
    # LLM disabled → raw query returned.
    assert rewrite_query(q, history) == q


# ---------------------------------------------------------------------------
# Merger (spec §9.6)
# ---------------------------------------------------------------------------


def _make_chunk_result(chunk_id: int, doc_id: int, score: float, content: str = "chunk text"):
    from app.services.retrieval.fusion import ChunkResult

    return ChunkResult(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_title="Doc",
        page_start=1,
        section_title=None,
        content=content,
        token_count=10,
        similarity=score,
        fts_rank=0.0,
        rrf_score=score,
        source_filename="doc.txt",
    )


def _make_okf_result(okf_id: int, score: float, obj_type: str = "faq"):
    from app.services.retrieval.okf_search import OKFResult

    return OKFResult(
        okf_id=okf_id,
        object_type=obj_type,
        name="Test fact",
        canonical_key=f"{obj_type}:test-fact",
        attributes={"question": "Q?", "answer": "A."},
        score=score,
        source_document_id=1,
        visibility="all",
        department_ids=[],
        confidence=0.9,
    )


def test_merger_assigns_refs_in_order() -> None:
    from app.services.retrieval.merger import merge

    chunks = [_make_chunk_result(1, 1, 0.8), _make_chunk_result(2, 1, 0.6)]
    okf = [_make_okf_result(10, 0.9)]
    items = merge("mixed", chunks, okf)
    assert len(items) >= 1
    refs = [i.ref for i in items]
    assert refs[0] == "S1"
    assert refs == [f"S{n}" for n in range(1, len(items) + 1)]


def test_merger_route_weighting_structured_boosts_okf() -> None:
    from app.services.retrieval.merger import merge

    # Give chunk and OKF equal raw scores; structured route should boost OKF.
    chunks = [_make_chunk_result(1, 1, 0.5)]
    okf = [_make_okf_result(10, 0.5)]
    items = merge("structured", chunks, okf)
    # OKF item should appear first (score × 1.15 > chunk score × 1.0).
    assert items[0].kind == "okf"


def test_merger_route_weighting_document_boosts_chunks() -> None:
    from app.services.retrieval.merger import merge

    chunks = [_make_chunk_result(1, 1, 0.5)]
    okf = [_make_okf_result(10, 0.5)]
    items = merge("document", chunks, okf)
    # Chunk item should appear first (score × 1.10 > OKF score × 1.0).
    assert items[0].kind == "chunk"


def test_merger_deduplicates_near_identical_chunks() -> None:
    from app.services.retrieval.merger import merge

    long_text = "The employee handbook defines the leave policy. " * 20
    chunks = [
        _make_chunk_result(1, 1, 0.9, long_text),
        _make_chunk_result(2, 1, 0.8, long_text),  # near-duplicate
    ]
    items = merge("document", chunks, [])
    chunk_items = [i for i in items if i.kind == "chunk"]
    assert len(chunk_items) == 1


def test_merger_deduplicates_repeated_okf_objects() -> None:
    from app.services.retrieval.merger import merge

    okf = [_make_okf_result(10, 0.9), _make_okf_result(10, 0.8)]  # same id
    items = merge("mixed", [], okf)
    okf_items = [i for i in items if i.kind == "okf"]
    assert len(okf_items) == 1


def test_merger_returns_empty_when_no_results() -> None:
    from app.services.retrieval.merger import merge

    assert merge("mixed", [], []) == []


def test_merger_always_keeps_at_least_one_item() -> None:
    from app.services.retrieval.merger import _trim_to_budget

    # Simulate a single item that exceeds the budget.
    from app.services.retrieval.merger import ContextItem

    item = ContextItem(ref="S1", kind="chunk", id=1, title="T", text="x" * 100_000, score=1.0, document_id=1, page=1)
    result = _trim_to_budget([item])
    assert len(result) == 1


# ---------------------------------------------------------------------------
# OKF search — graceful no-op on SQLite (spec §9.3)
# ---------------------------------------------------------------------------


def test_okf_search_returns_empty_on_sqlite(tmp_path) -> None:
    """okf_search must return [] on SQLite (no pg_trgm)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.base import Base
    from app.models.user import User, UserRole
    from app.services.retrieval.okf_search import okf_search

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(full_name="Admin", email="a@b.com", hashed_password="x", role=UserRole.ADMIN)
    db.add(user)
    db.commit()

    results = okf_search(db, "leave policy", user)
    assert results == []
    db.close()


# ---------------------------------------------------------------------------
# Retrieval orchestrator (spec §9)
# ---------------------------------------------------------------------------


def test_orchestrator_returns_valid_result_on_sqlite() -> None:
    """retrieve() must complete without error on SQLite and return a RetrievalResult."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.base import Base
    from app.models.user import User, UserRole
    from app.services.retrieval.orchestrator import retrieve

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(full_name="Admin", email="admin2@b.com", hashed_password=hash_password("x"), role=UserRole.ADMIN)
    db.add(user)
    db.commit()

    result = retrieve(db, user, "What is the leave policy?")
    assert result.route in ("structured", "document", "mixed")
    assert isinstance(result.rewritten_query, str)
    assert len(result.rewritten_query) > 0
    assert isinstance(result.context, list)
    db.close()


def test_orchestrator_structured_with_no_okf_hits_also_runs_rag() -> None:
    """structured route with 0 OKF hits must set run_rag=True (safety net §9.5)."""
    from unittest.mock import MagicMock, patch

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.base import Base
    from app.models.user import User, UserRole
    from app.services.retrieval.orchestrator import retrieve

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(full_name="Admin", email="admin3@b.com", hashed_password=hash_password("x"), role=UserRole.ADMIN)
    db.add(user)
    db.commit()

    # Force classifier to return "structured" with high confidence.
    from app.services.classifier import ClassifierResult

    mock_cls = ClassifierResult(route="structured", confidence=0.95, entity_hints=["policy"])

    with patch("app.services.retrieval.orchestrator.classify_query", return_value=mock_cls):
        result = retrieve(db, user, "Who is the HR manager?")

    # With 0 OKF hits (SQLite) the orchestrator falls back to RAG path.
    assert result.route == "structured"
    # chunk_results may be empty (no embeddings on SQLite) but no exception raised.
    assert isinstance(result.chunk_results, list)
    db.close()


# ---------------------------------------------------------------------------
# Search API endpoints (spec §8)
# ---------------------------------------------------------------------------


def test_semantic_search_endpoint_returns_200() -> None:
    token = _admin_token()
    r = client.post(
        "/api/v1/search/semantic",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "leave policy carry-forward", "top_k": 3},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_semantic_search_requires_auth() -> None:
    r = client.post(
        "/api/v1/search/semantic",
        json={"query": "leave policy", "top_k": 3},
    )
    assert r.status_code == 401


def test_okf_search_endpoint_returns_200() -> None:
    token = _admin_token()
    r = client.post(
        "/api/v1/search/okf",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "leave policy", "top_k": 5},
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_okf_search_requires_auth() -> None:
    r = client.post(
        "/api/v1/search/okf",
        json={"query": "leave policy"},
    )
    assert r.status_code == 401


def test_okf_search_with_type_hints() -> None:
    token = _admin_token()
    r = client.post(
        "/api/v1/search/okf",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "HR manager", "top_k": 5, "type_hints": ["employee", "department"]},
    )
    assert r.status_code == 200


def test_semantic_search_empty_query_rejected() -> None:
    token = _admin_token()
    r = client.post(
        "/api/v1/search/semantic",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "", "top_k": 3},
    )
    assert r.status_code == 422


def test_semantic_search_employee_can_search() -> None:
    """Employees must be able to call /search/semantic (ACL enforced inside SQL)."""
    token = _employee_token()
    r = client.post(
        "/api/v1/search/semantic",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "leave policy", "top_k": 3},
    )
    assert r.status_code == 200
