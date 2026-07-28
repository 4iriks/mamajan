import json

import pytest


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


def test_section_extra_components_save_through_api(client, admin_headers, project):
    components = [
        {
            "sku": "BOX-1",
            "name": "Бокс",
            "color": "RAL 9016",
            "size": "1200",
            "qty": "2",
        }
    ]
    r = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "Секция с комплектующими",
            "system": "СЛАЙД",
            "extra_components": json.dumps(components, ensure_ascii=False),
        },
    )

    assert r.status_code == 201
    section = r.json()
    assert json.loads(section["extra_components"]) == components

    updated_components = [{**components[0], "qty": "3"}]
    updated = client.put(
        f"/api/projects/{project['id']}/sections/{section['id']}",
        headers=admin_headers,
        json={
            **section,
            "extra_components": json.dumps(updated_components, ensure_ascii=False),
        },
    )

    assert updated.status_code == 200
    assert json.loads(updated.json()["extra_components"]) == updated_components


def test_lift_fields_save_through_api(client, admin_headers, project):
    created = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "ЛИФТ 4 панели",
            "system": "ЛИФТ",
            "width": 3043,
            "height": 3300,
            "panels": 4,
            "quantity": 2,
            "lift_filling_type": "ДРУГОЕ 20мм",
            "lift_filling_custom": "Сэндвич-панель 20мм",
            "lift_control_type": "Пульт ДУ",
            "lift_remote_1ch_qty": 3,
            "lift_remote_6ch_qty": 2,
            "lift_cable_side": "Слева",
            "lift_opening_type": "Верх/низ глухие, сдвиг вниз",
        },
    )

    assert created.status_code == 201
    section = created.json()
    assert section["lift_filling_type"] == "ДРУГОЕ 20мм"
    assert section["lift_filling_custom"] == "Сэндвич-панель 20мм"
    assert section["lift_control_type"] == "Пульт ДУ"
    assert "lift_remote_channels" not in section
    assert section["lift_remote_1ch_qty"] == 3
    assert section["lift_remote_6ch_qty"] == 2
    assert section["lift_cable_side"] == "Слева"
    assert section["lift_opening_type"] == "Верх/низ глухие, сдвиг вниз"

    updated = client.put(
        f"/api/projects/{project['id']}/sections/{section['id']}",
        headers=admin_headers,
        json={
            **section,
            "lift_filling_type": "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)",
            "lift_filling_custom": None,
            "lift_control_type": "Кнопка",
            "lift_remote_1ch_qty": 3,
            "lift_remote_6ch_qty": 2,
            "lift_cable_side": "Справа",
            "lift_opening_type": "Сдвиг вверх",
        },
    )

    assert updated.status_code == 200
    saved = updated.json()
    assert saved["lift_filling_type"] == "СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)"
    assert saved["lift_filling_custom"] is None
    assert saved["lift_control_type"] == "Кнопка"
    assert "lift_remote_channels" not in saved
    assert saved["lift_remote_1ch_qty"] == 3
    assert saved["lift_remote_6ch_qty"] == 2
    assert saved["lift_cable_side"] == "Справа"
    assert saved["lift_opening_type"] == "Сдвиг вверх"


def test_lift_fields_have_isolated_defaults(client, admin_headers, project):
    created = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={"name": "ЛИФТ по умолчанию", "system": "ЛИФТ", "panels": 2},
    )

    assert created.status_code == 201
    section = created.json()
    assert section["lift_filling_type"] == "СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    assert section["lift_control_type"] == "Пульт ДУ"
    assert "lift_remote_channels" not in section
    assert section["lift_remote_1ch_qty"] == 0
    assert section["lift_remote_6ch_qty"] == 0
    assert section["lift_cable_side"] == "Справа"
    assert section["lift_opening_type"] == "Сдвиг вниз"


@pytest.mark.parametrize(
    "overrides",
    [
        {"panels": 5},
        {"quantity": 0},
        {"width": 100},
        {"height": 100},
        {"lift_filling_type": "ДРУГОЕ 8мм", "lift_filling_custom": "  "},
        {"lift_filling_type": "НЕИЗВЕСТНО"},
        {"lift_control_type": "Тумблер"},
        {"lift_cable_side": "Сверху"},
        {"lift_opening_type": "Вбок"},
        {
            "panels": 3,
            "lift_opening_type": "Верх/низ глухие, сдвиг вниз",
        },
        {"lift_remote_channels": -1},
        {"lift_remote_1ch_qty": -1},
        {"lift_remote_6ch_qty": -1},
    ],
)
def test_invalid_lift_fields_are_rejected(
    client, admin_headers, project, overrides
):
    payload = {
        "name": "Некорректный ЛИФТ",
        "system": "ЛИФТ",
        "width": 2500,
        "height": 2500,
        "panels": 2,
        "quantity": 1,
    }
    payload.update(overrides)

    response = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json=payload,
    )

    assert response.status_code == 422


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


def test_center_handle_offset_is_saved_only_for_supported_handles(
    client, admin_headers, project
):
    created = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json={
            "name": "Секция с центральной ручкой",
            "system": "СЛАЙД",
            "slide_rows": 2,
            "panels": 4,
            "center_handle": "Ручка-кноб RS3014",
            "center_handle_offset": 100,
        },
    )
    assert created.status_code == 201
    section = created.json()
    assert section["center_handle_offset"] is None

    supported = client.put(
        f"/api/projects/{project['id']}/sections/{section['id']}",
        headers=admin_headers,
        json={
            **section,
            "center_handle": "Стеклянная ручка RS3017",
            "center_handle_offset": 75,
        },
    )
    assert supported.status_code == 200
    assert supported.json()["center_handle_offset"] == 75

    unsupported = client.put(
        f"/api/projects/{project['id']}/sections/{section['id']}",
        headers=admin_headers,
        json={
            **supported.json(),
            "center_handle": "Ручка-кноб RS3014",
            "center_handle_offset": 75,
        },
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["center_handle_offset"] is None


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
