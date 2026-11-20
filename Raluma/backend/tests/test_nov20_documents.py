"""Customer corrections: delivery contents, finished CS glass and sketch alignment."""

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from docx import Document
from PIL import Image, ImageChops
from pypdf import PdfReader

from engine.cs_calc import calculate_cs
from engine.cs_rounding import rounded_bounds
from engine.office_docx import _build_sketch_docx
from engine.office_diagrams import slide_room_frame
from engine.pdf import generate_pdf
from engine.project_documents import (
    build_project_document_context,
    render_project_document_html,
)
from schemas import SectionCreate


def section(**values):
    values.setdefault("name", "Секция 1")
    return SimpleNamespace(**SectionCreate(**values).model_dump())


@pytest.mark.parametrize(
    "mirror_x,mirror_y,reverse",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (True, True, True),
    ],
)
@pytest.mark.parametrize("radius,expected_width", [(0, 2518), (8, 2476), (10, 2466)])
def test_4346_finished_glass(mirror_x, mirror_y, reverse, radius, expected_width):
    points = [{"x": 0, "y": 0}, {"x": 2700, "y": 0}, {"x": 2700, "y": 900}]
    points = [
        {
            "x": 2700 - p["x"] if mirror_x else p["x"],
            "y": 900 - p["y"] if mirror_y else p["y"],
        }
        for p in points
    ]
    if reverse:
        points.reverse()
    item = section(
        system="ЦС",
        width=2700,
        height=900,
        quantity=2,
        cs_config={
            "version": 2,
            "dimensionMode": "installation",
            "vertices": points,
            "edgeTreatments": ["clamp"] * 3,
            "triangleCornerRadiusMm": radius,
        },
    )
    before = deepcopy(vars(item))
    result = calculate_cs(item)
    pane = result["panes"][0]
    assert (pane["width_mm"], pane["height_mm"], pane["qty"]) == (
        expected_width,
        839,
        2,
    )
    if radius:
        bounds = rounded_bounds(pane["polygon"], pane["rounded_corner"])
        assert bounds[2] - bounds[0] == pytest.approx(
            2518 - radius * (3 + 10**0.5 - 1), abs=1e-6
        )
        assert "после скругления" in pane["treatment_note"]
    assert vars(item) == before


@pytest.mark.parametrize("stages,stage", [(1, 1), (2, 1), (2, 2)])
def test_cs_delivery_only_components_and_slide_preserved(stages, stage):
    project = SimpleNamespace(
        number="4303", production_stages=stages, current_stage=stage
    )
    items = [
        section(system="ЦС", width=1150, height=2360, quantity=2),
        section(system="СЛАЙД", width=3600, height=2400, panels=3),
    ]
    before = deepcopy([vars(s) for s in items])
    context = build_project_document_context(project, items, "delivery")
    html = render_project_document_html(project, items, "delivery")
    assert "ЦЕЛЬНОСТЕКЛЯННАЯ КОНСТРУКЦИЯ" not in html
    assert "СТЕКЛО(ЦС)" not in html
    assert all(r.get("system") != "ЦС" for r in context["delivery_item1_rows"])
    if stage == 1:
        assert "Т40Т" in html and "Т40К" in html and "Подкладка" in html
    assert [vars(s) for s in items] == before


def test_project_comment_and_aligned_slide_in_html_pdf_and_word():
    note = "Проектное примечание <контроль>\nСохранить вторую строку."
    project = SimpleNamespace(number="4343", comments=note)
    items = [
        section(
            system="СЛАЙД",
            width=5944,
            height=2988,
            panels=5,
            rails=5,
            profile_left_wall=True,
            profile_right_wall=True,
            comments="Примечание секции",
        )
    ]
    context = build_project_document_context(project, items, "sketch")
    assert context["project_comments"] == note
    assert context["sections"][0]["system_text"] == "SLIDE, 5-рельсовая, 1 ряд"
    diagrams = context["sections"][0]["diagrams"]
    assert diagrams[0]["print_width_mm"] == diagrams[1]["print_width_mm"]
    assert (
        Image.open(BytesIO(diagrams[0]["png"])).width
        == Image.open(BytesIO(diagrams[1]["png"])).width
    )
    top_image = Image.open(BytesIO(diagrams[1]["png"])).convert("RGB")
    bounds = ImageChops.difference(
        top_image, Image.new("RGB", top_image.size, "white")
    ).getbbox()
    left, _, width, _ = slide_room_frame(items[0])
    assert abs(bounds[0] - (left - max(0, left - 24))) <= 1
    assert abs(bounds[2] - bounds[0] - width) <= 1
    html = render_project_document_html(project, items, "sketch", is_pdf=True)
    from weasyprint import HTML

    rendered = HTML(string=html).render()
    images = [
        box
        for page in rendered.pages
        for box in page._page_box.descendants()
        if box.element is not None and box.element.tag == "img"
    ]
    for box, diagram in zip(images, diagrams):
        image = Image.open(BytesIO(diagram["png"]))
        assert box.width / box.height == pytest.approx(
            image.width / image.height, abs=1e-6
        )
    assert html.count("Проектное примечание &lt;контроль&gt;") == 1
    pdf = PdfReader(BytesIO(generate_pdf(html)))
    text = "\n".join(p.extract_text() for p in pdf.pages)
    assert "Проектное примечание" in text and "Сохранить вторую строку." in text
    word = Document(BytesIO(_build_sketch_docx(context)))
    assert note in "\n".join(p.text for p in word.paragraphs)
    assert word.inline_shapes[0].width == word.inline_shapes[1].width
