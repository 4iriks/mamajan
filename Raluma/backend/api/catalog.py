import json
import re
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth import require_admin
from database import get_db
from engine.pdf import get_profile_asset_path
from engine.profile_catalog import PROFILE_CATALOG
import models
import schemas

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

CATALOG_UPDATED_AT = "2026-06-08"


def _variant_requires_paint(name: str, paint_mode: str) -> bool:
    normalized = name.casefold()
    mode = paint_mode.casefold()
    if "анод" in normalized or "без цвета" in normalized:
        return False
    return (
        "ral" in normalized
        or "окрас" in normalized
        or (
            ("красится" in mode or "частично" in mode)
            and "не красится" not in mode
        )
    )


def _variant_to_dict(
    variant: models.CatalogFinishVariant, *, include_cost: bool = False
) -> dict:
    result = {
        "id": variant.id,
        "name": variant.name,
        "requiresPaint": bool(variant.requires_paint),
        "isActive": bool(variant.is_active),
    }
    if include_cost:
        cost = variant.cost if variant.cost is not None else variant.price
        result["cost"] = f"{cost:.2f}"
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
        unit=item.unit,
        purchase_price=item.purchase_price,
        markup_percent=item.markup_percent,
        weight=item.weight,
        waste_percent=item.waste_percent,
        section_width_mm=item.section_width_mm,
        section_height_mm=item.section_height_mm,
        image_file=item.image,
        paint_mode=item.paint_mode,
        color_variants=json.dumps(list(item.color_variants), ensure_ascii=False),
        supplier=item.supplier,
        is_active=item.is_active,
        note=item.note or item.paint_note,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    sale_price = max(0, item.purchase_price) * (1 + max(0, item.markup_percent) / 100)
    for name in item.color_variants:
        model.finish_variants.append(
            models.CatalogFinishVariant(
                name=name,
                price=round(sale_price, 2),
                cost=max(0, item.purchase_price),
                requires_paint=_variant_requires_paint(name, item.paint_mode),
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
        (
            row
            for row in item.price_versions
            if row.effective_from <= datetime.utcnow()
        ),
        key=lambda row: (row.effective_from, row.id),
        default=None,
    )
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "group": item.group,
        "system": item.system,
        "unit": item.unit,
        "purchasePrice": float(active_price.cost) if active_price else item.purchase_price,
        "markupPercent": float(active_price.profile_markup_percent) if active_price else item.markup_percent,
        "profileDiscountPercent": float(active_price.profile_discount_percent) if active_price else 0,
        "weight": item.weight,
        "wastePercent": float(active_price.waste_markup_percent) if active_price else item.waste_percent,
        "constructionMarkupPercent": float(active_price.construction_markup_percent) if active_price else 0,
        "constructionDiscountPercent": float(active_price.construction_discount_percent) if active_price else 0,
        "sectionWidthMm": item.section_width_mm,
        "sectionHeightMm": item.section_height_mm,
        "imageFile": item.image_file or "",
        "paintMode": item.paint_mode,
        "colorVariants": _decode_color_variants(item.color_variants),
        "finishVariants": [
            _variant_to_dict(row, include_cost=True) for row in item.finish_variants
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
        _variant_to_dict(row) for row in item.finish_variants if row.is_active
    ]
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "category": _price_category(item.group),
        "unit": item.unit or "шт",
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
    item.system = data.system.strip() or "СЛАЙД"
    item.unit = data.unit.strip() or "шт"
    item.purchase_price = data.purchasePrice
    item.markup_percent = data.markupPercent
    item.weight = data.weight
    item.waste_percent = data.wastePercent
    item.section_width_mm = data.sectionWidthMm
    item.section_height_mm = data.sectionHeightMm
    item.image_file = (data.imageFile or "").strip() or None
    item.paint_mode = data.paintMode.strip() or "Не красится"
    variant_payloads = list(data.finishVariants)
    if not variant_payloads and data.colorVariants:
        sale_price = max(0, data.purchasePrice) * (1 + max(0, data.markupPercent) / 100)
        variant_payloads = [
            schemas.CatalogFinishVariantInput(
                name=name,
                price=round(sale_price, 2),
                requiresPaint=_variant_requires_paint(name, data.paintMode),
            )
            for name in data.colorVariants
            if str(name).strip()
        ]
    current = {row.id: row for row in item.finish_variants if row.id is not None}
    retained: list[models.CatalogFinishVariant] = []
    for payload in variant_payloads:
        variant = current.get(payload.id) if payload.id is not None else None
        if variant is None:
            variant = models.CatalogFinishVariant()
        variant.name = payload.name.strip()
        variant.cost = payload.cost if payload.cost is not None else payload.price
        variant.price = payload.price
        variant.requires_paint = payload.requiresPaint
        variant.is_active = payload.isActive
        variant.updated_at = datetime.utcnow()
        retained.append(variant)
    item.finish_variants[:] = retained
    item.color_variants = json.dumps(
        [row.name for row in retained], ensure_ascii=False
    )
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


def _sync_price_version(
    item: models.CatalogItem,
    data: schemas.CatalogItemBase,
    actor: models.User,
) -> None:
    current = max(
        (
            row
            for row in item.price_versions
            if row.effective_from <= datetime.utcnow()
        ),
        key=lambda row: (row.effective_from, row.id),
        default=None,
    )
    desired = (
        Decimal(str(data.purchasePrice)),
        Decimal(str(data.markupPercent)),
        Decimal(str(data.profileDiscountPercent)),
        Decimal(str(data.wastePercent)),
        Decimal(str(data.constructionMarkupPercent)),
        Decimal(str(data.constructionDiscountPercent)),
        _price_category(data.group),
        data.unit.strip() or "шт",
    )
    existing = (
        Decimal(str(current.cost)),
        Decimal(str(current.profile_markup_percent)),
        Decimal(str(current.profile_discount_percent)),
        Decimal(str(current.waste_markup_percent)),
        Decimal(str(current.construction_markup_percent)),
        Decimal(str(current.construction_discount_percent)),
        current.category,
        current.unit,
    ) if current else None
    if existing == desired:
        return
    item.price_versions.append(
        models.CatalogPriceVersion(
            cost=desired[0],
            profile_markup_percent=desired[1],
            profile_discount_percent=desired[2],
            waste_markup_percent=desired[3],
            construction_markup_percent=desired[4],
            construction_discount_percent=desired[5],
            category=desired[6],
            unit=desired[7],
            min_margin_percent=(current.min_margin_percent if current else 0),
            effective_from=datetime.utcnow(),
            created_at=datetime.utcnow(),
            created_by=actor.id,
            reason="Изменение позиции каталога",
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
    for field_name, value in (
        ("Закупочная цена", data.purchasePrice),
        ("Наценка на профиль", data.markupPercent),
        ("Скидка на профиль", data.profileDiscountPercent),
        ("Вес", data.weight),
        ("Отход", data.wastePercent),
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
                status_code=400, detail="Исполнения внутри артикула не должны повторяться"
            )
        normalized_variant_names.append(key)


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


@router.get("/construction-price-groups")
def list_construction_price_group_options(db: Session = Depends(get_db)):
    rows = (
        db.query(models.ConstructionPriceGroup)
        .filter(models.ConstructionPriceGroup.is_active == True)  # noqa: E712
        .order_by(models.ConstructionPriceGroup.name)
        .all()
    )
    # Markup is an internal coefficient and intentionally omitted.
    return [{"id": row.id, "code": row.code, "name": row.name} for row in rows]


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
    _sync_price_version(item, data, actor)
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
    _sync_price_version(item, data, actor)
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
