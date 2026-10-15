from copy import deepcopy
import os
from io import BytesIO
from math import hypot
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from shapely.geometry import Point, Polygon

from engine.cs_calc import CsCalculationError, calculate_cs
from engine.cs_rounding import triangle_rounding


def section(radius=None, **overrides):
    config = {
        "version": 2,
        "dimensionMode": "clear",
        "vertices": [{"x": 0, "y": 0}, {"x": 2390, "y": 0}, {"x": 2390, "y": 745}],
        "vertical": {"count": 0},
        "horizontal": {"count": 0},
    }
    if radius is not None:
        config["triangleCornerRadiusMm"] = radius
    config.update(overrides)
    return SimpleNamespace(width=2390, height=745, quantity=2, cs_config=config)


@pytest.mark.parametrize("radius", [8, 10])
@pytest.mark.parametrize(
    "mirrored,reversed_winding",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_cs_rounding_exact_circle_tangency_inside_original_and_no_mutation(
    radius, mirrored, reversed_winding
):
    points = section().cs_config["vertices"]
    if mirrored:
        points = [{"x": 2390 - p["x"], "y": p["y"]} for p in points]
    if reversed_winding:
        points.reverse()
    original = deepcopy(points)
    corner = triangle_rounding(points, radius)
    assert points == original
    assert corner["radius_mm"] == radius
    p = points[corner["vertex_index"]]
    assert p["y"] == 0
    assert p["x"] == (2390 if mirrored else 0)
    for key, neighbor in [
        ("start", points[corner["vertex_index"] - 1]),
        ("end", points[(corner["vertex_index"] + 1) % 3]),
    ]:
        t, c = corner[key], corner["center"]
        assert hypot(t["x"] - c["x"], t["y"] - c["y"]) == pytest.approx(radius)
        # Radius perpendicular to the edge at the tangent point.
        assert (t["x"] - c["x"]) * (neighbor["x"] - p["x"]) + (t["y"] - c["y"]) * (
            neighbor["y"] - p["y"]
        ) == pytest.approx(0, abs=1e-6)
    outline = Polygon([(p["x"], p["y"]) for p in corner["outline"]])
    polygon = Polygon([(p["x"], p["y"]) for p in points])
    assert outline.is_valid and polygon.buffer(1e-6).covers(outline)
    assert not outline.covers(Point(p["x"], p["y"]))
    assert outline.area < polygon.area


@pytest.mark.parametrize("radius", [8, 10])
@pytest.mark.parametrize("mode", ["clear", "installation"])
@pytest.mark.parametrize("split", [False, True])
def test_cs_rounding_does_not_change_any_calculation(radius, mode, split):
    options = {"dimensionMode": mode}
    if split:
        options["vertical"] = {"count": 1, "mode": "equal"}
    before = calculate_cs(section(**options))
    after = calculate_cs(section(radius, **options))
    assert any(p.get("rounded_corner") for p in after["panes"])
    for pane in after["panes"]:
        if len(pane["polygon"]) != 3:
            assert "rounded_corner" not in pane
        pane.pop("rounded_corner", None)
        pane.pop("treatment_note", None)
    after["normalized_config"].pop("triangleCornerRadiusMm")
    assert after == before  # sizes, glass area, profiles, tape, pads, gaps, quantities


def test_cs_legacy_off_and_rectangles_are_unchanged():
    assert "rounded_corner" not in calculate_cs(section())["panes"][0]
    assert "rounded_corner" not in calculate_cs(section(0))["panes"][0]
    rectangle = [
        {"x": 0, "y": 0},
        {"x": 2000, "y": 0},
        {"x": 2000, "y": 700},
        {"x": 0, "y": 700},
    ]
    assert (
        "rounded_corner"
        not in calculate_cs(section(10, vertices=rectangle))["panes"][0]
    )


@pytest.mark.parametrize("radius", [-1, 7, 9, 11, "bad", None])
def test_cs_invalid_radius_is_rejected(radius):
    data = section()
    data.cs_config["triangleCornerRadiusMm"] = radius
    with pytest.raises(CsCalculationError, match="R8 или R10"):
        calculate_cs(data)


def test_cs_radius_must_fit_without_silent_reduction():
    tiny = [{"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 10}]
    with pytest.raises(CsCalculationError, match="не помещается"):
        calculate_cs(section(10, vertices=tiny, edgeTreatments=["none"] * 3))


def test_cs_rounding_saves_and_reopens_without_changing_vertices(
    client, admin_headers, project
):
    data = section(10)
    payload = {
        "name": "R10",
        "system": "ЦС",
        "width": data.width,
        "height": data.height,
        "quantity": 1,
        "cs_config": data.cs_config,
    }
    path = f"/api/projects/{project['id']}/sections"
    created = client.post(path, headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    saved = created.json()
    assert saved["cs_config"] == data.cs_config
    config = {**saved["cs_config"], "triangleCornerRadiusMm": 8}
    updated = client.put(
        f"{path}/{saved['id']}",
        headers=admin_headers,
        json={**saved, "cs_config": config},
    )
    assert updated.status_code == 200, updated.text
    reopened = client.get(f"/api/projects/{project['id']}", headers=admin_headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["sections"][0]["cs_config"] == config


def test_cs_glass_group_key_distinguishes_treatment():
    from engine.cs_calc import cs_result_namespace
    from engine.project_documents import _physical_glass_pieces

    keys = []
    for radius in (0, 8, 10):
        data = section(radius)
        data.system = "ЦС"
        pieces = _physical_glass_pieces(
            data, cs_result_namespace(calculate_cs(data)), 1, include_penoplex=False
        )
        keys.append(pieces[0]["shape_key"])
    assert len(set(keys)) == 3


@pytest.mark.parametrize("radius", [8, 10])
def test_cs_rounding_documents_and_api(client, radius):
    data = section(radius)
    payload = {
        "name": f"Треугольник R{radius}",
        "system": "ЦС",
        "width": data.width,
        "height": data.height,
        "quantity": 2,
        "cs_config": data.cs_config,
    }
    result = client.post("/api/calculate/local/cs", json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["panes"][0]["rounded_corner"]["radius_mm"] == radius
    body = {
        "project": {"number": "CS-RADIUS", "customer": "Проверка"},
        "section": payload,
    }
    html = client.post("/api/projects/local/sections/preview", json=body)
    assert html.status_code == 200, html.text
    assert f"Скругление R{radius}; расчётные размеры до скругления" in html.text
    for extension in ("docx", "xlsx"):
        response = client.post(f"/api/projects/local/sections/{extension}", json=body)
        assert response.status_code == 200, response.text
        with ZipFile(BytesIO(response.content)) as archive:
            xml = "".join(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith(".xml")
            )
        assert f"Скругление R{radius}; расчётные размеры до скругления" in xml
        if os.environ.get("CS_ROUNDING_QA_DIR") and extension == "docx":
            directory = Path(os.environ["CS_ROUNDING_QA_DIR"]).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"cs-r{radius}.docx").write_bytes(response.content)
