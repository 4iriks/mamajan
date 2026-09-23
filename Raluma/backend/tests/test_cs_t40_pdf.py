"""Render the application's actual CS PDF exports for regression/optional visual QA."""

import os
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader


@pytest.mark.parametrize(
    "document", ["section", "sketch", "glass", "paint", "hardware_order"]
)
def test_cs_t40_pdf_contains_geometry_and_bom(client, document):
    section = dict(
        system="ЦС",
        name="Секция 1",
        width=1755,
        height=2835,
        quantity=2,
        glass_type="10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        painting_type="RAL стандарт",
        ral_color="9005",
        cs_config={"version": 2, "vertical": {"count": 2, "mode": "equal"}},
    )
    project = {"number": "CS-T40-QA", "customer": "Контрольный пример"}
    url = (
        "/api/projects/local/sections/pdf"
        if document == "section"
        else f"/api/projects/local/documents/{document}/pdf"
    )
    payload = (
        {"project": project, "section": section}
        if document == "section"
        else {"project": project, "sections": [section]}
    )
    response = client.post(url, json=payload)
    assert response.status_code == 200, response.text
    pdf = PdfReader(BytesIO(response.content))
    assert len(pdf.pages) > 0
    text = "\n".join(page.extract_text() for page in pdf.pages)
    assert "CS-T40-QA" in text
    if document in {"section", "sketch", "hardware_order"}:
        assert "CS-PVC-PAD" in "".join(text.split())
        assert "скотч" in text
        assert "12" in text
    if document == "paint":
        assert "Т40К" in text
        assert "CS-PVC-PAD" not in text
    if os.environ.get("CS_QA_DIRECTORY"):
        import fitz

        rendered = fitz.open(stream=response.content, filetype="pdf")
        directory = Path(os.environ["CS_QA_DIRECTORY"]).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        for index, page in enumerate(rendered, 1):
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(
                directory / f"{document}-{index}.png"
            )
