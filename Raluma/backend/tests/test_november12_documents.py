"""Delivery glass totals, extras-only shipments and rounded paint lengths."""

from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from types import SimpleNamespace

from docx import Document
from openpyxl import load_workbook
import pytest

from engine.office_docx import build_project_docx
from engine.office_xlsx import build_project_xlsx
from engine.project_documents import (
    _build_delivery_context,
    _delivery_glass_10mm_summary,
    _manual_paint_row,
    build_project_document_context,
    render_project_document_html,
)
from schemas import SectionCreate


def project(**overrides):
    return SimpleNamespace(
        **{
            "number": "TEST-81",
            "customer": "Тест",
            "delivery_note_data": '{"includeGlass":true}',
            **overrides,
        }
    )


def section(**overrides):
    return SimpleNamespace(
        **SectionCreate(
            **{
                "name": "Секция 1",
                "system": "СЛАЙД",
                "width": 2505,
                "height": 3093,
                "panels": 3,
                "quantity": 2,
                "painting_type": "RAL стандарт",
                "ral_color": "9016 МАТОВЫЙ",
                **overrides,
            }
        ).model_dump()
    )


def xlsx_text(payload):
    workbook = load_workbook(BytesIO(payload))
    return "\n".join(
        str(cell.value or "")
        for sheet in workbook
        for row in sheet.iter_rows()
        for cell in row
    )


def test_delivery_glass_area_and_weight_include_all_panes_and_section_quantity():
    p, sections = project(), [section()]
    context = _build_delivery_context(p, sections)
    glass = next(r for r in context["delivery_item1_rows"] if r["kind"] == "glass")
    assert sum(row["qty"] for row in glass["rows"]) == 6
    area = sum(
        Decimal(str(r["width"])) * Decimal(str(r["height"])) * r["qty"] / 1_000_000
        for r in glass["rows"]
    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    weight = (area * 25).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    summary = glass["glass_summary"]
    assert summary["area_m2"] == float(area)
    assert summary["weight_kg"] == float(weight)
    assert summary["text"] in render_project_document_html(p, sections, "delivery")
    assert summary["text"] in xlsx_text(build_project_xlsx(p, sections, "delivery"))
    assert context["delivery_glass_summary"] is None  # No duplicate grand total.


def test_delivery_glass_grand_total_combines_colors_and_excludes_other_thicknesses():
    context = _build_delivery_context(
        project(),
        [
            section(),
            section(name="Секция 2", ral_color="9005 МАТОВЫЙ", quantity=1),
            section(name="Секция 3", glass_type="8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"),
        ],
    )
    groups = [r for r in context["delivery_item1_rows"] if r["kind"] == "glass"]
    assert len(groups) == 3
    assert sum(bool(g["glass_summary"]) for g in groups) == 2
    expected = _delivery_glass_10mm_summary(r for g in groups for r in g["rows"])
    assert context["delivery_glass_summary"] == expected


@pytest.mark.parametrize(
    "glass_type",
    ["8ММ", "110ММ", "СТЕКЛОПАКЕТ 20мм (10-10)", "ТРИПЛЕКС 10мм", "ПЕНОПЛЕКС 20мм"],
)
def test_glass_weight_rule_is_only_for_single_ten_mm_glass(glass_type):
    assert (
        _delivery_glass_10mm_summary(
            [{"glass_type": glass_type, "width": 1000, "height": 2000, "qty": 3}]
        )
        is None
    )


def test_shaped_glass_uses_actual_shape_area_not_bounding_rectangle():
    summary = _delivery_glass_10mm_summary(
        [
            {
                "glass_type": "10мм",
                "width": 1000,
                "height": 2000,
                "qty": 3,
                "shape_area_m2": 1.5,
            }
        ]
    )
    assert summary["area_m2"] == 4.5
    assert summary["weight_kg"] == 112.5


def test_delivery_without_supplied_glass_has_no_glass_totals():
    p, sections = project(), [section(glass_supplied=False)]
    context = _build_delivery_context(p, sections)
    assert not any(r["kind"] == "glass" for r in context["delivery_item1_rows"])
    assert context["delivery_glass_summary"] is None
    assert "25 кг/м²" not in render_project_document_html(p, sections, "delivery")


@pytest.mark.parametrize("stage", [1, 2])
def test_delivery_with_only_extras_has_no_automatic_hardware_kit(stage):
    p = project(
        production_stages=2,
        current_stage=stage,
        extra_components=[
            {
                "sku": "RS1313",
                "name": "Верхний профиль",
                "category": "profile",
                "size": "2715",
                "qty": 1,
                "requires_paint": True,
                "delivery_stage": "both",
            },
            {
                "sku": "RS104B/106",
                "name": "Заглушка",
                "category": "component",
                "qty": 2,
                "delivery_stage": "both",
            },
        ],
    )
    context = _build_delivery_context(p, [])
    assert context["delivery_item2_rows"] == []
    assert {r["article"] for r in context["delivery_project_extra_rows"]} == {
        "RS1313",
        "RS104B/106",
    }
    for text in (
        render_project_document_html(p, [], "delivery"),
        xlsx_text(build_project_xlsx(p, [], "delivery")),
    ):
        assert "Комплект фурнитуры согласно ТЗ" not in text
        assert "RS1313" in text and "RS104B/106" in text


def test_delivery_with_sections_retains_hardware_kit():
    context = _build_delivery_context(project(), [section()])
    assert any(
        r["name"] == "Комплект фурнитуры согласно ТЗ"
        for r in context["delivery_item2_rows"]
    )


@pytest.mark.parametrize(
    "article,expected",
    [
        ("RS1313", [2800, 2750, 2600]),
        ("RS1315", [2800, 2750, 2600]),
        ("RS1323", [2800, 2700, 2550]),
        ("RS1333", [2800, 2700, 2550]),
    ],
)
def test_paint_lengths_round_up_after_allowance_without_changing_clean_sizes(
    article, expected
):
    lengths = [2715, 2633, 2494]
    p = project(
        extra_components=[
            {
                "sku": article,
                "name": "Профиль",
                "size": str(length),
                "qty": 2,
                "requires_paint": True,
                "color": "8017 ГЛЯНЦЕВЫЙ",
            }
            for length in lengths
        ]
    )
    page = build_project_document_context(p, [], "paint")["paint_pages"][0]
    assert [r["clean"] for r in page["rows"]] == lengths
    assert [r["allowance"] for r in page["rows"]] == expected
    assert [r["total_m"] for r in page["rows"]] == [
        round(2 * length / 1000, 1) for length in expected
    ]
    allowance = 80 if article in {"RS1313", "RS1315"} else 50
    assert page["allowance_label"] == f"С припуском {allowance} мм"
    html = render_project_document_html(p, [], "paint")
    spreadsheet = xlsx_text(build_project_xlsx(p, [], "paint"))
    document = Document(BytesIO(build_project_docx(p, [], "paint")))
    word = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    for text in (html, spreadsheet, word):
        assert all(str(length) in text for length in expected)


def test_paint_manual_default_rounds_up_but_explicit_size_is_preserved():
    raw = {"article": "RS1313", "clean": 2715, "qty": 1}
    assert _manual_paint_row(raw)[1]["allowance"] == 2800
    assert _manual_paint_row({**raw, "allowance": 2812})[1]["allowance"] == 2812
