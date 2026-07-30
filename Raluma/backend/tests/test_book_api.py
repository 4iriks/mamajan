def book_payload(**overrides):
    payload = {
        "name": "Секция КНИЖКА",
        "system": "КНИЖКА",
        "width": 3000,
        "height": 2500,
        "panels": 4,
        "quantity": 1,
        "door_side": "both",
        "doors": 2,
        "book_left_door_hardware": "handle",
        "book_right_door_hardware": "lock",
        "book_left_door_opening": "inside_in",
        "book_right_door_opening": "outside_out",
        "book_left_stack_panels": 2,
        "book_obstacle_distance": 500,
        "book_handle_height": 1000,
        "compensator": "both",
    }
    payload.update(overrides)
    return payload


def test_book_calculation_has_authenticated_and_guest_endpoints(
    client,
    admin_headers,
):
    guest = client.post("/api/calculate/local/book", json=book_payload())
    assert guest.status_code == 200
    assert guest.json()["panels"][0]["glass_width_mm"] == 742.0
    assert guest.json()["normalized_config"]["door_layout"] == "both"

    assert client.post("/api/calculate/book", json=book_payload()).status_code == 403
    authenticated = client.post(
        "/api/calculate/book",
        headers=admin_headers,
        json=book_payload(),
    )
    assert authenticated.status_code == 200
    assert authenticated.json() == guest.json()


def test_existing_guest_calc_dispatches_to_book(client):
    response = client.post(
        "/api/projects/local/sections/calc",
        json={
            "project": {"number": "Гость", "customer": ""},
            "section": book_payload(),
        },
    )

    assert response.status_code == 200
    assert len(response.json()["panels"]) == 4
    assert response.json()["source_priority"][0] == "tz"


def test_book_api_returns_clear_calculation_error(client):
    response = client.post(
        "/api/calculate/local/book",
        json=book_payload(width=20),
    )

    assert response.status_code == 422
    assert "Суммарная ширина стекол" in response.json()["detail"]


def test_book_fields_save_copy_and_legacy_mapping(
    client,
    admin_headers,
    project,
):
    created = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json=book_payload(),
    )
    assert created.status_code == 201
    data = created.json()
    assert data["book_left_door_hardware"] == "handle"
    assert data["book_right_door_hardware"] == "lock"
    assert data["book_left_door_opening"] == "inside_in"
    assert data["book_right_door_opening"] == "outside_out"
    assert data["book_obstacle_distance"] == 500
    assert data["book_left_stack_panels"] == 2
    assert data["book_handle_height"] == 1000

    copied = client.post(
        f"/api/projects/{project['id']}/copy",
        headers=admin_headers,
    )
    assert copied.status_code == 201
    copied_book = next(
        row for row in copied.json()["sections"] if row["system"] == "КНИЖКА"
    )
    for field in (
        "book_left_door_hardware",
        "book_right_door_hardware",
        "book_left_door_opening",
        "book_right_door_opening",
        "book_obstacle_distance",
        "book_left_stack_panels",
        "book_handle_height",
    ):
        assert copied_book[field] == data[field]
    client.delete(
        f"/api/projects/{copied.json()['id']}",
        headers=admin_headers,
    )

    legacy = client.post(
        f"/api/projects/{project['id']}/sections",
        headers=admin_headers,
        json=book_payload(
            name="Старая КНИЖКА",
            doors=1,
            door_side="Левая",
            door_type="Тип 4",
            door_opening="Наружу",
            book_left_door_hardware=None,
            book_right_door_hardware=None,
            book_left_door_opening=None,
            book_right_door_opening=None,
        ),
    )
    assert legacy.status_code == 201
    assert legacy.json()["door_side"] == "Левая"
    assert legacy.json()["book_left_door_hardware"] == "lock"
    assert legacy.json()["book_left_door_opening"] == "inside_out"


def test_book_template_preserves_new_fields(client, admin_headers):
    created = client.post(
        "/api/section-templates",
        headers=admin_headers,
        json={
            "name": "КНИЖКА с двумя дверями",
            "system": "КНИЖКА",
            "template_data": book_payload(),
        },
    )
    assert created.status_code == 201
    template = created.json()
    assert template["template_data"]["book_left_door_hardware"] == "handle"
    assert template["template_data"]["book_right_door_opening"] == "outside_out"
    assert template["template_data"]["book_left_stack_panels"] == 2

    client.delete(
        f"/api/section-templates/{template['id']}",
        headers=admin_headers,
    )


def test_book_production_documents_are_deferred_and_preliminary_are_blocked(client):
    confirmed = {
        "project": {"number": "Гость", "customer": ""},
        "section": book_payload(door_side="right", doors=1),
    }
    deferred = client.post("/api/projects/local/sections/pdf", json=confirmed)
    assert deferred.status_code == 501
    assert "следующим пакетом" in deferred.json()["detail"]

    preliminary = {
        "project": {"number": "Гость", "customer": ""},
        "section": book_payload(angle_left=90),
    }
    blocked = client.post("/api/projects/local/sections/pdf", json=preliminary)
    assert blocked.status_code == 409
    assert "заблокированы" in blocked.json()["detail"]

    project_doc = client.post(
        "/api/projects/local/documents/glass/preview",
        json={
            "project": {"number": "Гость", "customer": ""},
            "sections": [book_payload()],
        },
    )
    assert project_doc.status_code == 501
