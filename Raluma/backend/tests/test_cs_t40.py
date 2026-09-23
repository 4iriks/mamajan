"""Customer control dimensions, geometry migration and actual BOM, not snapshots."""

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from shapely.geometry import Polygon

from engine.cs_calc import CsCalculationError, calculate_cs, offset_contour


def section(width=1755, height=2835, **kwargs):
    return SimpleNamespace(width=width, height=height, quantity=1, **kwargs)


def rectangle(width=1755, height=2835, **kwargs):
    return {
        "version": 2,
        "vertices": [
            dict(x=0, y=0),
            dict(x=width, y=0),
            dict(x=width, y=height),
            dict(x=0, y=height),
        ],
        **kwargs,
    }


@pytest.mark.parametrize(
    "count, widths",
    [(0, [1703]), (1, [850, 850]), (2, [570 + 1 / 3, 556 + 1 / 3, 570 + 1 / 3])],
)
def test_customer_control_dimensions(count, widths):
    result = calculate_cs(
        section(cs_config=rectangle(vertical={"count": count, "mode": "equal"}))
    )
    assert result["clear_width_mm"] == 1675
    assert result["clear_height_mm"] == 2755
    assert [p["width_mm"] for p in result["panes"]] == pytest.approx(widths)
    assert [p["height_mm"] for p in result["panes"]] == [2783] * (count + 1)
    assert result["hardware"][0]["qty"] == 2 * (count + 1)
    profiles = {p["role"]: p for p in result["profiles"]}
    assert profiles["outer"]["total_length_mm"] == 9180
    assert profiles["cover"]["total_length_mm"] == 18360
    assert profiles["cover"]["pieces"] == 8
    assert all(not p["requires_paint"] for p in result["profiles"])
    if count:
        assert result["hardware"][1]["article"] == ""
        assert result["hardware"][1]["qty"] == pytest.approx(count * 2.783)


@pytest.mark.parametrize("deduction", [6, 7])
def test_mixed_sides_and_bubble_perpendicular_deduction(deduction):
    result = calculate_cs(
        section(
            945,
            2328,
            cs_config=rectangle(
                945,
                2328,
                edgeTreatments=["clamp", "none", "clamp", "bubble"],
                bubbleDeductionMm=deduction,
            ),
        )
    )
    assert result["panes"][0]["width_mm"] == 945 - deduction
    assert result["panes"][0]["height_mm"] == 2276
    assert result["profiles"][2]["article"] == "RS1002"
    assert result["profiles"][2]["total_length_mm"] == 2276
    assert result["profiles"][0]["total_length_mm"] == 1890


def test_quantity_and_only_covers_painted():
    s = section(
        cs_config=rectangle(vertical={"count": 2}),
        painting_type="RAL муар",
        ral_color="9005",
    )
    s.quantity = 2
    result = calculate_cs(s)
    assert result["hardware"][0]["qty"] == 12
    assert [p["qty"] for p in result["panes"]] == [2, 2, 2]
    assert result["profiles"][0]["pieces"] == 8
    assert result["profiles"][1]["pieces"] == 16
    assert [p["article"] for p in result["profiles"] if p["requires_paint"]] == ["Т40К"]
    assert result["commercial_price_allowed"] is False


def test_light_opening_restores_same_physical_geometry():
    mounted = calculate_cs(section(cs_config=rectangle(vertical={"count": 2})))
    light_config = rectangle(1675, 2755, dimensionMode="clear", vertical={"count": 2})
    light = calculate_cs(section(1675, 2755, cs_config=light_config))
    assert light["installation_width_mm"] == 1755
    assert light["installation_height_mm"] == 2835
    assert light["glass_area_m2"] == pytest.approx(mounted["glass_area_m2"])
    assert light["profiles"] == mounted["profiles"]
    assert [p["width_mm"] for p in light["panes"]] == pytest.approx(
        [p["width_mm"] for p in mounted["panes"]]
    )


def test_legacy_winding_keeps_corner_and_side_indices():
    config = rectangle()
    config.update(
        version=1, vertices=list(reversed(config["vertices"])), profiledEdges=[0, 2]
    )
    result = calculate_cs(section(cs_config=config))
    assert result["normalized_config"]["vertices"] == config["vertices"]
    assert result["normalized_config"]["edgeTreatments"] == [
        "clamp",
        "none",
        "clamp",
        "none",
    ]
    assert result["normalized_config"]["profiledEdges"] == [0, 2]
    assert result["panes"][0]["width_mm"] == 1755
    assert result["panes"][0]["height_mm"] == 2783


def test_concave_clip_returns_separate_panes_and_pads_for_every_component():
    # U shape: a horizontal line separates the two arms into two actual panes.
    points = [
        (0, 0),
        (3000, 0),
        (3000, 3000),
        (2000, 3000),
        (2000, 1000),
        (1000, 1000),
        (1000, 3000),
        (0, 3000),
    ]
    config = {
        "vertices": [dict(x=x, y=y) for x, y in points],
        "edgeTreatments": ["none"] * 8,
        "horizontal": {"mode": "manual", "positions": [1500]},
    }
    result = calculate_cs(section(3000, 3000, cs_config=config))
    assert len(result["panes"]) == 3
    assert result["hardware"][0]["qty"] == 6
    assert result["hardware"][1]["qty"] == 2
    assert result["glass_area_m2"] == pytest.approx(7 - 0.006)
    for pane in result["panes"]:
        polygon = Polygon([(p["x"], p["y"]) for p in pane["polygon"]])
        assert polygon.is_valid
        assert polygon.area / 1e6 == pytest.approx(pane["area_m2"])


def test_tape_excludes_crossing_air_gaps():
    result = calculate_cs(
        section(cs_config=rectangle(vertical={"count": 1}, horizontal={"count": 1}))
    )
    assert result["hardware"][1]["qty"] == pytest.approx((2783 - 3 + 1703 - 3) / 1000)


def test_triangle_excel_preserves_polygon_area_formula(client):
    from openpyxl import load_workbook

    s = dict(system="ЦС", width=3000, height=3000, quantity=2, cs_shape="Треугольник")
    response = client.post(
        "/api/projects/local/documents/glass/xlsx",
        json={"project": {"number": "CS-TRI"}, "sections": [s]},
    )
    assert response.status_code == 200, response.text
    workbook = load_workbook(BytesIO(response.content), data_only=False)
    formulas = [
        cell.value for row in workbook.active for cell in row if cell.data_type == "f"
    ]
    areas = [
        formula
        for formula in formulas
        if formula.startswith("=ROUND(") and "*F" in formula
    ]
    assert len(areas) == 1
    assert "*E" not in areas[0] and "1000000" not in areas[0]


@pytest.mark.parametrize(
    "config",
    [
        {"vertices": None},
        {"vertices": [1, 2, 3]},
        {"edgeTreatments": None},
        {"profiledEdges": None},
        {"vertical": {"mode": "manual", "positions": None}},
    ],
)
def test_malformed_config_returns_user_error(client, config):
    response = client.post(
        "/api/calculate/local/cs",
        json={"system": "ЦС", "width": 1755, "height": 2835, "cs_config": config},
    )
    assert response.status_code == 422


def test_slope_inset_is_perpendicular_not_axis_aligned():
    points = [dict(x=0, y=0), dict(x=3000, y=0), dict(x=1500, y=3000)]
    result = offset_contour(points, [26, 26, 26])
    from shapely.geometry import LineString, Point

    for i, start in enumerate(points):
        end = points[(i + 1) % 3]
        side = LineString([(start["x"], start["y"]), (end["x"], end["y"])])
        assert side.distance(Point(result[i]["x"], result[i]["y"])) == pytest.approx(26)


@pytest.mark.parametrize(
    "config",
    [
        rectangle(40, 40),
        rectangle(edgeTreatments=["bad"] * 4),
        rectangle(vertical={"mode": "manual", "positions": [40]}),
        rectangle(vertical={"mode": "manual", "positions": [500, 502]}),
    ],
)
def test_invalid_geometry_fails_explicitly(config):
    with pytest.raises(CsCalculationError):
        calculate_cs(section(cs_config=config))


@pytest.mark.parametrize("glass", ["8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ", "ТРИПЛЕКС 4.1.4"])
def test_only_ten_mm_tempered_glass(glass):
    with pytest.raises(CsCalculationError, match="10 мм"):
        calculate_cs(section(glass_type=glass))


def test_catalog_migration_and_system_links(client, admin_headers):
    response = client.get("/api/catalog/hardware", headers=admin_headers)
    assert response.status_code == 200
    catalog = {item["sku"]: item for item in response.json()}
    for sku in ["Т40Т", "Т40К", "CS-PVC-PAD", "RS1002"]:
        assert "CS" in catalog[sku]["systemGroups"]
    assert catalog["Т40Т"]["photoFile"] == "T40T-photo.jpg"
    assert catalog["Т40К"]["photoFile"] == "T40K-photo.jpg"
    assert len(catalog["Т40К"]["finishVariants"]) == 4
    assert catalog["CS-PVC-PAD"]["unit"] == "шт"
    assert (
        catalog["Т40Т"]["purchasePrice"] == 0
    )  # explicitly unknown, never a quoted CS price
    systems = client.get("/api/catalog/cs-systems", headers=admin_headers).json()
    default = next(s for s in systems if s["code"] == "CS_CLAMP")
    for field, sku in [
        ("outer_profile_item_id", "Т40Т"),
        ("cover_profile_item_id", "Т40К"),
        ("bubble_seal_item_id", "RS1002"),
        ("glass_pad_item_id", "CS-PVC-PAD"),
    ]:
        assert default[field] == catalog[sku]["id"]
    from migrations import _migrate_cs_t40_once
    from database import engine

    with engine.begin() as conn:
        _migrate_cs_t40_once(conn)
    assert (
        client.get("/api/catalog/hardware", headers=admin_headers).json()
        == response.json()
    )


@pytest.mark.parametrize("extension", ["preview", "docx", "xlsx"])
def test_documents_contain_real_bom_and_only_cover_in_paint(client, extension):
    s = dict(
        system="ЦС",
        width=1755,
        height=2835,
        quantity=2,
        painting_type="RAL стандарт",
        ral_color="9005",
        cs_config=rectangle(vertical={"count": 2}),
    )
    project = {"number": "CS-T40"}
    for doc in ["section", "hardware_order", "sketch", "paint"]:
        if doc == "sketch" and extension == "xlsx":
            continue
        url = (
            f"/api/projects/local/sections/{extension}"
            if doc == "section"
            else f"/api/projects/local/documents/{doc}/{extension}"
        )
        data = (
            {"project": project, "section": s}
            if doc == "section"
            else {"project": project, "sections": [s]}
        )
        response = client.post(url, json=data)
        assert response.status_code == 200, response.text
        if extension == "preview":
            body = response.text
        else:
            with ZipFile(BytesIO(response.content)) as archive:
                body = "".join(
                    archive.read(n).decode("utf-8")
                    for n in archive.namelist()
                    if n.endswith(".xml")
                )
        assert "Т40К" in body
        if doc == "paint":
            # Warning text may mention T40T, but no clamp or pad in paint rows.
            assert "Зажимной профиль Т40Т в сборе" not in body
            assert "CS-PVC-PAD" not in body
        else:
            assert "CS-PVC-PAD" in body
            assert "скотч" in body
