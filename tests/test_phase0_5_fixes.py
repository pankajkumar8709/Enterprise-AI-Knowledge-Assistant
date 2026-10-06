"""Regression tests for the Phase 0-5 audit fixes (one per P0/P1 finding).

Each test fails if the corresponding fix regresses.
"""

import io
import re
import time
import zipfile
from pathlib import Path

from jose import jwt
from pypdf import PdfWriter

from app.core.config import settings
from app.services.extraction import _clean_text, _extract_docx_text, _extract_pptx_text, _remove_repeated_page_lines
from tests.conftest import client


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
