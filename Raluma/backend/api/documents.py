"""
Эндпоинты для производственных документов.
GET  /api/projects/{pid}/sections/{sid}/preview  → HTML для iframe
GET  /api/projects/{pid}/sections/{sid}/pdf      → PDF файл
PATCH /api/projects/{pid}/sections/{sid}/overrides → сохранить правки
"""

import io
import json

from dataclasses import asdict
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user, decode_token
from engine.lift_calc import calculate_lift
from engine.office_common import normalize_filename
from engine.office_docx import build_project_docx, build_section_docx
from engine.office_xlsx import build_project_xlsx, build_section_xlsx
from engine.office_common import drawing_files_for_sections
from engine.slide_calc import calculate_slide
from engine.pdf import append_pdf_drawings, render_preview, render_pdf_html, generate_pdf
from engine.project_documents import DOC_TITLES, render_project_document_html

router = APIRouter(prefix="/api/projects", tags=["documents"])

ADMIN_ROLES = ("admin", "superadmin")
PRODUCTION_SHEET_SYSTEMS = {"СЛАЙД", "ЛИФТ"}
OFFICE_PROJECT_DOCUMENTS = {"glass", "paint", "hardware_order"}
OFFICE_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _calculate_section(section):
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "СЛАЙД":
        return calculate_slide(section)
    if system == "ЛИФТ":
        return calculate_lift(section)
    raise HTTPException(
        status_code=400,
        detail="Производственный лист для этой системы пока не реализован",
    )


def _get_section_or_404(
    project_id: int, section_id: int, db: Session, current_user: models.User
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role not in ADMIN_ROLES and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    section = (
        db.query(models.Section)
        .filter(
            models.Section.id == section_id,
            models.Section.project_id == project_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    return project, section


def _get_project_or_404(project_id: int, db: Session, current_user: models.User):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role not in ADMIN_ROLES and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return project


def _get_user_by_token(token: Optional[str], db: Session) -> models.User:
    """Аутентификация через query-параметр ?token= (для iframe)."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class LocalDocumentPayload(BaseModel):
    project: dict
    section: dict


class LocalProjectDocumentPayload(BaseModel):
    project: dict
    sections: list[dict] = []


def _build_local_document_objects(payload: LocalDocumentPayload):
    project_data = payload.project or {}
    section_data = payload.section or {}

    section_payload = {
        **section_data,
        "name": section_data.get("name") or "Секция 1",
    }
    section_values = schemas.SectionCreate(**section_payload).model_dump()
    section_values["id"] = section_data.get("id") or 0
    section_values["project_id"] = section_data.get("project_id") or 0
    section_values["document_overrides"] = (
        section_values.get("document_overrides") or "{}"
    )
    section_values["extra_components"] = section_values.get("extra_components") or "[]"

    project = SimpleNamespace(
        id=project_data.get("id") or 0,
        number=project_data.get("number") or "Локальный проект",
        customer=project_data.get("customer") or "",
        paint_manual_rows=project_data.get("paint_manual_rows") or "[]",
        glass_status=project_data.get("glass_status") or "",
        delivery_note_data=project_data.get("delivery_note_data") or "{}",
        production_stages=project_data.get("production_stages") or 1,
        current_stage=project_data.get("current_stage") or 1,
    )
    section = SimpleNamespace(**section_values)
    return project, section


def _build_local_project_document_objects(payload: LocalProjectDocumentPayload):
    project_data = payload.project or {}
    project = SimpleNamespace(
        id=project_data.get("id") or 0,
        number=project_data.get("number") or "Локальный проект",
        customer=project_data.get("customer") or "",
        paint_manual_rows=project_data.get("paint_manual_rows") or "[]",
        glass_status=project_data.get("glass_status") or "",
        delivery_note_data=project_data.get("delivery_note_data") or "{}",
        production_stages=project_data.get("production_stages") or 1,
        current_stage=project_data.get("current_stage") or 1,
    )
    sections = []
    for section_data in payload.sections or []:
        section_payload = {
            **section_data,
            "name": section_data.get("name") or f"Секция {len(sections) + 1}",
        }
        section_values = schemas.SectionCreate(**section_payload).model_dump()
        section_values["id"] = section_data.get("id") or len(sections) + 1
        section_values["project_id"] = section_data.get("project_id") or project.id
        section_values["document_overrides"] = (
            section_values.get("document_overrides") or "{}"
        )
        section_values["extra_components"] = section_values.get("extra_components") or "[]"
        sections.append(SimpleNamespace(**section_values))
    return project, sections


def _validate_project_doc_type(doc_type: str) -> str:
    if doc_type not in DOC_TITLES:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc_type


def _validate_office_project_doc_type(doc_type: str) -> str:
    _validate_project_doc_type(doc_type)
    if doc_type not in OFFICE_PROJECT_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Word и Excel доступны для заказа стекла, заявки на покраску "
                "и наряда-заказа на фурнитуру"
            ),
        )
    return doc_type


def _office_response(content: bytes, filename: str, file_format: str):
    from urllib.parse import quote

    encoded = quote(normalize_filename(filename))
    return StreamingResponse(
        io.BytesIO(content),
        media_type=OFFICE_MEDIA_TYPES[file_format],
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _build_section_office(
    project: object,
    section: object,
    file_format: str,
) -> bytes:
    calc = _calculate_section(section)
    if file_format == "docx":
        return build_section_docx(project, section, calc)
    return build_section_xlsx(project, section, calc)


def _build_project_office(
    project: object,
    sections,
    doc_type: str,
    file_format: str,
) -> bytes:
    if file_format == "docx":
        return build_project_docx(project, sections, doc_type)
    return build_project_xlsx(project, sections, doc_type)


@router.post("/local/sections/preview", response_class=HTMLResponse)
def preview_local_section(payload: LocalDocumentPayload):
    project, section = _build_local_document_objects(payload)
    if str(section.system or "").strip().upper() not in PRODUCTION_SHEET_SYSTEMS:
        return HTMLResponse(
            "<p style='padding:20px;font-family:sans-serif'>Производственный лист для этой системы пока не реализован</p>"
        )
    calc = _calculate_section(section)
    html = render_preview(project, section, calc)
    return HTMLResponse(html)


@router.post("/local/sections/calc")
def calculate_local_section(payload: LocalDocumentPayload):
    _, section = _build_local_document_objects(payload)
    return asdict(_calculate_section(section))


@router.post("/local/documents/{doc_type}/preview", response_class=HTMLResponse)
def preview_local_project_document(doc_type: str, payload: LocalProjectDocumentPayload):
    doc_type = _validate_project_doc_type(doc_type)
    project, sections = _build_local_project_document_objects(payload)
    html = render_project_document_html(project, sections, doc_type)
    return HTMLResponse(html)


@router.post("/local/sections/pdf")
def download_local_pdf(payload: LocalDocumentPayload):
    project, section = _build_local_document_objects(payload)
    calc = _calculate_section(section)
    html = render_pdf_html(project, section, calc)
    pdf_bytes = generate_pdf(html)
    pdf_bytes = append_pdf_drawings(pdf_bytes, drawing_files_for_sections([section]))
    filename = f"ПЛ_{project.number}_{section.name}.pdf"
    from urllib.parse import quote

    encoded = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _download_local_section_office(
    payload: LocalDocumentPayload,
    file_format: str,
):
    project, section = _build_local_document_objects(payload)
    content = _build_section_office(project, section, file_format)
    filename = f"ПЛ_{project.number}_{section.name}.{file_format}"
    return _office_response(content, filename, file_format)


@router.post("/local/sections/docx")
def download_local_section_docx(payload: LocalDocumentPayload):
    return _download_local_section_office(payload, "docx")


@router.post("/local/sections/xlsx")
def download_local_section_xlsx(payload: LocalDocumentPayload):
    return _download_local_section_office(payload, "xlsx")


@router.post("/local/documents/{doc_type}/pdf")
def download_local_project_document_pdf(
    doc_type: str,
    payload: LocalProjectDocumentPayload,
):
    doc_type = _validate_project_doc_type(doc_type)
    project, sections = _build_local_project_document_objects(payload)
    html = render_project_document_html(project, sections, doc_type, is_pdf=True)
    pdf_bytes = generate_pdf(html)
    if doc_type == "glass":
        pdf_bytes = append_pdf_drawings(pdf_bytes, drawing_files_for_sections(sections))
    filename = f"{DOC_TITLES[doc_type]}_{project.number}.pdf"
    from urllib.parse import quote

    encoded = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _download_local_project_office(
    doc_type: str,
    payload: LocalProjectDocumentPayload,
    file_format: str,
):
    doc_type = _validate_office_project_doc_type(doc_type)
    project, sections = _build_local_project_document_objects(payload)
    content = _build_project_office(
        project,
        sections,
        doc_type,
        file_format,
    )
    filename = f"{DOC_TITLES[doc_type]}_{project.number}.{file_format}"
    return _office_response(content, filename, file_format)


@router.post("/local/documents/{doc_type}/docx")
def download_local_project_document_docx(
    doc_type: str,
    payload: LocalProjectDocumentPayload,
):
    return _download_local_project_office(doc_type, payload, "docx")


@router.post("/local/documents/{doc_type}/xlsx")
def download_local_project_document_xlsx(
    doc_type: str,
    payload: LocalProjectDocumentPayload,
):
    return _download_local_project_office(doc_type, payload, "xlsx")


@router.get("/{project_id}/documents/{doc_type}/preview", response_class=HTMLResponse)
def preview_project_document(
    project_id: int,
    doc_type: str,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    doc_type = _validate_project_doc_type(doc_type)
    current_user = _get_user_by_token(token, db)
    project = _get_project_or_404(project_id, db, current_user)
    html = render_project_document_html(project, project.sections, doc_type)
    return HTMLResponse(html)


@router.get("/{project_id}/documents/{doc_type}/pdf")
def download_project_document_pdf(
    project_id: int,
    doc_type: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc_type = _validate_project_doc_type(doc_type)
    project = _get_project_or_404(project_id, db, current_user)
    html = render_project_document_html(project, project.sections, doc_type, is_pdf=True)
    pdf_bytes = generate_pdf(html)
    if doc_type == "glass":
        pdf_bytes = append_pdf_drawings(pdf_bytes, drawing_files_for_sections(project.sections))
    filename = f"{DOC_TITLES[doc_type]}_{project.number}.pdf"
    from urllib.parse import quote

    encoded = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _download_project_office(
    project_id: int,
    doc_type: str,
    file_format: str,
    db: Session,
    current_user: models.User,
):
    doc_type = _validate_office_project_doc_type(doc_type)
    project = _get_project_or_404(project_id, db, current_user)
    content = _build_project_office(
        project,
        project.sections,
        doc_type,
        file_format,
    )
    filename = f"{DOC_TITLES[doc_type]}_{project.number}.{file_format}"
    return _office_response(content, filename, file_format)


@router.get("/{project_id}/documents/{doc_type}/docx")
def download_project_document_docx(
    project_id: int,
    doc_type: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _download_project_office(
        project_id,
        doc_type,
        "docx",
        db,
        current_user,
    )


@router.get("/{project_id}/documents/{doc_type}/xlsx")
def download_project_document_xlsx(
    project_id: int,
    doc_type: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _download_project_office(
        project_id,
        doc_type,
        "xlsx",
        db,
        current_user,
    )


@router.get("/{project_id}/sections/{section_id}/preview", response_class=HTMLResponse)
def preview_section(
    project_id: int,
    section_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    current_user = _get_user_by_token(token, db)
    project, section = _get_section_or_404(project_id, section_id, db, current_user)
    if str(section.system or "").strip().upper() not in PRODUCTION_SHEET_SYSTEMS:
        return HTMLResponse(
            "<p style='padding:20px;font-family:sans-serif'>Производственный лист для этой системы пока не реализован</p>"
        )
    calc = _calculate_section(section)
    html = render_preview(project, section, calc)
    return HTMLResponse(html)


@router.get("/{project_id}/sections/{section_id}/pdf")
def download_pdf(
    project_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project, section = _get_section_or_404(project_id, section_id, db, current_user)
    calc = _calculate_section(section)
    html = render_pdf_html(project, section, calc)
    pdf_bytes = generate_pdf(html)
    pdf_bytes = append_pdf_drawings(pdf_bytes, drawing_files_for_sections([section]))
    filename = f"ПЛ_{project.number}_сек{section.order}.pdf"
    from urllib.parse import quote

    encoded = quote(filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _download_section_office(
    project_id: int,
    section_id: int,
    file_format: str,
    db: Session,
    current_user: models.User,
):
    project, section = _get_section_or_404(
        project_id,
        section_id,
        db,
        current_user,
    )
    content = _build_section_office(project, section, file_format)
    section_number = getattr(section, "order", None) or getattr(section, "name", "")
    filename = f"ПЛ_{project.number}_сек{section_number}.{file_format}"
    return _office_response(content, filename, file_format)


@router.get("/{project_id}/sections/{section_id}/docx")
def download_section_docx(
    project_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _download_section_office(
        project_id,
        section_id,
        "docx",
        db,
        current_user,
    )


@router.get("/{project_id}/sections/{section_id}/xlsx")
def download_section_xlsx(
    project_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _download_section_office(
        project_id,
        section_id,
        "xlsx",
        db,
        current_user,
    )


class OverridesPayload(BaseModel):
    overrides: dict


@router.patch("/{project_id}/sections/{section_id}/overrides")
def save_overrides(
    project_id: int,
    section_id: int,
    payload: OverridesPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _, section = _get_section_or_404(project_id, section_id, db, current_user)
    # Мёрджим с существующими overrides
    existing = {}
    try:
        existing = json.loads(section.document_overrides or "{}")
    except Exception:
        pass
    existing.pop("extra_components", None)
    clean_overrides = {
        key: value
        for key, value in payload.overrides.items()
        if key != "extra_components"
    }
    existing.update(clean_overrides)
    section.document_overrides = json.dumps(existing, ensure_ascii=False)
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}/sections/{section_id}/overrides")
def clear_overrides(
    project_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Сбросить все ручные правки — вернуть к расчётным значениям."""
    _, section = _get_section_or_404(project_id, section_id, db, current_user)
    section.document_overrides = "{}"
    db.commit()
    return {"ok": True}
