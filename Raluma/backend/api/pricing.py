"""Внутреннее управление версионируемыми ценами и условиями дилеров."""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

import models
import schemas
from api.catalog import (
    FINISH_DEFINITIONS,
    _ensure_catalog_seed,
    _finish_code,
)
from auth import get_current_user, require_admin, user_can_manage_prices
from database import get_db
from engine.pricing_rules import (
    normalized_at,
    price_preview,
    resolve_effective_price,
    sync_variant_cache,
)
from engine.quote_pricing import (
    MANUAL_SERVICE_UNITS,
    PRICE_CATEGORIES,
    QuotePricingError,
    calculate_standalone_sale,
    current_quote_preview_token,
    decimal_text,
    decimal_value,
    internal_quote_state,
    money,
    money_text,
    public_quote,
    safe_public_payload,
)


router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class FinishPriceVersionCreate(schemas.CatalogPriceVersionCreate):
    finish_variant_id: int | None = None


@router.post("/sale/quote")
def standalone_sale_quote(
    data: schemas.StandaloneSaleRequest,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    try:
        return calculate_standalone_sale(
            db,
            data.items,
            buyer_discount_mode=data.buyer_discount_mode,
            buyer_discount_value=data.buyer_discount_value,
        )
    except QuotePricingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
        "finish_variant_id": version.finish_variant_id,
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
        "min_margin_percent": decimal_text(decimal_value(version.min_margin_percent)),
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
    variants = [v for v in item.finish_variants if v.is_active]
    representative_id = variants[0].id if variants else None
    active, upcoming = _active_and_next_versions(
        [v for v in versions if v.finish_variant_id == representative_id], at
    )
    from sqlalchemy.orm import object_session

    db = object_session(item)
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
        "finish_prices": [
            {
                "finish_variant_id": v.id,
                "finish_name": v.name,
                "resolved": price_preview(resolve_effective_price(db, item, v, at)),
            }
            for v in variants
        ]
        if db
        else [],
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
    finish_variant_id: int | None = None,
    rollback_of_id: int | None = None,
) -> models.CatalogPriceVersion:
    _validate_price_payload(data)
    current = max(
        (
            v
            for v in item.price_versions
            if v.finish_variant_id == finish_variant_id
            and normalized_at(v.effective_from) <= normalized_at(data.effective_from)
        ),
        key=lambda v: (v.effective_from, v.id or 0),
        default=None,
    )
    return models.CatalogPriceVersion(
        catalog_item_id=item.id,
        finish_variant_id=finish_variant_id,
        cost=money(decimal_value(data.cost)),
        cost_is_set=True,
        profile_markup_percent=data.profile_markup_percent,
        profile_discount_percent=data.profile_discount_percent,
        waste_markup_percent=current.waste_markup_percent if current else 0,
        construction_markup_percent=current.construction_markup_percent
        if current
        else 0,
        construction_discount_percent=current.construction_discount_percent
        if current
        else 0,
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
    _: models.User = Depends(require_admin),
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
    _: models.User = Depends(require_admin),
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
    data: FinishPriceVersionCreate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    item = db.query(models.CatalogItem).filter_by(id=item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    variant_id = data.finish_variant_id
    variants = [v for v in item.finish_variants if v.is_active]
    if variant_id is None and len(variants) == 1:
        variant_id = variants[0].id
    variant = next((v for v in variants if v.id == variant_id), None)
    if variants and variant is None:
        raise HTTPException(400, "Выберите исполнение для новой версии цены")
    if variant_id is not None and variant is None:
        raise HTTPException(400, "Исполнение не относится к выбранному артикулу")
    version = _new_version(item, data, actor, finish_variant_id=variant_id)
    item.price_versions.append(version)
    if variant is not None:
        sync_variant_cache(item, variant)
    db.commit()
    db.refresh(version)
    return _version_dict(version)


@router.post("/catalog/{item_id}/rollback/{version_id}", status_code=201)
def rollback_price_version(
    item_id: int,
    version_id: int,
    data: schemas.CatalogPriceRollback,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    item = db.query(models.CatalogItem).filter_by(id=item_id).first()
    target = (
        db.query(models.CatalogPriceVersion)
        .filter_by(id=version_id, catalog_item_id=item_id)
        .first()
    )
    if item is None or target is None:
        raise HTTPException(status_code=404, detail="Версия цены не найдена")
    if target.finish_variant_id is None and any(
        v.is_active for v in item.finish_variants
    ):
        raise HTTPException(
            400,
            "Старая общая версия не определяет исполнение; выберите версию нужного исполнения",
        )
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
    version = _new_version(
        item,
        payload,
        actor,
        finish_variant_id=target.finish_variant_id,
        rollback_of_id=target.id,
    )
    item.price_versions.append(version)
    if target.finish_variant_id is not None:
        variant = db.get(models.CatalogFinishVariant, target.finish_variant_id)
        sync_variant_cache(item, variant)
    db.commit()
    db.refresh(version)
    return _version_dict(version)


_HEADER_ALIASES = {
    "артикул": "sku",
    "sku": "sku",
    "наименование": "name",
    "название": "name",
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
    "минимальная наценка": "min_margin_percent",
    "дата начала": "effective_from",
    "дата начала действия": "effective_from",
    "effective from": "effective_from",
}

_PENDING_COST_SKUS = {"RU003", "RU005"}
_PACK_LENGTHS_M = {
    "RS1006": Decimal("3.1"),
    "RS3110": Decimal("3"),
}


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - 64
    return result - 1


def _xlsx_rows(content: bytes) -> list[dict[str, Any]]:
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
                    "".join(
                        text.text or "" for text in node.findall(".//x:t", namespace)
                    )
                )
        percent_styles: set[int] = set()
        attention_styles: set[int] = set()
        if "xl/styles.xml" in archive.namelist():
            styles_root = ElementTree.fromstring(archive.read("xl/styles.xml"))
            custom_formats = {
                int(node.attrib["numFmtId"]): node.attrib.get("formatCode", "")
                for node in styles_root.findall("x:numFmts/x:numFmt", namespace)
            }
            attention_fills: set[int] = set()
            for fill_index, fill in enumerate(
                styles_root.findall("x:fills/x:fill", namespace)
            ):
                pattern = fill.find("x:patternFill", namespace)
                if pattern is None or pattern.attrib.get("patternType") != "solid":
                    continue
                foreground = pattern.find("x:fgColor", namespace)
                if foreground is None:
                    continue
                rgb = foreground.attrib.get("rgb", "").upper()
                indexed = foreground.attrib.get("indexed", "")
                # White/default fills are structural. Any other solid fill in a
                # data cell is treated as an explicit review marker.
                if rgb not in {
                    "",
                    "00000000",
                    "00FFFFFF",
                    "FFFFFFFF",
                } or indexed not in {"", "64"}:
                    attention_fills.add(fill_index)
            for style_index, style in enumerate(
                styles_root.findall("x:cellXfs/x:xf", namespace)
            ):
                format_id = int(style.attrib.get("numFmtId", "0"))
                format_code = custom_formats.get(format_id, "")
                if format_id in {9, 10} or "%" in format_code:
                    percent_styles.add(style_index)
                if int(style.attrib.get("fillId", "0")) in attention_fills:
                    attention_styles.add(style_index)
        sheet_root = ElementTree.fromstring(archive.read(sheet_path))
        result: list[dict[str, Any]] = []
        for row in sheet_root.findall(".//x:sheetData/x:row", namespace):
            values: dict[int, str] = {}
            highlighted: set[int] = set()
            for cell in row.findall("x:c", namespace):
                index = _column_index(cell.attrib.get("r", "A1"))
                cell_type = cell.attrib.get("t")
                value_node = cell.find("x:v", namespace)
                style_index = int(cell.attrib.get("s", "0"))
                if cell_type == "inlineStr":
                    value = "".join(
                        node.text or "" for node in cell.findall(".//x:t", namespace)
                    )
                elif value_node is None:
                    value = ""
                elif cell_type == "s":
                    value = shared[int(value_node.text or "0")]
                else:
                    value = value_node.text or ""
                    if value and style_index in percent_styles:
                        try:
                            value = decimal_text(Decimal(value) * Decimal("100"))
                        except InvalidOperation:
                            pass
                values[index] = value.strip()
                if style_index in attention_styles:
                    highlighted.add(index)
            if values:
                width = max(values) + 1
                result.append(
                    {
                        "row_number": int(row.attrib.get("r", len(result) + 1)),
                        "values": [values.get(index, "") for index in range(width)],
                        "highlighted": highlighted,
                    }
                )
        return result


def _normalized_header(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def _normalized_item_name(value: object) -> str:
    text = _normalized_header(value)
    return re.sub(r"[^a-zа-я0-9]+", "", text)


def _normalize_import_unit(value: object) -> str:
    text = _normalized_header(value).replace(" ", "")
    if text in {"п.м.", "п.м", "пог.м.", "пог.м", "м.п.", "м.п", "м"}:
        return "м.п."
    if text in {"шт.", "шт", "штука", "штук"}:
        return "шт"
    if text in {"м2", "м²", "кв.м.", "кв.м"}:
        return "м²"
    return str(value or "").strip() or "шт"


def _parse_import_cost(value: object) -> Decimal:
    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace("₽", "").replace("руб.", "").replace("руб", "")
    text = text.replace(",", ".")
    if not text:
        raise InvalidOperation
    return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _import_source_date(rows: list[dict[str, Any]]) -> datetime:
    for row in rows:
        for value in row["values"]:
            match = re.search(
                r"(?<!\d)(\d{1,2})[.]([01]?\d)[.](20\d{2})(?!\d)", str(value)
            )
            if match:
                day, month, year = map(int, match.groups())
                try:
                    return datetime(year, month, day)
                except ValueError:
                    continue
    return datetime.utcnow()


def _import_group(name: str, unit: str) -> str:
    normalized = name.casefold()
    if "уплотн" in normalized or "демпфер" in normalized:
        return "Уплотнители"
    # Extruded thresholds and handle/lock profiles are still profiles.  Check
    # the physical unit before semantic words such as "ручка" or "замок".
    if unit == "м.п." and any(
        word in normalized for word in ("профил", "порог", "направл", "пристеноч")
    ):
        return "Профили"
    if "ручк" in normalized:
        return "Ручки"
    if "замок" in normalized:
        return "Замки"
    if "защел" in normalized or "защёл" in normalized:
        return "Защёлки"
    return "Фурнитура"


def _import_paint_mode(name: str, group: str, unit: str) -> str:
    normalized = name.casefold()
    non_paintable = (
        group != "Профили"
        or unit != "м.п."
        or any(word in normalized for word in ("уплотн", "демпфер", "щеточ"))
    )
    return "Не красится" if non_paintable else "Красится"


def _import_finish_code(variant: models.CatalogFinishVariant) -> str:
    """Map legacy supplier-import rows without treating BASE as paintable anod."""

    explicit = str(getattr(variant, "code", "") or "").strip().upper()
    if explicit == "BASE":
        return "COLORLESS"
    if explicit == "ANOD":
        return "ANOD_UNPAINTED"
    return _finish_code(variant.name, explicit)


def _target_finish_code(item: models.CatalogItem | None, paint_mode: str = "") -> str:
    if item is not None:
        codes = {
            _import_finish_code(row) for row in item.finish_variants if row.is_active
        }
        if "ANOD_UNPAINTED" in codes:
            return "ANOD_UNPAINTED"
        if "COLORLESS" in codes:
            return "COLORLESS"
        if "ANOD" in codes:
            return "ANOD_UNPAINTED"
        if "BASE" in codes:
            return "COLORLESS"
        if (
            not codes
            and "крас" in str(item.paint_mode or "").casefold()
            and "не крас" not in str(item.paint_mode or "").casefold()
        ):
            return "ANOD_UNPAINTED"
        return "COLORLESS"
    return "COLORLESS" if paint_mode == "Не красится" else "ANOD_UNPAINTED"


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
    layout: dict[str, int] | None = None
    header_index = -1
    source_layout = False
    for index, row in enumerate(raw_rows):
        values = row["values"]
        headers = [
            _HEADER_ALIASES.get(_normalized_header(value), "") for value in values
        ]
        if "sku" in headers and "cost" in headers:
            layout = {header: column for column, header in enumerate(headers) if header}
            header_index = index
            break
        normalized_values = [_normalized_header(value) for value in values]
        if "себестоимость" in normalized_values and any(
            "наименование/артикул" in value for value in normalized_values
        ):
            # Supplier cost sheet: columns C-F are SKU, name, unit and cost,
            # while the visible A-E header is merged into one caption.
            layout = {"sku": 2, "name": 3, "unit": 4, "cost": 5}
            header_index = index
            source_layout = True
            break
    if layout is None:
        return {
            "valid": False,
            "rows": [],
            "errors": ["Обязательные колонки: Артикул и Себестоимость"],
        }
    _ensure_catalog_seed(db)
    catalog_items = db.query(models.CatalogItem).all()
    items = {item.sku.strip().upper(): item for item in catalog_items}
    items_by_name: dict[str, list[models.CatalogItem]] = {}
    for item in catalog_items:
        items_by_name.setdefault(_normalized_item_name(item.name), []).append(item)
    result_rows = []
    errors = []
    seen_skus: set[str] = set()
    effective_from = _import_source_date(raw_rows)
    import_effective_now = datetime.utcnow()
    for row in raw_rows[header_index + 1 :]:
        excel_row = int(row["row_number"])
        values = row["values"]
        mapped = {
            header: values[column] if column < len(values) else ""
            for header, column in layout.items()
        }
        sku = str(mapped.get("sku") or "").strip().upper()
        if not sku:
            continue
        if sku in seen_skus:
            errors.append(f"Строка {excel_row}: артикул {sku} указан повторно")
            continue
        seen_skus.add(sku)
        item = items.get(sku)
        name = str(mapped.get("name") or getattr(item, "name", "") or "").strip()
        unit = _normalize_import_unit(
            mapped.get("unit") or getattr(item, "unit", "") or "шт"
        )
        try:
            original_cost = _parse_import_cost(mapped.get("cost"))
        except (InvalidOperation, ValueError):
            errors.append(f"Строка {excel_row}: некорректная себестоимость для {sku}")
            continue
        conversion = ""
        cost = original_cost
        if source_layout and sku in _PACK_LENGTHS_M:
            pack_length = _PACK_LENGTHS_M[sku]
            cost = (cost / pack_length).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            unit = "м.п."
            conversion = (
                f"{money_text(original_cost)} ₽ за упаковку / "
                f"{decimal_text(pack_length)} м"
            )

        group = str(getattr(item, "group", "") or "") or _import_group(name, unit)
        paint_mode = str(getattr(item, "paint_mode", "") or "") or _import_paint_mode(
            name, group, unit
        )
        candidates = (
            []
            if item is not None
            else items_by_name.get(_normalized_item_name(name), [])
        )
        cost_column = layout["cost"]
        pending = sku in _PENDING_COST_SKUS or cost_column in row["highlighted"]
        unit_mismatch = bool(
            item is not None and _normalize_import_unit(item.unit) != unit
        )
        if pending:
            action = "skip"
            status = "pending"
        elif unit_mismatch:
            action = "review"
            status = "needs_review"
        elif item is not None:
            action = "update"
            status = "matched"
        elif candidates:
            action = "review"
            status = "needs_review"
        else:
            action = "create"
            status = "new"
        finish_code = _target_finish_code(item, paint_mode)
        current_variant = next(
            (
                variant
                for variant in getattr(item, "finish_variants", [])
                if variant.is_active and _import_finish_code(variant) == finish_code
            ),
            None,
        )
        normalized: dict[str, Any] = {
            "source_row": excel_row,
            "sku": sku,
            "name": name,
            "unit": unit,
            "cost": money_text(cost),
            "original_cost": money_text(original_cost),
            "current_cost": money_text(
                decimal_value(
                    current_variant.cost
                    if current_variant is not None
                    else getattr(item, "purchase_price", 0)
                )
            )
            if item is not None
            else "",
            "finish_code": finish_code,
            "finish_name": (
                "Анод/неокрас" if finish_code == "ANOD_UNPAINTED" else "Без цвета"
            ),
            # A supplier document date is provenance, not an instruction to
            # insert an obsolete historical price behind today's baseline.
            # Future-dated supplier prices still stay scheduled.
            "effective_from": max(effective_from, import_effective_now).isoformat(),
            "source_date": effective_from.date().isoformat(),
            "action": action,
            "status": status,
            "pending": pending,
            "conversion": conversion,
            "unit_mismatch": unit_mismatch,
            "target_item_id": item.id if item is not None else None,
            "group": group,
            "paint_mode": paint_mode,
            "system_groups": ["SLIDE_1", "SLIDE_2"],
            "candidates": [
                {
                    "id": candidate.id,
                    "sku": candidate.sku,
                    "name": candidate.name,
                    "unit": candidate.unit,
                }
                for candidate in candidates[:10]
            ],
        }
        # Preserve the legacy general price-import columns. Supplier sheets
        # intentionally change only cost and inherit every pricing factor.
        if not source_layout:
            normalized.update(
                {
                    "profile_markup_percent": mapped.get("profile_markup_percent")
                    or "",
                    "profile_discount_percent": mapped.get("profile_discount_percent")
                    or "",
                    "waste_markup_percent": mapped.get("waste_markup_percent") or "",
                    "construction_markup_percent": mapped.get(
                        "construction_markup_percent"
                    )
                    or "",
                    "construction_discount_percent": mapped.get(
                        "construction_discount_percent"
                    )
                    or "",
                    "category": mapped.get("category")
                    or (_infer_category(item) if item is not None else "component"),
                    "min_margin_percent": mapped.get("min_margin_percent") or "",
                    "effective_from": _excel_date(
                        mapped.get("effective_from") or ""
                    ).isoformat(),
                }
            )
        result_rows.append(normalized)
    return {
        "valid": not errors and bool(result_rows),
        "can_apply": not errors
        and any(row["action"] in {"update", "create"} for row in result_rows)
        and not any(row["action"] == "review" for row in result_rows),
        "source_date": effective_from.date().isoformat(),
        "summary": {
            status: sum(row["status"] == status for row in result_rows)
            for status in ("matched", "new", "needs_review", "pending")
        },
        "rows": result_rows,
        "errors": errors,
    }


@router.post("/catalog/import/preview")
async def preview_price_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Поддерживается только XLSX")
    content = await file.read()
    return _import_preview(db, content)


def _create_import_catalog_item(
    row: dict[str, Any], cost: Decimal
) -> models.CatalogItem:
    name = str(row.get("name") or row.get("sku") or "Позиция каталога").strip()
    unit = _normalize_import_unit(row.get("unit"))
    group = str(row.get("group") or _import_group(name, unit)).strip()
    paint_mode = str(
        row.get("paint_mode") or _import_paint_mode(name, group, unit)
    ).strip()
    finish_code = str(
        row.get("finish_code") or _target_finish_code(None, paint_mode)
    ).upper()
    markup = Decimal("35") if group in {"Профили", "Уплотнители"} else Decimal("40")
    waste = Decimal("4") if unit == "м.п." else Decimal("0")
    finish_codes = (
        ["ANOD_UNPAINTED", "RAL_STANDARD", "RAL_MOIRE", "SUBLIMATION"]
        if paint_mode != "Не красится"
        else ["COLORLESS"]
    )
    item = models.CatalogItem(
        sku=str(row.get("sku") or "").strip().upper(),
        name=name,
        group=group,
        system="СЛАЙД",
        system_groups=json.dumps(
            row.get("system_groups") or ["SLIDE_1", "SLIDE_2"],
            ensure_ascii=False,
        ),
        unit=unit,
        purchase_price=float(cost),
        markup_percent=float(markup),
        weight=0,
        waste_percent=float(waste),
        section_width_mm=0,
        section_height_mm=0,
        image_file=None,
        paint_mode=paint_mode,
        color_variants=json.dumps(
            [FINISH_DEFINITIONS[code][0] for code in finish_codes],
            ensure_ascii=False,
        ),
        supplier="Raluma",
        is_active=True,
        note="Создано при сверке файла себестоимости",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    for code in finish_codes:
        finish_name, requires_paint = FINISH_DEFINITIONS[code]
        selected_cost = cost if code == finish_code else Decimal("0")
        item.finish_variants.append(
            models.CatalogFinishVariant(
                code=code,
                name=finish_name,
                price=selected_cost,
                cost=selected_cost,
                profile_markup_percent=markup,
                profile_discount_percent=0,
                waste_markup_percent=waste if code != "SUBLIMATION" else 0,
                construction_markup_percent=0,
                construction_discount_percent=0,
                requires_paint=requires_paint,
                is_active=True,
            )
        )
    return item


def _import_version_payload(
    item: models.CatalogItem,
    row: dict[str, Any],
    cost: Decimal,
    variant: models.CatalogFinishVariant | None,
    reason: str,
) -> schemas.CatalogPriceVersionCreate:
    def selected(field: str, fallback: object) -> object:
        value = row.get(field)
        return fallback if value in (None, "") else value

    variant_id = variant.id if variant is not None else None
    effective_from = normalized_at(_excel_date(str(row.get("effective_from") or "")))
    current = max(
        (
            version
            for version in item.price_versions
            if version.finish_variant_id == variant_id
            and normalized_at(version.effective_from) <= effective_from
        ),
        key=lambda version: (version.effective_from, version.id or 0),
        default=None,
    )
    fallback = current or variant
    return schemas.CatalogPriceVersionCreate(
        cost=cost,
        profile_markup_percent=selected(
            "profile_markup_percent",
            fallback.profile_markup_percent
            if fallback is not None
            else item.markup_percent,
        ),
        profile_discount_percent=selected(
            "profile_discount_percent",
            fallback.profile_discount_percent if fallback is not None else 0,
        ),
        waste_markup_percent=selected(
            "waste_markup_percent",
            fallback.waste_markup_percent
            if fallback is not None
            else item.waste_percent,
        ),
        construction_markup_percent=selected(
            "construction_markup_percent",
            fallback.construction_markup_percent if fallback is not None else 0,
        ),
        construction_discount_percent=selected(
            "construction_discount_percent",
            fallback.construction_discount_percent if fallback is not None else 0,
        ),
        category=selected(
            "category",
            current.category if current is not None else _infer_category(item),
        ),
        unit=_normalize_import_unit(
            selected("unit", current.unit if current is not None else item.unit)
        ),
        min_margin_percent=selected(
            "min_margin_percent",
            current.min_margin_percent if current is not None else 0,
        ),
        effective_from=effective_from,
        reason=reason,
    )


@router.post("/catalog/import/apply", status_code=201)
def apply_price_import(
    data: schemas.CatalogPriceImportApply,
    db: Session = Depends(get_db),
    actor: models.User = Depends(require_admin),
):
    _ensure_catalog_seed(db)
    items = {
        item.sku.strip().upper(): item for item in db.query(models.CatalogItem).all()
    }
    items_by_id = {item.id: item for item in items.values()}
    errors: list[str] = []
    prepared: list[tuple[dict[str, Any], models.CatalogItem | None, Decimal]] = []
    seen_sources: set[str] = set()
    seen_targets: set[tuple[int | str, str]] = set()
    skipped: list[dict[str, str]] = []
    for index, row in enumerate(data.rows, start=1):
        sku = str(row.get("sku") or "").strip().upper()
        action = str(row.get("action") or "update").strip().lower()
        if action == "skip":
            skipped.append({"sku": sku, "reason": str(row.get("status") or "skipped")})
            continue
        if action not in {"update", "create"}:
            errors.append(
                f"Строка {index}: для {sku or '—'} завершите сверку или пропустите позицию"
            )
            continue
        if sku in seen_sources:
            errors.append(f"Строка {index}: артикул {sku or '—'} указан повторно")
            continue
        seen_sources.add(sku)
        if not sku:
            errors.append(f"Строка {index}: не указан артикул")
            continue
        try:
            cost = _parse_import_cost(row.get("cost"))
        except (InvalidOperation, ValueError):
            errors.append(f"Строка {index}: некорректная себестоимость для {sku}")
            continue
        target_id = row.get("target_item_id")
        item = (
            items_by_id.get(int(target_id))
            if target_id not in (None, "")
            else items.get(sku)
        )
        if action == "create":
            existing_item = items.get(sku)
            if existing_item is not None:
                source_unit = _normalize_import_unit(
                    row.get("unit") or existing_item.unit
                )
                if _normalize_import_unit(existing_item.unit) != source_unit:
                    errors.append(
                        f"Строка {index}: единица {source_unit} не совпадает с "
                        f"{existing_item.unit} у {existing_item.sku}"
                    )
                    continue
                # Re-applying the same reviewed import is idempotent: a row
                # created by the first pass becomes an update on later passes.
                item = existing_item
                target_key = int(existing_item.id)
            elif not str(row.get("name") or "").strip():
                errors.append(
                    f"Строка {index}: для новой позиции {sku} не указано название"
                )
                continue
            else:
                target_key = f"new:{sku}"
                item = None
        elif item is None:
            errors.append(f"Строка {index}: целевая позиция {sku} отсутствует")
            continue
        else:
            target_key = int(item.id)
            source_unit = _normalize_import_unit(row.get("unit") or item.unit)
            if _normalize_import_unit(item.unit) != source_unit:
                errors.append(
                    f"Строка {index}: единица {source_unit} не совпадает с "
                    f"{item.unit} у {item.sku}"
                )
                continue
        finish_code = str(row.get("finish_code") or "COLORLESS").upper()
        identity = (target_key, finish_code)
        if identity in seen_targets:
            errors.append(
                f"Строка {index}: цена исполнения {finish_code} указана повторно"
            )
            continue
        seen_targets.add(identity)
        prepared.append((row, item, cost))
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    created_versions: list[models.CatalogPriceVersion] = []
    created_items: list[models.CatalogItem] = []
    unchanged: list[str] = []
    try:
        for row, item, cost in prepared:
            if item is None:
                item = _create_import_catalog_item(row, cost)
                db.add(item)
                db.flush()
                created_items.append(item)
                items[item.sku] = item
            finish_code = str(
                row.get("finish_code") or _target_finish_code(item)
            ).upper()
            variant = next(
                (
                    candidate
                    for candidate in item.finish_variants
                    if candidate.is_active
                    and _import_finish_code(candidate) == finish_code
                ),
                None,
            )
            if item.finish_variants and variant is None:
                raise ValueError(f"У {item.sku} отсутствует исполнение {finish_code}")
            payload = _import_version_payload(item, row, cost, variant, data.reason)
            _validate_price_payload(payload)
            variant_id = variant.id if variant is not None else None
            existing = next(
                (
                    version
                    for version in item.price_versions
                    if version.finish_variant_id == variant_id
                    and decimal_value(version.cost) == decimal_value(payload.cost)
                    and _normalize_datetime(version.effective_from)
                    == _normalize_datetime(payload.effective_from)
                    and version.reason.strip() == data.reason.strip()
                ),
                None,
            )
            if existing is not None:
                unchanged.append(item.sku)
                continue
            version = _new_version(
                item,
                payload,
                actor,
                finish_variant_id=variant_id,
            )
            item.price_versions.append(version)
            if variant is not None:
                sync_variant_cache(item, variant)
                variant.updated_at = datetime.utcnow()
            if normalized_at(payload.effective_from) <= datetime.utcnow():
                item.purchase_price = float(cost)
            item.updated_at = datetime.utcnow()
            created_versions.append(version)
        db.commit()
    except (ValidationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"errors": [str(exc)]}) from exc
    except Exception:
        db.rollback()
        raise
    for version in created_versions:
        db.refresh(version)
    return {
        "versions": [_version_dict(version) for version in created_versions],
        "created_items": [
            {"id": item.id, "sku": item.sku, "name": item.name}
            for item in created_items
        ],
        "skipped": skipped,
        "unchanged": unchanged,
    }


@router.get("/dealers")
def list_pricing_dealers(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
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
    _: models.User = Depends(require_admin),
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
    actor: models.User = Depends(require_admin),
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


@router.get("/projects/{project_id}")
def get_internal_project_quote(
    project_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_current_user),
):
    project = db.query(models.Project).filter_by(id=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if actor.role == "dealer":
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    evaluation_at = datetime.utcnow()
    result = internal_quote_state(db, project, at=evaluation_at)
    # A fixed KP remains immutable, but the editor must let staff inspect the
    # next calculation before explicitly fixing a new revision. Never expose
    # internal calculation payloads as a substitute for this public projection.
    pending_public = result.get("calculation", {}).get("public")
    pending_quote = (
        safe_public_payload(pending_public)
        if isinstance(pending_public, dict)
        else public_quote(db, project, at=evaluation_at)
    )
    preview_token = current_quote_preview_token(db, project, at=evaluation_at)
    result["pending_quote"] = pending_quote
    result["preview_token"] = preview_token
    if not user_can_manage_prices(actor):
        config = result["config"]
        result = {
            "revision": result["revision"],
            "status": result["status"],
            "stale": result["stale"],
            "config": {
                "validity_days": config["validity_days"],
                "manufacturing_term": config["manufacturing_term"],
                "payment_terms": config["payment_terms"],
                "services": [
                    {key: value for key, value in row.items() if key != "actual_cost"}
                    for row in config["services"]
                ],
                "discounts": config["discounts"],
                "overrides": [],
                "margin_override_comment": "",
            },
            "missing_prices": [],
            "pending_warnings": list(pending_quote.get("warnings") or []),
            "pending_quote": pending_quote,
            "preview_token": preview_token,
            "margin_approval": {
                "required": False,
                "valid": False,
                "context_signature": "",
                "target_revision": result["revision"],
                "approved_revision": None,
                "comment": "",
                "approved_by": None,
                "approved_at": None,
            },
            "calculation": {},
        }
    db.commit()
    return result
