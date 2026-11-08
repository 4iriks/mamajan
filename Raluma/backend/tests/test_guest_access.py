"""Anonymous callers cannot use the application through legacy guest APIs."""

import pytest

from auth import create_access_token, hash_password
from database import SessionLocal
from models import User


APPLICATION_ENDPOINTS = [
    ("GET", "/api/projects"),
    ("GET", "/api/catalog/hardware/options"),
    ("GET", "/api/catalog/cs-systems"),
    ("POST", "/api/calculate/local/book"),
    ("POST", "/api/calculate/local/cs"),
    *[
        ("POST", f"/api/projects/local/sections/{kind}")
        for kind in ("calc", "preview", "pdf", "docx", "xlsx")
    ],
    *[
        ("POST", f"/api/projects/local/documents/sketch/{kind}")
        for kind in ("preview", "pdf", "docx", "xlsx")
    ],
]


@pytest.fixture
def inactive_headers(client):
    with SessionLocal() as db:
        user = User(
            username="inactive-guest-access-test",
            display_name="Inactive access test",
            password_hash=hash_password("unused-test-password"),
            role="user",
            is_active=False,
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, user.username, user.role)
        try:
            yield {"Authorization": f"Bearer {token}"}
        finally:
            db.delete(user)
            db.commit()


@pytest.mark.parametrize("method,path", APPLICATION_ENDPOINTS)
def test_application_requires_login(client, method, path):
    response = client.request(method, path, json={})
    assert response.status_code == 403


@pytest.mark.parametrize("method,path", APPLICATION_ENDPOINTS)
def test_application_rejects_invalid_token(client, method, path):
    response = client.request(
        method, path, json={}, headers={"Authorization": "Bearer invalid.token"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", APPLICATION_ENDPOINTS)
def test_application_rejects_inactive_account(client, inactive_headers, method, path):
    response = client.request(method, path, json={}, headers=inactive_headers)
    assert response.status_code == 401


def test_health_remains_public(client):
    assert client.get("/health").status_code == 200


def test_admin_created_user_can_use_local_calculations_and_catalog(
    client, admin_headers
):
    created = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "local-calculation-user",
            "display_name": "Test user",
            "password": "test-password",
            "role": "dealer",
        },
    )
    assert created.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "local-calculation-user", "password": "test-password"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (
        client.get("/api/catalog/hardware/options", headers=headers).status_code == 200
    )
    assert client.get("/api/catalog/cs-systems", headers=headers).status_code == 200
    response = client.post(
        "/api/projects/local/sections/calc",
        headers=headers,
        json={
            "project": {"number": "LOCAL-AUTH"},
            "section": {"system": "СЛАЙД", "width": 2000, "height": 2400, "panels": 3},
        },
    )
    assert response.status_code == 200

    client.delete(f"/api/users/{created.json()['id']}", headers=admin_headers)
