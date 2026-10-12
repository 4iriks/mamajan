"""Replay invoices 47/49/51 from a read-only backup; never modify the database."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

from engine.cs_calc import calculate_cs, cs_result_namespace
from engine.slide_calc import calculate_slide
from engine.pdf import generate_pdf, render_pdf_html
from engine.project_documents import render_project_document_html
from engine.office_docx import build_project_docx
from engine.office_xlsx import build_project_xlsx
from engine.quote_pricing import _section_snapshot

backup, destination = map(Path, sys.argv[1:3])
db = sqlite3.connect(f"file:{backup.resolve()}?mode=ro", uri=True)
db.row_factory = sqlite3.Row
assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
for invoice in ("00000047", "00000049", "00000051"):
    raw = db.execute("SELECT * FROM projects WHERE invoice_number=?", (invoice,)).fetchone()
    assert raw, invoice
    project = SimpleNamespace(**dict(raw))
    sections = []
    out = destination / invoice
    out.mkdir(parents=True, exist_ok=True)
    for record in db.execute('SELECT * FROM sections WHERE project_id=? ORDER BY "order",id', (project.id,)):
        data = dict(record)
        if data.get("cs_config"):
            data["cs_config"] = json.loads(data["cs_config"])
        s = SimpleNamespace(**data)
        sections.append(s)
        calc = cs_result_namespace(calculate_cs(s)) if s.system == "ЦС" else calculate_slide(s)
        (out / f"section-{s.id}.pdf").write_bytes(generate_pdf(render_pdf_html(project, s, calc)))
    for kind in ("sketch", "paint", "delivery", "glass", "hardware_order"):
        (out / f"{kind}.pdf").write_bytes(generate_pdf(render_project_document_html(project, sections, kind, is_pdf=True)))
        if kind != "delivery":
            (out / f"{kind}.docx").write_bytes(build_project_docx(project, sections, kind))
        if kind != "sketch":
            (out / f"{kind}.xlsx").write_bytes(build_project_xlsx(project, sections, kind))
    state = db.execute("SELECT * FROM project_quote_states WHERE project_id=?", (project.id,)).fetchone()
    if state and state["public_payload"] != "{}":
        old = json.loads(state["public_payload"])
        new = deepcopy(old)
        new["document_layout_version"] = 2
        by_id = {s.id: s for s in sections}
        for line in new.get("lines", []):
            details = line.get("section_details") or {}
            section = by_id.get(details.get("section_id"))
            if section and section.system == "СЛАЙД":
                snapshot = _section_snapshot(section, calculate_slide(section))
                details["side_projection_segments"] = snapshot["side_projection_segments"]
                details["side_projection_mm"] = snapshot["side_projection_mm"]
        for label, quote in (("frozen", old), ("new-layout", new)):
            for kind in ("commercial", "contract_appendix"):
                (out / f"{kind}-{label}.pdf").write_bytes(generate_pdf(render_project_document_html(project, sections, kind, is_pdf=True, quote=quote)))
                (out / f"{kind}-{label}.docx").write_bytes(build_project_docx(project, sections, kind, quote=quote))
        assert json.loads(state["public_payload"]) == old
    print(invoice, len(sections), "sections exported", flush=True)
db.close()
