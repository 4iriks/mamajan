"""Безопасный публичный API состояния коммерческого предложения проекта."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_price_manager
from database import get_db
from engine.quote_pricing import (
    MANUAL_SERVICE_UNITS,
    QuoteExportBlocked,
    decimal_text,
    get_or_create_quote_state,
    public_quote,
    refresh_quote_revision,
)


router = APIRouter(prefix="/api/projects", tags=["quotes"])
ADMIN_ROLES = {"admin", "superadmin"}


def _project_or_404(
    project_id: int, db: Session, current_user: models.User
) -> models.Project:
    project = db.query(models.Project).filter_by(id=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role not in ADMIN_ROLES and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    return project


def _require_quote_manager(current_user: models.User) -> None:
    if current_user.role == "dealer":
        raise HTTPException(
            status_code=403,
            detail="Дилер не может изменять условия коммерческого предложения",
        )


@router.get("/{project_id}/quote")
def get_public_quote(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    payload = public_quote(db, project)
    db.commit()
    return payload


@router.put("/{project_id}/quote/config")
def update_quote_config(
    project_id: int,
    data: schemas.QuoteConfigUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    _require_quote_manager(current_user)
    invalid_services = [
        service
        for service in data.services
        if not service.name.strip() or service.unit.strip() not in MANUAL_SERVICE_UNITS
    ]
    if invalid_services:
        raise HTTPException(
            status_code=400,
            detail="Укажите название и поддерживаемую единицу для каждой услуги",
        )
    state = get_or_create_quote_state(db, project)
    state.vat_mode = data.vat_mode
    state.vat_rate = data.vat_rate
    state.validity_days = data.validity_days
    state.manufacturing_term = data.manufacturing_term.strip()
    state.payment_terms = data.payment_terms.strip()
    state.services_payload = json.dumps(
        [
            {
                "id": service.id,
                "name": service.name.strip(),
                "quantity": decimal_text(service.quantity),
                "unit": service.unit.strip(),
                "base_cost": decimal_text(service.base_cost),
            }
            for service in data.services
        ],
        ensure_ascii=False,
    )
    state.source_signature = ""
    state.updated_at = datetime.utcnow()
    db.commit()
    payload = public_quote(db, project)
    db.commit()
    return payload


@router.put("/{project_id}/quote/overrides")
def update_quote_overrides(
    project_id: int,
    data: schemas.QuoteOverridesUpdate,
    db: Session = Depends(get_db),
    price_manager: models.User = Depends(require_price_manager),
):
    project = _project_or_404(project_id, db, price_manager)
    if (
        data.margin_override_comment is not None
        and price_manager.role not in ADMIN_ROLES
    ):
        raise HTTPException(
            status_code=403,
            detail="Исключение по минимальной цене может разрешить только администратор",
        )
    if any(
        not override.sku.strip() or not override.comment.strip()
        for override in data.overrides
    ):
        raise HTTPException(
            status_code=400,
            detail="Для каждой разовой цены нужны артикул и обоснование",
        )
    state = get_or_create_quote_state(db, project)
    now = datetime.utcnow().isoformat()
    state.overrides_payload = json.dumps(
        [
            {
                "sku": override.sku.strip(),
                "cost": decimal_text(override.cost),
                "comment": override.comment.strip(),
                "authorized_by": price_manager.id,
                "updated_at": now,
            }
            for override in data.overrides
        ],
        ensure_ascii=False,
    )
    if data.margin_override_comment is not None:
        comment = str(data.margin_override_comment).strip()
        state.margin_override_comment = comment or None
    state.source_signature = ""
    state.updated_at = datetime.utcnow()
    db.commit()
    payload = public_quote(db, project)
    db.commit()
    return payload


@router.post("/{project_id}/quote/refresh")
def refresh_quote(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    _require_quote_manager(current_user)
    try:
        payload = refresh_quote_revision(db, project, current_user)
        db.commit()
        return payload
    except QuoteExportBlocked as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Нельзя обновить редакцию: расчёт не прошёл проверку",
                "quote": exc.public_payload,
            },
        ) from exc
