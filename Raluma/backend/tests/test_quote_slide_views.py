"""Both quote views must use the same saved panel positions, including two rows."""

from copy import deepcopy
import io
import re
from types import SimpleNamespace
import zipfile

import pytest

from engine.office_docx import build_project_docx
from engine.project_documents import render_project_document_html
from engine.quote_diagrams import render_quote_room_png, render_quote_top_png
from engine.quote_pricing import _section_snapshot
from engine.slide_calc import calculate_slide
from schemas import SectionCreate


@pytest.mark.parametrize(
    "rows,panels,rails,placement,first",
    [
        (1, 3, 3, "center", "Слева"),
        (1, 4, 5, "center", "Справа"),
        (2, 6, 3, "center", "Слева"),
        (2, 8, 5, "outside", "Справа"),
    ],
)
def test_quote_views_preserve_snapshot_panel_positions(
    rows, panels, rails, placement, first
):
    section = SectionCreate(
        system="СЛАЙД",
        name="Секция 1",
        width=2505 if rows == 1 else 6000,
        height=3093,
        panels=panels,
        rails=rails,
        slide_rows=rows,
        quantity=1,
        first_panels_placement=placement,
        first_panel_inside=first,
        glass_supplied=False,
    )
    details = _section_snapshot(section, calculate_slide(section))
    quote = {
        "revision": 1,
        "status": "fixed",
        "document_layout_version": 2,
        "lines": [
            {
                "name": "Секция 1",
                "category": "construction",
                "quantity": 1,
                "unit": "шт.",
                "section_details": details,
                "document_line_total": 1000,
                "document_unit_final_price": 1000,
            }
        ],
        "totals": {
            "document_grand_total": 1000,
            "document_before_discount": 1000,
            "document_discount": 0,
        },
    }
    before = deepcopy(quote)
    project = SimpleNamespace(number="QA", customer="Проверка")
    html = render_project_document_html(project, [], "commercial", quote=quote)
    top_panels = re.findall(r'data-quote-top-panel="(\d+)" data-rail="(\d+)"', html)
    assert top_panels == [
        (str(p["number"]), str(p["rail"])) for p in details["panel_geometry"]
    ]
    assert 'aria-label="Вид из помещения"' in html
    assert 'aria-label="Вид сверху"' in html
    assert 'fill="#ffffff"' in html
    with zipfile.ZipFile(
        io.BytesIO(build_project_docx(project, [], "commercial", quote=quote))
    ) as archive:
        images = [
            archive.read(name)
            for name in archive.namelist()
            if name.startswith("word/media/")
        ]
        assert len(images) == 2
        assert render_quote_room_png(details, compact=True, show_title=False) in images
        assert render_quote_top_png(details, show_title=False) in images
        assert "ВИД СВЕРХУ" in archive.read("word/document.xml").decode()
    assert quote == before
