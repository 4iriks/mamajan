from uuid import uuid4


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _login_headers(client, username: str, password: str) -> dict[str, str]:
    r = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_user(client, admin_headers, role: str = "user", **overrides):
    password = overrides.pop("password", "secret123")
    username = overrides.pop("username", _unique(role))
    payload = {
        "username": username,
        "display_name": overrides.pop("display_name", username),
        "password": password,
        "role": role,
        "is_active": True,
    }
    payload.update(overrides)
    r = client.post("/api/users", headers=admin_headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json(), password


def test_superadmin_creates_dealer_with_normalized_details(client, admin_headers):
    username = _unique("dealer")
    r = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": f"  {username}  ",
            "display_name": "  ",
            "password": "secret123",
            "role": "dealer",
            "dealer_company": "  ООО Дилер  ",
            "dealer_contact_name": "  Иван Петров  ",
            "dealer_city": "  Казань  ",
            "dealer_discount_percent": 12.5,
            "is_active": True,
        },
    )

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["username"] == username
    assert data["display_name"] == username
    assert data["role"] == "dealer"
    assert data["dealer_company"] == "ООО Дилер"
    assert data["dealer_contact_name"] == "Иван Петров"
    assert data["dealer_city"] == "Казань"
    assert data["dealer_discount_percent"] == 12.5

    client.delete(f"/api/users/{data['id']}", headers=admin_headers)


def test_user_create_rejects_invalid_role_blank_credentials_and_bad_discount(
    client, admin_headers
):
    base = {
        "username": _unique("bad-dealer"),
        "display_name": "Bad Dealer",
        "password": "secret123",
        "role": "dealer",
        "is_active": True,
    }

    bad_role = client.post(
        "/api/users",
        headers=admin_headers,
        json={**base, "username": _unique("bad-role"), "role": "boss"},
    )
    assert bad_role.status_code == 400

    blank_username = client.post(
        "/api/users",
        headers=admin_headers,
        json={**base, "username": "   "},
    )
    assert blank_username.status_code == 400
    assert blank_username.json()["detail"] == "Введите логин"

    blank_password = client.post(
        "/api/users",
        headers=admin_headers,
        json={**base, "username": _unique("blank-pass"), "password": "   "},
    )
    assert blank_password.status_code == 400
    assert blank_password.json()["detail"] == "Введите пароль"

    for discount in (-1, 100.1):
        r = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                **base,
                "username": _unique("bad-discount"),
                "dealer_discount_percent": discount,
            },
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "Скидка дилера должна быть от 0 до 100"


def test_admin_sees_and_manages_only_employees_and_dealers(client, admin_headers):
    regular_admin, admin_password = _create_user(client, admin_headers, role="admin")
    employee, _ = _create_user(
        client,
        admin_headers,
        role="user",
        employee_number="EMP-101",
        position="Менеджер",
    )
    dealer, _ = _create_user(
        client,
        admin_headers,
        role="dealer",
        dealer_company="ООО Доступный дилер",
        dealer_discount_percent=7,
    )
    regular_admin_headers = _login_headers(
        client, regular_admin["username"], admin_password
    )
    seed_superadmin = client.get("/api/auth/me", headers=admin_headers).json()

    listed = client.get("/api/users", headers=regular_admin_headers)
    assert listed.status_code == 200
    listed_usernames = {user["username"] for user in listed.json()}
    assert employee["username"] in listed_usernames
    assert dealer["username"] in listed_usernames
    assert regular_admin["username"] not in listed_usernames
    assert seed_superadmin["username"] not in listed_usernames

    assert (
        client.get(
            f"/api/users/{seed_superadmin['id']}", headers=regular_admin_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/users/{employee['id']}", headers=regular_admin_headers
        ).status_code
        == 200
    )

    create_admin = client.post(
        "/api/users",
        headers=regular_admin_headers,
        json={
            "username": _unique("nested-admin"),
            "display_name": "Nested Admin",
            "password": "secret123",
            "role": "admin",
            "is_active": True,
        },
    )
    assert create_admin.status_code == 403

    promote_employee = client.put(
        f"/api/users/{employee['id']}",
        headers=regular_admin_headers,
        json={"role": "admin"},
    )
    assert promote_employee.status_code == 400
    assert promote_employee.json()["detail"] == (
        "Роль задаётся только при создании учётной записи"
    )

    client.delete(f"/api/users/{employee['id']}", headers=admin_headers)
    client.delete(f"/api/users/{dealer['id']}", headers=admin_headers)
    client.delete(f"/api/users/{regular_admin['id']}", headers=admin_headers)


def test_update_user_validates_discount_and_clears_blank_text_fields(
    client, admin_headers
):
    dealer, _ = _create_user(
        client,
        admin_headers,
        role="dealer",
        dealer_company="ООО Старое имя",
        dealer_discount_percent=5,
    )

    cleared = client.put(
        f"/api/users/{dealer['id']}",
        headers=admin_headers,
        json={"dealer_company": "   ", "dealer_discount_percent": 15},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["dealer_company"] is None
    assert cleared.json()["dealer_discount_percent"] == 15

    invalid_discount = client.put(
        f"/api/users/{dealer['id']}",
        headers=admin_headers,
        json={"dealer_discount_percent": 101},
    )
    assert invalid_discount.status_code == 400
    assert invalid_discount.json()["detail"] == "Скидка дилера должна быть от 0 до 100"

    immutable_role = client.put(
        f"/api/users/{dealer['id']}",
        headers=admin_headers,
        json={"role": "user"},
    )
    assert immutable_role.status_code == 400
    assert immutable_role.json()["detail"] == (
        "Роль задаётся только при создании учётной записи"
    )
    assert (
        client.get(f"/api/users/{dealer['id']}", headers=admin_headers).json()["role"]
        == "dealer"
    )

    client.delete(f"/api/users/{dealer['id']}", headers=admin_headers)


def test_dealer_is_not_admin_and_can_access_only_own_project_scope(
    client, admin_headers
):
    dealer, dealer_password = _create_user(client, admin_headers, role="dealer")
    dealer_headers = _login_headers(client, dealer["username"], dealer_password)
    dealer_token = dealer_headers["Authorization"].replace("Bearer ", "")

    own_project = client.post(
        "/api/projects",
        headers=dealer_headers,
        json={"number": _unique("DEALER-P"), "customer": "Дилер"},
    )
    assert own_project.status_code == 201, own_project.text
    own_project = own_project.json()

    other_project = client.post(
        "/api/projects",
        headers=admin_headers,
        json={"number": _unique("ADMIN-P"), "customer": "Админ"},
    )
    assert other_project.status_code == 201, other_project.text
    other_project = other_project.json()

    own_section = client.post(
        f"/api/projects/{own_project['id']}/sections",
        headers=dealer_headers,
        json={"name": "Своя секция", "system": "СЛАЙД"},
    )
    assert own_section.status_code == 201, own_section.text

    other_section = client.post(
        f"/api/projects/{other_project['id']}/sections",
        headers=admin_headers,
        json={"name": "Чужая секция", "system": "СЛАЙД"},
    )
    assert other_section.status_code == 201, other_section.text
    other_section = other_section.json()

    listed_projects = client.get("/api/projects", headers=dealer_headers)
    assert listed_projects.status_code == 200
    listed_ids = {project["id"] for project in listed_projects.json()}
    assert own_project["id"] in listed_ids
    assert other_project["id"] not in listed_ids

    assert (
        client.get(
            f"/api/projects/{own_project['id']}", headers=dealer_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/projects/{other_project['id']}", headers=dealer_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/projects/{other_project['id']}/sections", headers=dealer_headers
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/projects/{other_project['id']}/sections/{other_section['id']}/overrides",
            headers=dealer_headers,
            json={"overrides": {"x": "1"}},
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/projects/{other_project['id']}/sections/{other_section['id']}/preview",
            params={"token": dealer_token},
        ).status_code
        == 403
    )
    assert client.get("/api/users", headers=dealer_headers).status_code == 403

    client.delete(f"/api/projects/{own_project['id']}", headers=dealer_headers)
    client.delete(f"/api/projects/{other_project['id']}", headers=admin_headers)
    client.delete(f"/api/users/{dealer['id']}", headers=admin_headers)
