import os
import sys

# Must be set BEFORE any app imports — overrides the DB engine at module load time
os.environ["DATABASE_URL"] = "sqlite:///./test_raluma.db"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="session")
def client():
    """Single TestClient for the whole test session. Lifespan runs once (creates tables, seeds admin)."""
    with TestClient(app) as c:
        yield c
    # Dispose engine to release SQLite file lock (required on Windows)
    from database import engine
    engine.dispose()
    # Clean up test DB file after session
    if os.path.exists("./test_raluma.db"):
        os.remove("./test_raluma.db")


@pytest.fixture(scope="session")
def admin_headers(client):
    """Auth headers for the seeded superadmin account."""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def project(client, admin_headers):
    """Creates a test project and deletes it after the test."""
    r = client.post("/api/projects", headers=admin_headers, json={
        "number": "TEST-001",
        "customer": "ПРОЗРАЧНЫЕ РЕШЕНИЯ",
    })
    assert r.status_code == 201
    data = r.json()
    yield data
    client.delete(f"/api/projects/{data['id']}", headers=admin_headers)


@pytest.fixture
def section(client, admin_headers, project):
    """Creates a test СЛАЙД section inside the test project."""
    r = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "Секция 1",
            "system": "СЛАЙД",
            "width": 2000,
            "height": 2400,
            "panels": 3,
            "quantity": 1,
            "rails": 3,
            "first_panel_inside": "Справа",
        },
    )
    assert r.status_code == 201
    yield r.json()
    # Section is cascade-deleted when the project fixture deletes the project
