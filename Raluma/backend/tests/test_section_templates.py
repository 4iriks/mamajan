import json
import uuid
from datetime import datetime

import models
from database import SessionLocal


def _cleanup_templates(client, admin_headers):
    for template in client.get("/api/section-templates").json():
        client.delete(f"/api/section-templates/{template['id']}", headers=admin_headers)


def _slide_template_payload(name="Слайд 3 панели"):
    return {
        "name": name,
        "system": "СЛАЙД 1 ряд",
        "template_data": {
            "id": 999,
            "project_id": 777,
            "order": 8,
            "name": "Не переносить",
            "document_overrides": '{"threshold_length":"111"}',
            "system": "СЛАЙД",
            "width": 3100,
            "height": 2500,
            "panels": 3,
            "quantity": 2,
            "rails": 3,
            "threshold": "Стандартный окраш",
            "first_panel_inside": "Справа",
            "glass_type": "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
            "painting_type": "RAL стандарт",
            "ral_color": "9016 МАТОВЫЙ",
        },
    }


def test_section_templates_list_is_public_and_admin_creates_sanitized(
    client, admin_headers
):
    _cleanup_templates(client, admin_headers)

    listed = client.get("/api/section-templates")
    assert listed.status_code == 200
    assert listed.json() == []

    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=_slide_template_payload(),
    )

    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Слайд 3 панели"
    assert data["system"] == "СЛАЙД 1 ряд"
    assert data["template_data"]["width"] == 3100
    assert data["template_data"]["quantity"] == 2
    assert data["template_data"]["system"] == "СЛАЙД"
    assert data["template_data"]["slide_rows"] == 1
    assert "id" not in data["template_data"]
    assert "project_id" not in data["template_data"]
    assert "order" not in data["template_data"]
    assert "name" not in data["template_data"]
    assert "document_overrides" not in data["template_data"]

    filtered = client.get("/api/section-templates", params={"system": "СЛАЙД 1 ряд"})
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [data["id"]]

    client.delete(f"/api/section-templates/{data['id']}", headers=admin_headers)


def test_section_template_normalizes_center_handle_offset(client, admin_headers):
    _cleanup_templates(client, admin_headers)

    unsupported_payload = _slide_template_payload("Шаблон с кнобом")
    unsupported_payload["system"] = "СЛАЙД 2 ряда"
    unsupported_payload["template_data"].update(
        {
            "slide_rows": 2,
            "panels": 4,
            "center_handle": "Ручка-кноб RS3014",
            "center_handle_offset": 100,
        }
    )
    unsupported = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=unsupported_payload,
    )
    assert unsupported.status_code == 201
    assert unsupported.json()["template_data"]["center_handle_offset"] is None

    supported_payload = _slide_template_payload("Шаблон со скобой")
    supported_payload["system"] = "СЛАЙД 2 ряда"
    supported_payload["template_data"].update(
        {
            "slide_rows": 2,
            "panels": 4,
            "center_handle": "Ручка-скоба 600мм RS30201",
            "center_handle_offset": 80,
        }
    )
    supported = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=supported_payload,
    )
    assert supported.status_code == 201
    assert supported.json()["template_data"]["center_handle_offset"] == 80

    _cleanup_templates(client, admin_headers)


def test_section_templates_mutations_require_admin(client, admin_headers):
    _cleanup_templates(client, admin_headers)
    username = f"user-{uuid.uuid4().hex[:8]}"
    registered = client.post(
        "/api/auth/register",
        json={"username": username, "password": "pass1234", "display_name": username},
    )
    assert registered.status_code == 201
    user_headers = {
        "Authorization": f"Bearer {registered.json()['access_token']}",
    }

    payload = _slide_template_payload("Нельзя создать")
    assert client.post("/api/section-templates", json=payload).status_code == 403
    assert (
        client.post(
            "/api/section-templates", headers=user_headers, json=payload
        ).status_code
        == 403
    )

    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=_slide_template_payload("Можно создать"),
    ).json()
    assert (
        client.patch(
            f"/api/section-templates/{created['id']}",
            headers=user_headers,
            json={"name": "Не админ"},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/section-templates/{created['id']}",
            headers=user_headers,
        ).status_code
        == 403
    )

    client.delete(f"/api/section-templates/{created['id']}", headers=admin_headers)


def test_section_templates_limit_is_per_system(client, admin_headers):
    _cleanup_templates(client, admin_headers)
    for index in range(10):
        created = client.post(
            "/api/section-templates",
            headers=admin_headers,
            json={
                "name": f"Лифт {index + 1}",
                "system": "ЛИФТ",
                "template_data": {
                    "system": "ЛИФТ",
                    "width": 1000 + index,
                    "height": 2000,
                    "panels": 2,
                },
            },
        )
        assert created.status_code == 201

    over_limit = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json={
            "name": "Лишний лифт",
            "system": "ЛИФТ",
            "template_data": {"system": "ЛИФТ", "width": 2000, "height": 2400},
        },
    )
    assert over_limit.status_code == 400

    another_system = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=_slide_template_payload("Слайд разрешен"),
    )
    assert another_system.status_code == 201

    _cleanup_templates(client, admin_headers)


def test_slide_template_limit_is_per_row_type(client, admin_headers):
    _cleanup_templates(client, admin_headers)
    for index in range(10):
        payload = _slide_template_payload(f"Слайд 1 ряд {index + 1}")
        payload["system"] = "СЛАЙД 1 ряд"
        payload["template_data"]["slide_rows"] = 1
        created = client.post(
            "/api/section-templates",
            headers=admin_headers,
            json=payload,
        )
        assert created.status_code == 201

    over_limit = _slide_template_payload("Лишний 1 ряд")
    over_limit["system"] = "СЛАЙД 1 ряд"
    over_limit["template_data"]["slide_rows"] = 1
    assert (
        client.post(
            "/api/section-templates",
            headers=admin_headers,
            json=over_limit,
        ).status_code
        == 400
    )

    two_row = _slide_template_payload("Слайд 2 ряда разрешен")
    two_row["system"] = "СЛАЙД 2 ряда"
    two_row["template_data"]["slide_rows"] = 2
    two_row["template_data"]["panels"] = 4
    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=two_row,
    )
    assert created.status_code == 201
    assert created.json()["system"] == "СЛАЙД 2 ряда"
    assert created.json()["template_data"]["slide_rows"] == 2

    _cleanup_templates(client, admin_headers)


def test_section_templates_rename_update_and_delete(client, admin_headers):
    _cleanup_templates(client, admin_headers)
    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=_slide_template_payload("Старое имя"),
    ).json()

    updated = client.patch(
        f"/api/section-templates/{created['id']}",
        headers=admin_headers,
        json={
            "name": "Новое имя",
            "template_data": {
                "system": "СЛАЙД",
                "width": 4200,
                "height": 2600,
                "panels": 4,
                "rails": 5,
                "document_overrides": '{"foo":"bar"}',
            },
        },
    )

    assert updated.status_code == 200
    data = updated.json()
    assert data["name"] == "Новое имя"
    assert data["template_data"]["width"] == 4200
    assert data["template_data"]["rails"] == 5
    assert "document_overrides" not in data["template_data"]

    deleted = client.delete(
        f"/api/section-templates/{created['id']}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204
    assert client.get("/api/section-templates").json() == []


def test_section_template_legacy_slide_values_are_normalized(client, admin_headers):
    _cleanup_templates(client, admin_headers)
    payload = _slide_template_payload("Старый слайд")
    payload["template_data"].update(
        {
            "inter_glass_profile": "h-профиль RS1004",
            "lock_left": "ЗАМОК-ЗАЩЕЛКА 2стор с ключом",
            "lock_right": "1-сторонний RS3018",
            "handle_left": "Ручка-скоба",
            "handle_right": "Ручка-скоба",
            "center_handle": "Ручка-скоба",
        }
    )

    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json=payload,
    )

    assert created.status_code == 201
    data = created.json()["template_data"]
    assert data["inter_glass_profile"] == "Профиль с зацепом RS3061"
    assert data["lock_left"] == "ЗАМОК двухсторонний с ключом RS3020"
    assert data["lock_right"] == "ЗАМОК-ЗАЩЕЛКА 1стор RS3018"
    assert data["handle_left"] == "Ручка-скоба 600мм RS30201"
    assert data["handle_right"] == "Ручка-скоба 600мм RS30201"
    assert data["center_handle"] == "Ручка-скоба 600мм RS30201"

    _cleanup_templates(client, admin_headers)


def test_section_template_existing_legacy_json_is_normalized_on_read(
    client, admin_headers
):
    _cleanup_templates(client, admin_headers)
    db = SessionLocal()
    try:
        template = models.SectionTemplate(
            name="Старая комплектация",
            system="КОМПЛЕКТАЦИЯ",
            template_data=json.dumps(
                {
                    "system": "КОМПЛЕКТАЦИЯ",
                    "width": 1000,
                    "height": 2000,
                    "panels": 1,
                    "lock": "RS3019 С ключом",
                    "handle": "Ручка-скоба",
                },
                ensure_ascii=False,
            ),
            sort_order=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(template)
        db.commit()
    finally:
        db.close()

    listed = client.get("/api/section-templates", params={"system": "КОМПЛЕКТАЦИЯ"})
    assert listed.status_code == 200
    data = listed.json()[0]["template_data"]
    assert data["lock"] == "ЗАМОК двухсторонний с ключом RS3020"
    assert data["handle"] == "Ручка-скоба 600мм RS30201"

    _cleanup_templates(client, admin_headers)
