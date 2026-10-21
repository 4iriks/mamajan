"""Private system settings and strictly read-only construction previews."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import update
from sqlalchemy.orm import Session

import models
import schemas
from auth import require_price_manager
from database import get_db
from engine.construction_pricing import (
    SYSTEMS,
    FIELDS,
    configuration,
    component_key,
    system_code,
    unit_stages,
)
from engine.pricing_rules import decimal, text_decimal
from engine.quote_pricing import (
    price_construction_section,
    _section_snapshot,
    _active_price_versions,
)

router = APIRouter(prefix="/api/construction-pricing", tags=["construction-pricing"])


class GeneralSettings(schemas.PricingNumbers):
    markup_percent: Decimal = Field(ge=0, lt=10000, decimal_places=4)
    discount_percent: Decimal = Field(ge=0, le=100, decimal_places=4)


class ComponentSettings(GeneralSettings):
    waste_percent: Decimal = Field(ge=0, lt=10000, decimal_places=4)


class Draft(schemas.PricingNumbers):
    general: GeneralSettings | None = None
    components: dict[str, ComponentSettings] = Field(default_factory=dict)
    section_ids: list[int] = Field(default_factory=list, max_length=100)


class SaveSettings(Draft):
    token: str
    reason: str = Field(
        default="Настройка цен конструкции", min_length=1, max_length=500
    )


def check_code(code: str):
    if code not in SYSTEMS:
        raise HTTPException(404, "Система не найдена")


def overlay(data: Draft, config: dict) -> dict:
    allowed = {row["key"] for row in config["components"]}
    if set(data.components) - allowed:
        raise HTTPException(
            422, "Позиция или исполнение больше не относится к выбранной системе"
        )
    return {
        "general": data.general.model_dump(mode="json") if data.general else {},
        "components": {
            key: row.model_dump(mode="json") for key, row in data.components.items()
        },
    }


@router.get("/systems")
def systems(_actor: models.User = Depends(require_price_manager)):
    return [{"code": code, "name": name} for code, name in SYSTEMS.items()]


@router.get("/systems/{code}")
def load(
    code: str,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_price_manager),
):
    check_code(code)
    return configuration(db, code)


@router.get("/systems/{code}/samples")
def samples(
    code: str,
    search: str = "",
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_price_manager),
):
    check_code(code)
    # Price managers have the same project visibility as the existing project
    # API. Dealers cannot enter this endpoint or retrieve private sample costs.
    rows = (
        db.query(models.Section)
        .join(models.Project)
        .order_by(models.Project.created_at.desc(), models.Section.order)
        .all()
    )
    result = []
    for section in rows:
        if system_code(section) != code:
            continue
        project = section.project
        label = " · ".join(
            str(v)
            for v in (
                project.number or project.invoice_number or f"Проект {project.id}",
                project.customer,
                section.name,
            )
            if v
        )
        if search.strip().casefold() not in label.casefold():
            continue
        result.append(
            {
                "section_id": section.id,
                "project_id": project.id,
                "label": label,
                "width": section.width,
                "height": section.height,
                "quantity": section.quantity,
                "finish": section.painting_type,
                "system_code": code,
            }
        )
    return result


@router.post("/systems/{code}/preview")
def preview(
    code: str,
    data: Draft,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_price_manager),
):
    check_code(code)
    now = datetime.utcnow()
    config = configuration(db, code, now)
    draft = overlay(data, config)
    rows = []
    for row in config["components"]:
        values = draft["components"].get(row["key"], row["settings"])
        rows.append(
            {
                **row,
                "draft_settings": values,
                "draft_stages": unit_stages(row["cost"], values, row["cost_is_set"]),
            }
        )
    active = _active_price_versions(db, now)
    results = []
    for section_id in dict.fromkeys(data.section_ids):
        section = db.get(models.Section, section_id)
        if section is None or system_code(section) != code:
            results.append(
                {
                    "section_id": section_id,
                    "available": False,
                    "error": "Конструкция удалена или относится к другой системе",
                }
            )
            continue
        try:
            saved = price_construction_section(db, section, at=now, active=active)
            changed = price_construction_section(
                db, section, at=now, active=active, draft=draft
            )

            def summary(value):
                return {
                    "bom": value["bom"],
                    "issues": value["issues"],
                    "stages": value["stages"],
                    "complete": not value["issues"],
                    "total": value["stages"]["total"] if not value["issues"] else None,
                    "minimum_total": value["minimum_total"],
                    "below_minimum": decimal(value["stages"]["total"])
                    < decimal(value["minimum_total"]),
                }

            results.append(
                {
                    "section_id": section_id,
                    "available": True,
                    "section": schemas.SectionOut.model_validate(section).model_dump(
                        mode="json"
                    ),
                    "calculation": jsonable_encoder(changed["calc"]),
                    "snapshot": _section_snapshot(section, changed["calc"]),
                    "saved": summary(saved),
                    "draft": summary(changed),
                }
            )
        except ValueError as exc:
            results.append(
                {"section_id": section_id, "available": False, "error": str(exc)}
            )
    return {
        "token": config["token"],
        "components": rows,
        "samples": results,
        "general": {**config["general"], **draft["general"]},
    }


@router.put("/systems/{code}")
def save(
    code: str,
    data: SaveSettings,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    check_code(code)
    # Acquire the database write lock before reading the revision/cost token.
    # This also serializes a concurrent catalogue cost save with this operation.
    locked = db.execute(
        update(models.SystemPricingScope)
        .where(models.SystemPricingScope.code == code)
        .values(revision=models.SystemPricingScope.revision)
    )
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Настройки системы ещё не перенесены")
    config = configuration(db, code)
    if config["token"] != data.token:
        db.rollback()
        raise HTTPException(
            409, "Цены или настройки изменились. Обновите расчёт; ваш ввод сохранён."
        )
    draft = overlay(data, config)
    now = datetime.utcnow()
    changed = False
    current = {row["key"]: row for row in config["components"]}
    for key, values in draft["components"].items():
        row = current[key]
        if row["settings"] and all(
            decimal(values[f]) == decimal(row["settings"][f]) for f in FIELDS
        ):
            continue
        db.add(
            models.SystemComponentPriceVersion(
                system_code=code,
                catalog_item_id=row["catalog_item_id"],
                finish_variant_id=row["finish_variant_id"],
                **values,
                effective_from=now,
                created_by=actor.id,
                reason=data.reason,
            )
        )
        changed = True
    if data.general and any(
        decimal(draft["general"][f]) != decimal(config["general"][f])
        for f in draft["general"]
    ):
        db.add(
            models.SystemPricingVersion(
                system_code=code,
                **draft["general"],
                effective_from=now,
                created_by=actor.id,
                reason=data.reason,
            )
        )
        changed = True
    if changed:
        db.execute(
            update(models.SystemPricingScope)
            .where(models.SystemPricingScope.code == code)
            .values(revision=models.SystemPricingScope.revision + 1)
        )
    db.commit()
    return configuration(db, code)


@router.get("/systems/{code}/history")
def history(
    code: str,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(require_price_manager),
):
    check_code(code)
    now = datetime.utcnow()
    result = []
    for cls in (models.SystemPricingVersion, models.SystemComponentPriceVersion):
        for row in (
            db.query(cls)
            .filter_by(system_code=code)
            .order_by(cls.effective_from.desc(), cls.id.desc())
            .all()
        ):
            item_id = getattr(row, "catalog_item_id", None)
            item = db.get(models.CatalogItem, item_id) if item_id else None
            finish_id = getattr(row, "finish_variant_id", None)
            finish = (
                db.get(models.CatalogFinishVariant, finish_id) if finish_id else None
            )
            result.append(
                {
                    "id": row.id,
                    "kind": "component" if item_id else "system",
                    "component_key": component_key(item_id, finish_id)
                    if item_id
                    else None,
                    "label": f"{item.sku} · {finish.name if finish else 'Базовая цена'}"
                    if item
                    else "Общее для системы",
                    "effective_from": row.effective_from.isoformat() + "Z",
                    "scheduled": row.effective_from > now,
                    "created_by": row.created_by,
                    "reason": row.reason,
                    "settings": {
                        f: text_decimal(getattr(row, f))
                        for f in FIELDS
                        if hasattr(row, f)
                    },
                }
            )
    return sorted(
        result, key=lambda row: (row["effective_from"], row["id"]), reverse=True
    )
