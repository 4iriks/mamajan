def test_login_success(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrongpass"}
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "123"})
    assert r.status_code == 401


def test_register_success(client):
    r = client.post(
        "/api/auth/register",
        json={
            "username": "guest-user",
            "password": "secret123",
            "display_name": "Guest User",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "guest-user"
    assert me.json()["display_name"] == "Guest User"
    assert me.json()["role"] == "user"


def test_register_duplicate_username(client):
    payload = {"username": "duplicate-user", "password": "secret123"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 400
    assert second.json()["detail"] == "Логин уже занят"


def test_register_rejects_blank_username(client):
    r = client.post(
        "/api/auth/register", json={"username": "   ", "password": "secret123"}
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Введите логин"


def test_me_returns_current_user(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "admin"
    assert data["role"] == "superadmin"


def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 403


def test_me_invalid_token(client):
    r = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert r.status_code == 401
