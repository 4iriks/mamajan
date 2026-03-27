"""
Эндпоинты для производственных документов.
GET  /api/projects/{pid}/sections/{sid}/preview  → HTML для iframe
GET  /api/projects/{pid}/sections/{sid}/pdf      → PDF файл
PATCH /api/projects/{pid}/sections/{sid}/overrides → сохранить правки
"""

import io
import json

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import models
from auth import get_current_user, decode_token
from engine.slide_calc import calculate_slide
from engine.pdf import render_preview, render_pdf_html, generate_pdf

router = APIRouter(prefix="/api/projects", tags=["documents"])


def _get_section_or_404(
    project_id: int, section_id: int, db: Session, current_user: models.User
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role == "user" and project.created_by != current_user.id:
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


def _get_user_by_token(token: Optional[str], db: Session) -> models.User:
    """Аутентификация через query-параметр ?token= (для iframe)."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/{project_id}/sections/{section_id}/preview", response_class=HTMLResponse)
def preview_section(
    project_id: int,
    section_id: int,
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    current_user = _get_user_by_token(token, db)
    project, section = _get_section_or_404(project_id, section_id, db, current_user)
    if section.system != "СЛАЙД":
        return HTMLResponse(
            "<p style='padding:20px;font-family:sans-serif'>Производственный лист доступен только для системы СЛАЙД</p>"
        )
    calc = calculate_slide(section)
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
    if section.system != "СЛАЙД":
        raise HTTPException(
            status_code=400, detail="PDF доступен только для системы СЛАЙД"
        )
    calc = calculate_slide(section)
    html = render_pdf_html(project, section, calc)
    pdf_bytes = generate_pdf(html)
    filename = f"ПЛ_{project.number}_сек{section.order}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    existing.update(payload.overrides)
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
