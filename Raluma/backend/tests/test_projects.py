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
    assert data["customer"] == "ПРОЗРАЧНЫЕ РЕШЕНИЯ"
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
    r = client.post(f"/api/projects/{project['id']}/copy", headers=admin_headers)
    assert r.status_code == 201
    copy = r.json()
    assert copy["number"] == project["number"] + "-копия"
    assert len(copy["sections"]) == 1
    assert copy["sections"][0]["name"] == section["name"]
    # cleanup copy
    client.delete(f"/api/projects/{copy['id']}", headers=admin_headers)


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
