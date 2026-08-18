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
    MarginOverrideNotRequired,
    QuoteExportBlocked,
    approve_margin_override,
    decimal_value,
    decimal_text,
    get_or_create_quote_state,
    invalidate_margin_override,
    money_text,
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
    if current_user.role == "dealer" and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    return project


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
    services_payload = json.dumps(
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
    discounts_payload = json.dumps(
        [
            {
                "id": rule.id.strip(),
                "name": rule.name.strip() or "Скидка",
                "scope": rule.scope,
                "mode": rule.mode,
                "value": decimal_text(rule.value),
            }
            for rule in data.discounts
            if rule.value > 0
        ],
        ensure_ascii=False,
    )
    services_changed = state.services_payload != services_payload
    discounts_changed = state.discounts_payload != discounts_payload
    config_changed = any(
        (
            state.validity_days != data.validity_days,
            state.manufacturing_term != data.manufacturing_term.strip(),
            state.payment_terms != data.payment_terms.strip(),
            services_changed,
            discounts_changed,
        )
    )
    if config_changed:
        state.validity_days = data.validity_days
        state.manufacturing_term = data.manufacturing_term.strip()
        state.payment_terms = data.payment_terms.strip()
        state.services_payload = services_payload
        state.discounts_payload = discounts_payload
        if services_changed or discounts_changed:
            invalidate_margin_override(state)
        state.source_signature = ""
        state.updated_at = datetime.utcnow()
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
    margin_comment_supplied = "margin_override_comment" in data.model_fields_set
    if margin_comment_supplied and price_manager.role not in ADMIN_ROLES:
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
    evaluation_at = datetime.utcnow()
    now = evaluation_at.isoformat()
    try:
        current_rows = json.loads(state.overrides_payload or "[]")
    except (TypeError, json.JSONDecodeError):
        current_rows = []
    current_overrides = sorted(
        (
            str(row.get("sku") or "").strip(),
            money_text(decimal_value(row.get("cost"))),
            str(row.get("comment") or "").strip(),
        )
        for row in current_rows
        if isinstance(row, dict) and str(row.get("sku") or "").strip()
    )
    next_overrides = sorted(
        (
            override.sku.strip(),
            money_text(override.cost),
            override.comment.strip(),
        )
        for override in data.overrides
    )
    overrides_changed = current_overrides != next_overrides
    if overrides_changed:
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
        invalidate_margin_override(state)
        state.source_signature = ""
        state.updated_at = datetime.utcnow()
    if margin_comment_supplied:
        comment = str(data.margin_override_comment or "").strip()
        if comment:
            try:
                approve_margin_override(
                    db,
                    project,
                    state,
                    price_manager,
                    comment,
                    at=evaluation_at,
                )
            except MarginOverrideNotRequired as exc:
                db.rollback()
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            had_approval = bool(
                state.margin_override_comment
                or state.margin_override_context_signature
                or state.margin_override_target_revision is not None
                or state.margin_override_approved_by is not None
                or state.margin_override_approved_at is not None
            )
            invalidate_margin_override(state, clear_comment=True)
            if had_approval:
                state.source_signature = ""
                state.updated_at = datetime.utcnow()
    payload = public_quote(db, project, at=evaluation_at)
    db.commit()
    return payload


@router.post("/{project_id}/quote/refresh")
def refresh_quote(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
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
