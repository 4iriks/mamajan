"""Scoped regressions: painting allowance and CS production dimension legibility."""

from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from pypdf import PdfReader
from PIL import Image

from engine import office_diagrams
from engine.cs_calc import calculate_cs, cs_result_namespace
from engine.project_documents import (
    CalculatedSection,
    _build_paint_pages,
    _manual_paint_row,
    _paint_allowance_label,
    _project_extra_paint_rows,
)


@pytest.mark.parametrize(
    "article,extra",
    [
        ("RS1313", 80),
        ("RS1315", 80),
        (" rs1315 ", 80),
        ("RS2323", 50),
        ("RS2325", 50),
        ("RS2021", 50),
        ("RS2333", 50),
        ("RS2335", 50),
        ("RS13150", 50),
        ("RL101", 50),
    ],
)
def test_paint_allowance_only_for_two_upper_tracks(article, extra):
    profile = SimpleNamespace(
        article=article,
        name="Профиль",
        length_mm=1445.2,
        qty=3,
        painted=True,
        image="",
        paint_note="",
        paint_mode="Красится",
    )
    calc = SimpleNamespace(color_text="RAL 9016", profiles=[profile])
    before = deepcopy(calc)
    page = _build_paint_pages(
        [CalculatedSection(order=1, section=SimpleNamespace(), calc=calc)]
    )[0]
    row = page["rows"][0]
    assert row["clean"] == 1450  # Established upward rounding is not changed.
    assert row["allowance"] == 1450 + extra
    assert row["total_m"] == round(3 * (1450 + extra) / 1000, 1)
    assert page["allowance_label"] == f"С припуском {extra} мм"
    assert calc == before  # No change to production dimensions/quantities.


@pytest.mark.parametrize(
    "article,extra", [("RS1313", 80), ("RS1315", 80), ("RS2323", 50)]
)
def test_extra_and_manual_paint_defaults_follow_article(article, extra):
    project = SimpleNamespace(
        extra_components=[
            {
                "sku": article,
                "name": "Профиль",
                "size": "1000 мм",
                "qty": 2,
                "requires_paint": True,
                "color": "9005",
            }
        ]
    )
    rows = _project_extra_paint_rows(project)
    assert rows[0]["allowance"] == 1000 + extra
    raw = {"article": article, "qty": 2, "clean": 1000}
    assert _manual_paint_row(raw)[1]["allowance"] == 1000 + extra
    assert (
        _manual_paint_row({**raw, "allowance": 1123, "totalM": 9})[1]["allowance"]
        == 1123
    )
    assert _manual_paint_row({**raw, "allowance": 1123, "totalM": 9})[1]["total_m"] == 9


def test_paint_caption_does_not_claim_uniform_fifty_mm():
    rows = [{"clean": 1000, "allowance": 1080}, {"clean": 1000, "allowance": 1050}]
    assert _paint_allowance_label(rows) == "С припуском 50/80 мм"
    assert (
        _paint_allowance_label([{"clean": 1000, "allowance": 1123}])
        == "С припуском, мм"
    )
    assert (
        _paint_allowance_label([*rows, {"stock_length": True}]) == "Размер в заявку, мм"
    )


def test_cs_production_dimensions_have_print_size_without_changing_other_diagrams(
    monkeypatch,
):
    section = SimpleNamespace(
        system="ЦС", width=3000, height=2400, quantity=1, cs_config={}
    )
    calc = cs_result_namespace(calculate_cs(section))
    before = deepcopy(calc)
    default = office_diagrams.render_cs_front(section, calc)
    assert default == office_diagrams.render_cs_front(
        section, calc, print_dimensions=False
    )
    sizes = []
    original = office_diagrams._print_font_pixels

    def capture(point_size, *args, **kwargs):
        sizes.append((point_size, kwargs["max_height_mm"]))
        return original(point_size, *args, **kwargs)

    monkeypatch.setattr(office_diagrams, "_print_font_pixels", capture)
    production = office_diagrams.section_diagrams(
        section, calc, cs_print_dimensions=True
    )[0][1]
    assert production != default
    assert sizes == [(9.5, 49)]
    assert calc == before


@pytest.mark.parametrize("width,height", [(1755, 2835), (3000, 2400), (6000, 600)])
@pytest.mark.parametrize("print_size", [(188, 49), (90, float("inf"))])
def test_cs_dimension_font_is_readable_at_actual_export_size(
    monkeypatch, width, height, print_size
):
    section = SimpleNamespace(
        system="ЦС", width=width, height=height, quantity=1, cs_config={}
    )
    calc = cs_result_namespace(calculate_cs(section))
    sizes = []
    original = office_diagrams._print_font_pixels

    def capture(*args, **kwargs):
        size = original(*args, **kwargs)
        sizes.append(size)
        return size

    monkeypatch.setattr(office_diagrams, "_print_font_pixels", capture)
    png = office_diagrams.render_cs_front(
        section, calc, print_dimensions=True, print_size_mm=print_size
    )
    with Image.open(BytesIO(png)) as image:
        points = (
            sizes[0]
            * min(print_size[0] / image.width, print_size[1] / image.height)
            * 72
            / 25.4
        )
    assert 9 <= points <= 10.5


def qa_save(name, extension, content):
    if directory := os.environ.get("OCT16_QA_DIR"):
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / f"{name}.{extension}").write_bytes(content)


@pytest.mark.parametrize("kind", ["rectangle", "triangle", "roof", "slide-reference"])
def test_production_exports_use_large_cs_dimensions_only(client, kind):
    section = {
        "system": "ЦС",
        "name": "Секция 1",
        "width": 3000,
        "height": 2400,
        "quantity": 1,
        "painting_type": "RAL стандарт",
        "ral_color": "9005",
        "glass_type": "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        "cs_config": {"version": 2},
    }
    if kind == "rectangle":
        section["width"] = 1755
        section["height"] = 2835
        section["cs_config"]["vertical"] = {"count": 2, "mode": "equal"}
    elif kind == "triangle":
        section.update(width=2390, height=745)
        section["cs_config"].update(
            dimensionMode="clear",
            triangleCornerRadiusMm=10,
            vertices=[{"x": 0, "y": 0}, {"x": 2390, "y": 0}, {"x": 2390, "y": 745}],
        )
    elif kind == "roof":
        section["cs_config"].update(
            vertices=[
                {"x": 0, "y": 0},
                {"x": 3000, "y": 0},
                {"x": 3000, "y": 1700},
                {"x": 1500, "y": 2400},
                {"x": 0, "y": 1900},
            ]
        )
    else:
        section.update(system="СЛАЙД", panels=3, rails=3, first_panel_inside="Справа")
        section.pop("cs_config")
    body = {
        "project": {"number": "OCT16-QA", "customer": "Контрольный пример"},
        "section": section,
    }
    for extension in ("pdf", "docx", "xlsx"):
        response = client.post(f"/api/projects/local/sections/{extension}", json=body)
        assert response.status_code == 200, response.text
        qa_save(kind, extension, response.content)
        if extension == "pdf":
            assert PdfReader(BytesIO(response.content)).pages
        elif kind != "slide-reference":
            with ZipFile(BytesIO(response.content)) as archive:
                images = [
                    archive.read(name)
                    for name in archive.namelist()
                    if "/media/" in name and name.endswith(".png")
                ]
            assert images
            assert images[0].startswith(b"\x89PNG")


def test_paint_exports_share_eighty_mm_allowance(client):
    sections = [
        {
            "name": f"Секция {rails}",
            "system": "СЛАЙД",
            "width": 3000,
            "height": 2400,
            "quantity": 1,
            "panels": 3,
            "rails": rails,
            "first_panel_inside": "Справа",
            "painting_type": "RAL стандарт",
            "ral_color": "9005",
        }
        for rails in (3, 5)
    ]
    body = {
        "project": {"number": "OCT16-PAINT", "customer": "Контрольный пример"},
        "sections": sections,
    }
    for extension in ("preview", "pdf", "docx", "xlsx"):
        response = client.post(
            f"/api/projects/local/documents/paint/{extension}", json=body
        )
        assert response.status_code == 200, response.text
        qa_save(
            "paint", "html" if extension == "preview" else extension, response.content
        )
        if extension == "pdf":
            text = "\n".join(
                page.extract_text()
                for page in PdfReader(BytesIO(response.content)).pages
            )
        elif extension == "preview":
            text = response.text
        else:
            with ZipFile(BytesIO(response.content)) as archive:
                text = "".join(
                    archive.read(name).decode("utf-8")
                    for name in archive.namelist()
                    if name.endswith(".xml")
                )
        assert "3080" in text and "3050" in text
        assert "RS1313" in text and "RS1315" in text
        assert "50/80" in text
