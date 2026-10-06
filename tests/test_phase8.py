"""Phase 8 tests — LLM answer generation, confidence, citations, chat API.

All tests run against SQLite with LLM_EXTERNAL_ALLOWED=false (default).
LLM-dependent paths are tested via mocking.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "employee8@example.com", "password": "StrongPass123"},
    )
    if r.status_code == 200:
        return r.json()["access_token"]
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Phase8 Employee", "email": "employee8@example.com", "password": "StrongPass123"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "employee8@example.com", "password": "StrongPass123"},
    )
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Confidence (spec §10.3)
# ---------------------------------------------------------------------------


def test_confidence_high() -> None:
    from app.services.confidence import compute_confidence, confidence_label

    score = compute_confidence([0.9, 0.8], 2)
    assert score == round(0.7 * 0.9 + 0.3 * min(1.0, 2 / 2), 2)
    assert confidence_label(score) == "high"


def test_confidence_medium() -> None:
    from app.services.confidence import compute_confidence, confidence_label

    score = compute_confidence([0.6], 1)
    assert confidence_label(score) == "medium"


def test_confidence_low_no_citations() -> None:
    from app.services.confidence import compute_confidence, confidence_label

    score = compute_confidence([], 0)
    assert score == 0.0
    assert confidence_label(score) == "low"


def test_confidence_caps_at_one() -> None:
    from app.services.confidence import compute_confidence

    score = compute_confidence([1.0], 10)
    assert score <= 1.0


# ---------------------------------------------------------------------------
# Citation parsing (spec §10.3)
# ---------------------------------------------------------------------------


def test_clean_citations_keeps_valid_refs() -> None:
    from app.services.answer import _clean_citations

    text = "The limit is 12 days [S1]. See also [S2]."
    cleaned, cited = _clean_citations(text, {"S1", "S2"})
    assert "[S1]" in cleaned
    assert "[S2]" in cleaned
    assert cited == {"S1", "S2"}


def test_clean_citations_removes_absent_refs() -> None:
    from app.services.answer import _clean_citations

    text = "The limit is 12 days [S1]. Also [S99]."
    cleaned, cited = _clean_citations(text, {"S1"})
    assert "[S99]" not in cleaned
    assert "S99" not in cited
    assert "S1" in cited


def test_clean_citations_no_markers() -> None:
    from app.services.answer import _clean_citations

    text = "No citations here."
    cleaned, cited = _clean_citations(text, {"S1"})
    assert cleaned == text
    assert cited == set()


# ---------------------------------------------------------------------------
# Prompts (spec §10.1/10.2)
# ---------------------------------------------------------------------------


def test_answer_system_prompt_contains_rules() -> None:
    from app.services.prompts import ANSWER_SYSTEM

    assert "ONLY the numbered sources" in ANSWER_SYSTEM
    assert "INSUFFICIENT_CONTEXT" in ANSWER_SYSTEM
    assert "citation markers" in ANSWER_SYSTEM


def test_build_user_message_contains_context_block() -> None:
    from app.services.prompts import build_user_message
    from app.services.retrieval.fusion import ChunkResult
    from app.services.retrieval.merger import ContextItem

    cr = ChunkResult(
        chunk_id=1,
        document_id=1,
        document_title="Leave Policy",
        page_start=3,
        section_title="Carry-forward",
        content="Employees may carry forward up to 12 days.",
        token_count=10,
        similarity=0.9,
        fts_rank=0.0,
        rrf_score=0.9,
        source_filename="leave.pdf",
    )
    item = ContextItem(
        ref="S1",
        kind="chunk",
        id=1,
        title="Leave Policy",
        text="Employees may carry forward up to 12 days.",
        score=0.9,
        document_id=1,
        page=3,
        chunk_result=cr,
    )
    msg = build_user_message("What is the carry-forward limit?", [item])
    assert "<context>" in msg
    assert "[S1]" in msg
    assert "carry-forward" in msg.lower() or "carry forward" in msg.lower()
    assert "Question:" in msg


# ---------------------------------------------------------------------------
# LLM wrapper (spec §10)
# ---------------------------------------------------------------------------


def test_llm_raises_when_external_not_allowed() -> None:
    from app.services.llm import LLMUnavailableError, call_llm

    with pytest.raises(LLMUnavailableError, match="LLM_EXTERNAL_ALLOWED"):
        call_llm("system", "user")


def test_llm_retries_on_retryable_error() -> None:
    from app.services.llm import LLMUnavailableError, _is_retryable

    assert _is_retryable(Exception("429 rate limit"))
    assert _is_retryable(Exception("503 service unavailable"))
    assert not _is_retryable(Exception("400 bad request"))


# ---------------------------------------------------------------------------
# Answer service — fallback when no context (spec §10.3)
# ---------------------------------------------------------------------------


def test_generate_answer_fallback_when_no_context() -> None:
    """With empty context, generate_answer must return answerable=False without calling LLM."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.base import Base
    from app.models.conversation import Conversation
    from app.models.user import User, UserRole
    from app.services.answer import generate_answer
    from app.services.classifier import ClassifierResult
    from app.services.retrieval.orchestrator import RetrievalResult

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(full_name="U", email="u@test.com", hashed_password=hash_password("x"), role=UserRole.ADMIN)
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    retrieval = RetrievalResult(
        route="mixed",
        rewritten_query="What is the leave policy?",
        classifier=ClassifierResult(route="mixed", confidence=0.0),
        context=[],
    )

    result = generate_answer(db, user, conv.id, "What is the leave policy?", retrieval)
    assert result.answerable is False
    assert result.confidence == 0.0
    assert result.sources == []
    assert "couldn't find" in result.answer.lower()
    db.close()


def test_generate_answer_with_mocked_llm() -> None:
    """With context and a mocked LLM response, answer is parsed and sources cited."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.base import Base
    from app.models.conversation import Conversation
    from app.models.user import User, UserRole
    from app.services.answer import generate_answer
    from app.services.classifier import ClassifierResult
    from app.services.llm import LLMResponse
    from app.services.retrieval.fusion import ChunkResult
    from app.services.retrieval.merger import ContextItem
    from app.services.retrieval.orchestrator import RetrievalResult

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(full_name="U2", email="u2@test.com", hashed_password=hash_password("x"), role=UserRole.ADMIN)
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    cr = ChunkResult(
        chunk_id=1, document_id=1, document_title="Leave Policy",
        page_start=3, section_title="Carry-forward",
        content="Employees may carry forward up to 12 days.",
        token_count=10, similarity=0.9, fts_rank=0.0, rrf_score=0.9,
        source_filename="leave.pdf",
    )
    item = ContextItem(
        ref="S1", kind="chunk", id=1, title="Leave Policy",
        text="Employees may carry forward up to 12 days.",
        score=0.9, document_id=1, page=3, chunk_result=cr,
    )

    retrieval = RetrievalResult(
        route="document",
        rewritten_query="What is the carry-forward limit?",
        classifier=ClassifierResult(route="document", confidence=0.9),
        context=[item],
    )

    mock_resp = LLMResponse(
        content="Employees may carry forward up to 12 days [S1].",
        token_in=50,
        token_out=20,
    )

    with patch("app.services.answer.call_llm", return_value=mock_resp):
        result = generate_answer(db, user, conv.id, "What is the carry-forward limit?", retrieval)

    assert result.answerable is True
    assert "[S1]" in result.answer
    assert any(s.ref == "S1" and s.cited for s in result.sources)
    assert result.confidence > 0
    db.close()


def test_generate_answer_insufficient_context_response() -> None:
    """LLM returning INSUFFICIENT_CONTEXT → answerable=False, fallback answer."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.base import Base
    from app.models.conversation import Conversation
    from app.models.user import User, UserRole
    from app.services.answer import generate_answer
    from app.services.classifier import ClassifierResult
    from app.services.llm import LLMResponse
    from app.services.retrieval.fusion import ChunkResult
    from app.services.retrieval.merger import ContextItem
    from app.services.retrieval.orchestrator import RetrievalResult

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(full_name="U3", email="u3@test.com", hashed_password=hash_password("x"), role=UserRole.ADMIN)
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)

    cr = ChunkResult(
        chunk_id=2, document_id=1, document_title="Doc",
        page_start=1, section_title=None,
        content="Some unrelated text.",
        token_count=5, similarity=0.4, fts_rank=0.0, rrf_score=0.4,
        source_filename="doc.pdf",
    )
    item = ContextItem(
        ref="S1", kind="chunk", id=2, title="Doc",
        text="Some unrelated text.", score=0.4,
        document_id=1, page=1, chunk_result=cr,
    )

    retrieval = RetrievalResult(
        route="document",
        rewritten_query="What is the secret formula?",
        classifier=ClassifierResult(route="document", confidence=0.9),
        context=[item],
    )

    mock_resp = LLMResponse(content="INSUFFICIENT_CONTEXT", token_in=30, token_out=5)

    with patch("app.services.answer.call_llm", return_value=mock_resp):
        result = generate_answer(db, user, conv.id, "What is the secret formula?", retrieval)

    assert result.answerable is False
    assert result.confidence == 0.0
    assert "couldn't find" in result.answer.lower()
    db.close()


# ---------------------------------------------------------------------------
# Chat API endpoints (spec §8)
# ---------------------------------------------------------------------------


def test_create_conversation_requires_auth() -> None:
    r = client.post("/api/v1/chat/conversations")
    assert r.status_code == 401


def test_create_conversation() -> None:
    token = _admin_token()
    r = client.post("/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["archived"] is False


def test_list_conversations_empty_initially() -> None:
    token = _employee_token()
    r = client.get("/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_conversation() -> None:
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    r = client.get(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == conv_id
    assert "messages" in r.json()


def test_get_conversation_not_found() -> None:
    token = _admin_token()
    r = client.get("/api/v1/chat/conversations/999999", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_get_conversation_forbidden_for_other_user() -> None:
    admin_token = _admin_token()
    emp_token = _employee_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()["id"]
    r = client.get(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {emp_token}"})
    assert r.status_code == 403


def test_delete_conversation() -> None:
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    r = client.delete(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 404


def test_send_message_empty_content_rejected() -> None:
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": ""},
    )
    assert r.status_code == 422


def test_send_message_returns_answer_with_llm_disabled() -> None:
    """With LLM disabled and no chunks (SQLite), answer is the fallback."""
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "What is the leave policy?"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "answerable" in data
    assert data["answerable"] is False  # no chunks in SQLite test DB
    assert "sources" in data
    assert "confidence" in data
    assert "latency_ms" in data


def test_send_message_auto_titles_conversation() -> None:
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "What is the carry-forward limit?"},
    )
    r = client.get(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["title"] is not None


def test_send_message_persists_messages() -> None:
    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]
    client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Tell me about the leave policy."},
    )
    r = client.get(f"/api/v1/chat/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    msgs = r.json()["messages"]
    # user message + assistant message
    assert len(msgs) >= 2
    roles = [m["role"] for m in msgs]
    assert "user" in roles
    assert "assistant" in roles


def test_send_message_requires_auth() -> None:
    r = client.post(
        "/api/v1/chat/conversations/1/messages",
        json={"content": "Hello"},
    )
    assert r.status_code == 401


def test_send_message_to_nonexistent_conversation() -> None:
    token = _admin_token()
    r = client.post(
        "/api/v1/chat/conversations/999999/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Hello"},
    )
    assert r.status_code == 404


def test_send_message_503_on_llm_error() -> None:
    """When LLM raises LLMUnavailableError mid-call, endpoint returns 503."""
    from app.services.llm import LLMUnavailableError

    token = _admin_token()
    conv_id = client.post(
        "/api/v1/chat/conversations", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]

    # Patch retrieve to return a non-empty context so the LLM is actually called.
    from app.services.retrieval.fusion import ChunkResult
    from app.services.retrieval.merger import ContextItem
    from app.services.classifier import ClassifierResult
    from app.services.retrieval.orchestrator import RetrievalResult

    cr = ChunkResult(
        chunk_id=1, document_id=1, document_title="Doc",
        page_start=1, section_title=None, content="Some text.",
        token_count=5, similarity=0.8, fts_rank=0.0, rrf_score=0.8,
        source_filename="doc.pdf",
    )
    item = ContextItem(
        ref="S1", kind="chunk", id=1, title="Doc",
        text="Some text.", score=0.8, document_id=1, page=1, chunk_result=cr,
    )
    mock_retrieval = RetrievalResult(
        route="document",
        rewritten_query="test",
        classifier=ClassifierResult(route="document", confidence=0.9),
        context=[item],
    )

    with patch("app.api.routes.chat.retrieve", return_value=mock_retrieval), \
         patch("app.services.answer.call_llm", side_effect=LLMUnavailableError("timeout")):
        r = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "What is the policy?"},
        )
    assert r.status_code == 503
