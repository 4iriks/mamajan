"""Acceptance checks for October editor/document changes (no production data)."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from engine.component_groups import group_extra_sources
from engine.cs_calc import calculate_cs
from engine.project_documents import (
    _project_extra_paint_rows,
    _build_delivery_project_extra_rows,
    _delivery_key,
)
from engine.side_projection import side_projection, snapshot_side_projection
from engine.slide_calc import calculate_slide, _inter_glass_overlap_mm
from migrations import _seed_customer_directory_once
from schemas import SectionCreate


def _make_section(**overrides):
    values = dict(
        name="Секция",
        system="СЛАЙД",
        width=2000,
        height=2400,
        panels=3,
        quantity=1,
        rails=3,
        threshold="Стандартный анод",
        profile_left_wall=True,
        profile_right_wall=True,
    )
    values.update(overrides)
    return SimpleNamespace(**SectionCreate(**values).model_dump())


@pytest.mark.parametrize(
    "edges,bars",
    [
        (["clamp"] * 4, 4),
        (["none", "clamp", "clamp", "clamp"], 3),
        (["clamp", "none", "none", "none"], 2),
        (["none"] * 4, 0),
    ],
)
@pytest.mark.parametrize("quantity", [1, 2, 3])
def test_t40k_rounding_per_section(edges, bars, quantity):
    result = calculate_cs(
        SimpleNamespace(
            width=2240,
            height=600,
            quantity=quantity,
            cs_config={"version": 2, "edgeTreatments": edges},
        )
    )
    cover = next((row for row in result["profiles"] if row["role"] == "cover"), None)
    if not bars:
        assert cover is None
    else:
        assert cover["pieces"] == bars * quantity
        assert cover["cut_lengths_mm"] == [3000] * bars
        assert cover["total_length_mm"] == 3000 * bars * quantity


@pytest.mark.parametrize("rows,panels,joints", [(1, 3, 2), (2, 6, 4)])
@pytest.mark.parametrize(
    "name",
    [
        "Алюминиевый с зацепом RS3061",
        "Алюминиевый RS3061",
        "RS3061",
        "h-профиль RS1004",
        "Профиль с зацепом RS3061",
    ],
)
def test_rs3061_two_parts_and_11mm_overlap(rows, panels, joints, name):
    section = _make_section(
        slide_rows=rows, panels=panels, quantity=2, inter_glass_profile=name
    )
    result = calculate_slide(section)
    items = [item for item in result.profiles if item.article == "RS3061"]
    assert sum(item.qty for item in items) == joints * 2 * 2
    assert all(item.name == "Алюминиевый с зацепом RS3061" for item in items)
    assert _inter_glass_overlap_mm("RS3061") == 11.0
    other = calculate_slide(
        _make_section(
            slide_rows=rows, panels=panels, quantity=2, inter_glass_profile="RS2061"
        )
    )
    # Felt/seals depend on the chosen inter-glass profile; rollers do not.
    assert [
        (x.article, x.value) for x in result.hardware if x.article in {"RU003", "RU005"}
    ] == [
        (x.article, x.value) for x in other.hardware if x.article in {"RU003", "RU005"}
    ]


def test_asymmetric_profile_projection_uses_dimensions_without_changing_glass():
    section = _make_section(profile_right_wall=False, profile_left_lock_bar=True)
    calc = calculate_slide(section)
    original = deepcopy(calc.glass)
    projection = side_projection(
        section,
        SimpleNamespace(
            profiles=[SimpleNamespace(article="RS2081", section_width_mm=63)]
        ),
    )
    assert projection == {"left": 66, "right": 0}
    assert calc.glass == original
    assert snapshot_side_projection({"side_projection_mm": projection}) == projection
    assert snapshot_side_projection(
        {"technical_left": [{"article": "RS2333"}, {"article": "RS2081"}]}
    ) == {"left": 73, "right": 0}


def test_extra_grouping_preserves_identity_and_source_rows():
    base = dict(
        catalogItemId=7,
        sku="T",
        name="Профиль",
        color="9005",
        finishName="RAL стандарт",
        unit="шт",
        deliveryStage="1",
        size="1000",
        qty=2,
    )
    rows = [base, {**base, "size": "1000.0", "qty": 3}, {**base, "size": "2000"}]
    for field, value in [
        ("finishName", "RAL муар"),
        ("color", "9006"),
        ("unit", "м"),
        ("deliveryStage", "2"),
    ]:
        rows.append({**base, field: value})
    before = deepcopy(rows)
    result = group_extra_sources(rows)
    assert len(result) == 6
    assert result[0]["qty"] == 5
    assert result[0]["_view_group"] == result[1]["_view_group"]
    assert len({row["_view_group"] for row in result}) == 5
    assert rows == before
    assert group_extra_sources(None) == []
    assert (
        len(
            group_extra_sources(
                [{**base, "sku": None, "art": "A"}, {**base, "sku": None, "art": "B"}]
            )
        )
        == 2
    )


def test_sketch_hides_rs1121_only_and_paint_combines_cs_stock():
    from engine.project_documents import build_project_document_context

    project = SimpleNamespace(number="QA")
    slide = _make_section(
        profile_left_handle_bar=True, painting_type="RAL стандарт", ral_color="9005"
    )
    calc = calculate_slide(slide)
    assert any(row.article == "RS1121" for row in calc.hardware)
    sketch = build_project_document_context(project, [slide], "sketch")
    assert all(row["article"] != "RS1121" for row in sketch["sections"][0]["profiles"])
    cs = _make_section(
        system="ЦС",
        width=2240,
        height=600,
        quantity=2,
        painting_type="RAL стандарт",
        ral_color="9005",
    )
    paint = build_project_document_context(project, [slide, cs], "paint")
    assert len(paint["paint_pages"]) == 1
    cover = next(
        row for row in paint["paint_pages"][0]["rows"] if row["article"] == "Т40К"
    )
    assert (cover["clean"], cover["allowance"], cover["qty"]) == (3000, 3000, 8)


@pytest.mark.parametrize("quantity", [1, 3])
def test_tape_and_pads_follow_actual_grid_and_section_quantity(quantity):
    result = calculate_cs(
        _make_section(
            system="ЦС",
            width=2240,
            height=600,
            quantity=quantity,
            cs_config={
                "version": 2,
                "vertical": {"count": 2},
                "horizontal": {"count": 1},
            },
        )
    )
    tape = next(row for row in result["hardware"] if row["role"] == "tape")
    pads = next(row for row in result["hardware"] if row["role"] == "pad")
    assert len(result["panes"]) == 6
    assert pads["qty"] == 12 * quantity
    assert tape["qty"] == pytest.approx(
        2 * (2 * (548 - 3) + (2188 - 2 * 3)) * quantity / 1000
    )


def test_glass_note_uses_each_pane_geometry_not_section_name():
    from engine.project_documents import build_project_document_context

    cs = _make_section(
        system="ЦС",
        width=3000,
        height=3000,
        cs_shape="Многоугольник",
        cs_config={
            "version": 2,
            "vertices": [
                {"x": 0, "y": 0},
                {"x": 3000, "y": 0},
                {"x": 3000, "y": 1800},
                {"x": 2000, "y": 3000},
                {"x": 0, "y": 3000},
            ],
            "vertical": {"count": 1},
        },
    )
    context = build_project_document_context(
        SimpleNamespace(number="QA"), [cs], "glass"
    )
    assert {row["note"] for row in context["glass_rows"]} == {"", "ЧЕРТЕЖ"}


def test_paint_extras_keep_finish_and_delivery_places_compatible():
    base = dict(
        catalogItemId=7,
        sku="T",
        name="Профиль",
        color="9005",
        finishName="RAL муар",
        requiresPaint=True,
        unit="шт",
        deliveryStage="1",
        size="1000",
        qty=2,
    )
    project = SimpleNamespace(extra_components=[base])
    assert _project_extra_paint_rows(project)[0]["color"] == "RAL муар 9005"
    old_key = _delivery_key(
        "project-extra", "T", "Профиль", "9005", "1000", "шт", "", "1"
    )
    rows = _build_delivery_project_extra_rows(project, {old_key: "3"}, None)
    assert rows[0]["places"] == "3"


def test_customer_seed_only_confirmed_and_never_reseeds_changed_names():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, name_key TEXT UNIQUE, is_active BOOLEAN)"
            )
        )
        conn.execute(text("CREATE TABLE migration_markers (name TEXT PRIMARY KEY)"))
        _seed_customer_directory_once(conn)
        assert conn.execute(
            text("SELECT name FROM customers ORDER BY name")
        ).scalars().all() == ["ООО КРОКНА ИНЖИНИРИНГ", "ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ"]
        conn.execute(
            text(
                "UPDATE customers SET name='Новое', name_key='новое', is_active=0 WHERE id=1"
            )
        )
        _seed_customer_directory_once(conn)
        assert conn.execute(text("SELECT count(*) FROM customers")).scalar() == 2
        assert (
            conn.execute(text("SELECT is_active FROM customers WHERE id=1")).scalar()
            == 0
        )


def test_directory_preserves_old_projects_and_requires_active_on_copy(
    client, admin_headers, project
):
    from database import SessionLocal
    from models import Project

    assert client.get("/api/customers").status_code in (401, 403)
    created = client.post(
        "/api/customers", headers=admin_headers, json={"name": "  Новый   заказчик  "}
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["name"] == "Новый заказчик"
    assert (
        client.post(
            "/api/customers", headers=admin_headers, json={"name": "новый заказчик"}
        ).status_code
        == 409
    )
    with SessionLocal() as db:
        db.get(Project, project["id"]).customer = "Старая опечатка"
        db.commit()
    response = client.put(
        f"/api/projects/{project['id']}",
        headers=admin_headers,
        json={"customer": "Старая опечатка"},
    )
    assert response.status_code == 200, response.text
    assert (
        client.post(
            "/api/projects", headers=admin_headers, json={"customer": "Старая опечатка"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/projects/{project['id']}/copy", headers=admin_headers
        ).status_code
        == 422
    )
    copied = client.post(
        f"/api/projects/{project['id']}/copy",
        params={"customer": row["name"]},
        headers=admin_headers,
    )
    assert copied.status_code == 201, copied.text
    assert copied.json()["customer"] == row["name"]
    disabled = client.put(
        f"/api/customers/{row['id']}",
        headers=admin_headers,
        json={"name": "Переименован", "is_active": False},
    )
    assert disabled.status_code == 200
    assert (
        client.get(
            f"/api/projects/{copied.json()['id']}", headers=admin_headers
        ).json()["customer"]
        == row["name"]
    )
    assert all(
        item["id"] != row["id"]
        for item in client.get("/api/customers", headers=admin_headers).json()
    )
    assert (
        client.post(
            "/api/projects", headers=admin_headers, json={"customer": "Переименован"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("role", ["admin", "dealer", "user", "superadmin"])
def test_directory_permissions_all_superadmins_only(client, role):
    from auth import create_access_token
    from database import SessionLocal
    from models import User

    with SessionLocal() as db:
        user = User(
            username=f"directory-{role}",
            password_hash="unused",
            display_name=role,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        token = create_access_token(user.id, user.username, user.role)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/customers", headers=headers, json={"name": f"Проверка прав {role}"}
    )
    assert response.status_code == (201 if role == "superadmin" else 403), response.text
    assert client.put(
        "/api/customers/999999", headers=headers, json={"name": "Нет"}
    ).status_code == (404 if role == "superadmin" else 403)
