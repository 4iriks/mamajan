from types import SimpleNamespace

import pytest

from engine.cs_calc import CsCalculationError, calculate_cs


def _section(**overrides):
    values = {
        "width": 3000,
        "height": 3000,
        "quantity": 1,
        "cs_shape": "Прямоугольник",
        "cs_width2": None,
        "cs_config": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_cs_equal_grid_produces_nine_deterministic_panes_and_profile_lengths():
    result = calculate_cs(
        _section(
            cs_config={
                "version": 1,
                "vertices": [
                    {"x": 0, "y": 0},
                    {"x": 3000, "y": 0},
                    {"x": 3000, "y": 3000},
                    {"x": 0, "y": 3000},
                ],
                "vertical": {"count": 2, "mode": "equal"},
                "horizontal": {"count": 2, "mode": "equal"},
                "profiledEdges": [1, 2, 3],
            }
        )
    )

    assert len(result["panes"]) == 9
    assert [row["number"] for row in result["panes"]] == list(range(1, 10))
    assert all(row["width_mm"] == 1000 for row in result["panes"])
    assert all(row["height_mm"] == 1000 for row in result["panes"])
    assert result["glass_area_m2"] == 9
    assert result["outer_edge_lengths_mm"] == [3000, 3000, 3000]
    assert result["divider_lengths_mm"] == [3000, 3000, 3000, 3000]
    assert result["commercial_price_allowed"] is False
    assert result["status"] == "preliminary"


def test_cs_trapezoid_preserves_polygon_area_and_physical_quantity():
    result = calculate_cs(
        _section(
            quantity=2,
            cs_shape="Трапеция",
            cs_width2=1500,
        )
    )

    assert len(result["panes"]) == 1
    assert result["panes"][0]["area_m2"] == 6.75
    assert result["panes"][0]["qty"] == 2
    assert result["glass_area_m2"] == 13.5


def test_cs_rejects_self_intersecting_contour():
    with pytest.raises(CsCalculationError, match="пересекать"):
        calculate_cs(
            _section(
                cs_config={
                    "version": 1,
                    "vertices": [
                        {"x": 0, "y": 0},
                        {"x": 3000, "y": 3000},
                        {"x": 0, "y": 3000},
                        {"x": 3000, "y": 0},
                    ],
                    "vertical": {"count": 0, "mode": "equal"},
                    "horizontal": {"count": 0, "mode": "equal"},
                    "profiledEdges": [1, 2, 3],
                }
            )
        )


def test_cs_guest_and_authenticated_endpoints_return_same_preliminary_result(
    client,
    admin_headers,
):
    payload = {
        "name": "ЦС 1",
        "system": "ЦС",
        "width": 3000,
        "height": 3000,
        "quantity": 1,
        "cs_config": {
            "version": 1,
            "vertices": [
                {"x": 0, "y": 0},
                {"x": 3000, "y": 0},
                {"x": 3000, "y": 3000},
                {"x": 0, "y": 3000},
            ],
            "vertical": {"count": 2, "mode": "equal"},
            "horizontal": {"count": 0, "mode": "equal"},
            "profiledEdges": [1, 2, 3],
        },
    }

    guest = client.post("/api/calculate/local/cs", json=payload)
    assert guest.status_code == 200, guest.text
    authenticated = client.post(
        "/api/calculate/cs", headers=admin_headers, json=payload
    )
    assert authenticated.status_code == 200, authenticated.text
    assert authenticated.json() == guest.json()
    assert len(guest.json()["panes"]) == 3
    assert guest.json()["commercial_price_allowed"] is False


def test_cs_preliminary_documents_cover_sheet_sketch_glass_and_profiles(client):
    section = {
        "name": "ЦС 1",
        "system": "ЦС",
        "width": 3000,
        "height": 3000,
        "quantity": 1,
        "glass_type": "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        "cs_config": {
            "version": 1,
            "vertices": [
                {"x": 0, "y": 0},
                {"x": 3000, "y": 0},
                {"x": 2500, "y": 3000},
                {"x": 500, "y": 3000},
            ],
            "vertical": {"count": 2, "mode": "equal"},
            "horizontal": {"count": 1, "mode": "equal"},
            "profiledEdges": [1, 2, 3],
        },
    }
    project = {"number": "CS-DOCS", "customer": "Заказчик"}

    preview = client.post(
        "/api/projects/local/sections/preview",
        json={"project": project, "section": section},
    )
    assert preview.status_code == 200, preview.text
    assert "ПРЕДВАРИТЕЛЬНЫЙ ПЛ" in preview.text
    assert "Количество стекол" in preview.text

    for extension, content_type in (
        ("docx", "wordprocessingml"),
        ("xlsx", "spreadsheetml"),
    ):
        response = client.post(
            f"/api/projects/local/sections/{extension}",
            json={"project": project, "section": section},
        )
        assert response.status_code == 200, response.text
        assert content_type in response.headers["content-type"]
        assert response.content.startswith(b"PK")

    for document, expected in (
        ("sketch", "ПРЕДВАРИТЕЛЬНЫЙ"),
        ("glass", "1,1"),
        ("hardware_order", "артикул уточняется"),
    ):
        response = client.post(
            f"/api/projects/local/documents/{document}/preview",
            json={"project": project, "sections": [section]},
        )
        assert response.status_code == 200, response.text
        assert expected.casefold() in response.text.casefold()
