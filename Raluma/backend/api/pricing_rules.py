"""Administrative, preview-first opt-in pricing inheritance."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

import models
from schemas import PricingNumbers
from auth import require_price_manager
from database import get_db
from engine.pricing_rules import (
    PERCENT_FIELDS, append_binding, binding_mode, capture_individual_price,
    normalized_at, price_preview, resolve_effective_price, text_decimal,
)

router = APIRouter()


class RuleWrite(PricingNumbers):
    name: str = Field(min_length=1, max_length=160)
    scope: Literal["default", "group"]
    group_name: str = Field(default="", max_length=160)
    is_active: bool = True
    profile_markup_percent: Decimal = Field(default=Decimal(0), ge=0)
    profile_discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100)
    waste_markup_percent: Decimal = Field(default=Decimal(0), ge=0)
    construction_markup_percent: Decimal = Field(default=Decimal(0), ge=0)
    construction_discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100)
    effective_from: datetime
    reason: str = Field(min_length=1, max_length=1000)
    rule_id: int | None = None

    @model_validator(mode="after")
    def validate_text(self):
        self.name, self.group_name, self.reason = self.name.strip(), self.group_name.strip(), self.reason.strip()
        if not self.name or not self.reason:
            raise ValueError("Укажите название и причину изменения")
        if self.scope == "group" and not self.group_name:
            raise ValueError("Выберите группу каталога")
        if self.scope == "default":
            self.group_name = ""
        self.effective_from = normalized_at(self.effective_from)
        return self


class BindingWrite(BaseModel):
    finish_variant_ids: list[int] = Field(min_length=1)
    mode: Literal["individual", "auto"]
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_text(self):
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("Укажите причину изменения")
        self.finish_variant_ids = list(dict.fromkeys(self.finish_variant_ids))
        return self


def _scope_key(data: RuleWrite) -> str:
    return "default" if data.scope == "default" else "group:" + data.group_name.casefold()


def _version_dict(row):
    if row is None:
        return None
    return {"id": row.id, "name": row.name, "is_active": row.is_active,
            **{field: text_decimal(getattr(row, field)) for field in PERCENT_FIELDS},
            "effective_from": row.effective_from.isoformat(), "created_at": row.created_at.isoformat(),
            "created_by": row.created_by, "reason": row.reason}


def _rule_dict(rule, at):
    versions = sorted(rule.versions, key=lambda v: (normalized_at(v.effective_from), v.id or 0), reverse=True)
    active = next((v for v in versions if normalized_at(v.effective_from) <= at), None)
    upcoming = min((v for v in versions if normalized_at(v.effective_from) > at),
                   key=lambda v: (normalized_at(v.effective_from), v.id), default=None)
    return {"id": rule.id, "name": active.name if active else upcoming.name if upcoming else "",
            "scope": rule.scope, "group_name": rule.group_name,
            "is_active": bool(active and active.is_active), "active_version": _version_dict(active),
            "next_version": _version_dict(upcoming), "versions": [_version_dict(v) for v in versions]}


def _active_variants(db):
    return (db.query(models.CatalogFinishVariant).join(models.CatalogItem)
            .filter(models.CatalogFinishVariant.is_active == True,  # noqa: E712
                    models.CatalogItem.is_active == True).all())  # noqa: E712


def _row(variant, mode, before, after=None):
    item = variant.catalog_item
    result = {"catalog_item_id": item.id, "finish_variant_id": variant.id, "sku": item.sku,
              "name": item.name, "group_name": item.group, "finish_name": variant.name,
              "mode": mode, "resolved": price_preview(before)}
    if after is not None:
        result.update(before=price_preview(before), after=price_preview(after))
    return result


def _candidate(db, data, rule_id=None):
    rule_id = rule_id if rule_id is not None else data.rule_id
    existing = db.get(models.CatalogPricingRule, rule_id) if rule_id is not None else None
    if rule_id is not None and existing is None:
        raise HTTPException(404, "Правило не найдено")
    if existing is not None and existing.scope_key != _scope_key(data):
        raise HTTPException(400, "Область правила менять нельзя; создайте отдельное правило для группы")
    if existing is None and db.query(models.CatalogPricingRule).filter_by(scope_key=_scope_key(data)).first():
        raise HTTPException(409, "Для этой области уже есть правило; измените его существующую версию")
    rule = models.CatalogPricingRule(id=existing.id if existing else None, scope=data.scope,
                                    scope_key=_scope_key(data), group_name=data.group_name)
    version = models.CatalogPricingRuleVersion(
        name=data.name, is_active=data.is_active, effective_from=data.effective_from,
        **{field: getattr(data, field) for field in PERCENT_FIELDS}, reason=data.reason)
    return existing, rule, version


def _rule_preview(db, data, rule_id=None):
    _, candidate, version = _candidate(db, data, rule_id)
    evaluation_at = max(data.effective_from, normalized_at())
    rows = []
    for variant in _active_variants(db):
        mode = binding_mode(db, variant, evaluation_at)
        if mode != "auto":
            continue
        item = variant.catalog_item
        before = resolve_effective_price(db, item, variant, evaluation_at)
        after = resolve_effective_price(db, item, variant, evaluation_at,
                                        rule_override=(candidate, version))
        if price_preview(before) != price_preview(after):
            rows.append(_row(variant, mode, before, after))
    return {"count": len(rows), "rows": rows, "effective_from": data.effective_from.isoformat(),
            "individual_unchanged": True}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), _: models.User = Depends(require_price_manager)):
    now = normalized_at()
    rules = db.query(models.CatalogPricingRule).order_by(models.CatalogPricingRule.id).all()
    groups = sorted({row[0] for row in db.query(models.CatalogItem.group).distinct().all() if row[0]})
    return {"rules": [_rule_dict(rule, now) for rule in rules], "groups": groups}


@router.post("/rules/preview")
def preview_rule(data: RuleWrite, db: Session = Depends(get_db),
                 _: models.User = Depends(require_price_manager)):
    return _rule_preview(db, data)


def _save_rule(db, data, actor, rule_id=None):
    preview = _rule_preview(db, data, rule_id)
    existing, candidate, version = _candidate(db, data, rule_id)
    rule = existing or candidate
    if existing is None:
        db.add(rule)
        db.flush()
    version.rule_id = rule.id
    version.created_by = actor.id
    version.created_at = datetime.utcnow()
    db.add(version)
    db.commit()
    db.refresh(rule)
    return {**_rule_dict(rule, normalized_at()), "affected_count": preview["count"]}


@router.post("/rules", status_code=201)
def create_rule(data: RuleWrite, db: Session = Depends(get_db),
                actor: models.User = Depends(require_price_manager)):
    return _save_rule(db, data, actor)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, data: RuleWrite, db: Session = Depends(get_db),
                actor: models.User = Depends(require_price_manager)):
    return _save_rule(db, data, actor, rule_id)


@router.get("/rule-bindings")
def list_bindings(db: Session = Depends(get_db), _: models.User = Depends(require_price_manager)):
    now = normalized_at()
    return {"rows": [_row(v, binding_mode(db, v, now),
                          resolve_effective_price(db, v.catalog_item, v, now)) for v in _active_variants(db)]}


def _binding_preview(db, data, now):
    by_id = {v.id: v for v in _active_variants(db)}
    if any(variant_id not in by_id for variant_id in data.finish_variant_ids):
        raise HTTPException(400, "Выбранное исполнение недоступно")
    rows, prepared = [], []
    for variant_id in data.finish_variant_ids:
        variant = by_id[variant_id]
        mode = binding_mode(db, variant, now)
        before = resolve_effective_price(db, variant.catalog_item, variant, now)
        if before is None:
            raise HTTPException(400, f"У {variant.catalog_item.sku} нет действующей цены")
        # Becoming individual freezes the effective coefficients instead of
        # unexpectedly resurrecting coefficients from before inheritance.
        after = before if data.mode == "individual" else resolve_effective_price(
            db, variant.catalog_item, variant, now, mode_override="auto")
        if data.mode == "individual":
            from dataclasses import replace
            after = replace(before, source={"mode": "individual", "scope": "individual",
                "rule_id": None, "rule_version_id": None, "name": "Индивидуальные условия",
                "label": "Индивидуальные условия"})
        rows.append(_row(variant, mode, before, after))
        prepared.append((variant, mode, before))
    return {"count": len(rows), "rows": rows}, prepared


@router.post("/rule-bindings/preview")
def preview_bindings(data: BindingWrite, db: Session = Depends(get_db),
                     _: models.User = Depends(require_price_manager)):
    return _binding_preview(db, data, normalized_at())[0]


@router.post("/rule-bindings/apply")
def apply_bindings(data: BindingWrite, db: Session = Depends(get_db),
                   actor: models.User = Depends(require_price_manager)):
    now = normalized_at()
    preview, prepared = _binding_preview(db, data, now)
    for variant, mode, before in prepared:
        if mode == data.mode:
            continue
        if data.mode == "individual":
            capture_individual_price(db, variant.catalog_item, variant, before, actor.id, data.reason, now)
        append_binding(db, variant, data.mode, actor.id, data.reason, now)
    db.commit()
    return preview
