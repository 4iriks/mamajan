"""Безопасный публичный API состояния коммерческого предложения проекта."""

from __future__ import annotations

import json
import hmac
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_price_manager, user_can_manage_prices
from database import get_db
from engine.quote_pricing import (
    MANUAL_SERVICE_UNITS,
    MarginOverrideNotRequired,
    QuoteExportBlocked,
    QuotePricingError,
    _canonical_discounts,
    approve_margin_override,
    current_quote_preview_token,
    decimal_value,
    decimal_text,
    get_or_create_quote_state,
    freeze_quote,
    invalidate_margin_override,
    public_quote,
    quote_revision_list,
    quote_revision_snapshot,
    refresh_quote_revision,
)


router = APIRouter(prefix="/api/projects", tags=["quotes"])
ADMIN_ROLES = {"admin", "superadmin"}


class QuoteRefreshRequest(BaseModel):
    expected_preview_token: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )


def _require_current_preview(
    db: Session,
    project: models.Project,
    data: QuoteRefreshRequest | None,
    evaluation_at: datetime,
) -> None:
    if data is None or data.expected_preview_token is None:
        return  # Backward-compatible callers still use the explicit fix action.
    actual_token = current_quote_preview_token(db, project, at=evaluation_at)
    if not hmac.compare_digest(data.expected_preview_token, actual_token):
        raise HTTPException(
            status_code=409,
            detail="Расчёт изменился после просмотра. Проверьте обновлённую сумму и подтвердите фиксацию ещё раз.",
        )


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


@router.get("/{project_id}/quote/revisions")
def get_quote_revisions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    return quote_revision_list(db, project)


@router.get("/{project_id}/quote/revisions/{revision}")
def get_quote_revision(
    project_id: int,
    revision: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    try:
        return quote_revision_snapshot(db, project, revision)[0]
    except QuotePricingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/quote/freeze")
def fix_quote(
    project_id: int,
    data: QuoteRefreshRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    evaluation_at = datetime.utcnow()
    _require_current_preview(db, project, data, evaluation_at)
    try:
        payload = freeze_quote(db, project, current_user, at=evaluation_at)
        db.commit()
        return payload
    except QuoteExportBlocked as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Исправьте ошибки расчёта перед фиксацией",
                "quote": exc.public_payload,
            },
        ) from exc


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
    previous_services = {
        row.get("id"): row
        for row in json.loads(state.services_payload or "[]")
        if isinstance(row, dict)
    }
    service_rows = []
    for service in data.services:
        previous_cost = previous_services.get(service.id, {}).get("actual_cost")
        if not user_can_manage_prices(current_user):
            if (
                "actual_cost" in service.model_fields_set
                and service.actual_cost is not None
            ):
                raise HTTPException(
                    status_code=403, detail="Нет доступа к себестоимости услуги"
                )
            actual_cost = previous_cost
        else:
            actual_cost = (
                previous_cost
                if "actual_cost" not in service.model_fields_set
                else decimal_text(service.actual_cost)
                if service.actual_cost is not None
                else None
            )
        service_rows.append(
            {
                "id": service.id,
                "name": service.name.strip(),
                "quantity": decimal_text(service.quantity),
                "unit": service.unit.strip(),
                "base_cost": decimal_text(service.sale_price),
                "sale_price": decimal_text(service.sale_price),
                "actual_cost": actual_cost,
            }
        )
    services_payload = json.dumps(
        service_rows,
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
    discounts_payload = json.dumps(
        _canonical_discounts(discounts_payload), ensure_ascii=False
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
            decimal_text(decimal_value(row.get("cost"))),
            str(row.get("comment") or "").strip(),
        )
        for row in current_rows
        if isinstance(row, dict) and str(row.get("sku") or "").strip()
    )
    next_overrides = sorted(
        (
            override.sku.strip(),
            decimal_text(override.cost),
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
    data: QuoteRefreshRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _project_or_404(project_id, db, current_user)
    evaluation_at = datetime.utcnow()
    _require_current_preview(db, project, data, evaluation_at)
    try:
        payload = refresh_quote_revision(db, project, current_user, at=evaluation_at)
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
