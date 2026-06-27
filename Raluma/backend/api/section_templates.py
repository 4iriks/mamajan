import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from auth import require_admin
from database import get_db
from engine.legacy_values import normalize_section_data_values


router = APIRouter(prefix="/api/section-templates", tags=["section-templates"])

VALID_SYSTEMS = {
    "СЛАЙД 1 ряд",
    "СЛАЙД 2 ряда",
    "КНИЖКА",
    "ЛИФТ",
    "ЦС",
    "КОМПЛЕКТАЦИЯ",
}
MAX_TEMPLATES_PER_SYSTEM = 10
TEMPLATE_OMIT_FIELDS = {
    "id",
    "project_id",
    "order",
    "name",
    "created_at",
    "updated_at",
    "created_by",
    "document_overrides",
}


def _slide_template_system_from_data(data: dict[str, Any]) -> str:
    try:
        slide_rows = int((data or {}).get("slide_rows") or 1)
    except (TypeError, ValueError):
        slide_rows = 1
    return "СЛАЙД 2 ряда" if slide_rows == 2 else "СЛАЙД 1 ряд"


def _ensure_system(system: str | None, data: dict[str, Any] | None = None) -> str:
    value = (system or "").strip()
    if value == "ДВЕРЬ":
        value = "КОМПЛЕКТАЦИЯ"
    if value == "СЛАЙД":
        value = _slide_template_system_from_data(data or {})
    if value not in VALID_SYSTEMS:
        raise HTTPException(status_code=400, detail="Неизвестный тип секции")
    return value


def _section_system(template_system: str) -> str:
    return "СЛАЙД" if template_system.startswith("СЛАЙД ") else template_system


def _slide_rows_for_template_system(template_system: str) -> int | None:
    if template_system == "СЛАЙД 1 ряд":
        return 1
    if template_system == "СЛАЙД 2 ряда":
        return 2
    return None


def _normalize_template_system(system: str, template_data: dict[str, Any]) -> str:
    if system == "СЛАЙД":
        return _slide_template_system_from_data(template_data)
    return _ensure_system(system, template_data)


def _sanitize_template_data(template_system: str, data: dict[str, Any]) -> dict[str, Any]:
    normalized_data = normalize_section_data_values(data or {})
    source = {
        key: value
        for key, value in normalized_data.items()
        if key not in TEMPLATE_OMIT_FIELDS
    }
    source["system"] = _section_system(template_system)
    slide_rows = _slide_rows_for_template_system(template_system)
    if slide_rows is not None:
        source["slide_rows"] = slide_rows

    try:
        validated = schemas.SectionCreate(
            name="Шаблон",
            order=0,
            document_overrides="{}",
            **source,
        ).model_dump()
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="Некорректные параметры секции"
        ) from exc

    return {
        key: value
        for key, value in validated.items()
        if key not in TEMPLATE_OMIT_FIELDS
    }


def _template_to_dict(template: models.SectionTemplate) -> dict[str, Any]:
    try:
        template_data = json.loads(template.template_data or "{}")
    except json.JSONDecodeError:
        template_data = {}
    template_data = normalize_section_data_values(template_data)
    system = _normalize_template_system(template.system, template_data)

    return {
        "id": template.id,
        "name": template.name,
        "system": system,
        "template_data": template_data,
        "sort_order": template.sort_order,
        "created_by": template.created_by,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _count_templates(
    db: Session,
    system: str,
    exclude_id: int | None = None,
) -> int:
    query = db.query(models.SectionTemplate)
    if exclude_id is not None:
        query = query.filter(models.SectionTemplate.id != exclude_id)

    count = 0
    for template in query.all():
        try:
            existing_data = json.loads(template.template_data or "{}")
        except json.JSONDecodeError:
            existing_data = {}
        existing_data = normalize_section_data_values(existing_data)
        if _normalize_template_system(template.system, existing_data) == system:
            count += 1
    return count


@router.get("", response_model=list[schemas.SectionTemplateOut])
def list_section_templates(
    system: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.SectionTemplate)
    if system:
        target_system = _ensure_system(system)
        templates = query.order_by(
            models.SectionTemplate.system,
            models.SectionTemplate.sort_order,
            models.SectionTemplate.id,
        ).all()
        rows = [_template_to_dict(template) for template in templates]
        return [row for row in rows if row["system"] == target_system]
    templates = query.order_by(
        models.SectionTemplate.system,
        models.SectionTemplate.sort_order,
        models.SectionTemplate.id,
    ).all()
    return [_template_to_dict(template) for template in templates]


@router.post("", response_model=schemas.SectionTemplateOut, status_code=201)
def create_section_template(
    data: schemas.SectionTemplateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    system = _ensure_system(data.system, data.template_data)
    template_data = _sanitize_template_data(system, data.template_data)
    if _count_templates(db, system) >= MAX_TEMPLATES_PER_SYSTEM:
        raise HTTPException(status_code=400, detail="Лимит 10 шаблонов для типа секции")

    sort_order = data.sort_order
    if sort_order <= 0:
        sort_order = _count_templates(db, system) + 1

    template = models.SectionTemplate(
        name=data.name.strip() or "Шаблон",
        system=system,
        template_data=json.dumps(template_data, ensure_ascii=False),
        sort_order=sort_order,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_dict(template)


@router.patch("/{template_id}", response_model=schemas.SectionTemplateOut)
def update_section_template(
    template_id: int,
    data: schemas.SectionTemplateUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    template = (
        db.query(models.SectionTemplate)
        .filter(models.SectionTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    try:
        existing_data = json.loads(template.template_data or "{}")
    except json.JSONDecodeError:
        existing_data = {}
    existing_data = normalize_section_data_values(existing_data)
    next_system = _ensure_system(
        data.system or _normalize_template_system(template.system, existing_data),
        data.template_data or existing_data,
    )
    next_template_data = (
        _sanitize_template_data(next_system, data.template_data)
        if data.template_data is not None
        else _sanitize_template_data(next_system, existing_data)
    )
    if _count_templates(db, next_system, template.id) >= MAX_TEMPLATES_PER_SYSTEM:
        raise HTTPException(status_code=400, detail="Лимит 10 шаблонов для типа секции")

    if data.name is not None:
        template.name = data.name.strip() or "Шаблон"
    if data.sort_order is not None:
        template.sort_order = data.sort_order
    if data.system is not None:
        template.system = next_system
    if data.template_data is not None:
        template.template_data = json.dumps(next_template_data, ensure_ascii=False)
    elif data.system is not None:
        template.template_data = json.dumps(next_template_data, ensure_ascii=False)

    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    return _template_to_dict(template)


@router.delete("/{template_id}", status_code=204)
def delete_section_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    template = (
        db.query(models.SectionTemplate)
        .filter(models.SectionTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    db.delete(template)
    db.commit()
