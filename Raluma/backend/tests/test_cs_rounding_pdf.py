"""Actual export pipeline; optional artifacts for visual regression review."""

import os
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader


@pytest.mark.parametrize("radius,mirror", [(10, False), (8, True)])
def test_cs_rounded_sheet_exports(client, radius, mirror):
    vertices = [{"x": 0, "y": 0}, {"x": 2390, "y": 0}, {"x": 2390, "y": 745}]
    if mirror:
        vertices = [{**p, "x": 2390 - p["x"]} for p in vertices]
    section = {
        "system": "ЦС",
        "name": f"Треугольник R{radius}",
        "width": 2390,
        "height": 745,
        "quantity": 1,
        "glass_type": "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
        "cs_config": {
            "version": 2,
            "vertices": vertices,
            "dimensionMode": "clear",
            "triangleCornerRadiusMm": radius,
        },
    }
    body = {
        "project": {"number": "CS-RADIUS", "customer": "Контрольный пример"},
        "section": section,
    }
    pdf = client.post("/api/projects/local/sections/pdf", json=body)
    assert pdf.status_code == 200, pdf.text
    text = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages
    )
    assert f"Скругление R{radius}" in text
    assert "до скругления" in text
    if os.environ.get("CS_ROUNDING_QA_DIR"):
        directory = Path(os.environ["CS_ROUNDING_QA_DIR"]).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"cs-r{radius}.pdf").write_bytes(pdf.content)
        docx = client.post("/api/projects/local/sections/docx", json=body)
        assert docx.status_code == 200, docx.text
        (directory / f"cs-r{radius}.docx").write_bytes(docx.content)
        from engine.cs_calc import calculate_cs, cs_result_namespace
        from engine.office_diagrams import render_cs_front
        from types import SimpleNamespace

        data = SimpleNamespace(**section)
        (directory / f"cs-r{radius}-diagram.png").write_bytes(
            render_cs_front(data, cs_result_namespace(calculate_cs(data)))
        )
