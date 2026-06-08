import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import require_admin
from engine.pdf import ASSETS_DIR
from engine.profile_catalog import PROFILE_CATALOG
import models

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

CATALOG_UPDATED_AT = "2026-06-08"


@router.get("/hardware")
def list_hardware_catalog(_: models.User = Depends(require_admin)):
    return [
        {
            "id": index,
            "sku": item.article,
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
            "imageFile": item.image,
            "paintMode": item.paint_mode,
            "colorVariants": list(item.color_variants),
            "supplier": item.supplier,
            "isActive": item.is_active,
            "updatedAt": CATALOG_UPDATED_AT,
            "note": item.note or item.paint_note,
        }
        for index, item in enumerate(PROFILE_CATALOG.values(), start=101)
    ]


@router.get("/profile-assets/{filename}")
def get_profile_asset(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.join(ASSETS_DIR, safe_name)
    if safe_name != filename or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    return FileResponse(path)
