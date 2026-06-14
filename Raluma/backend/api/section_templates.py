import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from auth import require_admin
from database import get_db


router = APIRouter(prefix="/api/section-templates", tags=["section-templates"])

VALID_SYSTEMS = {"СЛАЙД", "КНИЖКА", "ЛИФТ", "ЦС", "КОМПЛЕКТАЦИЯ"}
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


def _ensure_system(system: str | None) -> str:
    value = (system or "").strip()
    if value == "ДВЕРЬ":
        value = "КОМПЛЕКТАЦИЯ"
    if value not in VALID_SYSTEMS:
        raise HTTPException(status_code=400, detail="Неизвестный тип секции")
    return value


def _sanitize_template_data(system: str, data: dict[str, Any]) -> dict[str, Any]:
    source = {
        key: value
        for key, value in (data or {}).items()
        if key not in TEMPLATE_OMIT_FIELDS
    }
    source["system"] = system

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

    return {
        "id": template.id,
        "name": template.name,
        "system": template.system,
        "template_data": template_data,
        "sort_order": template.sort_order,
        "created_by": template.created_by,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _count_templates(db: Session, system: str, exclude_id: int | None = None) -> int:
    query = db.query(func.count(models.SectionTemplate.id)).filter(
        models.SectionTemplate.system == system
    )
    if exclude_id is not None:
        query = query.filter(models.SectionTemplate.id != exclude_id)
    return int(query.scalar() or 0)


@router.get("", response_model=list[schemas.SectionTemplateOut])
def list_section_templates(
    system: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.SectionTemplate)
    if system:
        query = query.filter(models.SectionTemplate.system == _ensure_system(system))
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
    system = _ensure_system(data.system)
    if _count_templates(db, system) >= MAX_TEMPLATES_PER_SYSTEM:
        raise HTTPException(status_code=400, detail="Лимит 10 шаблонов для типа секции")

    sort_order = data.sort_order
    if sort_order <= 0:
        sort_order = _count_templates(db, system) + 1

    template = models.SectionTemplate(
        name=data.name.strip() or "Шаблон",
        system=system,
        template_data=json.dumps(
            _sanitize_template_data(system, data.template_data),
            ensure_ascii=False,
        ),
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

    next_system = _ensure_system(data.system or template.system)
    if (
        next_system != template.system
        and _count_templates(db, next_system, template.id) >= MAX_TEMPLATES_PER_SYSTEM
    ):
        raise HTTPException(status_code=400, detail="Лимит 10 шаблонов для типа секции")

    if data.name is not None:
        template.name = data.name.strip() or "Шаблон"
    if data.sort_order is not None:
        template.sort_order = data.sort_order
    if data.system is not None:
        template.system = next_system
    if data.template_data is not None:
        template.template_data = json.dumps(
            _sanitize_template_data(next_system, data.template_data),
            ensure_ascii=False,
        )
    elif data.system is not None:
        try:
            existing_data = json.loads(template.template_data or "{}")
        except json.JSONDecodeError:
            existing_data = {}
        template.template_data = json.dumps(
            _sanitize_template_data(next_system, existing_data),
            ensure_ascii=False,
        )

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
