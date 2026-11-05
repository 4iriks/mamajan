"""Supply labels must not remove the glass dimensions needed for assembly."""

import io
import zipfile
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest
from openpyxl import load_workbook

from engine.office_docx import build_section_docx
from engine.office_xlsx import build_section_xlsx
from engine.pdf import render_pdf_html, render_preview
from engine.slide_calc import calculate_slide
from schemas import SectionCreate


@pytest.mark.parametrize("slide_rows,panels", [(1, 3), (2, 6)])
@pytest.mark.parametrize("glass_supplied", [True, False])
def test_slide_supply_label_and_glass_dimensions_in_all_formats(
    slide_rows, panels, glass_supplied
):
    project = SimpleNamespace(number="GLASS-LABEL", customer="Тест")
    section = SectionCreate(
        name="Секция 1",
        system="СЛАЙД",
        width=3038,
        height=2520,
        panels=panels,
        rails=3,
        slide_rows=slide_rows,
        quantity=1,
        glass_type="10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ",
        glass_supplied=glass_supplied,
        comments="Нарезка профилей с припуском 50 мм.",
    )
    calc = calculate_slide(section)
    supplied_calc = calculate_slide(section.model_copy(update={"glass_supplied": True}))
    assert calc.glass == supplied_calc.glass
    title = "РАЗМЕРЫ СТЕКОЛ (10ММ)"
    label = section.glass_type if glass_supplied else "БЕЗ СТЕКЛА"
    for render in (render_preview, render_pdf_html):
        html = render(project, section, calc)
        assert f'class="val">{label}</td>' in html
        assert f"<th>{title}</th>" in html
        assert "Промежуточные" in html

    docx = build_section_docx(project, section, calc)
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    text = " ".join(root.itertext())
    assert label in text
    assert title in text
    assert "Промежуточные" in text

    workbook = load_workbook(io.BytesIO(build_section_xlsx(project, section, calc)))
    values = [cell.value for row in workbook.worksheets[0] for cell in row]
    assert label in values
    assert title in values
    assert "Промежуточные" in values
