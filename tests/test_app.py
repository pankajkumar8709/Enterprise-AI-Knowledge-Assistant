import io
import time
import zipfile

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.core.config import settings
from app.models.user import User, UserRole
from tests.conftest import client


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
    assert extracted_payload["created"] >= 6
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
    assert extract_response.json()["created"] >= 1

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204
