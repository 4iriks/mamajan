"""Effective-dated catalogue prices and opt-in inherited pricing rules.

No calculation writes catalogue state. Monetary source values are immutable
price versions; mutable finish fields remain a compatibility cache only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

import models

PERCENT_FIELDS = (
    "profile_markup_percent", "profile_discount_percent", "waste_markup_percent",
    "construction_markup_percent", "construction_discount_percent",
)
ZERO = Decimal("0")


def normalized_at(at: datetime | None = None) -> datetime:
    value = at or datetime.utcnow()
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def decimal(value: Any) -> Decimal:
    result = Decimal(str(value if value is not None else 0))
    if not result.is_finite():
        raise ValueError("Цена и проценты должны быть конечными числами")
    return result


def text_decimal(value: Any) -> str:
    return format(decimal(value).normalize(), "f")


def price_category(group: str) -> str:
    group = str(group or "").casefold()
    return ("service" if "услуг" in group or "работ" in group else
            "profile" if "проф" in group or "уплотн" in group else "component")


@dataclass(frozen=True)
class ResolvedPrice:
    id: int | None
    catalog_item_id: int
    finish_variant_id: int | None
    cost: Decimal
    profile_markup_percent: Decimal
    profile_discount_percent: Decimal
    waste_markup_percent: Decimal
    construction_markup_percent: Decimal
    construction_discount_percent: Decimal
    category: str
    unit: str
    min_margin_percent: Decimal
    effective_from: datetime
    source: dict[str, Any]


def latest_price_version(item: models.CatalogItem, variant: models.CatalogFinishVariant | None,
                         at: datetime) -> models.CatalogPriceVersion | None:
    variant_id = variant.id if variant is not None else None
    # A price for another finish must never supply cost, category or floor.
    exact = [v for v in item.price_versions if v.finish_variant_id == variant_id
             and normalized_at(v.effective_from) <= at]
    if not exact and variant is not None:
        exact = [v for v in item.price_versions if v.finish_variant_id is None
                 and normalized_at(v.effective_from) <= at]
    return max(exact, key=lambda v: (normalized_at(v.effective_from), v.id or 2**63), default=None)


def binding_mode(db: Session, variant: models.CatalogFinishVariant, at: datetime) -> str:
    history = (db.query(models.CatalogPricingBindingVersion)
               .filter_by(finish_variant_id=variant.id)
               .order_by(models.CatalogPricingBindingVersion.effective_from.desc(),
                         models.CatalogPricingBindingVersion.id.desc()).all())
    current = next((row for row in history if normalized_at(row.effective_from) <= at), None)
    if current is not None:
        return current.mode
    # Before the first explicit switch every variant had individual conditions.
    return "individual" if history else (getattr(variant, "pricing_mode", None) or "individual")


def effective_rule(db: Session, group: str, at: datetime,
                   override: tuple[models.CatalogPricingRule, Any] | None = None) -> tuple[Any, Any] | None:
    rules = db.query(models.CatalogPricingRule).all()
    if override is not None and not any(rule.scope_key == override[0].scope_key for rule in rules):
        rules.append(override[0])
    selected = []
    for rule in rules:
        if rule.scope != "default" and rule.group_name.casefold() != str(group).strip().casefold():
            continue
        versions = list(rule.versions)
        if override is not None and rule.scope_key == override[0].scope_key:
            versions.append(override[1])
        version = max((row for row in versions if normalized_at(row.effective_from) <= at),
                      key=lambda row: (normalized_at(row.effective_from), row.id or 2**63), default=None)
        if version is not None and version.is_active:
            selected.append((rule, version))
    return max(selected, key=lambda pair: pair[0].scope == "group", default=None)


def resolve_effective_price(
    db: Session, item: models.CatalogItem,
    finish_variant: models.CatalogFinishVariant | None = None,
    at: datetime | None = None, *, mode_override: str | None = None,
    rule_override: tuple[models.CatalogPricingRule, Any] | None = None,
) -> ResolvedPrice | None:
    """Resolve an explicit finish's cost and coefficients at one UTC instant.

    No finish argument means a generic item price, never a random finish.
    Compatibility fallback is limited to entries having no version history.
    """
    when = normalized_at(at)
    variant = finish_variant
    if variant is not None and variant.catalog_item_id not in (None, item.id):
        raise ValueError("Исполнение не относится к выбранному артикулу")
    version = latest_price_version(item, variant, when)
    if version is None:
        relevant = [v for v in item.price_versions if v.finish_variant_id in (
            None, variant.id if variant is not None else None)]
        if relevant or variant is None:
            return None
        # Allows unsaved/new legacy rows to be previewed, not future-only prices.
        raw = variant
        cost = decimal(variant.cost if variant.cost is not None else variant.price)
        source_scope = "fallback"
    else:
        raw = version
        cost = decimal(version.cost)
        source_scope = "individual"
    mode = mode_override or (binding_mode(db, variant, when) if variant is not None else "individual")
    source = {"mode": mode, "scope": source_scope, "rule_id": None, "rule_version_id": None,
              "name": "Индивидуальные условия", "label": "Индивидуальные условия"}
    percentages = {field: decimal(getattr(raw, field, 0)) for field in PERCENT_FIELDS}
    if mode == "auto":
        selected = effective_rule(db, item.group, when, rule_override)
        if selected is not None:
            rule, rule_version = selected
            percentages = {field: decimal(getattr(rule_version, field)) for field in PERCENT_FIELDS}
            source = {"mode": mode, "scope": rule.scope, "rule_id": rule.id,
                      "rule_version_id": getattr(rule_version, "id", None), "name": rule_version.name,
                      "label": ("Группа: " + rule.group_name if rule.scope == "group" else "Общее правило")
                               + " · " + rule_version.name}
        else:
            source.update(scope="fallback", label="Правило не задано — сохранённые индивидуальные условия")
    return ResolvedPrice(
        id=version.id if version else None, catalog_item_id=item.id,
        finish_variant_id=variant.id if variant is not None else None, cost=cost,
        **percentages, category=getattr(version, "category", None) or price_category(item.group),
        unit=getattr(version, "unit", None) or item.unit,
        min_margin_percent=decimal(getattr(version, "min_margin_percent", 0)),
        effective_from=normalized_at(version.effective_from) if version else when, source=source,
    )


def price_preview(price: ResolvedPrice | None) -> dict[str, Any] | None:
    if price is None:
        return None
    profile = price.cost * (1 + price.profile_markup_percent / 100) * (1 - price.profile_discount_percent / 100)
    construction = (price.cost * (1 + price.waste_markup_percent / 100)
                    * (1 + price.construction_markup_percent / 100)
                    * (1 - price.construction_discount_percent / 100))
    return {"price_version_id": price.id, "finish_variant_id": price.finish_variant_id,
            "cost": text_decimal(price.cost), **{f: text_decimal(getattr(price, f)) for f in PERCENT_FIELDS},
            "unit": price.unit, "category": price.category,
            "min_margin_percent": text_decimal(price.min_margin_percent),
            "minimum_markup_percent": text_decimal(price.min_margin_percent), "source": price.source,
            "profile": {"final": str(profile.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))},
            "construction": {"final": str(construction.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))}}


def capture_individual_price(db: Session, item: models.CatalogItem, variant: models.CatalogFinishVariant,
                             price: ResolvedPrice, actor_id: int, reason: str, at: datetime) -> None:
    """Leave inheritance without jumping to an older individual price."""
    db.add(models.CatalogPriceVersion(
        catalog_item_id=item.id, finish_variant_id=variant.id, cost=price.cost,
        **{field: getattr(price, field) for field in PERCENT_FIELDS}, category=price.category,
        unit=price.unit, min_margin_percent=price.min_margin_percent, effective_from=at,
        created_at=datetime.utcnow(), created_by=actor_id, reason=reason))
    variant.cost = variant.price = price.cost
    for field in PERCENT_FIELDS:
        setattr(variant, field, getattr(price, field))


def append_binding(db: Session, variant: models.CatalogFinishVariant, mode: str,
                   actor_id: int, reason: str, at: datetime) -> None:
    variant.pricing_mode = mode
    db.add(models.CatalogPricingBindingVersion(finish_variant_id=variant.id, mode=mode,
           effective_from=at, created_at=datetime.utcnow(), created_by=actor_id, reason=reason))


def sync_variant_cache(item: models.CatalogItem, variant: models.CatalogFinishVariant,
                       at: datetime | None = None) -> None:
    """Refresh legacy fields only from the currently effective own version."""
    version = latest_price_version(item, variant, normalized_at(at))
    if version is None:
        return
    variant.cost = variant.price = version.cost
    for field in PERCENT_FIELDS:
        setattr(variant, field, getattr(version, field))
