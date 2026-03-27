def test_create_section(client, admin_headers, project):
    r = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "Секция A",
            "system": "СЛАЙД",
            "width": 1500,
            "height": 2200,
            "panels": 2,
            "quantity": 1,
            "rails": 3,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Секция A"
    assert data["system"] == "СЛАЙД"
    assert data["width"] == 1500
    assert data["project_id"] == project["id"]


def test_list_sections(client, admin_headers, project, section):
    r = client.get(f"/api/projects/{project['id']}/sections", headers=admin_headers)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert section["id"] in ids


def test_section_order_increments(client, admin_headers, project):
    """После удаления секции order нового элемента должен быть max+1, не count+1."""
    # Создаём 2 секции
    s1 = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "S1",
            "system": "КНИЖКА",
        },
    ).json()
    s2 = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "S2",
            "system": "КНИЖКА",
        },
    ).json()
    assert s2["order"] > s1["order"]

    # Удаляем первую
    client.delete(
        f"/api/projects/{project['id']}/sections/{s1['id']}", headers=admin_headers
    )

    # Новая секция должна иметь order > s2["order"]
    s3 = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "S3",
            "system": "КНИЖКА",
        },
    ).json()
    assert s3["order"] > s2["order"]

    # cleanup
    client.delete(
        f"/api/projects/{project['id']}/sections/{s2['id']}", headers=admin_headers
    )
    client.delete(
        f"/api/projects/{project['id']}/sections/{s3['id']}", headers=admin_headers
    )


def test_update_section(client, admin_headers, project, section):
    r = client.put(
        f"/api/projects/{project['id']}/sections/{section['id']}",
        headers=admin_headers,
        json={**section, "name": "Обновлённая", "width": 3000},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Обновлённая"
    assert data["width"] == 3000


def test_update_section_not_found(client, admin_headers, project):
    r = client.put(
        f"/api/projects/{project['id']}/sections/999999",
        headers=admin_headers,
        json={"name": "X", "system": "СЛАЙД"},
    )
    assert r.status_code == 404


def test_delete_section(client, admin_headers, project):
    s = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "ToDelete",
            "system": "ЦС",
        },
    ).json()
    r = client.delete(
        f"/api/projects/{project['id']}/sections/{s['id']}", headers=admin_headers
    )
    assert r.status_code == 204
    sections = client.get(
        f"/api/projects/{project['id']}/sections", headers=admin_headers
    ).json()
    assert not any(sec["id"] == s["id"] for sec in sections)


def test_sections_require_auth(client, project):
    r = client.get(f"/api/projects/{project['id']}/sections")
    assert r.status_code == 403
