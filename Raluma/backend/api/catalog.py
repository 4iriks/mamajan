import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, object_session

from auth import require_admin
from database import get_db
from engine.pdf import get_profile_asset_path
from engine.profile_catalog import PROFILE_CATALOG
from engine.pricing_rules import resolve_effective_price
import models
import schemas

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

CATALOG_UPDATED_AT = "2026-06-08"

SYSTEM_GROUPS = {
    "SLIDE_1": "СЛАЙД 1 ряд",
    "SLIDE_2": "СЛАЙД 2 ряда",
    "CS": "ЦС",
}
FINISH_DEFINITIONS = {
    "ANOD_UNPAINTED": ("Анод/неокрас", False),
    "RAL_STANDARD": ("RAL стандарт", True),
    "RAL_MOIRE": ("RAL муар", True),
    "SUBLIMATION": ("Сублимация", True),
    "COLORLESS": ("Без цвета", False),
}


def _is_paintable(paint_mode: str | None) -> bool:
    normalized = " ".join(str(paint_mode or "").strip().casefold().split())
    return (
        "красится" in normalized and "не красится" not in normalized
    ) or "частично" in normalized


def _finish_code(name: str | None, code: str | None = None) -> str:
    explicit = str(code or "").strip().upper()
    if explicit in FINISH_DEFINITIONS:
        return explicit
    if explicit in {"ANOD", "BASE"}:
        return "ANOD_UNPAINTED"
    if explicit == "RAL_NONSTANDARD":
        return "RAL_MOIRE"
    normalized = " ".join(str(name or "").strip().casefold().split())
    if "без цвет" in normalized:
        return "COLORLESS"
    if "сублим" in normalized:
        return "SUBLIMATION"
    if "нестандарт" in normalized or "муар" in normalized:
        return "RAL_MOIRE"
    if "ral" in normalized:
        return "RAL_STANDARD"
    if "анод" in normalized or "неокрас" in normalized or "без окраски" in normalized:
        return "ANOD_UNPAINTED"
    return "COLORLESS"


def _decode_system_groups(raw: str | None, system: str | None = None) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        values = []
    result = [str(value) for value in values if str(value) in SYSTEM_GROUPS]
    if result:
        return list(dict.fromkeys(result))
    if "СЛАЙД" in str(system or "").upper():
        return ["SLIDE_1", "SLIDE_2"]
    return []


def _variant_requires_paint(name: str, paint_mode: str) -> bool:
    normalized = name.casefold()
    mode = paint_mode.casefold()
    if (
        "анод" in normalized
        or "неокрас" in normalized
        or "без цвета" in normalized
        or "без окраски" in normalized
    ):
        return False
    return (
        "ral" in normalized
        or "окрас" in normalized
        or "сублим" in normalized
        or (("красится" in mode or "частично" in mode) and "не красится" not in mode)
    )


def _variant_to_dict(
    variant: models.CatalogFinishVariant, *, include_cost: bool = False
) -> dict:
    result = {
        "id": variant.id,
        "code": _finish_code(variant.name, getattr(variant, "code", None)),
        "name": variant.name,
        "requiresPaint": bool(variant.requires_paint),
        "isActive": bool(variant.is_active),
    }
    if include_cost:
        db = object_session(variant)
        resolved = resolve_effective_price(db, variant.catalog_item, variant) if db else None
        actual = resolved or variant
        cost = actual.cost if actual.cost is not None else variant.price
        result.update(
            {
                "cost": f"{cost:.2f}",
                "costIsSet": getattr(actual, "cost_is_set", True) is not False,
                "profileMarkupPercent": float(actual.profile_markup_percent or 0),
                "profileDiscountPercent": float(actual.profile_discount_percent or 0),
                "wasteMarkupPercent": float(actual.waste_markup_percent or 0),
                "constructionMarkupPercent": float(
                    actual.construction_markup_percent or 0
                ),
                "constructionDiscountPercent": float(
                    actual.construction_discount_percent or 0
                ),
                "pricingMode": resolved.source["mode"] if resolved else "individual",
                "pricingSource": resolved.source if resolved else None,
                "minimumMarkupPercent": float(resolved.min_margin_percent) if resolved else 0,
                "priceAvailable": resolved is not None and resolved.cost_is_set,
            }
        )
    return result


def _natural_sku_key(item: models.CatalogItem) -> tuple:
    sku = str(item.sku or "").casefold()
    normalized_sku = re.sub(
        r"\d+",
        lambda match: f"{int(match.group()):020d}",
        sku,
    )
    return normalized_sku, sku, str(item.name or "").casefold()


def _seed_item_to_model(index: int, item) -> models.CatalogItem:
    model = models.CatalogItem(
        id=index,
        sku=item.article,
        name=item.name,
        group=item.group,
        system=item.system,
        system_groups=json.dumps(
            ["SLIDE_1", "SLIDE_2"]
            if "СЛАЙД" in str(item.system or "").upper()
            else ["CS"] if item.system == 'ЦС' else [],
            ensure_ascii=False,
        ),
        unit=item.unit,
        purchase_price=item.purchase_price,
        markup_percent=item.markup_percent,
        weight=item.weight,
        waste_percent=item.waste_percent,
        section_width_mm=item.section_width_mm,
        section_height_mm=item.section_height_mm,
        image_file=item.image,
        photo_file=item.photo,
        paint_mode=item.paint_mode,
        color_variants=json.dumps(list(item.color_variants), ensure_ascii=False),
        supplier=item.supplier,
        is_active=item.is_active,
        note=item.note or item.paint_note,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    finish_codes = (
        ["ANOD_UNPAINTED", "RAL_STANDARD", "RAL_MOIRE", "SUBLIMATION"]
        if _is_paintable(item.paint_mode)
        else ["COLORLESS"]
    )
    for code in finish_codes:
        fixed_name, requires_paint = FINISH_DEFINITIONS[code]
        base_cost = 0 if code == "SUBLIMATION" else max(0, item.purchase_price)
        model.finish_variants.append(
            models.CatalogFinishVariant(
                code=code,
                name=fixed_name,
                price=base_cost,
                cost=base_cost,
                profile_markup_percent=max(0, item.markup_percent),
                profile_discount_percent=0,
                waste_markup_percent=max(0, item.waste_percent),
                construction_markup_percent=0,
                construction_discount_percent=0,
                requires_paint=requires_paint,
                is_active=True,
            )
        )
    return model


def _ensure_catalog_seed(db: Session) -> None:
    has_existing_items = db.query(models.CatalogItem).count() > 0
    for index, item in enumerate(PROFILE_CATALOG.values(), start=101):
        if (
            db.query(models.CatalogItem)
            .filter(models.CatalogItem.sku == item.article)
            .first()
        ):
            continue
        model = _seed_item_to_model(index, item)
        if has_existing_items:
            model.id = None
        db.add(model)
    db.flush()
    actor = (
        db.query(models.User)
        .filter(models.User.role.in_(("admin", "superadmin")))
        .order_by(models.User.id)
        .first()
    )
    actor_id = actor.id if actor is not None else None
    if actor_id is not None:
        now = datetime.utcnow()
        for catalog_item in db.query(models.CatalogItem).all():
            for variant in catalog_item.finish_variants:
                if not variant.is_active or any(
                    row.finish_variant_id == variant.id
                    for row in catalog_item.price_versions
                ):
                    continue
                catalog_item.price_versions.append(
                    models.CatalogPriceVersion(
                        finish_variant_id=variant.id,
                        cost=variant.cost,
                        profile_markup_percent=variant.profile_markup_percent,
                        profile_discount_percent=variant.profile_discount_percent,
                        waste_markup_percent=variant.waste_markup_percent,
                        construction_markup_percent=variant.construction_markup_percent,
                        construction_discount_percent=variant.construction_discount_percent,
                        category=_price_category(catalog_item.group),
                        unit=catalog_item.unit,
                        min_margin_percent=0,
                        effective_from=now,
                        created_at=now,
                        created_by=actor_id,
                        reason="Начальная цена единого каталога",
                    )
                )
    db.commit()


def _decode_color_variants(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _item_to_dict(item: models.CatalogItem) -> dict:
    active_price = max(
        (row for row in item.price_versions if row.effective_from <= datetime.utcnow()),
        key=lambda row: (row.effective_from, row.id),
        default=None,
    )
    finish_order = {code: index for index, code in enumerate(FINISH_DEFINITIONS)}
    variants = sorted(
        (row for row in item.finish_variants if row.is_active),
        key=lambda row: finish_order.get(
            _finish_code(row.name, getattr(row, "code", None)), 99
        ),
    )
    representative = variants[0] if variants else None
    db = object_session(item)
    if representative is not None and db is not None:
        representative = resolve_effective_price(db, item, representative) or representative
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "group": item.group,
        "system": item.system,
        "systemGroups": _decode_system_groups(item.system_groups, item.system),
        "unit": item.unit,
        "purchasePrice": float(representative.cost)
        if representative
        else float(active_price.cost)
        if active_price
        else item.purchase_price,
        "markupPercent": float(representative.profile_markup_percent)
        if representative
        else float(active_price.profile_markup_percent)
        if active_price
        else item.markup_percent,
        "profileDiscountPercent": float(representative.profile_discount_percent)
        if representative
        else float(active_price.profile_discount_percent)
        if active_price
        else 0,
        "weight": item.weight,
        # Deprecated rollout fallback. New clients use the value on each
        # finish row so different finishes can have different waste factors.
        "wastePercent": float(representative.waste_markup_percent)
        if representative
        else float(item.waste_percent or 0),
        "constructionMarkupPercent": float(representative.construction_markup_percent)
        if representative
        else float(active_price.construction_markup_percent)
        if active_price
        else 0,
        "constructionDiscountPercent": float(
            representative.construction_discount_percent
        )
        if representative
        else float(active_price.construction_discount_percent)
        if active_price
        else 0,
        "sectionWidthMm": item.section_width_mm,
        "sectionHeightMm": item.section_height_mm,
        "imageFile": item.image_file or "",
        "photoFile": item.photo_file or "",
        "paintMode": item.paint_mode,
        "colorVariants": _decode_color_variants(item.color_variants),
        "finishVariants": [
            _variant_to_dict(row, include_cost=True) for row in variants
        ],
        "supplier": item.supplier or "",
        "isActive": bool(item.is_active),
        "updatedAt": item.updated_at.date().isoformat()
        if item.updated_at
        else CATALOG_UPDATED_AT,
        "note": item.note or "",
    }


def _item_to_option(item: models.CatalogItem) -> dict:
    variants = [
        _variant_to_dict(row)
        for row in item.finish_variants
        if row.is_active
        and _finish_code(row.name, getattr(row, "code", None)) != "COLORLESS"
    ]
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "category": _price_category(item.group),
        "unit": item.unit or "шт",
        "systemGroups": _decode_system_groups(item.system_groups, item.system),
        "imageFile": item.image_file or "",
        "paintMode": item.paint_mode,
        "finishVariants": variants,
        "requiresPaint": any(row["requiresPaint"] for row in variants),
        "isActive": bool(item.is_active),
    }


def _apply_payload(item: models.CatalogItem, data: schemas.CatalogItemBase) -> None:
    item.sku = data.sku.strip()
    item.name = data.name.strip()
    item.group = data.group.strip() or "Профили"
    groups = list(
        dict.fromkeys(code for code in data.systemGroups if code in SYSTEM_GROUPS)
    )
    item.system_groups = json.dumps(groups, ensure_ascii=False)
    item.system = data.system.strip() or item.system or "СЛАЙД"
    item.unit = data.unit.strip() or "шт"
    item.purchase_price = data.purchasePrice
    item.markup_percent = data.markupPercent
    item.weight = data.weight
    # Keep the legacy item-level field synchronized for old clients during the
    # rolling deployment; it is no longer a source of truth.
    item.section_width_mm = data.sectionWidthMm
    item.section_height_mm = data.sectionHeightMm
    item.image_file = (data.imageFile or "").strip() or None
    if 'photoFile' in data.model_fields_set:
        item.photo_file = (data.photoFile or '').strip() or None
    item.paint_mode = data.paintMode.strip() or "Не красится"
    current = {
        _finish_code(row.name, getattr(row, "code", None)): row
        for row in item.finish_variants
    }
    payloads = {_finish_code(row.name, row.code): row for row in data.finishVariants}
    for variant in item.finish_variants:
        variant.is_active = False
        variant.updated_at = datetime.utcnow()
    expected_codes = (
        ["ANOD_UNPAINTED", "RAL_STANDARD", "RAL_MOIRE", "SUBLIMATION"]
        if _is_paintable(item.paint_mode)
        else ["COLORLESS"]
    )
    retained: list[models.CatalogFinishVariant] = []
    for code in expected_codes:
        payload = payloads.get(code)
        variant = current.get(code) or models.CatalogFinishVariant()
        fixed_name, requires_paint = FINISH_DEFINITIONS[code]
        cost = (
            payload.cost
            if payload is not None and payload.cost is not None
            else payload.price
            if payload is not None
            else data.purchasePrice
        )
        variant.code = code
        variant.name = fixed_name
        variant.cost = cost
        variant.price = cost
        variant.cost_is_set = payload.costIsSet if payload and payload.costIsSet is not None else True
        variant.profile_markup_percent = (
            payload.profileMarkupPercent if payload else data.markupPercent
        )
        variant.profile_discount_percent = (
            payload.profileDiscountPercent if payload else data.profileDiscountPercent
        )
        # Historical construction caches are retained for archive compatibility;
        # catalogue writes cannot change independent system prices.
        for field in ("waste_markup_percent", "construction_markup_percent", "construction_discount_percent"):
            if getattr(variant, field, None) is None:
                setattr(variant, field, 0)
        variant.requires_paint = requires_paint
        variant.is_active = True
        variant.updated_at = datetime.utcnow()
        if variant not in item.finish_variants:
            item.finish_variants.append(variant)
        retained.append(variant)
    item.color_variants = json.dumps([row.name for row in retained], ensure_ascii=False)
    item.waste_percent = float(retained[0].waste_markup_percent or 0) if retained else 0
    item.supplier = (data.supplier or "").strip() or None
    item.is_active = data.isActive
    item.note = (data.note or "").strip() or None
    item.updated_at = datetime.utcnow()


def _price_category(group: str) -> str:
    normalized = group.casefold()
    if "услуг" in normalized or "работ" in normalized:
        return "service"
    if "проф" in normalized or "уплотн" in normalized:
        return "profile"
    return "component"


def _sync_price_versions(
    item: models.CatalogItem,
    data: schemas.CatalogItemBase,
    actor: models.User,
) -> None:
    now = datetime.utcnow()
    variants: list[models.CatalogFinishVariant | None] = [
        row for row in item.finish_variants if row.is_active
    ] or [None]
    for variant in variants:
        variant_id = variant.id if variant is not None else None
        current = max(
            (
                row
                for row in item.price_versions
                if row.effective_from <= now and row.finish_variant_id == variant_id
            ),
            key=lambda row: (row.effective_from, row.id or 0),
            default=None,
        )
        finish_input = next((row for row in data.finishVariants
                             if variant is not None and _finish_code(row.name, row.code)
                             == _finish_code(variant.name, variant.code)), None)
        minimum = (finish_input.minimumMarkupPercent
                   if finish_input is not None and finish_input.minimumMarkupPercent is not None
                   else current.min_margin_percent if current else 0)
        desired = (
            Decimal(str(variant.cost if variant is not None else data.purchasePrice)),
            Decimal(
                str(
                    variant.profile_markup_percent
                    if variant is not None
                    else data.markupPercent
                )
            ),
            Decimal(
                str(
                    variant.profile_discount_percent
                    if variant is not None
                    else data.profileDiscountPercent
                )
            ),
            Decimal(
                str(
                    variant.waste_markup_percent
                    if variant is not None
                    else data.wastePercent
                )
            ),
            Decimal(
                str(
                    variant.construction_markup_percent
                    if variant is not None
                    else data.constructionMarkupPercent
                )
            ),
            Decimal(
                str(
                    variant.construction_discount_percent
                    if variant is not None
                    else data.constructionDiscountPercent
                )
            ),
            _price_category(data.group),
            data.unit.strip() or "шт",
            Decimal(str(minimum)),
            bool(variant.cost_is_set) if variant is not None else True,
        )
        existing = (
            (
                Decimal(str(current.cost)),
                Decimal(str(current.profile_markup_percent)),
                Decimal(str(current.profile_discount_percent)),
                Decimal(str(current.waste_markup_percent)),
                Decimal(str(current.construction_markup_percent)),
                Decimal(str(current.construction_discount_percent)),
                current.category,
                current.unit,
                Decimal(str(current.min_margin_percent)),
                current.cost_is_set,
            )
            if current
            else None
        )
        if existing == desired:
            continue
        item.price_versions.append(
            models.CatalogPriceVersion(
                finish_variant_id=variant_id,
                cost=desired[0],
                cost_is_set=desired[9],
                profile_markup_percent=desired[1],
                profile_discount_percent=desired[2],
                waste_markup_percent=desired[3],
                construction_markup_percent=desired[4],
                construction_discount_percent=desired[5],
                category=desired[6],
                unit=desired[7],
                min_margin_percent=desired[8],
                effective_from=now,
                created_at=now,
                created_by=actor.id,
                reason=f"Изменение позиции каталога: {variant.name if variant else 'базовая цена'}",
            )
        )


def _validate_payload(
    db: Session, data: schemas.CatalogItemBase, item_id: int | None = None
) -> None:
    sku = data.sku.strip()
    name = data.name.strip()
    if not sku:
        raise HTTPException(status_code=400, detail="Введите артикул")
    if not name:
        raise HTTPException(status_code=400, detail="Введите название")
    duplicate = (
        db.query(models.CatalogItem).filter(models.CatalogItem.sku == sku).first()
    )
    if duplicate and duplicate.id != item_id:
        raise HTTPException(status_code=400, detail="Артикул уже существует")
    if any(code not in SYSTEM_GROUPS for code in data.systemGroups):
        raise HTTPException(
            status_code=400,
            detail="Неизвестная группа системы",
        )
    if "СЛАЙД" in data.system.strip().upper() and not data.systemGroups:
        raise HTTPException(
            status_code=400,
            detail="Выберите СЛАЙД 1 ряд и/или СЛАЙД 2 ряда",
        )
    for field_name, value in (
        ("Закупочная цена", data.purchasePrice),
        ("Наценка на профиль", data.markupPercent),
        ("Скидка на профиль", data.profileDiscountPercent),
        ("Вес", data.weight),
        ("Наценка на конструкцию", data.constructionMarkupPercent),
        ("Скидка на конструкцию", data.constructionDiscountPercent),
        ("Ширина сечения", data.sectionWidthMm),
        ("Высота сечения", data.sectionHeightMm),
    ):
        if value < 0:
            raise HTTPException(
                status_code=400, detail=f"{field_name} не может быть меньше 0"
            )
    normalized_variant_names = []
    for variant in data.finishVariants:
        name = " ".join(variant.name.split())
        if not name:
            raise HTTPException(status_code=400, detail="Введите название исполнения")
        key = name.casefold()
        if key in normalized_variant_names:
            raise HTTPException(
                status_code=400,
                detail="Исполнения внутри артикула не должны повторяться",
            )
        normalized_variant_names.append(key)
        for field_name, value in (
            ("Себестоимость исполнения", variant.cost or variant.price),
            ("Наценка на профиль", variant.profileMarkupPercent),
            ("Скидка на профиль", variant.profileDiscountPercent),
            ("Наценка на отходы", variant.wasteMarkupPercent),
            ("Наценка на конструкцию", variant.constructionMarkupPercent),
            ("Скидка на конструкцию", variant.constructionDiscountPercent),
        ):
            if value < 0:
                raise HTTPException(
                    status_code=400, detail=f"{field_name} не может быть меньше 0"
                )


@router.get("/hardware")
def list_hardware_catalog(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    _ensure_catalog_seed(db)
    items = db.query(models.CatalogItem).order_by(models.CatalogItem.id).all()
    return [_item_to_dict(item) for item in items]


@router.get("/hardware/options")
def list_hardware_options(db: Session = Depends(get_db)):
    _ensure_catalog_seed(db)
    items = (
        db.query(models.CatalogItem)
        .filter(models.CatalogItem.is_active == True)  # noqa: E712
        .all()
    )
    items.sort(key=_natural_sku_key)
    return [_item_to_option(item) for item in items]


def _cs_profile_summary(item: models.CatalogItem | None) -> dict | None:
    if item is None:
        return None
    return {"id": item.id, "sku": item.sku, "name": item.name}


def _cs_system_to_dict(row: models.CsSystem, db: Session) -> dict:
    item_ids = {
        value
        for value in (row.outer_profile_item_id, row.joint_profile_item_id, row.cover_profile_item_id, row.bubble_seal_item_id, row.glass_pad_item_id)
        if value is not None
    }
    items = (
        db.query(models.CatalogItem)
        .filter(models.CatalogItem.id.in_(item_ids))
        .all()
        if item_ids
        else []
    )
    by_id = {item.id: item for item in items}
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "outer_profile_item_id": row.outer_profile_item_id,
        "joint_profile_item_id": row.joint_profile_item_id,
        "cover_profile_item_id": row.cover_profile_item_id,
        "bubble_seal_item_id": row.bubble_seal_item_id,
        "glass_pad_item_id": row.glass_pad_item_id,
        "is_active": row.is_active,
        "outer_profile": _cs_profile_summary(by_id.get(row.outer_profile_item_id)),
        "joint_profile": _cs_profile_summary(by_id.get(row.joint_profile_item_id)),
    }


def _validate_cs_profile_links(db: Session, data: schemas.CsSystemBase) -> None:
    ids = {
        value
        for value in (data.outer_profile_item_id, data.joint_profile_item_id, data.cover_profile_item_id, data.bubble_seal_item_id, data.glass_pad_item_id)
        if value is not None
    }
    if not ids:
        return
    items = db.query(models.CatalogItem).filter(models.CatalogItem.id.in_(ids)).all()
    found = {item.id for item in items if item.is_active}
    missing = sorted(ids - found)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Не найдены активные профили каталога: {', '.join(map(str, missing))}",
        )
    profile_ids = {data.outer_profile_item_id, data.joint_profile_item_id, data.cover_profile_item_id}
    invalid = [item.sku for item in items if item.id in profile_ids and _price_category(item.group) != "profile"]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Для системы ЦС можно выбрать только профили: {', '.join(invalid)}",
        )


@router.get("/cs-systems")
def list_cs_systems(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CsSystem)
        .filter(models.CsSystem.is_active == True)  # noqa: E712
        .order_by(models.CsSystem.name, models.CsSystem.id)
        .all()
    )
    return [_cs_system_to_dict(row, db) for row in rows]


@router.post("/cs-systems", status_code=201)
def create_cs_system(
    data: schemas.CsSystemCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    code = data.code.strip().upper()
    if db.query(models.CsSystem).filter(models.CsSystem.code == code).first():
        raise HTTPException(status_code=400, detail="Код системы ЦС уже используется")
    _validate_cs_profile_links(db, data)
    row = models.CsSystem(
        code=code,
        name=data.name.strip(),
        outer_profile_item_id=data.outer_profile_item_id,
        joint_profile_item_id=data.joint_profile_item_id,
        cover_profile_item_id=data.cover_profile_item_id,
        bubble_seal_item_id=data.bubble_seal_item_id,
        glass_pad_item_id=data.glass_pad_item_id,
        is_active=data.is_active,
        updated_by=actor.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _cs_system_to_dict(row, db)


@router.put("/cs-systems/{system_id}")
def update_cs_system(
    system_id: int,
    data: schemas.CsSystemUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    row = db.query(models.CsSystem).filter(models.CsSystem.id == system_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Система ЦС не найдена")
    code = data.code.strip().upper()
    duplicate = (
        db.query(models.CsSystem)
        .filter(models.CsSystem.code == code, models.CsSystem.id != system_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Код системы ЦС уже используется")
    _validate_cs_profile_links(db, data)
    row.code = code
    row.name = data.name.strip()
    row.outer_profile_item_id = data.outer_profile_item_id
    row.joint_profile_item_id = data.joint_profile_item_id
    for field in ('cover_profile_item_id', 'bubble_seal_item_id', 'glass_pad_item_id'):
        if field in data.model_fields_set:
            setattr(row, field, getattr(data, field))
    row.is_active = data.is_active
    row.updated_by = actor.id
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _cs_system_to_dict(row, db)


@router.post("/hardware", status_code=201)
def create_hardware_item(
    data: schemas.CatalogItemCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    _validate_payload(db, data)
    item = models.CatalogItem(created_at=datetime.utcnow())
    _apply_payload(item, data)
    db.add(item)
    db.flush()
    _sync_price_versions(item, data, actor)
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.put("/hardware/{item_id}")
def update_hardware_item(
    item_id: int,
    data: schemas.CatalogItemUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    item = db.query(models.CatalogItem).filter(models.CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    _validate_payload(db, data, item_id=item.id)
    _apply_payload(item, data)
    db.flush()
    _sync_price_versions(item, data, actor)
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.delete("/hardware/{item_id}")
def archive_hardware_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    item = db.query(models.CatalogItem).filter(models.CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    item.is_active = False
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.get("/profile-assets/{filename}")
def get_profile_asset(filename: str):
    path = get_profile_asset_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    return FileResponse(path)
