"""Versioned construction settings. Reads and draft calculations never write."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

import models
from engine.pricing_rules import (
    PERCENT_FIELDS,
    decimal,
    normalized_at,
    resolve_effective_price,
    text_decimal,
)

SYSTEMS = {"SLIDE_1": "Слайд 1 ряд", "SLIDE_2": "Слайд 2 ряда", "CS": "ЦС"}
MARKER = "independent_construction_pricing_v1"
UNFILLED_CS_SKUS = {"Т40Т", "Т40К", "CS-PVC-PAD", "CS-JOINT-TAPE"}
FIELDS = ("waste_percent", "markup_percent", "discount_percent")
CENT = Decimal("0.01")


def money(value: Any) -> Decimal:
    return decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def system_code(section: object) -> str | None:
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "СЛАЙД":
        return (
            "SLIDE_2" if int(getattr(section, "slide_rows", 1) or 1) == 2 else "SLIDE_1"
        )
    return "CS" if system == "ЦС" else None


def component_key(item_id: int, finish_id: int | None) -> str:
    return f"{item_id}:{finish_id or 0}"


def resolve_cs_kit(db: Session, section: object):
    kit_id = getattr(section, "cs_system_id", None)
    kit = (
        db.get(models.CsSystem, kit_id)
        if kit_id is not None
        else db.query(models.CsSystem)
        .filter_by(code="CS_CLAMP", is_active=True)
        .first()
    )
    if kit is None or not kit.is_active:
        raise ValueError(
            "Выбранная система ЦС недоступна. Выберите действующий состав ЦС."
        )
    if not kit.outer_profile or not kit.cover_profile or not kit.glass_pad:
        raise ValueError(
            "Заполните состав системы ЦС: зажимной профиль, крышка и подкладка"
        )
    return kit


def applicable_systems(item: models.CatalogItem, kits=()) -> set[str]:
    try:
        groups = set(json.loads(item.system_groups or "[]")) & SYSTEMS.keys()
    except (ValueError, TypeError):
        groups = set()
    if str(item.sku).startswith(("GLASS:", "GLASS|")):
        groups.update(SYSTEMS)
    if item.sku in UNFILLED_CS_SKUS:
        groups.add("CS")
    for kit in kits:
        if item.id in (
            kit.outer_profile_item_id,
            kit.cover_profile_item_id,
            kit.bubble_seal_item_id,
            kit.glass_pad_item_id,
        ):
            groups.add("CS")
    return groups


def current_components(
    db: Session, code: str, at: datetime | None = None
) -> dict[str, Any]:
    when = normalized_at(at)
    rows = (
        db.query(models.SystemComponentPriceVersion)
        .filter_by(system_code=code)
        .filter(models.SystemComponentPriceVersion.effective_from <= when)
        .order_by(
            models.SystemComponentPriceVersion.effective_from,
            models.SystemComponentPriceVersion.id,
        )
        .all()
    )
    return {
        component_key(row.catalog_item_id, row.finish_variant_id): row for row in rows
    }


def current_global(db: Session, code: str, at: datetime | None = None):
    return (
        db.query(models.SystemPricingVersion)
        .filter_by(system_code=code)
        .filter(models.SystemPricingVersion.effective_from <= normalized_at(at))
        .order_by(
            models.SystemPricingVersion.effective_from.desc(),
            models.SystemPricingVersion.id.desc(),
        )
        .first()
    )


def settings_values(row: Any) -> dict[str, str] | None:
    if row is None:
        return None
    return {
        field: text_decimal(
            row[field] if isinstance(row, dict) else getattr(row, field)
        )
        for field in FIELDS
    }


def unit_stages(
    cost: Any, settings: dict | None, cost_is_set: bool = True
) -> dict | None:
    if settings is None or cost is None or not cost_is_set:
        return None
    after_waste = decimal(cost) * (1 + decimal(settings["waste_percent"]) / 100)
    after_markup = after_waste * (1 + decimal(settings["markup_percent"]) / 100)
    final = after_markup * (1 - decimal(settings["discount_percent"]) / 100)
    return {
        "after_waste": str(money(after_waste)),
        "after_markup": str(money(after_markup)),
        "final": str(money(final)),
    }


def configuration(db: Session, code: str, at: datetime | None = None) -> dict:
    when = normalized_at(at)
    current = current_components(db, code, when)
    kits = db.query(models.CsSystem).all()
    items = (
        db.query(models.CatalogItem)
        .filter_by(is_active=True)
        .options(
            selectinload(models.CatalogItem.finish_variants),
            selectinload(models.CatalogItem.price_versions),
        )
        .all()
    )
    # Include actual BOM users as well as catalogue membership. Old imports did
    # not always populate system_groups, notably for glass and accessories.
    used_skus = set()
    from engine.quote_pricing import construction_requirements

    for section in db.query(models.Section).all():
        if system_code(section) != code:
            continue
        try:
            _, requirements = construction_requirements(db, section)
            used_skus.update(row["sku"] for row in requirements)
        except ValueError:
            continue
    rows = []
    for item in items:
        if code not in applicable_systems(item, kits) and item.sku not in used_skus:
            continue
        for finish in [v for v in item.finish_variants if v.is_active] or [None]:
            key = component_key(item.id, finish.id if finish else None)
            price = resolve_effective_price(db, item, finish, when)
            setting = current.get(key)
            values = settings_values(setting)
            rows.append(
                {
                    "key": key,
                    "catalog_item_id": item.id,
                    "finish_variant_id": finish.id if finish else None,
                    "sku": item.sku,
                    "name": item.name,
                    "group": item.group,
                    "finish": finish.name if finish else "Без исполнения",
                    "finish_code": finish.code if finish else "BASE",
                    "unit": item.unit,
                    "cost": str(money(price.cost)) if price else None,
                    "cost_is_set": bool(price and price.cost_is_set),
                    "cost_version_id": price.id if price else None,
                    "minimum_markup_percent": text_decimal(price.min_margin_percent)
                    if price
                    else "0",
                    "version_id": setting.id if setting else None,
                    "configured": values is not None,
                    "settings": values,
                    "stages": unit_stages(
                        price.cost if price else None,
                        values,
                        bool(price and price.cost_is_set),
                    ),
                }
            )
    rows.sort(key=lambda row: (row["group"], row["sku"], row["finish_variant_id"] or 0))
    scope = db.get(models.SystemPricingScope, code)
    general = current_global(db, code, when)
    general_values = {
        "markup_percent": text_decimal(general.markup_percent if general else 0),
        "discount_percent": text_decimal(general.discount_percent if general else 0),
    }
    kit_state = (
        [
            {
                "id": k.id,
                "active": k.is_active,
                "code": k.code,
                "name": k.name,
                "parts": [
                    k.outer_profile_item_id,
                    k.cover_profile_item_id,
                    k.bubble_seal_item_id,
                    k.glass_pad_item_id,
                ],
            }
            for k in kits
        ]
        if code == "CS"
        else []
    )
    token = hashlib.sha256(
        json.dumps(
            [
                scope.revision if scope else 0,
                general.id if general else None,
                general_values,
                rows,
                kit_state,
            ],
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return {
        "code": code,
        "name": SYSTEMS[code],
        "revision": scope.revision if scope else 0,
        "token": token,
        "general": general_values,
        "components": rows,
    }


def migrate_construction_pricing(db: Session, at: datetime | None = None) -> bool:
    """Materialize old effective prices once, including every future boundary.

    Caller commits the whole migration. Original versions/quote snapshots are
    retained. Resolve ALL snapshots before appending replacement price versions.
    """
    db.execute(
        text("CREATE TABLE IF NOT EXISTS migration_markers (name TEXT PRIMARY KEY)")
    )
    if db.execute(
        text("SELECT 1 FROM migration_markers WHERE name=:name"), {"name": MARKER}
    ).first():
        return False
    when = normalized_at(at)
    actor = (
        db.query(models.User)
        .filter(models.User.role.in_(("admin", "superadmin")))
        .order_by(models.User.id)
        .first()
    )
    if actor is None:
        raise ValueError("Для переноса цен необходим администратор")
    tape = db.query(models.CatalogItem).filter_by(sku="CS-JOINT-TAPE").first()
    if tape is None:
        tape = models.CatalogItem(
            sku="CS-JOINT-TAPE",
            name="Двухсторонний скотч для соединения стёкол",
            group="Расходники",
            system="ЦС",
            system_groups='["CS"]',
            unit="м",
            purchase_price=0,
            paint_mode="Не красится",
            is_active=True,
        )
        variant = models.CatalogFinishVariant(
            code="COLORLESS",
            name="Без цвета",
            cost=0,
            price=0,
            cost_is_set=False,
            is_active=True,
        )
        tape.finish_variants.append(variant)
        db.add(tape)
        db.flush()
        tape.price_versions.append(
            models.CatalogPriceVersion(
                finish_variant_id=variant.id,
                cost=0,
                cost_is_set=False,
                category="component",
                unit="м",
                effective_from=when,
                created_by=actor.id,
                reason="Себестоимость скотча не заполнена",
            )
        )
        db.flush()
    items = db.query(models.CatalogItem).all()
    kits = db.query(models.CsSystem).all()
    for item in items:
        if item.sku in UNFILLED_CS_SKUS:
            for version in item.price_versions:
                if decimal(version.cost) == 0:
                    version.cost_is_set = False
            for variant in item.finish_variants:
                if decimal(variant.cost) == 0:
                    variant.cost_is_set = False
    db.flush()
    future = {
        normalized_at(v.effective_from)
        for cls in (
            models.CatalogPriceVersion,
            models.CatalogPricingRuleVersion,
            models.CatalogPricingBindingVersion,
        )
        for v in db.query(cls).all()
        if normalized_at(v.effective_from) > when
    }
    boundaries = [when, *sorted(future)]
    observed: dict[str, set[str]] = {}
    from engine.quote_pricing import construction_requirements

    for section in db.query(models.Section).all():
        code = system_code(section)
        if not code:
            continue
        try:
            _, requirements = construction_requirements(db, section)
            for required in requirements:
                observed.setdefault(required["sku"], set()).add(code)
        except ValueError:
            continue
    snapshots = []
    for item in items:
        groups = applicable_systems(item, kits) | observed.get(item.sku, set())
        variants = list(item.finish_variants)
        # Preserve generic prices too, including exact generic fallback semantics.
        if (
            any(v.finish_variant_id is None for v in item.price_versions)
            or not variants
        ):
            variants.append(None)
        for variant in variants:
            previous = None
            for boundary in boundaries:
                price = resolve_effective_price(
                    db, item, variant, boundary, use_legacy_rules=True
                )
                if price is None:
                    continue
                signature = (
                    price.cost,
                    price.cost_is_set,
                    *(getattr(price, f) for f in PERCENT_FIELDS),
                    price.category,
                    price.unit,
                    price.min_margin_percent,
                )
                # Explicit future own versions must be shadowed even if the old
                # rule produced the same effective value on both sides.
                own_boundary = any(
                    normalized_at(v.effective_from) == boundary
                    for v in item.price_versions
                    if v.finish_variant_id in (None, variant.id if variant else None)
                )
                if signature != previous or own_boundary:
                    snapshots.append((item, variant, groups, boundary, price))
                previous = signature
    for code in SYSTEMS:
        db.add(models.SystemPricingScope(code=code, revision=1))
        db.add(
            models.SystemPricingVersion(
                system_code=code,
                markup_percent=0,
                discount_percent=0,
                effective_from=when,
                created_by=actor.id,
                reason="Перенос цен: общие условия системы 0%",
            )
        )
    db.flush()
    for item, variant, groups, boundary, price in snapshots:
        item.price_versions.append(
            models.CatalogPriceVersion(
                finish_variant_id=variant.id if variant else None,
                cost=price.cost,
                cost_is_set=price.cost_is_set,
                **{f: getattr(price, f) for f in PERCENT_FIELDS},
                category=price.category,
                unit=price.unit,
                min_margin_percent=price.min_margin_percent,
                effective_from=boundary,
                created_by=actor.id,
                reason="Перенос действующей цены без наследования правил",
            )
        )
        for code in groups:
            db.add(
                models.SystemComponentPriceVersion(
                    system_code=code,
                    catalog_item_id=item.id,
                    finish_variant_id=variant.id if variant else None,
                    waste_percent=price.waste_markup_percent,
                    markup_percent=price.construction_markup_percent,
                    discount_percent=price.construction_discount_percent,
                    effective_from=boundary,
                    created_by=actor.id,
                    reason="Перенос действующих условий конструкции",
                )
            )
        if variant is not None and boundary == when:
            variant.pricing_mode = "individual"
            variant.cost = variant.price = price.cost
            variant.cost_is_set = price.cost_is_set
            for field in PERCENT_FIELDS:
                setattr(variant, field, getattr(price, field))
    db.execute(
        text("INSERT INTO migration_markers (name) VALUES (:name)"), {"name": MARKER}
    )
    db.flush()
    return True
