"""Unified backend test suite -- all phases in one file.

Consolidates the former four test modules into a single file, preserving the
original module order (and therefore the original execution order):
  1. Core API surface          (former tests/test_app.py)
  2. Phase 0-5 audit fixes     (former tests/test_phase0_5_fixes.py)
  3. Phase 7 retrieval         (former tests/test_phase7.py)
  4. Phase 8 answers and chat  (former tests/test_phase8.py)
  5. Admin bootstrap           (former tests/test_admin_bootstrap.py)

The duplicate role-token helpers from the Phase 7 / Phase 8 modules were
merged: one shared ``_admin_token`` (identical in both), and the two
``_employee_token`` variants kept under distinct names because they use
different emails (employee@example.com vs employee8@example.com).

Runs against the SQLite harness in tests/conftest.py:
    python -m pytest tests/test_all.py -q

Sections 1-4 keep the original merge-module order (and therefore execution
order); section 5 is self-contained (in-memory DB per test).
"""

from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from pypdf import PdfWriter

from app.core.config import settings
from app.models.user import User, UserRole
from app.services.extraction import (
    _clean_text,
    _extract_docx_text,
    _extract_pptx_text,
    _remove_repeated_page_lines,
)
from tests.conftest import TestingSessionLocal, client

# ===========================================================================
# 1. Core API surface (former tests/test_app.py)
# ===========================================================================

def _wait_document_ready(test_client: TestClient, token: str, document_id: int, *, timeout_s: float = 10.0) -> dict:
    """Poll the §8 status endpoint until the background ingestion finishes."""

    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        status_response = test_client.get(
            f"/api/v1/documents/{document_id}/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_response.status_code == 200
        last = status_response.json()
        if last["status"] in {"ready", "failed"}:
            return last
        time.sleep(0.05)
    return last


def _build_docx_bytes(paragraphs: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        )
        paragraph_xml = "".join(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs)
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraph_xml}</w:body></w:document>',
        )
    return buffer.getvalue()


def _build_pptx_bytes(slides: list[list[str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        )
        archive.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )
        for index, slide_lines in enumerate(slides, start=1):
            text_nodes = "".join(f"<a:t>{line}</a:t>" for line in slide_lines)
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                f'<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody>{text_nodes}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>',
            )
    return buffer.getvalue()


def _build_blank_pdf_bytes() -> bytes:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    return buffer.getvalue()


def test_health_check() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_user_role_enum_uses_database_values() -> None:
    assert User.__table__.c.role.type.enums == [UserRole.ADMIN.value, UserRole.EMPLOYEE.value]


def test_signup_login_and_verify_token() -> None:
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "New Employee",
            "email": "new.employee@example.com",
            "password": "StrongPass123",
            "role": UserRole.ADMIN.value,
        },
    )
    assert signup_response.status_code == 201
    assert signup_response.json()["role"] == UserRole.EMPLOYEE.value

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "new.employee@example.com", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    verify_response = client.get(
        "/api/v1/auth/verify-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["email"] == "new.employee@example.com"


def test_login_with_unrecognized_stored_password_hash_returns_401() -> None:
    email = f"bad-hash-{uuid4().hex}@example.com"
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Bad Hash User", "email": email, "password": "StrongPass123"},
    )
    assert signup_response.status_code == 201

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.hashed_password = "unrecognized-password-hash"
        db.commit()
    finally:
        db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login_response.status_code == 401
    assert login_response.json()["error"]["message"] == "Invalid credentials"


def test_admin_can_list_users() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    users_response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert users_response.status_code == 200
    assert len(users_response.json()) >= 1


def test_admin_can_manage_documents() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Employee Handbook"},
        files={"file": ("handbook.txt", b"phase 2 upload content", "text/plain")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion).
    assert upload_response.status_code == 202
    created_document = upload_response.json()
    # Status follows the pipeline (audit F-006): ingestion now runs as a
    # background task, so the response is `processing` and clients poll §8 status.
    final_status = _wait_document_ready(client, token, created_document["id"])
    assert final_status["status"] == "ready", final_status
    assert created_document["version"] == 1
    assert created_document["sha256"]
    # Internal storage paths must not leak to API clients (audit F-034).
    assert "storage_path" not in created_document
    assert "extraction_raw_text_path" not in created_document

    list_response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    update_response = client.put(
        f"/api/v1/documents/{created_document['id']}",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Updated Handbook"},
        files={"file": ("handbook.md", b"# updated phase 2 content", "text/markdown")},
    )
    assert update_response.status_code == 200
    updated_document = update_response.json()
    assert updated_document["title"] == "Updated Handbook"
    assert updated_document["version"] == 2
    assert updated_document["source_name"] == "handbook.md"
    # Phase 5.5: re-ingestion of the new version runs in the background (§7.1.5);
    # the PUT response shows the pipeline state at accept time, so poll §8 status.
    v2_status = _wait_document_ready(client, token, created_document["id"])
    assert v2_status["status"] == "ready", v2_status

    # Pipeline states are visible after ingestion completes (§8 status contract).
    refreshed = client.get(
        f"/api/v1/documents/{created_document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert refreshed["extraction_status"] == "ready"
    # Version 2 replaced the file, so pipeline stats now reflect its content.
    assert refreshed["extracted_char_count"] == len("# updated phase 2 content")
    assert refreshed["chunking_status"] == "ready"
    # Single production chunking strategy (audit F-019): one chunk, not three.
    assert refreshed["chunk_count"] == 1

    extraction_status_response = client.get(
        f"/api/v1/documents/{created_document['id']}/extraction-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extraction_status_response.status_code == 200
    assert extraction_status_response.json()["status"] == "ready"

    chunk_status_response = client.get(
        f"/api/v1/documents/{created_document['id']}/chunk-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chunk_status_response.status_code == 200
    assert chunk_status_response.json()["status"] == "ready"
    assert chunk_status_response.json()["chunk_count"] == 1

    # Combined status endpoint (spec §8)
    status_response = client.get(
        f"/api/v1/documents/{created_document['id']}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"
    assert status_response.json()["progress_pct"] == 100

    chunk_preview_response = client.get(
        f"/api/v1/documents/{created_document['id']}/chunks/preview",
        headers={"Authorization": f"Bearer {token}"},
        params={"strategy": "section_based"},
    )
    assert chunk_preview_response.status_code == 200
    assert chunk_preview_response.json()["strategy"] == "section_based"
    assert chunk_preview_response.json()["total"] == 1
    assert chunk_preview_response.json()["items"][0]["page_number"] == 1
    assert chunk_preview_response.json()["items"][0]["source_file_name"] == "handbook.md"
    assert chunk_preview_response.json()["items"][0]["token_count"] >= 1

    extracted_text_response = client.get(
        f"/api/v1/documents/{created_document['id']}/extracted-text",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extracted_text_response.status_code == 200
    assert extracted_text_response.json()["raw_text"] == "# updated phase 2 content"
    assert extracted_text_response.json()["clean_text"] == "# updated phase 2 content"

    delete_response = client.delete(
        f"/api/v1/documents/{created_document['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204


def test_document_upload_rejects_invalid_type_and_non_admin() -> None:
    employee_signup = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Employee User",
            "email": "employee@example.com",
            "password": "StrongPass123",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    assert employee_signup.status_code == 201

    employee_login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "StrongPass123"},
    )
    employee_token = employee_login.json()["access_token"]

    forbidden_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {employee_token}"},
        data={"title": "Should Fail"},
        files={"file": ("notes.txt", b"content", "text/plain")},
    )
    assert forbidden_response.status_code == 403

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    admin_token = admin_login.json()["access_token"]

    invalid_type_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Unsupported"},
        files={"file": ("script.exe", b"binary", "application/octet-stream")},
    )
    # Spec §8: unsupported file type is 415, not 400 (audit F-007).
    assert invalid_type_response.status_code == 415
    # Spec §8 error contract (R0 #17): {"error": {code, message, details}}.
    assert invalid_type_response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_document_upload_rejects_file_over_size_limit() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    oversized_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Oversized"},
        files={"file": ("large.txt", b"a" * 2048, "text/plain")},
    )
    # Spec §8: FILE_TOO_LARGE is 413 (audit F-007).
    assert oversized_response.status_code == 413
    # Spec §8 error contract (R0 #17): {"error": {code, message, details}}.
    assert oversized_response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_docx_and_pptx_extraction_work() -> None:
    original_limit = settings.max_document_size_bytes
    settings.max_document_size_bytes = 4096

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    try:
        docx_response = client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={"title": "Policy DOCX"},
            files={
                "file": (
                    "policy.docx",
                    _build_docx_bytes(["Policy Heading", "Line two"]),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        # Phase 5.5: ingestion is asynchronous (§7.1.5); poll until it settles.
        assert docx_response.status_code == 202
        docx_payload = docx_response.json()
        assert _wait_document_ready(client, token, docx_payload["id"])["status"] == "ready"
        docx_payload = client.get(
            f"/api/v1/documents/{docx_payload['id']}", headers={"Authorization": f"Bearer {token}"}
        ).json()
        assert docx_payload["extraction_status"] == "ready"

        docx_text_response = client.get(
            f"/api/v1/documents/{docx_payload['id']}/extracted-text",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert docx_text_response.status_code == 200
        assert docx_text_response.json()["clean_text"] == "Policy Heading\nLine two"

        pptx_response = client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={"title": "Deck PPTX"},
            files={
                "file": (
                    "deck.pptx",
                    _build_pptx_bytes([["Slide one title", "Body line"]]),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )
        # Phase 5.5: ingestion is asynchronous (§7.1.5); poll until it settles.
        assert pptx_response.status_code == 202
        pptx_payload = pptx_response.json()
        assert _wait_document_ready(client, token, pptx_payload["id"])["status"] == "ready"
        pptx_payload = client.get(
            f"/api/v1/documents/{pptx_payload['id']}", headers={"Authorization": f"Bearer {token}"}
        ).json()
        assert pptx_payload["extraction_status"] == "ready"

        pptx_text_response = client.get(
            f"/api/v1/documents/{pptx_payload['id']}/extracted-text",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pptx_text_response.status_code == 200
        assert pptx_text_response.json()["clean_text"] == "Slide one title\nBody line"
    finally:
        settings.max_document_size_bytes = original_limit


def test_scanned_pdf_without_ocr_dependencies_marks_extraction_failed() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Scanned PDF"},
        files={"file": ("scan.pdf", _build_blank_pdf_bytes(), "application/pdf")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion);
    # the OCR failure surfaces through the §8 status endpoint once the task runs.
    assert upload_response.status_code == 202
    final_status = _wait_document_ready(client, token, upload_response.json()["id"])
    assert final_status["status"] == "failed", final_status
    assert "OCR" in (final_status["error_message"] or "")


def test_empty_text_document_is_detected_as_broken() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Empty Notes"},
        files={"file": ("empty.txt", b"   \n\n\t", "text/plain")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion);
    # the deterministic extraction failure marks the document failed.
    assert upload_response.status_code == 202
    final_status = _wait_document_ready(client, token, upload_response.json()["id"])
    assert final_status["status"] == "failed", final_status
    payload = client.get(
        f"/api/v1/documents/{upload_response.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert payload["extraction_status"] == "failed"
    assert payload["extraction_error"] == "Document is empty or unreadable after cleaning"
    assert payload["chunking_status"] == "pending"
    assert payload["chunk_count"] == 0


def test_document_chunk_preview_and_manual_regeneration_support_multiple_strategies() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    # Each sentence is long enough to clear the token floor that
    # _apply_token_limits enforces (audit F-018), so multi-chunk splits survive.
    text = (
        "# Overview\n"
        "The employee handbook defines the leave policy for every department in the company and explains "
        "how requests are submitted, approved, and recorded throughout the year.\n\n"
        "## Details\n"
        "Carry-forward requests must be reviewed by the HR manager before the end of the annual cycle, and "
        "any exception requires written approval from the department head as well."
    )
    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Chunk Strategy Sample"},
        files={"file": ("chunk-sample.md", text.encode("utf-8"), "text/markdown")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion).
    assert upload_response.status_code == 202
    payload = upload_response.json()
    assert _wait_document_ready(client, token, payload["id"])["status"] == "ready"
    payload = client.get(f"/api/v1/documents/{payload['id']}", headers={"Authorization": f"Bearer {token}"}).json()
    assert payload["chunking_status"] == "ready"

    regenerate_response = client.post(
        f"/api/v1/documents/{payload['id']}/chunk",
        headers={"Authorization": f"Bearer {token}"},
        json={"chunk_size": 100, "overlap": 20, "strategies": ["sentence_based", "section_based"]},
    )
    assert regenerate_response.status_code == 200
    assert regenerate_response.json()["status"] == "ready"
    # Explicit multi-strategy runs still work for the Phase 4 comparison;
    # indices stay contiguous across strategies (audit F-019).
    assert regenerate_response.json()["chunk_count"] >= 2

    sentence_preview_response = client.get(
        f"/api/v1/documents/{payload['id']}/chunks/preview",
        headers={"Authorization": f"Bearer {token}"},
        params={"strategy": "sentence_based", "page_size": 10},
    )
    assert sentence_preview_response.status_code == 200
    sentence_payload = sentence_preview_response.json()
    assert sentence_payload["total"] >= 2
    assert all(item["strategy"] == "sentence_based" for item in sentence_payload["items"])

    section_preview_response = client.get(
        f"/api/v1/documents/{payload['id']}/chunks/preview",
        headers={"Authorization": f"Bearer {token}"},
        params={"strategy": "section_based", "page_size": 10},
    )
    assert section_preview_response.status_code == 200
    section_payload = section_preview_response.json()
    assert section_payload["total"] >= 1
    assert any(item["section_title"] == "Overview" for item in section_payload["items"])


def test_phase5_okf_knowledge_extraction_search_and_versioning() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    document_text = (
        "# Leave Policy\n"
        "Department: Human Resources\n"
        "Employee: Jane Doe\n"
        "Title: HR Manager\n"
        "Department: Human Resources\n"
        "Manager: John Smith\n"
        "Product: Knowledge Portal\n"
        "Asset: Employee Handbook\n"
        "Q: What is the carry-forward limit?\n"
        "A: Employees may carry forward up to 5 leave days.\n"
        "Employees must submit leave requests 3 days in advance.\n"
        "Only HR should approve emergency leave exceptions.\n"
    )

    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Leave Policy Source"},
        files={"file": ("leave-policy.md", document_text.encode("utf-8"), "text/markdown")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion).
    assert upload_response.status_code == 202
    document_payload = upload_response.json()

    extract_response = client.post(
        f"/api/v1/knowledge/extract/{document_payload['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extract_response.status_code == 200
    extracted_payload = extract_response.json()
    assert extracted_payload["document_id"] == document_payload["id"]
    # The ingestion pipeline now auto-extracts on upload, so re-running the
    # endpoint deduplicates by object_key (created=0); the items list carries
    # every live object for the document.
    assert len(extracted_payload["items"]) >= 6
    assert any(item["object_type"] == "policy" for item in extracted_payload["items"])
    assert any(item["object_type"] == "department" for item in extracted_payload["items"])
    assert any(item["object_type"] == "employee" for item in extracted_payload["items"])
    assert any(item["object_type"] == "faq" for item in extracted_payload["items"])
    assert any(item["object_type"] == "business_rule" for item in extracted_payload["items"])

    list_response = client.get(
        "/api/v1/knowledge",
        headers={"Authorization": f"Bearer {token}"},
        params={"document_id": document_payload["id"]},
    )
    assert list_response.status_code == 200
    listed_payload = list_response.json()
    assert listed_payload["total"] >= 6

    search_response = client.get(
        "/api/v1/knowledge/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "carry-forward", "document_id": document_payload["id"]},
    )
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["total"] >= 1
    faq_item = next(item for item in search_payload["items"] if item["object_type"] == "faq")
    assert faq_item["payload"]["answer"] == "Employees may carry forward up to 5 leave days."
    assert faq_item["source_document_id"] == document_payload["id"]

    read_response = client.get(
        f"/api/v1/knowledge/{faq_item['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read_response.status_code == 200
    assert read_response.json()["name"] == "What is the carry-forward limit?"

    update_response = client.put(
        f"/api/v1/knowledge/{faq_item['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "payload": {
                "question": "What is the carry-forward limit?",
                "answer": "Employees may carry forward up to 7 leave days.",
            },
            "summary": "Carry-forward allowance updated",
            # Spec §8: edits require a change note (audit F-038).
            "change_note": "Answer corrected after policy review",
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["object_version"] == 2
    assert updated_payload["is_current"] is True
    assert updated_payload["payload"]["answer"] == "Employees may carry forward up to 7 leave days."

    versions_response = client.get(
        f"/api/v1/knowledge/{faq_item['id']}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert versions_response.status_code == 200
    versions_payload = versions_response.json()
    assert versions_payload["total"] == 2
    assert versions_payload["items"][0]["object_version"] == 2
    assert versions_payload["items"][0]["payload"]["answer"] == "Employees may carry forward up to 7 leave days."
    assert versions_payload["items"][1]["object_version"] == 1
    assert versions_payload["items"][1]["is_current"] is False


def test_knowledge_write_requires_admin_and_read_allows_authenticated_user() -> None:
    employee_login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "StrongPass123"},
    )
    employee_token = employee_login.json()["access_token"]

    read_response = client.get(
        "/api/v1/knowledge",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert read_response.status_code == 200

    create_response = client.post(
        "/api/v1/knowledge",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={
            "object_type": "department",
            "name": "Finance",
            "payload": {"name": "Finance"},
        },
    )
    assert create_response.status_code == 403


def test_document_delete_removes_phase5_knowledge_objects() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    token = login_response.json()["access_token"]

    document_text = "# Security Policy\nDepartment: Compliance\nEmployees must follow the approved workflow.\n"
    upload_response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Security Policy"},
        files={"file": ("security-policy.md", document_text.encode("utf-8"), "text/markdown")},
    )
    # Phase 5.5: spec §7.1.5 — upload returns 202 Accepted (async ingestion).
    assert upload_response.status_code == 202
    document_id = upload_response.json()["id"]

    extract_response = client.post(
        f"/api/v1/knowledge/extract/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extract_response.status_code == 200
    assert len(extract_response.json()["items"]) >= 1  # pipeline auto-extracted; endpoint dedupes

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204


# ===========================================================================
# 2. Phase 0-5 audit-fix regressions (former tests/test_phase0_5_fixes.py)
# ===========================================================================

def _login(email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {_login('admin@example.com', 'StrongPass123')}"}


def _employee_headers() -> tuple[dict, str]:
    client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Reg Employee", "email": "reg.employee@test.com", "password": "Passw0rd123"},
    )
    token = _login("reg.employee@test.com", "Passw0rd123")
    return {"Authorization": f"Bearer {token}"}, token


def _wait_ingestion_settled(headers: dict, document_id: int, *, timeout_s: float = 10.0) -> dict:
    """Poll the §8 status endpoint until background ingestion reaches ready/failed."""

    deadline = time.monotonic() + timeout_s
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/documents/{document_id}/status", headers=headers)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in {"ready", "failed"}:
            return last
        time.sleep(0.05)
    return last


# ---------------------------------------------------------------------------
# P0 F-003 / F-017 / F-036 — cleaner must never destroy content
# ---------------------------------------------------------------------------


def test_cleaner_preserves_currency_dates_unicode_and_strips_controls() -> None:
    src = (
        "Leave: 12 days. Salary band \u20b95,000-\u20b99,000 on 15/03/2025 (10%). "
        "Mail hr@acme.com\nCost \u20b9500 \u2014 approved \u201cyes\u201d\nHindi: \u0939\u093f\u0928\u094d\u0926\u0940"
    )
    out = _clean_text(src)
    for token in [
        "12 days",
        "\u20b95,000",
        "\u20b99,000",
        "15/03/2025",
        "10%",
        "hr@acme.com",
        "\u2014",
        "\u201cyes\u201d",
        "\u0939\u093f\u0928\u094d\u0926\u0940",
    ]:
        assert token in out, f"{token!r} was destroyed by the cleaner"
    # control / zero-width characters are still removed
    cleaned = _clean_text("ok\u200b\u0007text")
    assert "\u200b" not in cleaned and "\u0007" not in cleaned and cleaned == "oktext"


def test_cleaner_is_idempotent() -> None:
    once = _clean_text("A  b\r\n\r\n\r\n\r\nC \u20b9100")
    assert _clean_text(once) == once


def test_cleaner_rejoins_hyphen_wraps_but_keeps_real_hyphens() -> None:
    out = _clean_text("full-time staff may carry-\nforward leave")
    assert "full-time" in out
    assert "carry-\nforward" not in out
    assert "carryforward" in out


def test_header_footer_removes_only_over_40_percent_lines() -> None:
    pages = [
        f"{'ACME Confidential' if i < 2 else f'Unique header {i}'}\nBody paragraph {i} text.\nPage {i + 1} of 30"
        for i in range(30)
    ]
    joined = "\n".join(_remove_repeated_page_lines(pages))
    # a line on 2/30 pages (6.7%) must NOT be deleted (audit P3-22)
    assert "ACME Confidential" in joined
    # a line on >40% of pages must be deleted
    pages2 = [f"ACME Footer\nBody {i}." for i in range(10)]
    joined2 = "\n".join(_remove_repeated_page_lines(pages2))
    assert "ACME Footer" not in joined2 and "Body 3." in joined2


# ---------------------------------------------------------------------------
# P0 F-002 / F-007 — upload validation, status codes, no 500 / stuck rows
# ---------------------------------------------------------------------------


def test_disguised_executable_is_rejected_415() -> None:
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Fake PDF"},
        files={"file": ("report.pdf", b"MZ\x90\x00 definitely not a pdf", "application/pdf")},
    )
    assert response.status_code == 415


def test_empty_file_is_rejected_422() -> None:
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Empty"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 422


def test_binary_content_masquerading_as_text_is_rejected_415() -> None:
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Binary txt"},
        files={"file": ("notes.txt", b"hello\x00world", "text/plain")},
    )
    assert response.status_code == 415


def test_corrupt_pdf_fails_gracefully_without_500_or_stuck_processing() -> None:
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Corrupt PDF"},
        files={"file": ("corrupt.pdf", b"%PDF-1.4\n%\xff\xfe garbage bytes", "application/pdf")},
    )
    assert response.status_code == 202, response.text  # §7.1.5: async ingestion
    doc_id = response.json()["id"]
    # The failure surfaces once the background task has run; never stuck processing.
    assert _wait_ingestion_settled(headers, doc_id)["status"] == "failed"
    body = client.get(f"/api/v1/documents/{doc_id}", headers=headers).json()
    assert body["extraction_status"] == "failed"
    assert body["extraction_error"]
    assert body["status"] == "failed"


def test_encrypted_pdf_fails_with_clear_message_not_500() -> None:
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret123")
    writer.write(buffer)
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Locked PDF"},
        files={"file": ("locked.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 202, response.text  # §7.1.5: async ingestion
    doc_id = response.json()["id"]
    assert _wait_ingestion_settled(headers, doc_id)["status"] == "failed"
    body = client.get(f"/api/v1/documents/{doc_id}", headers=headers).json()
    assert body["extraction_status"] == "failed"
    assert body["status"] == "failed"


def test_oversized_upload_returns_413() -> None:
    headers = _admin_headers()
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Too big"},
        files={"file": ("big.txt", b"a" * (settings.max_document_size_bytes + 100), "text/plain")},
    )
    assert response.status_code == 413


def test_duplicate_upload_returns_409_and_force_overrides() -> None:
    headers = _admin_headers()
    payload = b"unique duplicate content for audit test 409"
    first = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Dup A"},
        files={"file": ("dup_a.txt", payload, "text/plain")},
    )
    assert first.status_code == 202, first.text  # §7.1.5: async ingestion
    second = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Dup B"},
        files={"file": ("dup_b.txt", payload, "text/plain")},
    )
    assert second.status_code == 409
    assert str(first.json()["id"]) in second.json()["error"]["message"]
    forced = client.post(
        "/api/v1/documents",
        headers=headers,
        params={"force": "true"},
        data={"title": "Dup C"},
        files={"file": ("dup_c.txt", payload, "text/plain")},
    )
    assert forced.status_code == 202


def test_document_status_lifecycle_and_no_client_writable_status() -> None:
    headers = _admin_headers()
    upload = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": "Lifecycle", "status": "uploaded"},
        files={"file": ("lifecycle.txt", b"lifecycle content for status test", "text/plain")},
    )
    assert upload.status_code == 202, upload.text  # §7.1.5: async ingestion
    doc_id = upload.json()["id"]
    # Status is derived from the pipeline: the ignored client "status" field
    # never wins, and the finished document is ready — not the forced value.
    assert _wait_ingestion_settled(headers, doc_id)["status"] == "ready"
    updated = client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"status": "uploaded"},  # not part of the PATCH schema -> ignored
    )
    assert updated.status_code == 200
    assert client.get(f"/api/v1/documents/{doc_id}", headers=headers).json()["status"] == "ready"


def test_list_documents_is_paginated() -> None:
    headers = _admin_headers()
    response = client.get("/api/v1/documents", params={"page": 1, "page_size": 2}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert len(body["items"]) <= 2
    assert body["page"] == 1 and body["page_size"] == 2


# ---------------------------------------------------------------------------
# P0 F-001 / F-011 — knowledge review workflow, employee filter, archive
# ---------------------------------------------------------------------------


def _upload_policy(headers: dict, name: str, content: str) -> int:
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"title": name},
        files={"file": (f"{name.lower().replace(' ', '_')}.md", content.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 202, response.text  # §7.1.5: async ingestion
    doc_id = response.json()["id"]
    # Extraction/chunking must have finished before callers run knowledge extract.
    assert _wait_ingestion_settled(headers, doc_id)["status"] == "ready"
    return doc_id


def test_extracted_knowledge_is_pending_until_approved() -> None:
    admin = _admin_headers()
    employee, _ = _employee_headers()
    doc_id = _upload_policy(
        admin,
        "Review Policy",
        "# Review Policy\nDepartment: Review Dept\nQ: Is review needed?\nA: Yes, always review.\n",
    )
    extract = client.post(f"/api/v1/knowledge/extract/{doc_id}", headers=admin)
    assert extract.status_code == 200
    items = extract.json()["items"]
    assert items and all(item["status"] == "pending_review" for item in items)

    # employee sees nothing before approval (audit P0 F-001)
    hidden = client.get("/api/v1/knowledge", headers=employee)
    assert hidden.status_code == 200
    assert hidden.json()["total"] == 0

    target = next(item for item in items if item["object_type"] == "faq")
    detail = client.get(f"/api/v1/knowledge/{target['id']}", headers=employee)
    assert detail.status_code == 404  # unreviewed objects are invisible

    # approve -> visible to the employee
    approve = client.post(f"/api/v1/knowledge/{target['id']}/approve", headers=admin, json={"note": "ok"})
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    assert approve.json()["reviewed_by_id"] is not None
    assert approve.json()["review_note"] == "ok"
    visible = client.get(f"/api/v1/knowledge/{target['id']}", headers=employee)
    assert visible.status_code == 200

    # reject another object -> stays hidden
    dept = next(item for item in items if item["object_type"] == "department")
    reject = client.post(f"/api/v1/knowledge/{dept['id']}/reject", headers=admin, json={"note": "dupe"})
    assert reject.status_code == 200 and reject.json()["status"] == "rejected"
    assert client.get(f"/api/v1/knowledge/{dept['id']}", headers=employee).status_code == 404


def test_bulk_review_and_delete_archives() -> None:
    admin = _admin_headers()
    employee, _ = _employee_headers()
    doc_id = _upload_policy(
        admin,
        "Bulk Policy",
        "# Bulk Policy\nDepartment: Bulk Dept\nAsset: Bulk Asset\n",
    )
    extract = client.post(f"/api/v1/knowledge/extract/{doc_id}", headers=admin)
    ids = [item["id"] for item in extract.json()["items"]]
    assert ids

    bulk = client.post(
        "/api/v1/knowledge/bulk-review",
        headers=admin,
        json={"ids": ids, "action": "approve"},
    )
    assert bulk.status_code == 200 and bulk.json()["reviewed"] == len(ids)
    assert client.get("/api/v1/knowledge", headers=employee).json()["total"] >= len(ids)

    # DELETE archives (never hard-deletes) — spec §8 / audit F-011
    delete = client.delete(f"/api/v1/knowledge/{ids[0]}", headers=admin)
    assert delete.status_code == 204
    listed = client.get("/api/v1/knowledge?include_history=true", headers=admin).json()["items"]
    archived = [item for item in listed if item["id"] == ids[0]]
    assert archived and archived[0]["status"] == "archived"
    assert client.get(f"/api/v1/knowledge/{ids[0]}", headers=employee).status_code == 404


def test_deleting_document_archives_knowledge_and_leaves_no_orphans() -> None:
    admin = _admin_headers()
    doc_id = _upload_policy(
        admin,
        "Orphan Policy",
        "# Orphan Policy\nDepartment: Orphan Dept\nQ: Why?\nA: Because.\n",
    )
    extract = client.post(f"/api/v1/knowledge/extract/{doc_id}", headers=admin)
    knowledge_ids = [item["id"] for item in extract.json()["items"]]
    assert knowledge_ids

    assert client.delete(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 204
    assert client.get(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 404

    listed = client.get("/api/v1/knowledge?include_history=true", headers=admin).json()["items"]
    survivors = [item for item in listed if item["id"] in knowledge_ids]
    # rows are archived, not destroyed; nothing references the document anymore
    assert survivors and all(item["status"] == "archived" for item in survivors)
    assert all(item["source_document_id"] is None for item in survivors)


def test_same_entity_from_two_documents_stays_one_live_object() -> None:
    admin = _admin_headers()
    doc_a = _upload_policy(admin, "Key Doc A", "# Policy A\nDepartment: Shared Entity Dept\n")
    doc_b = _upload_policy(admin, "Key Doc B", "# Policy B\nDepartment: Shared Entity Dept\n")
    assert client.post(f"/api/v1/knowledge/extract/{doc_a}", headers=admin).status_code == 200
    assert client.post(f"/api/v1/knowledge/extract/{doc_b}", headers=admin).status_code == 200

    items = [
        item
        for item in client.get("/api/v1/knowledge?include_history=true", headers=admin).json()["items"]
        if item["object_key"] == "department:shared-entity-dept"
    ]
    live = [item for item in items if item["status"] in ("pending_review", "approved")]
    assert len(live) == 1, f"expected one live object per key, got {len(live)}"


def test_spec_required_attributes_enforced() -> None:
    admin = _admin_headers()
    missing_subject = client.post(
        "/api/v1/knowledge",
        headers=admin,
        json={"object_type": "business_rule", "name": "No subject", "payload": {"statement": "x"}},
    )
    assert missing_subject.status_code == 422
    missing_summary = client.post(
        "/api/v1/knowledge",
        headers=admin,
        json={"object_type": "policy", "name": "No summary", "payload": {"title": "T"}},
    )
    assert missing_summary.status_code == 422
    ok = client.post(
        "/api/v1/knowledge",
        headers=admin,
        json={
            "object_type": "business_rule",
            "name": "Valid rule",
            "payload": {"statement": "Carry forward up to 12 days.", "subject": "annual leave"},
        },
    )
    assert ok.status_code == 201
    assert ok.json()["status"] == "approved"  # manual creation is admin-approved


def test_unknown_relation_predicate_rejected() -> None:
    admin = _admin_headers()
    response = client.post(
        "/api/v1/knowledge",
        headers=admin,
        json={
            "object_type": "department",
            "name": "Predicate Dept",
            "payload": {"name": "Predicate Dept"},
            "relations": [{"relation_type": "loves", "target_name": "IT"}],
        },
    )
    assert response.status_code == 422


def test_knowledge_update_requires_change_note() -> None:
    admin = _admin_headers()
    created = client.post(
        "/api/v1/knowledge",
        headers=admin,
        json={"object_type": "asset", "name": "Note Asset", "payload": {"name": "Note Asset"}},
    )
    assert created.status_code == 201
    obj_id = created.json()["id"]
    missing_note = client.put(
        f"/api/v1/knowledge/{obj_id}",
        headers=admin,
        json={"payload": {"name": "Note Asset", "status": "retired"}},
    )
    assert missing_note.status_code == 422
    with_note = client.put(
        f"/api/v1/knowledge/{obj_id}",
        headers=admin,
        json={"payload": {"name": "Note Asset", "status": "retired"}, "change_note": "decommissioned"},
    )
    assert with_note.status_code == 200
    assert with_note.json()["object_version"] == 2


# ---------------------------------------------------------------------------
# P1 — chunking fixes
# ---------------------------------------------------------------------------


def test_default_chunking_is_single_strategy_with_contiguous_indices_and_tokens() -> None:
    headers = _admin_headers()
    # Kept under the test size cap (conftest sets MAX_DOCUMENT_SIZE_BYTES=1024).
    content = (
        "# Chunk Policy\n\nIntro on 15/03/2025.\n\n"
        "## Leave\n\nCarry forward 12 days.\n\n"
        "## Assets\n\nLaptops refresh in 3 years.\n\n"
        "## Travel\n\nClass II rail allowed.\n"
    )
    doc_id = _upload_policy(headers, "Chunk Policy Doc", content)
    preview = client.get(
        f"/api/v1/documents/{doc_id}/chunks/preview",
        headers=headers,
        params={"page_size": 100},
    )
    assert preview.status_code == 200
    body = preview.json()
    items = body["items"]
    assert items, "expected chunks"
    strategies = {item["strategy"] for item in items}
    assert strategies == {"section_based"}, "default must be the single production strategy"
    indices = sorted(item["chunk_index"] for item in items)
    assert indices == list(range(len(items)))  # contiguous from 0, unique
    assert all(item["token_count"] and item["token_count"] <= settings.chunk_max_tokens for item in items)
    # metadata copied onto chunks (ACL denormalization)
    from app.models.chunk import Chunk
    from tests.conftest import TestingSessionLocal

    session = TestingSessionLocal()
    try:
        rows = session.query(Chunk).filter(Chunk.document_id == doc_id).all()
        assert all(row.visibility is not None and row.department_ids is not None for row in rows)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# P1 — extraction fidelity
# ---------------------------------------------------------------------------


def test_pptx_slide_order_and_speaker_notes(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        for n in range(1, 13):
            archive.writestr(
                f"ppt/slides/slide{n}.xml",
                '<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>SLIDE {n}</a:t></a:r></a:p></p:txBody></p:sp>"
                "</p:spTree></p:cSld></p:sld>",
            )
        archive.writestr(
            "ppt/notesSlides/notesSlide2.xml",
            '<?xml version="1.0"?><p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>NOTE two</a:t></a:r></a:p></p:notes>',
        )
    path = tmp_path / "deck.pptx"
    path.write_bytes(buffer.getvalue())

    text = _extract_pptx_text(path)
    order = re.findall(r"SLIDE (\d+)", text)
    assert order == [str(i) for i in range(1, 13)]  # natural order, not 1,10,11,12,2...
    assert "[speaker notes] NOTE two" in text


def test_docx_headings_tables_and_lists(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        )
        body = (
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Policy Title</w:t></w:r></w:p>'
            "<w:p><w:r><w:t>Plain paragraph.</w:t></w:r></w:p>"
            "<w:tbl><w:tr><w:tc><w:p><w:t>Cell A</w:t></w:p></w:tc>"
            "<w:tc><w:p><w:t>Cell B</w:t></w:p></w:tc></w:tr></w:tbl>"
            "<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Bullet item</w:t></w:r></w:p>"
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body></w:document>",
        )
    path = tmp_path / "policy.docx"
    path.write_bytes(buffer.getvalue())

    text = _extract_docx_text(path)
    assert "# Policy Title" in text  # heading marked for the section splitter
    assert "Plain paragraph." in text
    assert "Cell A | Cell B" in text  # table row flattened, cells joined
    assert "- Bullet item" in text  # list marker preserved


# ---------------------------------------------------------------------------
# P1 — infra fixes: audit log, CORS, health, .env.example, auth attacks
# ---------------------------------------------------------------------------


def test_audit_log_records_login_upload_and_review() -> None:
    admin = _admin_headers()
    _upload_policy(admin, "Audit Policy", "# Audit Policy\nnothing special here\n")
    from app.models.audit import AuditLog
    from tests.conftest import TestingSessionLocal

    session = TestingSessionLocal()
    try:
        actions = [row.action for row in session.query(AuditLog).all()]
    finally:
        session.close()
    assert "auth.login" in actions
    assert "document.upload" in actions


def test_cors_allows_configured_origin_only() -> None:
    allowed = settings.cors_origin_list[0]
    ok = client.get("/api/v1/health", headers={"Origin": allowed})
    assert "access-control-allow-origin" in ok.headers
    blocked = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_health_is_liveness_and_ready_checks_database() -> None:
    live = client.get("/api/v1/health")
    assert live.status_code == 200 and live.json() == {"status": "ok"}
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200 and ready.json()["database"] == "connected"


def test_env_example_exists_and_lists_required_variables() -> None:
    env_example = Path(__file__).resolve().parent.parent / ".env.example"
    assert env_example.exists(), ".env.example is required by the README/setup"
    content = env_example.read_text(encoding="utf-8")
    for var in ["DATABASE_URL", "JWT_SECRET", "ACCESS_TOKEN_EXPIRE_MINUTES"]:
        assert var in content


def test_alembic_ini_has_no_embedded_credentials() -> None:
    ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    content = ini.read_text(encoding="utf-8")
    assert not re.search(r"://[^/\s]+:[^@\s]+@", content), "credentials must not live in alembic.ini"


def test_token_attacks_are_rejected() -> None:
    headers = _admin_headers()
    token = headers["Authorization"].split(" ", 1)[1]

    tampered = token[:-3] + "abc"
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401

    none_alg = jwt.encode({"sub": "admin@example.com", "role": "admin"}, "", algorithm="HS256")
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {none_alg}"}).status_code == 401

    secret = settings.secret_key
    expired = jwt.encode(
        {"sub": "admin@example.com", "role": "admin", "exp": 1, "iat": 1, "jti": "x"},
        secret,
        algorithm="HS256",
    )
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_signup_cannot_self_promote_and_weak_password_rejected() -> None:
    weak = client.post(
        "/api/v1/auth/signup",
        json={"full_name": "Weak", "email": "weak.signup@test.com", "password": "abc"},
    )
    assert weak.status_code == 422
    promoted = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Promoted",
            "email": "promoted.signup@test.com",
            "password": "Passw0rd123",
            "role": "admin",
        },
    )
    assert promoted.status_code == 201 and promoted.json()["role"] == "employee"


# ===========================================================================
# 3. Phase 7 retrieval (former tests/test_phase7.py)
# ===========================================================================

def _admin_token() -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _employee_token() -> str:
    # Reuse the employee (employee@example.com) created in the core-API section
    # above; create if absent.
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
    # Simulate a single item that exceeds the budget.
    from app.services.retrieval.merger import ContextItem, _trim_to_budget

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
    from unittest.mock import patch

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


# ===========================================================================
# 4. Phase 8 answer generation and chat (former tests/test_phase8.py)
# ===========================================================================

def _phase8_employee_token() -> str:
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


def test_clean_citations_normalizes_groq_fullwidth_refs() -> None:
    from app.services.answer import _clean_citations

    text = "The model is BAAI/bge-small-en-v1.5【S1】."
    cleaned, cited = _clean_citations(text, {"S1"})
    assert cleaned == "The model is BAAI/bge-small-en-v1.5[S1]."
    assert cited == {"S1"}


def test_clean_citations_removes_absent_refs() -> None:
    from app.services.answer import _clean_citations

    text = "The limit is 12 days [S1]. Also [S99] and 【S100】."
    cleaned, cited = _clean_citations(text, {"S1"})
    assert "[S99]" not in cleaned
    assert "S99" not in cited
    assert "S100" not in cleaned
    assert "S100" not in cited
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
    from app.services.llm import _is_retryable

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
    token = _phase8_employee_token()
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
    emp_token = _phase8_employee_token()
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
    from app.services.classifier import ClassifierResult
    from app.services.retrieval.fusion import ChunkResult
    from app.services.retrieval.merger import ContextItem
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


# ===========================================================================
# 5. Admin bootstrap (managed account from ADMIN_EMAIL/ADMIN_PASSWORD)
# ===========================================================================

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password, verify_password
from app.models.base import Base
from app.services.admin_bootstrap import sync_configured_admin


def test_sync_configured_admin_updates_managed_account(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        monkeypatch.setattr(settings, "admin_email", "first.admin@example.com")
        monkeypatch.setattr(settings, "admin_password", SecretStr("FirstPassword1"))
        initial = sync_configured_admin(db)

        assert initial is not None
        initial_id = initial.id
        assert initial.role == UserRole.ADMIN
        assert initial.is_bootstrap_admin is True
        assert verify_password("FirstPassword1", initial.hashed_password)

        monkeypatch.setattr(settings, "admin_email", "new.admin@example.com")
        monkeypatch.setattr(settings, "admin_password", SecretStr("SecondPassword2"))
        updated = sync_configured_admin(db)

        assert updated is not None
        assert updated.id == initial_id
        assert updated.email == "new.admin@example.com"
        assert verify_password("SecondPassword2", updated.hashed_password)
        assert not verify_password("FirstPassword1", updated.hashed_password)
        assert db.query(User).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_sync_configured_admin_rejects_email_owned_by_another_user(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        managed = User(
            full_name="Managed Admin",
            email="managed@example.com",
            hashed_password=hash_password("ManagedPassword1"),
            role=UserRole.ADMIN,
            is_active=True,
            is_bootstrap_admin=True,
        )
        other = User(
            full_name="Other User",
            email="taken@example.com",
            hashed_password=hash_password("OtherPassword1"),
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        db.add_all([managed, other])
        db.commit()

        monkeypatch.setattr(settings, "admin_email", "taken@example.com")
        monkeypatch.setattr(settings, "admin_password", SecretStr("NewPassword2"))

        try:
            sync_configured_admin(db)
        except RuntimeError as exc:
            assert "different user" in str(exc)
        else:
            raise AssertionError("Expected conflicting admin email to be rejected")

        db.expire_all()
        assert db.query(User).filter(User.email == "managed@example.com").one().is_bootstrap_admin
        assert db.query(User).filter(User.email == "taken@example.com").one().role == UserRole.EMPLOYEE
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# 6. Trusted documents — admin auto-approve of extracted knowledge
# ---------------------------------------------------------------------------


def _upload_small_policy(title: str, marker: str) -> int:
    upload = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {_admin_token()}"},
        data={"title": title},
        files={
            "file": (
                f"{marker}.md",
                (
                    f"# {title}\nDepartment: Trust Dept {marker}\n"
                    f"Q: Does {marker} trust work?\nA: Trusted documents approve facts automatically.\n"
                ).encode(),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 202, upload.text
    document_id = upload.json()["id"]
    assert _wait_document_ready(client, _admin_token(), document_id)["status"] == "ready"
    return document_id


def test_trusted_document_auto_approves_knowledge() -> None:
    admin_headers = {"Authorization": f"Bearer {_admin_token()}"}
    document_id = _upload_small_policy("Trusted Policy Doc", "trustone")

    # The ingestion pipeline auto-extracted, but an untrusted document waits for review.
    listed = client.get("/api/v1/knowledge", headers=admin_headers, params={"document_id": document_id}).json()
    assert listed["total"] >= 1
    assert all(item["status"] == "pending_review" for item in listed["items"])

    # Marking the document trusted approves its pending facts in bulk.
    patched = client.patch(
        f"/api/v1/documents/{document_id}",
        headers=admin_headers,
        json={"auto_approve_knowledge": True},
    )
    assert patched.status_code == 200
    assert patched.json()["auto_approve_knowledge"] is True

    listed = client.get("/api/v1/knowledge", headers=admin_headers, params={"document_id": document_id}).json()
    assert listed["total"] >= 1
    assert all(item["status"] == "approved" for item in listed["items"])

    # Employees immediately see trusted facts without a manual review step.
    employee_headers, _ = _employee_headers()
    visible = client.get("/api/v1/knowledge", headers=employee_headers, params={"document_id": document_id}).json()
    assert visible["total"] >= 1

    # Re-extraction (e.g. after reprocess) keeps facts approved — no review regression.
    again = client.post(f"/api/v1/knowledge/extract/{document_id}", headers=admin_headers)
    assert again.status_code == 200
    assert again.json()["items"], "expected extraction items"
    assert all(item["status"] == "approved" for item in again.json()["items"])


def test_untrusted_document_keeps_knowledge_pending() -> None:
    admin_headers = {"Authorization": f"Bearer {_admin_token()}"}
    document_id = _upload_small_policy("Untrusted Policy Doc", "trusttwo")

    listed = client.get("/api/v1/knowledge", headers=admin_headers, params={"document_id": document_id}).json()
    assert listed["total"] >= 1
    assert all(item["status"] == "pending_review" for item in listed["items"])

    # Employee still sees nothing while it is untrusted and unreviewed.
    employee_headers, _ = _employee_headers()
    hidden = client.get("/api/v1/knowledge", headers=employee_headers, params={"document_id": document_id}).json()
    assert hidden["total"] == 0
