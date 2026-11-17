import io
import json
import re
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest

from engine.book_calc import calculate_book
from engine.book_diagrams import book_room_svg, book_top_svg
from engine.book_sheet import build_book_sheet_data
from engine.office_docx import build_section_docx
from engine.office_xlsx import build_section_xlsx
from engine.pdf import render_preview
from schemas import SectionCreate


def section(**updates):
    data = dict(
        name="Секция 1",
        system="КНИЖКА",
        width=3660,
        height=2400,
        panels=5,
        quantity=1,
        door_side="right",
        book_system="B25",
        compensator="lower",
        book_right_door_hardware="handle",
        book_right_door_opening="inside_in",
        glass_supplied=False,
    )
    data.update(updates)
    data["document_overrides"] = json.dumps(
        updates.get("document_overrides", {}), ensure_ascii=False
    )
    return SimpleNamespace(**SectionCreate(**data).model_dump())


def test_grouped_operations_keep_original_keys_and_calculation():
    s = section()
    calc = calculate_book(s)
    before = deepcopy(asdict(calc))
    sheet = build_book_sheet_data(s, calc)
    d6 = [row for row in sheet.operation_rows if row.kind == "Крепёжные отверстия D6"]
    assert len(d6) == 1
    assert d6[0].profile == "RBP001 · верх и низ"
    assert d6[0].field_prefix == "book_operation_d6_upper"
    assert d6[0].field_aliases == ("book_operation_d6_lower",)
    assert asdict(calc) == before
    assert (sheet.glass_rows[0].width_mm, sheet.glass_rows[0].height_mm) == (724, 2265)
    assert (sheet.assembly_rows[0].width_mm, sheet.assembly_rows[0].height_mm) == (
        727,
        2298,
    )
    assert "Система" not in dict(sheet.summary_rows)
    assert "Поставка стекла" not in dict(sheet.summary_rows)
    assert dict(sheet.summary_rows)["Компенсирующий профиль"] == "Нижний"


@pytest.mark.parametrize(
    "field,value",
    [
        ("coordinates", "125; 247"),
        ("dimensions", "Ø6 × 12"),
        ("note", "Особая обработка"),
    ],
)
def test_different_saved_operations_remain_separate(field, value):
    saved = {f"book_operation_d6_lower_{field}": value}
    s = section(document_overrides=saved)
    original = s.document_overrides
    d6 = [
        r
        for r in build_book_sheet_data(s, calculate_book(s)).operation_rows
        if r.kind == "Крепёжные отверстия D6"
    ]
    assert len(d6) == 2 and all(not r.field_aliases for r in d6)
    assert getattr(next(r for r in d6 if r.profile.endswith("низ")), field) == value
    assert s.document_overrides == original


def test_shared_edit_and_cutting_note_reach_preview_and_office():
    saved = {
        f"book_operation_d6_{side}_coordinates": "125; 247; 701.25"
        for side in ("upper", "lower")
    }
    saved["book_cutting_note"] = "Контрольное примечание к нарезке"
    s = section(document_overrides=saved)
    calc = calculate_book(s)
    project = SimpleNamespace(number="VISUAL-QA", customer="")
    html = render_preview(project, s, calc)
    assert 'data-field-aliases="book_operation_d6_lower_coordinates"' in html
    assert html.count("125; 247; 701.25</span>") == 1
    assert saved["book_cutting_note"] in html
    assert "B25" not in re.sub(r"<[^>]+>", "", html)
    for builder, xml in (
        (build_section_docx, "word/document.xml"),
        (build_section_xlsx, "xl/sharedStrings.xml"),
    ):
        with ZipFile(io.BytesIO(builder(project, s, calc))) as archive:
            text = " ".join(ElementTree.fromstring(archive.read(xml)).itertext())
        assert "RBP001 · верх и низ" in text
        assert "125; 247; 701.25" in text
        assert saved["book_cutting_note"] in text
        assert "B25" not in text


@pytest.mark.parametrize(
    "side,opening",
    [("left", "inside_in"), ("right", "inside_out"), ("both", "inside_in")],
)
def test_top_leaves_use_actual_scale_and_boundary_door(side, opening):
    s = section(
        door_side=side,
        book_left_stack_panels=2,
        book_left_door_opening=opening,
        book_right_door_opening=opening,
        book_left_door_hardware="handle",
        book_left_door_width=800,
        book_right_door_width=900,
    )
    calc = calculate_book(s)
    svg = ElementTree.fromstring(book_top_svg(s, calc))
    leaves = [el for el in svg.iter() if el.get("data-book-panel")]
    assert len(leaves) == len(calc.panels)
    panels = {p.number: p for p in calc.panels}
    for leaf in leaves:
        panel = panels[int(leaf.get("data-book-panel"))]
        expected = panel.panel_width_mm / s.width * 416
        assert abs(float(leaf.get("y2"))) == pytest.approx(expected)
        if panel.role == "door":
            assert float(leaf.get("x1")) == (20 if panel.door_side == "left" else 436)
    assert len({round(abs(float(leaf.get("y2"))), 3) for leaf in leaves}) > 1
    assert (
        ElementTree.fromstring(book_room_svg(s, calc)).get("viewBox").split()[2]
        == svg.get("viewBox").split()[2]
        == "480"
    )
