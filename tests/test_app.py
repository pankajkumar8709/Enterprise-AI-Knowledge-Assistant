from pathlib import Path

from app.models.user import UserRole

from tests.conftest import client


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
    assert Path(created_document["storage_path"]).exists()

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
