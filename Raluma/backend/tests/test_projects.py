from concurrent.futures import ThreadPoolExecutor
import json

from sqlalchemy import create_engine, text

from migrations import _DATA_MIGRATIONS, _migrate_section_extras_to_project


def test_create_project(client, admin_headers):
    r = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "number": "P-CREATE-TEST",
            "customer": "ПРОЗРАЧНЫЕ РЕШЕНИЯ",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["number"] == "P-CREATE-TEST"
    assert data["order_number"] == "P-CREATE-TEST"
    assert data["invoice_number"].isdigit()
    assert len(data["invoice_number"]) == 8
    assert data["customer"] == "ПРОЗРАЧНЫЕ РЕШЕНИЯ"
    assert data["extra_components"] == "[]"
    assert data["hardware_installation"] == "installed"
    assert "id" in data
    # cleanup
    client.delete(f"/api/projects/{data['id']}", headers=admin_headers)


def test_list_projects(client, admin_headers, project):
    r = client.get("/api/projects", headers=admin_headers)
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert project["id"] in ids


def test_get_project(client, admin_headers, project):
    r = client.get(f"/api/projects/{project['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["id"] == project["id"]


def test_get_project_not_found(client, admin_headers):
    r = client.get("/api/projects/999999", headers=admin_headers)
    assert r.status_code == 404


def test_update_project(client, admin_headers, project):
    r = client.put(
        f"/api/projects/{project['id']}",
        headers=admin_headers,
        json={
            "number": "P-UPDATED",
            "status": "В работе",
        },
    )
    assert r.status_code == 200
    assert r.json()["number"] == "P-UPDATED"
    assert r.json()["status"] == "В работе"


def test_copy_project(client, admin_headers, project, section):
    extra_components = '[{"sku":"PROJECT-EXTRA","qty":2}]'
    updated = client.put(
        f"/api/projects/{project['id']}",
        headers=admin_headers,
        json={
            "extra_components": extra_components,
            "hardware_installation": "not_installed",
        },
    )
    assert updated.status_code == 200

    r = client.post(f"/api/projects/{project['id']}/copy", headers=admin_headers)
    assert r.status_code == 201
    copy = r.json()
    assert copy["number"] == ""
    assert copy["order_number"] is None
    assert copy["invoice_number"] != project["invoice_number"]
    assert len(copy["sections"]) == 1
    assert copy["sections"][0]["name"] == section["name"]
    assert copy["extra_components"] == extra_components
    assert copy["hardware_installation"] == "not_installed"
    # cleanup copy
    client.delete(f"/api/projects/{copy['id']}", headers=admin_headers)


def test_invoice_numbers_are_unique_and_atomic_under_parallel_creation(
    client, admin_headers
):
    def create(index: int):
        return client.post(
            "/api/projects",
            headers=admin_headers,
            json={"order_number": f"PARALLEL-{index}", "customer": "Тест"},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(create, range(8)))

    try:
        assert {response.status_code for response in responses} == {201}
        numbers = [response.json()["invoice_number"] for response in responses]
        assert len(set(numbers)) == len(numbers)
        numeric = sorted(int(number) for number in numbers)
        assert numeric == list(range(numeric[0], numeric[0] + len(numeric)))
        assert all(len(number) == 8 for number in numbers)
    finally:
        for response in responses:
            if response.status_code == 201:
                client.delete(
                    f"/api/projects/{response.json()['id']}",
                    headers=admin_headers,
                )


def test_invoice_number_is_server_owned_and_order_number_is_optional(
    client, admin_headers
):
    response = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "invoice_number": "99999999",
            "customer": "Без внутреннего номера",
        },
    )
    assert response.status_code == 201, response.text
    project = response.json()
    try:
        assert project["invoice_number"] != "99999999"
        assert project["order_number"] is None
        assert project["number"] == ""

        updated = client.put(
            f"/api/projects/{project['id']}",
            headers=admin_headers,
            json={"order_number": "ЗАКАЗ-42", "invoice_number": "88888888"},
        )
        assert updated.status_code == 200
        assert updated.json()["order_number"] == "ЗАКАЗ-42"
        assert updated.json()["number"] == "ЗАКАЗ-42"
        assert updated.json()["invoice_number"] == project["invoice_number"]
    finally:
        client.delete(f"/api/projects/{project['id']}", headers=admin_headers)


def test_legacy_project_numbers_and_section_extras_migrate_once():
    migration_engine = create_engine("sqlite:///:memory:")
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id INTEGER PRIMARY KEY, number VARCHAR, invoice_number VARCHAR, "
                "order_number VARCHAR, extra_components TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE sections ("
                "id INTEGER PRIMARY KEY, project_id INTEGER, quantity INTEGER, "
                "extra_components TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects VALUES "
                "(1, 'OLD-77', NULL, NULL, :extras)"
            ),
            {
                "extras": json.dumps(
                    [{"sku": "A", "name": "Позиция A", "qty": 1, "unit": "шт"}],
                    ensure_ascii=False,
                )
            },
        )
        connection.execute(
            text("INSERT INTO sections VALUES (1, 1, 3, :extras)"),
            {
                "extras": json.dumps(
                    [{"sku": "A", "name": "Позиция A", "qty": 2, "unit": "шт"}],
                    ensure_ascii=False,
                )
            },
        )
        connection.execute(
            text("INSERT INTO sections VALUES (2, 1, 2, :extras)"),
            {
                "extras": json.dumps(
                    [{"sku": "B", "name": "Позиция B", "qty": 1, "unit": "шт"}],
                    ensure_ascii=False,
                )
            },
        )

        order_migration = next(
            statement
            for statement in _DATA_MIGRATIONS
            if "SET order_number = number" in statement
        )
        connection.execute(text(order_migration))
        _migrate_section_extras_to_project(connection)
        first_payload = connection.execute(
            text("SELECT extra_components FROM projects WHERE id = 1")
        ).scalar_one()
        _migrate_section_extras_to_project(connection)
        second_payload = connection.execute(
            text("SELECT extra_components FROM projects WHERE id = 1")
        ).scalar_one()

        migrated = {row["sku"]: row for row in json.loads(first_payload)}
        assert migrated["A"]["qty"] == "7"
        assert migrated["B"]["qty"] == "2"
        assert second_payload == first_payload
        assert connection.execute(
            text("SELECT COUNT(*) FROM sections WHERE extra_components <> '[]'")
        ).scalar_one() == 0
        project_row = connection.execute(
            text("SELECT order_number, invoice_number FROM projects WHERE id = 1")
        ).one()
        assert project_row == ("OLD-77", None)


def test_copy_project_keeps_lift_fields(client, admin_headers, project):
    section = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "ЛИФТ",
            "system": "ЛИФТ",
            "panels": 4,
            "lift_filling_type": "ДРУГОЕ 8мм",
            "lift_filling_custom": "Зеркало 8мм",
            "lift_control_type": "Пульт ДУ",
            "lift_remote_1ch_qty": 4,
            "lift_remote_6ch_qty": 1,
            "lift_cable_side": "Слева",
            "lift_opening_type": "Верх/низ глухие, сдвиг вниз",
        },
    )
    assert section.status_code == 201

    response = client.post(
        f"/api/projects/{project['id']}/copy",
        headers=admin_headers,
    )
    assert response.status_code == 201
    copied_project = response.json()
    copied_lift = next(
        row for row in copied_project["sections"] if row["system"] == "ЛИФТ"
    )
    assert copied_lift["lift_filling_type"] == "ДРУГОЕ 8мм"
    assert copied_lift["lift_filling_custom"] == "Зеркало 8мм"
    assert "lift_remote_channels" not in copied_lift
    assert copied_lift["lift_remote_1ch_qty"] == 4
    assert copied_lift["lift_remote_6ch_qty"] == 1
    assert copied_lift["lift_cable_side"] == "Слева"
    assert copied_lift["lift_opening_type"] == "Верх/низ глухие, сдвиг вниз"

    client.delete(
        f"/api/projects/{copied_project['id']}",
        headers=admin_headers,
    )


def test_delete_project(client, admin_headers):
    r = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "number": "P-TO-DELETE",
            "customer": "КРОКНА ИНЖИНИРИНГ",
        },
    )
    project_id = r.json()["id"]
    r = client.delete(f"/api/projects/{project_id}", headers=admin_headers)
    assert r.status_code == 204
    r = client.get(f"/api/projects/{project_id}", headers=admin_headers)
    assert r.status_code == 404


def test_projects_require_auth(client):
    r = client.get("/api/projects")
    assert r.status_code == 403


def test_project_rejects_unknown_hardware_installation(
    client, admin_headers, project
):
    response = client.put(
        f"/api/projects/{project['id']}",
        headers=admin_headers,
        json={"hardware_installation": "sometimes"},
    )

    assert response.status_code == 422


def test_startup_sqlite_columns_keep_legacy_projects_unchanged():
    import sqlite3

    from migrations import _ADD_COLUMNS

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO projects (id) VALUES (1)")
    statements = [
        sql
        for sql in _ADD_COLUMNS
        if "projects ADD COLUMN extra_components" in sql
        or "projects ADD COLUMN hardware_installation" in sql
    ]
    assert len(statements) == 2
    for statement in statements:
        connection.execute(statement)

    row = connection.execute(
        "SELECT extra_components, hardware_installation FROM projects WHERE id = 1"
    ).fetchone()

    assert row == ("[]", "not_installed")
