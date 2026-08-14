import json
import re
from datetime import datetime

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


def _natural_sku_key(item: models.CatalogItem) -> tuple:
    sku = str(item.sku or "").casefold()
    normalized_sku = re.sub(
        r"\d+",
        lambda match: f"{int(match.group()):020d}",
        sku,
    )
    return normalized_sku, sku, str(item.name or "").casefold()


def _seed_item_to_model(index: int, item) -> models.CatalogItem:
    return models.CatalogItem(
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
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "group": item.group,
        "system": item.system,
        "unit": item.unit,
        "purchasePrice": item.purchase_price,
        "markupPercent": item.markup_percent,
        "weight": item.weight,
        "wastePercent": item.waste_percent,
        "sectionWidthMm": item.section_width_mm,
        "sectionHeightMm": item.section_height_mm,
        "imageFile": item.image_file or "",
        "paintMode": item.paint_mode,
        "colorVariants": _decode_color_variants(item.color_variants),
        "supplier": item.supplier or "",
        "isActive": bool(item.is_active),
        "updatedAt": item.updated_at.date().isoformat()
        if item.updated_at
        else CATALOG_UPDATED_AT,
        "note": item.note or "",
    }


def _item_to_option(item: models.CatalogItem) -> dict:
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "unit": item.unit or "шт",
        "imageFile": item.image_file or "",
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
    item.color_variants = json.dumps(data.colorVariants, ensure_ascii=False)
    item.supplier = (data.supplier or "").strip() or None
    item.is_active = data.isActive
    item.note = (data.note or "").strip() or None
    item.updated_at = datetime.utcnow()


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
        ("Наценка", data.markupPercent),
        ("Вес", data.weight),
        ("Отход", data.wastePercent),
        ("Ширина сечения", data.sectionWidthMm),
        ("Высота сечения", data.sectionHeightMm),
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


@router.post("/hardware", status_code=201)
def create_hardware_item(
    data: schemas.CatalogItemCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    _validate_payload(db, data)
    item = models.CatalogItem(created_at=datetime.utcnow())
    _apply_payload(item, data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_dict(item)


@router.put("/hardware/{item_id}")
def update_hardware_item(
    item_id: int,
    data: schemas.CatalogItemUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    item = db.query(models.CatalogItem).filter(models.CatalogItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    _validate_payload(db, data, item_id=item.id)
    _apply_payload(item, data)
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
