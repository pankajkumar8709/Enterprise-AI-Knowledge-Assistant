import io
from pathlib import Path
import zipfile

from pypdf import PdfWriter

from app.core.config import settings
from app.models.user import UserRole

from tests.conftest import client


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
        paragraph_xml = "".join(
            f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs
        )
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
            text_nodes = "".join(
                f"<a:t>{line}</a:t>" for line in slide_lines
            )
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


def test_signup_login_and_verify_token() -> None:
    signup_response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Admin User",
            "email": "admin@example.com",
            "password": "StrongPass123",
            "role": UserRole.ADMIN.value,
        },
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    verify_response = client.get(
        "/api/v1/auth/verify-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["email"] == "admin@example.com"


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
    assert upload_response.status_code == 201
    created_document = upload_response.json()
    assert created_document["status"] == "uploaded"
    assert created_document["version"] == 1
    assert created_document["extraction_status"] == "ready"
    assert created_document["extracted_char_count"] == len("phase 2 upload content")
    assert Path(created_document["storage_path"]).exists()
    assert Path(created_document["extraction_raw_text_path"]).exists()
    assert Path(created_document["extraction_clean_text_path"]).exists()

    list_response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    update_response = client.put(
        f"/api/v1/documents/{created_document['id']}",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Updated Handbook", "status": "ready"},
        files={"file": ("handbook.md", b"# updated phase 2 content", "text/markdown")},
    )
    assert update_response.status_code == 200
    updated_document = update_response.json()
    assert updated_document["title"] == "Updated Handbook"
    assert updated_document["status"] == "uploaded"
    assert updated_document["version"] == 2
    assert updated_document["source_name"] == "handbook.md"
    assert updated_document["extraction_status"] == "ready"

    extraction_status_response = client.get(
        f"/api/v1/documents/{created_document['id']}/extraction-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert extraction_status_response.status_code == 200
    assert extraction_status_response.json()["status"] == "ready"

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
    assert invalid_type_response.status_code == 400
    assert invalid_type_response.json()["detail"] == "Unsupported file type"


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
    assert oversized_response.status_code == 400
    assert oversized_response.json()["detail"] == "File exceeds size limit"


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
        assert docx_response.status_code == 201
        docx_payload = docx_response.json()
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
        assert pptx_response.status_code == 201
        pptx_payload = pptx_response.json()
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
    assert upload_response.status_code == 201
    payload = upload_response.json()
    assert payload["extraction_status"] == "failed"
    assert "OCR" in payload["extraction_error"]


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
    assert upload_response.status_code == 201
    payload = upload_response.json()
    assert payload["extraction_status"] == "failed"
    assert payload["extraction_error"] == "Document is empty or unreadable after cleaning"
