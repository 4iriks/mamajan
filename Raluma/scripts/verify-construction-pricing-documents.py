"""Export QA documents from a separate seeded database, rolling back quote writes."""
import io
import os
from pathlib import Path
import sys

database, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import models
from database import SessionLocal
from engine.quote_pricing import freeze_quote
from engine.project_documents import render_project_document_html
from engine.office_docx import build_project_docx
from engine.quote_diagrams import render_quote_room_png
from engine.pdf import generate_pdf
from pypdf import PdfReader

with SessionLocal() as db:
    section = db.query(models.Section).filter_by(system='ЦС').order_by(models.Section.id).first()
    project = section.project
    actor = db.query(models.User).filter_by(username='admin').one()
    frozen = freeze_quote(db, project, actor)
    html = render_project_document_html(project, project.sections, 'commercial', is_pdf=True, quote=frozen)
    pdf = generate_pdf(html)
    word = build_project_docx(project, project.sections, 'commercial', quote=frozen)
    text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert 'ЦС' in text and 'рельс.' not in text and 'Ряды' not in text
    assert 'ПРОФИЛЬ' in text.upper() or 'Т40' in text
    (output/'cs-commercial.html').write_text(html, encoding='utf-8')
    (output/'cs-commercial.pdf').write_bytes(pdf)
    (output/'cs-commercial.docx').write_bytes(word)
    (output/'cs-diagram.png').write_bytes(render_quote_room_png(frozen['lines'][0]['section_details']))
    db.rollback()
    print(f'CS exports verified: {len(PdfReader(io.BytesIO(pdf)).pages)} PDF pages, {len(word)} Word bytes')
