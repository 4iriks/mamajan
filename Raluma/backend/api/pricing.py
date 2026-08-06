"""Внутреннее управление версионируемыми ценами и условиями дилеров."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

import models
import schemas
from api.catalog import _ensure_catalog_seed
from auth import require_price_manager
from database import get_db
from engine.quote_pricing import (
    MANUAL_SERVICE_UNITS,
    PRICE_CATEGORIES,
    decimal_text,
    decimal_value,
    get_pricing_settings,
    internal_quote_state,
    money,
    money_text,
)


router = APIRouter(prefix="/api/pricing", tags=["pricing"])


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _version_dict(version: models.CatalogPriceVersion | None) -> dict | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "catalog_item_id": version.catalog_item_id,
        "cost": money_text(decimal_value(version.cost)),
        "profile_markup_percent": decimal_text(
            decimal_value(version.profile_markup_percent)
        ),
        "profile_discount_percent": decimal_text(
            decimal_value(version.profile_discount_percent)
        ),
        "waste_markup_percent": decimal_text(
            decimal_value(version.waste_markup_percent)
        ),
        "construction_markup_percent": decimal_text(
            decimal_value(version.construction_markup_percent)
        ),
        "construction_discount_percent": decimal_text(
            decimal_value(version.construction_discount_percent)
        ),
        "category": version.category,
        "unit": version.unit,
        "min_margin_percent": decimal_text(
            decimal_value(version.min_margin_percent)
        ),
        "effective_from": version.effective_from.isoformat(),
        "created_at": version.created_at.isoformat(),
        "created_by": version.created_by,
        "reason": version.reason,
        "rollback_of_id": version.rollback_of_id,
    }


def _active_and_next_versions(
    versions: list[models.CatalogPriceVersion], at: datetime
) -> tuple[models.CatalogPriceVersion | None, models.CatalogPriceVersion | None]:
    active = [row for row in versions if row.effective_from <= at]
    future = [row for row in versions if row.effective_from > at]
    active_version = max(
        active, key=lambda row: (row.effective_from, row.id), default=None
    )
    next_version = min(
        future, key=lambda row: (row.effective_from, row.id), default=None
    )
    return active_version, next_version


def _catalog_item_dict(item: models.CatalogItem, at: datetime) -> dict:
    versions = list(item.price_versions)
    active, upcoming = _active_and_next_versions(versions, at)
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "group": item.group,
        "system": item.system,
        "catalog_unit": item.unit,
        "supplier": item.supplier or "",
        "is_active": bool(item.is_active),
        "active_price": _version_dict(active),
        "next_price": _version_dict(upcoming),
        "history_count": len(versions),
    }


def _validate_price_payload(data: schemas.CatalogPriceVersionBase) -> None:
    if data.category not in PRICE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Неизвестная категория цены")
    if not data.unit.strip():
        raise HTTPException(status_code=400, detail="Укажите единицу измерения")
    if not data.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину изменения")


def _new_version(
    item: models.CatalogItem,
    data: schemas.CatalogPriceVersionBase,
    actor: models.User,
    *,
    rollback_of_id: int | None = None,
) -> models.CatalogPriceVersion:
    _validate_price_payload(data)
    return models.CatalogPriceVersion(
        catalog_item_id=item.id,
        cost=money(decimal_value(data.cost)),
        profile_markup_percent=data.profile_markup_percent,
        profile_discount_percent=data.profile_discount_percent,
        waste_markup_percent=data.waste_markup_percent,
        construction_markup_percent=data.construction_markup_percent,
        construction_discount_percent=data.construction_discount_percent,
        category=data.category,
        unit=data.unit.strip(),
        min_margin_percent=data.min_margin_percent,
        effective_from=_normalize_datetime(data.effective_from),
        created_at=datetime.utcnow(),
        created_by=actor.id,
        reason=data.reason.strip(),
        rollback_of_id=rollback_of_id,
    )


@router.get("/catalog")
def list_priced_catalog(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    _ensure_catalog_seed(db)
    now = datetime.utcnow()
    items = db.query(models.CatalogItem).order_by(models.CatalogItem.sku).all()
    return {
        "items": [_catalog_item_dict(item, now) for item in items],
        "categories": sorted(PRICE_CATEGORIES),
        "manual_service_units": list(MANUAL_SERVICE_UNITS),
    }


@router.get("/catalog/{item_id}/versions")
def price_history(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    item = db.query(models.CatalogItem).filter_by(id=item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    versions = (
        db.query(models.CatalogPriceVersion)
        .filter_by(catalog_item_id=item.id)
        .order_by(
            models.CatalogPriceVersion.effective_from.desc(),
            models.CatalogPriceVersion.id.desc(),
        )
        .all()
    )
    return {
        "item": {"id": item.id, "sku": item.sku, "name": item.name},
        "versions": [_version_dict(version) for version in versions],
    }


@router.post("/catalog/{item_id}/versions", status_code=201)
def create_price_version(
    item_id: int,
    data: schemas.CatalogPriceVersionCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    item = db.query(models.CatalogItem).filter_by(id=item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    version = _new_version(item, data, actor)
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_dict(version)


@router.post("/catalog/{item_id}/rollback/{version_id}", status_code=201)
def rollback_price_version(
    item_id: int,
    version_id: int,
    data: schemas.CatalogPriceRollback,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    item = db.query(models.CatalogItem).filter_by(id=item_id).first()
    target = (
        db.query(models.CatalogPriceVersion)
        .filter_by(id=version_id, catalog_item_id=item_id)
        .first()
    )
    if item is None or target is None:
        raise HTTPException(status_code=404, detail="Версия цены не найдена")
    payload = schemas.CatalogPriceVersionCreate(
        cost=target.cost,
        profile_markup_percent=target.profile_markup_percent,
        profile_discount_percent=target.profile_discount_percent,
        waste_markup_percent=target.waste_markup_percent,
        construction_markup_percent=target.construction_markup_percent,
        construction_discount_percent=target.construction_discount_percent,
        category=target.category,
        unit=target.unit,
        min_margin_percent=target.min_margin_percent,
        effective_from=data.effective_from,
        reason=data.reason,
    )
    version = _new_version(item, payload, actor, rollback_of_id=target.id)
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_dict(version)


def _bulk_preview(
    db: Session, data: schemas.CatalogPriceBulkRequest
) -> list[dict]:
    item_ids = list(dict.fromkeys(data.item_ids))
    items = db.query(models.CatalogItem).filter(models.CatalogItem.id.in_(item_ids)).all()
    by_id = {item.id: item for item in items}
    if len(by_id) != len(item_ids):
        missing = sorted(set(item_ids) - set(by_id))
        raise HTTPException(
            status_code=400,
            detail=f"Позиции каталога не найдены: {', '.join(map(str, missing))}",
        )
    now = datetime.utcnow()
    factor = Decimal("1") + decimal_value(data.percent) / Decimal("100")
    rows = []
    for item_id in item_ids:
        item = by_id[item_id]
        active, _future = _active_and_next_versions(list(item.price_versions), now)
        if active is None:
            raise HTTPException(
                status_code=400,
                detail=f"У позиции {item.sku} нет действующей версии цены",
            )
        rows.append(
            {
                "item_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "old_cost": money_text(decimal_value(active.cost)),
                "new_cost": money_text(decimal_value(active.cost) * factor),
                "source_version_id": active.id,
                "source": active,
            }
        )
    return rows


@router.post("/catalog/bulk/preview")
def preview_bulk_price_change(
    data: schemas.CatalogPriceBulkRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    return {
        "rows": [
            {key: value for key, value in row.items() if key != "source"}
            for row in _bulk_preview(db, data)
        ]
    }


@router.post("/catalog/bulk/apply", status_code=201)
def apply_bulk_price_change(
    data: schemas.CatalogPriceBulkRequest,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    preview = _bulk_preview(db, data)
    created = []
    try:
        for row in preview:
            source = row["source"]
            item = source.catalog_item
            payload = schemas.CatalogPriceVersionCreate(
                cost=Decimal(row["new_cost"]),
                profile_markup_percent=source.profile_markup_percent,
                profile_discount_percent=source.profile_discount_percent,
                waste_markup_percent=source.waste_markup_percent,
                construction_markup_percent=source.construction_markup_percent,
                construction_discount_percent=source.construction_discount_percent,
                category=source.category,
                unit=source.unit,
                min_margin_percent=source.min_margin_percent,
                effective_from=data.effective_from,
                reason=data.reason,
            )
            version = _new_version(item, payload, actor)
            db.add(version)
            created.append(version)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for version in created:
        db.refresh(version)
    return {"versions": [_version_dict(version) for version in created]}


_HEADER_ALIASES = {
    "артикул": "sku",
    "sku": "sku",
    "себестоимость": "cost",
    "стоимость": "cost",
    "cost": "cost",
    "наценка на профиль": "profile_markup_percent",
    "скидка на профиль": "profile_discount_percent",
    "наценка на отходы": "waste_markup_percent",
    "наценка на конструкции": "construction_markup_percent",
    "скидка на конструкции": "construction_discount_percent",
    "категория": "category",
    "category": "category",
    "единица": "unit",
    "единица измерения": "unit",
    "unit": "unit",
    "минимальная маржа": "min_margin_percent",
    "дата начала": "effective_from",
    "дата начала действия": "effective_from",
    "effective from": "effective_from",
}


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def _xlsx_rows(content: bytes) -> list[list[str]]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_namespace = {
        "r": "http://schemas.openxmlformats.org/package/2006/relationships"
    }
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Файл не является XLSX") from exc
    with archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        rels = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall("r:Relationship", rel_namespace)
        }
        sheets = workbook.findall("x:sheets/x:sheet", namespace)
        if not sheets:
            return []
        selected = next(
            (sheet for sheet in sheets if sheet.attrib.get("name") == "Цены"),
            sheets[0],
        )
        relation_id = selected.attrib[f"{{{office_rel}}}id"]
        target = rels[relation_id].lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for node in shared_root.findall("x:si", namespace):
                shared.append(
                    "".join(text.text or "" for text in node.findall(".//x:t", namespace))
                )
        percent_styles: set[int] = set()
        if "xl/styles.xml" in archive.namelist():
            styles_root = ElementTree.fromstring(archive.read("xl/styles.xml"))
            custom_formats = {
                int(node.attrib["numFmtId"]): node.attrib.get("formatCode", "")
                for node in styles_root.findall("x:numFmts/x:numFmt", namespace)
            }
            for style_index, style in enumerate(
                styles_root.findall("x:cellXfs/x:xf", namespace)
            ):
                format_id = int(style.attrib.get("numFmtId", "0"))
                format_code = custom_formats.get(format_id, "")
                if format_id in {9, 10} or "%" in format_code:
                    percent_styles.add(style_index)
        sheet_root = ElementTree.fromstring(archive.read(sheet_path))
        result: list[list[str]] = []
        for row in sheet_root.findall(".//x:sheetData/x:row", namespace):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", namespace):
                index = _column_index(cell.attrib.get("r", "A1"))
                cell_type = cell.attrib.get("t")
                value_node = cell.find("x:v", namespace)
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or ""
                        for node in cell.findall(".//x:t", namespace)
                    )
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    value = shared[int(value_node.text or "0")]
                else:
                    value = value_node.text or ""
                    style_index = int(cell.attrib.get("s", "0"))
                    if value and style_index in percent_styles:
                        try:
                            value = decimal_text(Decimal(value) * Decimal("100"))
                        except InvalidOperation:
                            pass
                values[index] = value.strip()
            if values:
                width = max(values) + 1
                result.append([values.get(index, "") for index in range(width)])
        return result


def _infer_category(item: models.CatalogItem) -> str:
    group = str(item.group or "").casefold()
    if "проф" in group or "уплотн" in group:
        return "profile"
    if "услуг" in group or "работ" in group or item.sku.startswith("PAINT|"):
        return "service"
    if "конструк" in group or item.sku == "WORK-SLIDE":
        return "construction"
    return "component"


def _excel_date(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.utcnow()
    try:
        serial = Decimal(text)
    except InvalidOperation:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _normalize_datetime(parsed)
    return datetime(1899, 12, 30) + timedelta(days=float(serial))


def _import_preview(db: Session, content: bytes) -> dict:
    raw_rows = _xlsx_rows(content)
    if not raw_rows:
        return {"valid": False, "rows": [], "errors": ["В файле нет данных"]}
    header_index = next(
        (
            index
            for index, row in enumerate(raw_rows)
            if any(str(cell).strip() for cell in row)
        ),
        0,
    )
    headers = [
        _HEADER_ALIASES.get(" ".join(str(value).casefold().split()), "")
        for value in raw_rows[header_index]
    ]
    if "sku" not in headers or "cost" not in headers:
        return {
            "valid": False,
            "rows": [],
            "errors": ["Обязательные колонки: Артикул и Себестоимость"],
        }
    items = {item.sku: item for item in db.query(models.CatalogItem).all()}
    result_rows = []
    errors = []
    seen_skus: set[str] = set()
    for excel_row, values in enumerate(raw_rows[header_index + 1 :], start=header_index + 2):
        mapped = {
            header: values[index] if index < len(values) else ""
            for index, header in enumerate(headers)
            if header
        }
        sku = str(mapped.get("sku") or "").strip()
        if not sku:
            continue
        if sku in seen_skus:
            errors.append(f"Строка {excel_row}: артикул {sku} указан повторно")
            continue
        seen_skus.add(sku)
        item = items.get(sku)
        if item is None:
            errors.append(f"Строка {excel_row}: артикул {sku} отсутствует в каталоге")
            continue
        normalized = {
            "sku": sku,
            "cost": mapped.get("cost"),
            "profile_markup_percent": mapped.get("profile_markup_percent") or "0",
            "profile_discount_percent": mapped.get("profile_discount_percent") or "0",
            "waste_markup_percent": mapped.get("waste_markup_percent") or "0",
            "construction_markup_percent": mapped.get("construction_markup_percent") or "0",
            "construction_discount_percent": mapped.get("construction_discount_percent") or "0",
            "category": mapped.get("category") or _infer_category(item),
            "unit": mapped.get("unit") or item.unit or "шт",
            "min_margin_percent": mapped.get("min_margin_percent") or "0",
            "effective_from": _excel_date(mapped.get("effective_from") or "").isoformat(),
        }
        try:
            schemas.CatalogPriceVersionCreate(
                **normalized,
                reason="Импорт из Excel",
            )
        except (ValidationError, ValueError) as exc:
            errors.append(f"Строка {excel_row}: {exc}")
            continue
        result_rows.append(normalized)
    return {"valid": not errors and bool(result_rows), "rows": result_rows, "errors": errors}


@router.post("/catalog/import/preview")
async def preview_price_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Поддерживается только XLSX")
    content = await file.read()
    return _import_preview(db, content)


@router.post("/catalog/import/apply", status_code=201)
def apply_price_import(
    data: schemas.CatalogPriceImportApply,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    skus = [str(row.get("sku") or "").strip() for row in data.rows]
    items = {
        item.sku: item
        for item in db.query(models.CatalogItem)
        .filter(models.CatalogItem.sku.in_(skus))
        .all()
    }
    errors = []
    validated: list[tuple[models.CatalogItem, schemas.CatalogPriceVersionCreate]] = []
    seen_skus: set[str] = set()
    for index, row in enumerate(data.rows, start=1):
        sku = str(row.get("sku") or "").strip()
        if sku in seen_skus:
            errors.append(f"Строка {index}: артикул {sku or '—'} указан повторно")
            continue
        seen_skus.add(sku)
        item = items.get(sku)
        if item is None:
            errors.append(f"Строка {index}: артикул {sku or '—'} отсутствует")
            continue
        try:
            payload = schemas.CatalogPriceVersionCreate(
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {"sku", "reason"}
                },
                reason=data.reason,
            )
            _validate_price_payload(payload)
            validated.append((item, payload))
        except (ValidationError, ValueError) as exc:
            errors.append(f"Строка {index}: {exc}")
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    created = [_new_version(item, payload, actor) for item, payload in validated]
    try:
        db.add_all(created)
        db.commit()
    except Exception:
        db.rollback()
        raise
    for version in created:
        db.refresh(version)
    return {"versions": [_version_dict(version) for version in created]}


@router.get("/dealers")
def list_pricing_dealers(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    dealers = (
        db.query(models.User)
        .filter(models.User.role == "dealer", models.User.is_active == True)  # noqa: E712
        .order_by(models.User.dealer_company, models.User.display_name)
        .all()
    )
    return [
        {
            "id": dealer.id,
            "display_name": dealer.display_name,
            "company": dealer.dealer_company or dealer.customer or "",
        }
        for dealer in dealers
    ]


@router.get("/dealers/{user_id}")
def get_dealer_terms(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    dealer = db.query(models.User).filter_by(id=user_id, role="dealer").first()
    if dealer is None:
        raise HTTPException(status_code=404, detail="Дилер не найден")
    terms = db.query(models.DealerPricingTerms).filter_by(user_id=user_id).first()
    if terms is None:
        return {
            "user_id": user_id,
            "dealer_markup_percent": "0",
            "profile_discount_percent": "0",
            "construction_discount_percent": "0",
            "component_discount_percent": "0",
            "service_discount_percent": "0",
            "updated_at": None,
            "updated_by": None,
        }
    return {
        "user_id": terms.user_id,
        "dealer_markup_percent": decimal_text(
            decimal_value(terms.dealer_markup_percent)
        ),
        "profile_discount_percent": decimal_text(
            decimal_value(terms.profile_discount_percent)
        ),
        "construction_discount_percent": decimal_text(
            decimal_value(terms.construction_discount_percent)
        ),
        "component_discount_percent": decimal_text(
            decimal_value(terms.component_discount_percent)
        ),
        "service_discount_percent": decimal_text(
            decimal_value(terms.service_discount_percent)
        ),
        "updated_at": terms.updated_at.isoformat(),
        "updated_by": terms.updated_by,
    }


@router.put("/dealers/{user_id}")
def update_dealer_terms(
    user_id: int,
    data: schemas.DealerPricingTermsUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    dealer = db.query(models.User).filter_by(id=user_id, role="dealer").first()
    if dealer is None:
        raise HTTPException(status_code=404, detail="Дилер не найден")
    terms = db.query(models.DealerPricingTerms).filter_by(user_id=user_id).first()
    if terms is None:
        terms = models.DealerPricingTerms(user_id=user_id, updated_by=actor.id)
        db.add(terms)
    for field, value in data.model_dump().items():
        setattr(terms, field, value)
    terms.updated_at = datetime.utcnow()
    terms.updated_by = actor.id
    db.commit()
    return get_dealer_terms(user_id, db, actor)


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_price_manager),
):
    settings = get_pricing_settings(db)
    db.commit()
    return {
        "id": settings.id,
        "include_waste_markup": bool(settings.include_waste_markup),
        "default_vat_rate": decimal_text(decimal_value(settings.default_vat_rate)),
        "updated_at": settings.updated_at.isoformat(),
        "updated_by": settings.updated_by,
    }


@router.put("/settings")
def update_settings(
    data: schemas.PricingSettingsUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    settings = get_pricing_settings(db)
    settings.include_waste_markup = data.include_waste_markup
    settings.default_vat_rate = data.default_vat_rate
    settings.updated_at = datetime.utcnow()
    settings.updated_by = actor.id
    db.commit()
    return get_settings(db, actor)


@router.get("/projects/{project_id}")
def get_internal_project_quote(
    project_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_price_manager),
):
    project = db.query(models.Project).filter_by(id=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if actor.role not in {"admin", "superadmin"} and project.created_by != actor.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    result = internal_quote_state(db, project)
    db.commit()
    return result
