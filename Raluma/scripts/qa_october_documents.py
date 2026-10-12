"""Generate synthetic application exports for local October acceptance QA.

No API calls, database writes or production data. Run with backend on PYTHONPATH.
"""
from pathlib import Path
from types import SimpleNamespace
import sys

from schemas import SectionCreate
from engine.cs_calc import calculate_cs, cs_result_namespace
from engine.slide_calc import calculate_slide
from engine.pdf import render_pdf_html, generate_pdf
from engine.project_documents import render_project_document_html
from engine.office_docx import build_project_docx
from engine.office_xlsx import build_project_xlsx
from engine.quote_pricing import _section_snapshot


def section(**kwargs):
    values = dict(name="Секция", system="СЛАЙД", width=3000, height=3000, panels=3, rails=3,
                  profile_left_wall=True, profile_right_wall=True,
                  profile_left_lock_bar=True, profile_right_handle_bar=True,
                  lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018", inter_glass_profile="Алюминиевый RS2061",
                  painting_type="RAL стандарт", ral_color="9005")
    values.update(kwargs)
    return SimpleNamespace(**SectionCreate(**values).model_dump())


directory = Path(sys.argv[1]).resolve()
directory.mkdir(parents=True, exist_ok=True)
only = next((arg.removeprefix("--only=").split(",") for arg in sys.argv if arg.startswith("--only=")), None)
project = SimpleNamespace(number="OCTOBER-QA", invoice_number="00000047", order_number="QA",
                          customer="ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ", production_stages=1, current_stage=1)
base_extra = dict(sku="RS112", name="Профиль-ручка", imageFile="RS112.png", qty=2, size="1000",
                  unit="шт", color="9005", finishName="RAL стандарт", requiresPaint=True, deliveryStage="both")
project.extra_components = [base_extra, {**base_extra, "size": "2000"}, {**base_extra, "qty": 1}]
one = section(name="SLIDE один ряд", profile_right_wall=False, profile_right_handle_bar=False)
two = section(name="SLIDE два ряда", width=4500, panels=6, slide_rows=2, profile_left_wall=False, profile_left_lock_bar=False)
cs = section(name="ЦС 2240×600", system="ЦС", width=2240, height=600, quantity=2,
             cs_config={"version": 2, "vertical": {"count": 2}, "horizontal": {"count": 1}})
shaped = section(name="ЦС скат", system="ЦС", width=3000, height=3000, cs_shape="Многоугольник",
                 cs_config={"version": 2, "vertices": [{"x":0,"y":0},{"x":3000,"y":0},{"x":3000,"y":1800},{"x":1500,"y":3000},{"x":0,"y":3000}],
                            "vertical": {"count": 1}})
sections = [one, two, cs, shaped]
for index, item in enumerate([] if "--quotes-only" in sys.argv or (only and "section" not in only) else sections, 1):
    item.id = index
    item.order = index
    calc = calculate_slide(item) if item.system == "СЛАЙД" else cs_result_namespace(calculate_cs(item))
    (directory / f"section-{index}.pdf").write_bytes(generate_pdf(render_pdf_html(project, item, calc)))

for kind in (() if "--quotes-only" in sys.argv else ("sketch", "glass", "paint", "hardware_order", "delivery")):
    if only and kind not in only:
        continue
    html = render_project_document_html(project, sections, kind, is_pdf=True)
    (directory / f"{kind}.pdf").write_bytes(generate_pdf(html))
    if kind != "delivery":
        (directory / f"{kind}.docx").write_bytes(build_project_docx(project, sections, kind))
    if kind != "sketch":
        (directory / f"{kind}.xlsx").write_bytes(build_project_xlsx(project, sections, kind))

quote = {"lines": [], "quote_date": "09.10.2026", "manager": "Проверка", "total_area_m2": "22.5",
         "revision": 1, "status": "fixed", "vat": {"mode": "none", "rate": "0", "amount": "0"},
         "totals": {"document_grand_total": 246912, "document_before_discount": 246912, "document_discount": 0}}
for item in (one, two):
    quote["lines"].append({"name": item.name, "category": "construction", "quantity": "1", "unit": "изд.",
        "document_unit_final_price": 123456, "document_line_total_before_discount": 123456, "document_line_discount_amount": 0,
        "document_line_total": 123456, "section_details": _section_snapshot(item, calculate_slide(item))})
for kind in ("commercial", "contract_appendix"):
    if only and kind not in only:
        continue
    (directory / f"{kind}.pdf").write_bytes(generate_pdf(render_project_document_html(project, sections, kind, is_pdf=True, quote=quote)))
    (directory / f"{kind}.docx").write_bytes(build_project_docx(project, sections, kind, quote=quote))
print(f"QA exports generated in {directory}")
