"""Customer acceptance cases: invoice 71, independent rails, CS and delivery."""

from collections import Counter
from copy import deepcopy
from io import BytesIO
import json
from math import hypot
from types import SimpleNamespace

from openpyxl import load_workbook
import pytest
from shapely.geometry import Polygon

from engine.cs_calc import (
    calculate_cs,
    offset_contour,
    CsCalculationError,
    split_profile_lengths,
)
from engine.cs_cover_cutting import cover_cuts
from engine.quote_pricing import _section_snapshot
from engine.office_xlsx import _build_delivery_xlsx
from engine.project_documents import (
    _build_delivery_context,
    render_project_document_html,
)
from engine.slide_calc import (
    calculate_slide,
    _apply_two_row_glass_total_correction,
    SlideCalcResult,
    PanelGlassItem,
)


def slide(**changes):
    values = dict(
        width=7704,
        height=2633,
        quantity=1,
        rails=5,
        panels=8,
        slide_rows=2,
        inter_glass_profile="Алюминиевый RS2061",
        profile_left_bubble=True,
        profile_right_bubble=True,
        handle_left="Без ручки (глухая)",
        handle_right="Без ручки (глухая)",
        threshold="Стандартный окраш",
        unused_track="Внешний",
    )
    return SimpleNamespace(**(values | changes))


@pytest.mark.parametrize("quantity", [1, 2, 7])
def test_invoice_71_section_2(quantity):
    result = calculate_slide(slide(quantity=quantity))
    assert [p.width_mm for p in result.panel_glass] == [968] * 8
    assert sum(p.width_mm for p in result.panel_glass) == 7744
    assert 7704 - 5 - 5 - 3 + 9.5 * 6 - 7744 == 4
    assert not result.warnings
    assert sum(row.qty for row in result.glass) == 8 * quantity
    assert Counter(
        {row.length_mm: row.qty for row in result.profiles if row.article == "RS2021"}
    ) == {968: 2 * quantity, 965: 6 * quantity}


@pytest.mark.parametrize("count", [6, 8, 10])
@pytest.mark.parametrize("difference", [2, 2.25, 3, 4, 4.5, 5])
def test_positive_section_tolerance_preserves_all_cuts(count, difference):
    result = SlideCalcResult(
        panel_glass=[
            PanelGlassItem(i + 1, "", 600.96, 2200, 597.96) for i in range(count)
        ]
    )
    _apply_two_row_glass_total_correction(result, count * 600 + difference)
    assert [p.width_mm for p in result.panel_glass] == [600] * count
    assert [p.glass_profile_length for p in result.panel_glass] == [597] * count
    assert not result.warnings


@pytest.mark.parametrize("count", [4, 6, 8, 10])
@pytest.mark.parametrize("difference", [-5, -4, 5.1, 6])
def test_unaccepted_differences_still_warn(count, difference):
    result = SlideCalcResult(
        panel_glass=[PanelGlassItem(i + 1, "", 600, 2200, 597) for i in range(count)]
    )
    _apply_two_row_glass_total_correction(result, count * 600 + difference)
    assert len(result.warnings) == 1


def test_four_panels_do_not_receive_new_allowance():
    result = SlideCalcResult(
        panel_glass=[PanelGlassItem(i + 1, "", 600, 2200, 597) for i in range(4)]
    )
    _apply_two_row_glass_total_correction(result, 2404)
    assert result.warnings


@pytest.mark.parametrize("placement", ["center", "outside"])
def test_unused_strip_translates_without_reversing_panels(placement):
    outside = calculate_slide(
        slide(first_panels_placement=placement, unused_track="Внешний")
    )
    inside = calculate_slide(
        slide(first_panels_placement=placement, unused_track="Внутренний")
    )
    assert inside.panel_rails == [rail - 1 for rail in outside.panel_rails]
    assert inside.panel_numbers == outside.panel_numbers
    assert inside.panel_glass == outside.panel_glass
    assert inside.hardware == outside.hardware
    assert inside.panel_numbers == (
        [4, 3, 2, 1, 1, 2, 3, 4] if placement == "center" else [1, 2, 3, 4, 4, 3, 2, 1]
    )


def test_api_preserves_placement_when_old_client_changes_unused_strip(
    client, admin_headers, project
):
    payload = vars(slide()) | {"system": "СЛАЙД", "name": "Секция"}
    created = client.post(
        f"/api/projects/{project['id']}/sections", json=payload, headers=admin_headers
    )
    assert created.status_code == 201, created.text
    url = f"/api/projects/{project['id']}/sections/{created.json()['id']}"
    payload["unused_track"] = "Внутренний"
    saved = client.put(url, json=payload, headers=admin_headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["first_panels_placement"] == "center"
    payload["first_panels_placement"] = "outside"
    saved = client.put(url, json=payload, headers=admin_headers)
    assert saved.json()["first_panels_placement"] == "outside"
    read = client.get(f"/api/projects/{project['id']}", headers=admin_headers)
    assert read.json()["sections"][0]["first_panels_placement"] == "outside"
    copied = client.post(f"/api/projects/{project['id']}/copy", headers=admin_headers)
    assert copied.status_code == 201, copied.text
    try:
        assert copied.json()["sections"][0]["first_panels_placement"] == "outside"
    finally:
        client.delete(f"/api/projects/{copied.json()['id']}", headers=admin_headers)


@pytest.mark.parametrize("placement", [None, "center", "outside"])
def test_new_quote_snapshot_retains_placement_and_panel_numbers(placement):
    section = slide(system="СЛАЙД", first_panels_placement=placement)
    calc = calculate_slide(section)
    snapshot = _section_snapshot(section, calc)
    assert snapshot["first_panels_placement"] == (placement or "center")
    assert [p["number"] for p in snapshot["panel_geometry"]] == calc.panel_numbers


def narrow_cs(mirror=False):
    points = [
        {"x": 0, "y": 0},
        {"x": 4499, "y": 0},
        {"x": 4499, "y": 40},
        {"x": 0, "y": 967},
    ]
    if mirror:
        points = [{"x": 4499 - p["x"], "y": p["y"]} for p in points]
    return SimpleNamespace(
        width=4499,
        height=967,
        quantity=2,
        cs_config={
            "version": 2,
            "dimensionMode": "installation",
            "vertices": points,
            "edgeTreatments": ["clamp", "none", "clamp", "clamp"],
            "vertical": {"count": 1, "mode": "equal"},
            "triangleCornerRadiusMm": 8,
        },
    )


@pytest.mark.parametrize("mirror", [False, True])
def test_narrow_trapezoid_keeps_full_profiles_and_valid_rounded_glass(mirror):
    section = narrow_cs(mirror)
    before = deepcopy(section.cs_config)
    result = calculate_cs(section)
    assert section.cs_config == before
    assert len(result["installation_polygon"]) == 4
    assert len(result["glass_polygon"]) == len(result["clear_polygon"]) == 3
    assert len(result["panes"]) == 2
    assert sum(p["qty"] for p in result["panes"]) == 4
    assert sum(bool(p.get("rounded_corner")) for p in result["panes"]) == 1
    for pane in result["panes"]:
        assert Polygon([(p["x"], p["y"]) for p in pane["polygon"]]).is_valid
    full = [4499, hypot(4499, 927), 967]
    assert result["outer_edge_lengths_mm"] == pytest.approx(full)
    assert result["cover_cuts"] == cover_cuts(full)
    outer = result["profiles"][0]
    assert outer["pieces"] == 10
    assert outer["cut_lengths_mm"] == pytest.approx(
        [3000, 1499, 3000, hypot(4499, 927) - 3000, 967]
    )
    assert outer["total_length_mm"] == pytest.approx(sum(full) * 2)


@pytest.mark.parametrize(
    "length,expected",
    [
        (2999, [2999]),
        (3000, [3000]),
        (3001, [3000, 1]),
        (4499, [3000, 1499]),
        (6000, [3000, 3000]),
        (7500, [3000, 3000, 1500]),
    ],
)
def test_t40_cuts_respect_stock_and_preserve_length(length, expected):
    assert split_profile_lengths([length]) == expected
    assert sum(split_profile_lengths([length])) == length


def test_inset_with_no_glass_is_still_rejected():
    points = [
        {"x": 0, "y": 0},
        {"x": 40, "y": 0},
        {"x": 40, "y": 40},
        {"x": 0, "y": 40},
    ]
    with pytest.raises(CsCalculationError):
        offset_contour(points, [26] * 4)


def test_bubble_on_disappearing_side_does_not_take_another_sides_length():
    section = narrow_cs()
    section.cs_config["edgeTreatments"][1] = "bubble"
    result = calculate_cs(section)
    assert not any(p["role"] == "bubble" for p in result["profiles"])


def delivery_project():
    rows = [
        dict(
            name="УГОЛ АЛ, 20х30мм",
            color="7024 МАТОВЫЙ",
            size=str(size),
            qty=qty,
            unit="шт",
            deliveryStage="both",
        )
        for size, qty in [
            (3020, 20),
            (3750, 2),
            (2600, 2),
            (3450, 4),
            (2250, 2),
            (3950, 2),
            (2150, 2),
            (2700, 2),
        ]
    ]
    return SimpleNamespace(
        number="С26-7-4282",
        customer="Контроль",
        extra_components=json.dumps(rows, ensure_ascii=False),
    )


def test_delivery_groups_sizes_and_keeps_individual_places():
    project = delivery_project()
    context = _build_delivery_context(project, [])
    assert len(context["delivery_extra_groups"]) == 1
    group = context["delivery_extra_groups"][0]
    assert len(group) == 8
    assert sum(row["qty"] for row in group) == 36
    places = {row["place_key"]: str(i + 1) for i, row in enumerate(group)}
    project.delivery_note_data = json.dumps({"places": places})
    context = _build_delivery_context(project, [])
    assert [row["places"] for row in context["delivery_extra_groups"][0]] == [
        str(i) for i in range(1, 9)
    ]
    html = render_project_document_html(project, [], "delivery")
    assert html.count("УГОЛ АЛ, 20х30мм") == 1
    assert html.count("Цвет: 7024 МАТОВЫЙ") == 1
    assert (
        html.count("data-delivery-place-key=")
        == len(context["delivery_item2_rows"]) + 8
    )
    workbook = load_workbook(BytesIO(_build_delivery_xlsx(context)))
    values = [
        cell.value for row in workbook.active for cell in row if cell.value is not None
    ]
    assert sum("УГОЛ АЛ, 20х30мм" in str(value) for value in values) == 1
    assert len([value for value in values if str(value).startswith("Размер:")]) == 8
