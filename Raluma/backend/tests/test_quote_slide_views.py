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
from engine.quote_pricing import _section_snapshot, safe_public_payload
from engine.quote_slide_top import render_quote_top_svg
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
        profile_left_wall=True,
        profile_right_wall=True,
        profile_left_lock_bar=True,
        profile_right_lock_bar=True,
        profile_left_handle_bar=True,
        profile_right_handle_bar=True,
        inter_glass_profile="Алюминиевый RS2061",
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
    assert html.count('data-side-assembly="lock-handle"') == 2
    assert html.count('data-profile="inter-glass"') == panels - (2 if rows == 2 else 1)
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


@pytest.mark.parametrize(
    "kind,fields,filename",
    [
        (
            "lock-handle",
            {"lock_bar": True, "handle_bar": True},
            "SIDE_RS2081_RS112.png",
        ),
        ("p-handle", {"p_bar": True, "handle_bar": True}, "SIDE_RS1082_RS112.png"),
        ("p-bubble", {"p_bar": True, "bubble": True}, "SIDE_RS1082_RS1002.png"),
        ("bubble", {"bubble": True}, "SIDE_RS1002.png"),
    ],
)
def test_detailed_top_view_selected_assemblies_and_legacy_quotes(
    kind, fields, filename
):
    from xml.etree import ElementTree as ET

    section = SectionCreate(
        system="СЛАЙД",
        name="Секция 1",
        width=6000,
        height=3000,
        rails=5,
        panels=8,
        slide_rows=2,
        quantity=1,
        glass_supplied=False,
        profile_left_wall=True,
        profile_right_wall=False,
        center_handle="Ручки-профиль RS112 (2шт)",
        inter_glass_profile="Прозрачный межстекольный RS1006",
        **{f"profile_left_{key}": value for key, value in fields.items()},
    )
    snapshot = _section_snapshot(section, calculate_slide(section))
    original = deepcopy(snapshot)
    for legacy in (False, True):
        details = deepcopy(snapshot)
        if legacy:
            details.pop("top_view_options")
        svg = render_quote_top_svg(details)
        root = ET.fromstring(svg)
        assert svg.count(f'data-side-assembly="{kind}"') == 1
        assert f'data-side-assembly-image="{filename}"' in svg
        assert 'data-profile-image="RS2335-left"' in svg
        assert 'data-profile-image="RS2335-right"' not in svg
        assert svg.count("data-center-rs112-top=") == 2
        assert svg.count('data-profile="inter-glass"') == 6
        image_uris = [
            node.attrib["href"] for node in root.iter() if "href" in node.attrib
        ]
        assert len(image_uris) == 2
        assert all(uri.startswith("data:image/png;base64,") for uri in image_uris)
    assert snapshot == original


def test_top_view_preserves_explicit_absence_and_public_snapshot_filters_options():
    section = SectionCreate(
        name="Секция 1",
        system="СЛАЙД",
        width=2505,
        height=3093,
        panels=3,
        rails=3,
        quantity=1,
    )
    details = _section_snapshot(section, calculate_slide(section))
    details["top_view_options"]["supplier_cost"] = "PRIVATE"
    quote = safe_public_payload({"lines": [{"section_details": details}]})
    assert "PRIVATE" not in str(quote)
    svg = render_quote_top_svg(quote["lines"][0]["section_details"])
    assert "data-side-assembly=" not in svg
    assert "data-profile-image=" not in svg
    assert 'data-profile="inter-glass"' not in svg
