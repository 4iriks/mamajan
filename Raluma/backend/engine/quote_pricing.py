"""Точный расчёт стоимости коммерческого предложения СЛАЙД.

Публичный результат намеренно отделён от внутренней расшифровки: наружу не
попадают себестоимость, коэффициенты, дилерская наценка, маржа и BOM.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from math import ceil
from typing import Any, Iterable

from sqlalchemy.orm import Session

import models
from engine.glass_types import normalize_slide_glass_type
from engine.slide_calc import calculate_slide


MONEY = Decimal("0.01")
WHOLE_RUBLE = Decimal("1")
HUNDRED = Decimal("100")
ZERO = Decimal("0")

PRICE_CATEGORIES = {"profile", "construction", "component", "service"}
VAT_MODES = {"none", "included", "on_top"}
MANUAL_SERVICE_UNITS = (
    "п.м.",
    "шт.",
    "кв.м.",
)
QUOTE_SNAPSHOT_VERSION = 2

PUBLIC_QUOTE_FIELDS = {
    "project",
    "revision",
    "status",
    "fixed_at",
    "currency",
    "lines",
    "totals",
    "vat",
    "validity_days",
    "valid_until",
    "manufacturing_term",
    "payment_terms",
    "missing_price_count",
    "warnings",
    "export_allowed",
    "stale",
}
PUBLIC_LINE_FIELDS = {
    "id",
    "name",
    "category",
    "quantity",
    "unit",
    "unit_price_before_discount",
    "discount_percent",
    "unit_discount_amount",
    "unit_final_price",
    "line_total_before_discount",
    "line_discount_amount",
    "line_total",
    "document_line_total_before_discount",
    "document_line_discount_amount",
    "document_line_total",
    "document_unit_price_before_discount",
    "document_unit_discount_amount",
    "document_unit_final_price",
    "section_details",
    "breakdown",
}
PUBLIC_PROJECT_FIELDS = {"id", "number", "customer"}
PUBLIC_TOTAL_FIELDS = {
    "before_discount",
    "discount",
    "subtotal",
    "vat",
    "grand_total",
    "document_before_discount",
    "document_discount",
    "document_grand_total",
}
PUBLIC_VAT_FIELDS = {"mode", "rate", "amount", "document_amount"}
PUBLIC_SECTION_DETAIL_FIELDS = {
    "section_id",
    "name",
    "width_mm",
    "height_mm",
    "panels",
    "quantity",
    "glass_area_m2",
    "color",
    "system",
    "glass_type",
    "threshold",
    "rails",
    "slide_rows",
    "first_panel_inside",
    "unused_track",
    "slide_direction",
    "panel_width_total_mm",
    "panel_geometry",
}
PUBLIC_PANEL_GEOMETRY_FIELDS = {
    "index",
    "number",
    "width_mm",
    "rail",
    "direction",
    "deaf",
}
PUBLIC_BREAKDOWN_FIELDS = {
    "sku",
    "name",
    "quantity",
    "unit",
    "unit_price",
    "line_total",
}


class QuotePricingError(ValueError):
    pass


class QuoteExportBlocked(QuotePricingError):
    def __init__(self, public_payload: dict[str, Any]):
        super().__init__("Коммерческое предложение нельзя экспортировать")
        self.public_payload = public_payload


def safe_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply an allow-list at every dealer-facing API/document boundary."""
    if not isinstance(payload, dict):
        payload = {}
    safe = {key: value for key, value in payload.items() if key in PUBLIC_QUOTE_FIELDS}
    safe_lines = []
    for line in payload.get("lines") or []:
        if not isinstance(line, dict):
            continue
        safe_line = {
            key: value for key, value in line.items() if key in PUBLIC_LINE_FIELDS
        }
        details = line.get("section_details")
        if isinstance(details, dict):
            safe_details = {
                key: value
                for key, value in details.items()
                if key in PUBLIC_SECTION_DETAIL_FIELDS
            }
            safe_details["panel_geometry"] = [
                {
                    key: value
                    for key, value in panel.items()
                    if key in PUBLIC_PANEL_GEOMETRY_FIELDS
                }
                for panel in details.get("panel_geometry") or []
                if isinstance(panel, dict)
            ]
            safe_line["section_details"] = safe_details
        else:
            safe_line.pop("section_details", None)
        safe_line["breakdown"] = [
            {
                key: value
                for key, value in item.items()
                if key in PUBLIC_BREAKDOWN_FIELDS
            }
            for item in line.get("breakdown") or []
            if isinstance(item, dict)
        ]
        safe_lines.append(safe_line)
    safe["lines"] = safe_lines
    for field, allowed in (
        ("project", PUBLIC_PROJECT_FIELDS),
        ("totals", PUBLIC_TOTAL_FIELDS),
        ("vat", PUBLIC_VAT_FIELDS),
    ):
        value = payload.get(field)
        safe[field] = (
            {key: item for key, item in value.items() if key in allowed}
            if isinstance(value, dict)
            else {}
        )
    if "document_amount" not in safe["vat"]:
        safe["vat"]["document_amount"] = int(
            decimal_value(safe["vat"].get("amount")).quantize(
                WHOLE_RUBLE,
                rounding=ROUND_HALF_UP,
            )
        )
    if "missing_price_count" not in safe:
        legacy_missing = payload.get("missing_prices", [])
        safe["missing_price_count"] = (
            len(legacy_missing) if isinstance(legacy_missing, list) else 0
        )
    safe["warnings"] = (
        ["Расчёт требует проверки менеджером."]
        if not bool(payload.get("export_allowed"))
        else []
    )
    return safe


def decimal_value(value: Any, default: Decimal = ZERO) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return default


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def money_text(value: Decimal) -> str:
    return f"{money(value):.2f}"


def decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f") if normalized else "0"


def _markup_factor(percent: Any) -> Decimal:
    return Decimal("1") + decimal_value(percent) / HUNDRED


def _discount_factor(percent: Any) -> Decimal:
    return Decimal("1") - decimal_value(percent) / HUNDRED


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _json_load(raw: str | None, fallback: Any) -> Any:
    try:
        parsed = json.loads(raw or "")
    except (TypeError, json.JSONDecodeError):
        return fallback
    return parsed


def _canonical_unit(value: str | None) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    aliases = {
        "м.п.": "m",
        "м.п": "m",
        "п.м.": "m",
        "п.м": "m",
        "пог.м": "m",
        "пог. м": "m",
        "погонный метр": "m",
        "м": "m",
        "м2": "m2",
        "м²": "m2",
        "кв.м.": "m2",
        "кв.м": "m2",
        "кв. м": "m2",
        "шт.": "piece",
        "шт": "piece",
        "штука": "piece",
        "компл.": "set",
        "компл": "set",
        "комплект": "set",
    }
    return aliases.get(text, text)


def _units_compatible(required: str, priced: str) -> bool:
    return _canonical_unit(required) == _canonical_unit(priced)


def _active_price_versions(
    db: Session, at: datetime
) -> dict[str, tuple[models.CatalogItem, models.CatalogPriceVersion]]:
    versions = (
        db.query(models.CatalogPriceVersion)
        .join(models.CatalogItem)
        .filter(
            models.CatalogItem.is_active == True,  # noqa: E712
            models.CatalogPriceVersion.effective_from <= at,
        )
        .order_by(
            models.CatalogPriceVersion.catalog_item_id,
            models.CatalogPriceVersion.effective_from.desc(),
            models.CatalogPriceVersion.id.desc(),
        )
        .all()
    )
    active: dict[str, tuple[models.CatalogItem, models.CatalogPriceVersion]] = {}
    for version in versions:
        item = version.catalog_item
        active.setdefault(item.sku, (item, version))
    return active


def get_pricing_settings(db: Session) -> models.PricingSettings:
    settings = db.query(models.PricingSettings).filter_by(id=1).first()
    if settings is None:
        settings = models.PricingSettings(
            id=1,
            include_waste_markup=False,
            default_vat_rate=Decimal("20"),
            updated_at=datetime.utcnow(),
        )
        db.add(settings)
        db.flush()
    return settings


def _dealer_terms(db: Session, owner: models.User | None) -> dict[str, Decimal]:
    zeros = {
        "dealer_markup_percent": ZERO,
        "profile_discount_percent": ZERO,
        "construction_discount_percent": ZERO,
        "component_discount_percent": ZERO,
        "service_discount_percent": ZERO,
    }
    if owner is None or owner.role != "dealer":
        return zeros
    terms = (
        db.query(models.DealerPricingTerms)
        .filter(models.DealerPricingTerms.user_id == owner.id)
        .first()
    )
    if terms is None:
        return zeros
    return {
        key: decimal_value(getattr(terms, key))
        for key in zeros
    }


def _discount_for_category(terms: dict[str, Decimal], category: str) -> Decimal:
    field = {
        "profile": "profile_discount_percent",
        "construction": "construction_discount_percent",
        "component": "component_discount_percent",
        "service": "service_discount_percent",
    }[category]
    return terms[field]


def _paint_color(section: object, calc: object) -> str:
    color = " ".join(str(getattr(calc, "color_text", "") or "").split())
    if color:
        return color
    painting_type = " ".join(
        str(getattr(section, "painting_type", "") or "").split()
    )
    return painting_type or "Без цвета"


def _price_sku(prefix: str, *parts: object) -> str:
    normalized = [" ".join(str(part or "").strip().upper().split()) for part in parts]
    return "|".join((prefix, *normalized))


def _parse_extra_components(raw: str | None) -> list[dict[str, Any]]:
    parsed = _json_load(raw, [])
    return [row for row in parsed if isinstance(row, dict)] if isinstance(parsed, list) else []


def _slide_panel_widths(calc: object, panels: int, fallback_width: Decimal) -> list[Decimal]:
    physical = sorted(
        list(getattr(calc, "panel_glass", None) or []),
        key=lambda panel: int(getattr(panel, "panel", 0) or 0),
    )
    if len(physical) >= panels:
        return [
            max(decimal_value(getattr(panel, "width_mm", 0)), Decimal("1"))
            for panel in physical[:panels]
        ]
    fallback = max(fallback_width / max(panels, 1), Decimal("1"))
    return [fallback for _ in range(max(panels, 1))]


def _is_no_option(value: object) -> bool:
    text = " ".join(str(value or "").strip().lower().strip("—- ").split())
    return not text or text.startswith(("без", "нет"))


def _section_snapshot(section: object, calc: object) -> dict[str, Any]:
    """Capture only dealer-safe inputs needed to reproduce both quote sketches."""

    panels = max(int(getattr(section, "panels", 0) or 0), 1)
    width = decimal_value(getattr(section, "width", 0))
    height = decimal_value(getattr(section, "height", 0))
    quantity = max(int(getattr(section, "quantity", 0) or 0), 1)
    slide_rows = 2 if int(getattr(section, "slide_rows", 1) or 1) == 2 else 1
    first_inside = str(getattr(section, "first_panel_inside", "") or "Справа")
    first_right = slide_rows == 1 and first_inside == "Справа"
    panel_widths = _slide_panel_widths(calc, panels, width)
    panel_rails = list(getattr(calc, "panel_rails", None) or [])

    left_handle = str(getattr(section, "handle_left", "") or "Без").lower()
    right_handle = str(getattr(section, "handle_right", "") or "Без").lower()
    left_deaf = (
        ("глух" in left_handle or _is_no_option(left_handle))
        and _is_no_option(getattr(section, "lock_left", None))
        and not bool(getattr(section, "profile_left_handle_bar", False))
    )
    right_deaf = (
        ("глух" in right_handle or _is_no_option(right_handle))
        and _is_no_option(getattr(section, "lock_right", None))
        and not bool(getattr(section, "profile_right_handle_bar", False))
    )
    center_handle = str(getattr(section, "center_handle", "") or "").lower()
    center_deaf = slide_rows == 2 and (not center_handle or "глух" in center_handle)
    center_left = panels // 2 - 1
    center_right = panels // 2
    room_bidirectional = slide_rows == 1 and not left_deaf and not right_deaf

    geometry = []
    for index, panel_width in enumerate(panel_widths):
        is_center = slide_rows == 2 and index in {center_left, center_right}
        deaf = (
            (index == 0 and left_deaf)
            or (index == panels - 1 and right_deaf)
            or (is_center and center_deaf)
        )
        arrow_left = index < panels / 2 if slide_rows == 2 else first_right
        bidirectional = room_bidirectional or (
            slide_rows == 2
            and (
                (index < panels / 2 and not left_deaf)
                or (index >= panels / 2 and not right_deaf)
            )
        )
        geometry.append(
            {
                "index": index + 1,
                "number": (
                    index + 1
                    if slide_rows == 2
                    else panels - index
                    if first_right
                    else index + 1
                ),
                "width_mm": decimal_text(panel_width),
                "rail": int(panel_rails[index]) if index < len(panel_rails) else index,
                "direction": (
                    "none"
                    if deaf
                    else "both"
                    if bidirectional
                    else "left"
                    if arrow_left
                    else "right"
                ),
                "deaf": deaf,
            }
        )

    glass_area = sum(
        (
            decimal_value(glass.width_mm)
            * decimal_value(glass.height_mm)
            * decimal_value(glass.qty)
            / Decimal("1000000")
        )
        for glass in getattr(calc, "glass", [])
        if int(getattr(glass, "qty", 0) or 0) > 0
    )
    return {
        "section_id": int(getattr(section, "id", 0) or 0),
        "name": str(getattr(section, "name", "") or "Секция"),
        "width_mm": decimal_text(width),
        "height_mm": decimal_text(height),
        "panels": panels,
        "quantity": quantity,
        "glass_area_m2": decimal_text(glass_area.quantize(Decimal("0.001"))),
        "color": _paint_color(section, calc),
        "system": "СЛАЙД",
        "glass_type": normalize_slide_glass_type(
            getattr(calc, "glass_type", None) or getattr(section, "glass_type", None)
        ),
        "threshold": str(
            getattr(calc, "threshold_text", "")
            or getattr(section, "threshold", "")
            or ""
        ),
        "rails": max(int(getattr(section, "rails", 0) or 0), 1),
        "slide_rows": slide_rows,
        "first_panel_inside": first_inside,
        "unused_track": str(getattr(section, "unused_track", "") or ""),
        "slide_direction": (
            "both" if slide_rows == 2 else "left" if first_right else "right"
        ),
        "panel_width_total_mm": decimal_text(sum(panel_widths, ZERO)),
        "panel_geometry": geometry,
    }


def _section_breakdown_exact(
    priced_bom: list[dict[str, Any]],
    sale_factor: Decimal,
    section_total: Decimal,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    public_sources = {"profile", "component", "extra_component"}
    public_total = ZERO
    for row in priced_bom:
        if row.get("source") not in public_sources:
            continue
        key = (str(row["sku"]), str(row["name"]), str(row["unit"]))
        grouped_row = grouped.setdefault(
            key,
            {
                "sku": key[0],
                "name": key[1],
                "quantity_exact": ZERO,
                "unit": key[2],
                "total_exact": ZERO,
            },
        )
        grouped_row["quantity_exact"] += decimal_value(row["quantity"])
        grouped_row["total_exact"] += decimal_value(row["internal_total"]) * sale_factor

    result = []
    for row in sorted(grouped.values(), key=lambda item: (item["sku"], item["name"])):
        total = max(ZERO, row.pop("total_exact"))
        quantity = row.pop("quantity_exact")
        public_total += total
        result.append(
            {
                **row,
                "quantity": decimal_text(quantity),
                "exact_total": total,
            }
        )
    result.append(
        {
            "sku": "",
            "name": "Стекло, покраска и изготовление",
            "quantity": "1",
            "unit": "компл.",
            "exact_total": max(ZERO, section_total - public_total),
        }
    )
    return result


def _section_requirements(section: object) -> tuple[object, list[dict[str, Any]]]:
    calc = calculate_slide(section)
    required: list[dict[str, Any]] = []
    section_quantity = decimal_value(
        getattr(section, "quantity", 1), Decimal("1")
    )

    for profile in calc.profiles:
        quantity = decimal_value(profile.length_mm) * decimal_value(profile.qty) / 1000
        if quantity <= 0 or not str(profile.article or "").strip():
            continue
        required.append(
            {
                "sku": str(profile.article).strip(),
                "name": str(profile.name or profile.article),
                "category": "profile",
                "unit": "п.м.",
                "quantity": quantity,
                "source": "profile",
            }
        )

    for hardware in calc.hardware:
        if hardware.sub_items:
            for sub_item in hardware.sub_items:
                quantity = decimal_value(sub_item.value)
                if quantity <= 0 or not str(sub_item.article or "").strip():
                    continue
                required.append(
                    {
                        "sku": str(sub_item.article).strip(),
                        "name": f"{hardware.name} {sub_item.label}".strip(),
                        "category": "component",
                        "unit": hardware.unit or "шт",
                        "quantity": quantity,
                        "source": "component",
                    }
                )
            continue
        quantity = decimal_value(hardware.value)
        if quantity <= 0 or not str(hardware.article or "").strip():
            continue
        required.append(
            {
                "sku": str(hardware.article).strip(),
                "name": str(hardware.name or hardware.article),
                "category": "component",
                "unit": hardware.unit or "шт",
                "quantity": quantity,
                "source": "component",
            }
        )

    glass_area = sum(
        (
            decimal_value(glass.width_mm)
            * decimal_value(glass.height_mm)
            * decimal_value(glass.qty)
            / Decimal("1000000")
        )
        for glass in calc.glass
        if glass.qty > 0
    )
    if glass_area > 0:
        glass_type = normalize_slide_glass_type(
            calc.glass_type or getattr(section, "glass_type", "Стекло")
        )
        required.append(
            {
                "sku": _price_sku("GLASS", glass_type),
                "name": glass_type,
                "category": "component",
                "unit": "м²",
                "quantity": glass_area,
                "source": "glass",
            }
        )

    paint_groups: dict[tuple[str, str, str, str, int], int] = defaultdict(int)
    paint_type = " ".join(
        str(getattr(section, "painting_type", "") or "Покрытие").split()
    )
    paint_color = _paint_color(section, calc)
    for profile in calc.profiles:
        if not profile.painted or profile.length_mm <= 0 or profile.qty <= 0:
            continue
        clean = int(ceil(profile.length_mm / 50) * 50)
        allowance = clean + 50
        key = (
            str(profile.article),
            str(profile.name),
            paint_type,
            paint_color,
            allowance,
        )
        paint_groups[key] += int(profile.qty)
    for (article, name, coating, color, allowance), quantity in paint_groups.items():
        total_m = decimal_value(round(quantity * allowance / 1000, 1))
        if total_m <= 0:
            continue
        required.append(
            {
                "sku": _price_sku("PAINT", article, coating, color),
                "name": f"Покраска {name}, {coating}, {color}",
                "category": "service",
                "unit": "п.м.",
                "quantity": total_m,
                "source": "paint",
            }
        )

    work_area = (
        decimal_value(getattr(section, "width", 0))
        * decimal_value(getattr(section, "height", 0))
        * decimal_value(getattr(section, "quantity", 1), Decimal("1"))
        / Decimal("1000000")
    )
    if work_area > 0:
        required.append(
            {
                "sku": "WORK-SLIDE",
                "name": "Изготовление конструкции СЛАЙД",
                "category": "service",
                "unit": "м²",
                "quantity": work_area,
                "source": "fabrication",
            }
        )

    for extra in _parse_extra_components(getattr(section, "extra_components", None)):
        sku = str(extra.get("sku") or extra.get("art") or "").strip()
        quantity = (
            decimal_value(extra.get("qty") or extra.get("quantity"))
            * section_quantity
        )
        if not sku or quantity <= 0:
            continue
        required.append(
            {
                "sku": sku,
                "name": str(extra.get("name") or sku).strip(),
                "category": "component",
                "unit": str(extra.get("unit") or "шт").strip(),
                "quantity": quantity,
                "source": "extra_component",
            }
        )

    # calc.screws намеренно не включаются: крепёж входит в стоимость монтажа.
    return calc, required


def _price_requirement(
    required: dict[str, Any],
    active: dict[str, tuple[models.CatalogItem, models.CatalogPriceVersion]],
    overrides: dict[str, dict[str, Any]],
    include_waste_markup: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    sku = required["sku"]
    override = overrides.get(sku)
    item_and_version = active.get(sku)
    if item_and_version is None and override is None:
        return None, {
            "code": "missing_price",
            "sku": sku,
            "name": required["name"],
            "unit": required["unit"],
        }

    if override is not None:
        cost = decimal_value(override.get("cost"))
        version = None
        price_unit = required["unit"]
        category = required["category"]
        profile_markup = ZERO
        profile_discount = ZERO
        waste_markup = ZERO
        construction_markup = ZERO
        construction_discount = ZERO
        min_margin = ZERO
    else:
        item, version = item_and_version
        if not _units_compatible(required["unit"], version.unit):
            return None, {
                "code": "unit_mismatch",
                "sku": sku,
                "name": required["name"],
                "unit": required["unit"],
                "priced_unit": version.unit,
            }
        cost = decimal_value(version.cost)
        price_unit = version.unit
        category = version.category
        profile_markup = decimal_value(version.profile_markup_percent)
        profile_discount = decimal_value(version.profile_discount_percent)
        waste_markup = decimal_value(version.waste_markup_percent)
        construction_markup = decimal_value(version.construction_markup_percent)
        construction_discount = decimal_value(version.construction_discount_percent)
        min_margin = decimal_value(version.min_margin_percent)

    quantity = decimal_value(required["quantity"])
    base_cost = cost * quantity
    multiplier = (
        _markup_factor(profile_markup)
        * _discount_factor(profile_discount)
        * _markup_factor(construction_markup)
        * _discount_factor(construction_discount)
    )
    if include_waste_markup:
        multiplier *= _markup_factor(waste_markup)
    internal_total = money(base_cost * multiplier)
    minimum_total = money(base_cost * _markup_factor(min_margin))
    return {
        **required,
        "quantity": decimal_text(quantity),
        "catalog_category": category,
        "price_unit": price_unit,
        "price_version_id": version.id if version is not None else None,
        "override_comment": str(override.get("comment") or "") if override else "",
        "cost": money_text(cost),
        "base_cost_total": money_text(base_cost),
        "profile_markup_percent": decimal_text(profile_markup),
        "profile_discount_percent": decimal_text(profile_discount),
        "waste_markup_percent": decimal_text(waste_markup),
        "waste_markup_applied": include_waste_markup,
        "construction_markup_percent": decimal_text(construction_markup),
        "construction_discount_percent": decimal_text(construction_discount),
        "min_margin_percent": decimal_text(min_margin),
        "internal_total": money_text(internal_total),
        "minimum_total": money_text(minimum_total),
    }, None


def _allocate_whole_rubles(values: Iterable[Decimal]) -> list[int]:
    source = [max(ZERO, value) for value in values]
    if not source:
        return []
    floors = [int(value.quantize(WHOLE_RUBLE, rounding=ROUND_FLOOR)) for value in source]
    target = int(sum(source, ZERO).quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP))
    remaining = target - sum(floors)
    order = sorted(
        range(len(source)),
        key=lambda index: (source[index] - Decimal(floors[index]), -index),
        reverse=True,
    )
    result = list(floors)
    for offset in range(max(remaining, 0)):
        result[order[offset % len(order)]] += 1
    return result


def _allocate_whole_rubles_to_target(
    values: Iterable[Decimal],
    target: int,
) -> list[int]:
    """Allocate non-negative values to an already fixed document-line total."""

    source = [max(ZERO, decimal_value(value)) for value in values]
    if not source:
        return []
    floors = [int(value.quantize(WHOLE_RUBLE, rounding=ROUND_FLOOR)) for value in source]
    result = list(floors)
    delta = int(target) - sum(result)
    if delta >= 0:
        order = sorted(
            range(len(source)),
            key=lambda index: (source[index] - Decimal(floors[index]), -index),
            reverse=True,
        )
        for offset in range(delta):
            result[order[offset % len(order)]] += 1
        return result

    order = sorted(
        range(len(source)),
        key=lambda index: (source[index] - Decimal(floors[index]), index),
    )
    for _ in range(-delta):
        for index in order:
            if result[index] > 0:
                result[index] -= 1
                break
    return result


def _vat_values(
    subtotal: Decimal,
    mode: str,
    rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return VAT amount, grand total and the document-line display factor."""
    if mode == "on_top":
        amount = money(subtotal * rate / HUNDRED)
        return amount, money(subtotal + amount), _markup_factor(rate)
    if mode == "included" and rate > 0:
        amount = money(subtotal * rate / (HUNDRED + rate))
        return amount, subtotal, Decimal("1")
    return ZERO, subtotal, Decimal("1")


def _public_line(
    *,
    line_id: str,
    name: str,
    category: str,
    quantity: Decimal,
    unit: str,
    internal_total: Decimal,
    terms: dict[str, Decimal],
) -> tuple[dict[str, Any], dict[str, Decimal]]:
    dealer_markup = terms["dealer_markup_percent"]
    discount = _discount_for_category(terms, category)
    before_discount = money(internal_total * _markup_factor(dealer_markup))
    discount_amount = money(before_discount * discount / HUNDRED)
    total = money(before_discount - discount_amount)
    divisor = quantity if quantity > 0 else Decimal("1")
    public = {
        "id": line_id,
        "name": name,
        "category": category,
        "quantity": decimal_text(quantity),
        "unit": unit,
        "unit_price_before_discount": money_text(before_discount / divisor),
        "discount_percent": decimal_text(discount),
        "unit_discount_amount": money_text(discount_amount / divisor),
        "unit_final_price": money_text(total / divisor),
        "line_total_before_discount": money_text(before_discount),
        "line_discount_amount": money_text(discount_amount),
        "line_total": money_text(total),
    }
    exact = {
        "before_discount": before_discount,
        "discount_amount": discount_amount,
        "total": total,
    }
    return public, exact


def _quote_signature(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    at: datetime,
) -> str:
    active = _active_price_versions(db, at)
    catalog_rows = (
        db.query(models.CatalogItem)
        .order_by(models.CatalogItem.id)
        .all()
    )
    settings = get_pricing_settings(db)
    owner = project.owner
    terms_row = None
    if owner is not None and owner.role == "dealer":
        terms_row = (
            db.query(models.DealerPricingTerms)
            .filter(models.DealerPricingTerms.user_id == owner.id)
            .first()
        )
    payload = {
        "snapshot_version": QUOTE_SNAPSHOT_VERSION,
        "project_updated_at": project.updated_at.isoformat()
        if project.updated_at
        else "",
        "catalog": [
            {
                "id": item.id,
                "sku": item.sku,
                "active": bool(item.is_active),
                "updated_at": item.updated_at.isoformat() if item.updated_at else "",
                "price_version_id": active[item.sku][1].id if item.sku in active else None,
            }
            for item in catalog_rows
        ],
        "settings": {
            "include_waste_markup": bool(settings.include_waste_markup),
            "default_vat_rate": decimal_text(decimal_value(settings.default_vat_rate)),
            "updated_at": settings.updated_at.isoformat() if settings.updated_at else "",
        },
        "dealer_terms": {
            "user_id": terms_row.user_id,
            "updated_at": terms_row.updated_at.isoformat(),
        }
        if terms_row
        else None,
        "quote_config": {
            "services": state.services_payload,
            "overrides": state.overrides_payload,
            "vat_mode": state.vat_mode,
            "vat_rate": decimal_text(decimal_value(state.vat_rate)),
            "validity_days": state.validity_days,
            "manufacturing_term": state.manufacturing_term,
            "payment_terms": state.payment_terms,
            "margin_override_comment": state.margin_override_comment or "",
        },
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_or_create_quote_state(
    db: Session, project: models.Project
) -> models.ProjectQuoteState:
    state = (
        db.query(models.ProjectQuoteState)
        .filter(models.ProjectQuoteState.project_id == project.id)
        .first()
    )
    if state is not None:
        return state
    settings = get_pricing_settings(db)
    state = models.ProjectQuoteState(
        project_id=project.id,
        revision=1,
        status="draft",
        public_payload="{}",
        internal_payload="{}",
        services_payload="[]",
        overrides_payload="[]",
        vat_mode="none",
        vat_rate=decimal_value(settings.default_vat_rate),
        validity_days=14,
        manufacturing_term="",
        payment_terms="",
        source_signature="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(state)
    db.flush()
    return state


def calculate_quote(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    *,
    at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    now = _normalize_datetime(at or datetime.utcnow())
    active = _active_price_versions(db, now)
    settings = get_pricing_settings(db)
    terms = _dealer_terms(db, project.owner)
    override_rows = _json_load(state.overrides_payload, [])
    overrides = {
        str(row.get("sku") or "").strip(): row
        for row in override_rows
        if isinstance(row, dict) and str(row.get("sku") or "").strip()
    }

    public_lines: list[dict[str, Any]] = []
    exact_lines: list[dict[str, Decimal]] = []
    internal_sections: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    slide_sections = [
        section
        for section in sorted(project.sections, key=lambda row: row.order)
        if str(section.system or "").strip().upper() == "СЛАЙД"
    ]
    for section in slide_sections:
        calc, requirements = _section_requirements(section)
        priced_bom: list[dict[str, Any]] = []
        section_issues: list[dict[str, Any]] = []
        for required in requirements:
            priced, issue = _price_requirement(
                required,
                active,
                overrides,
                bool(settings.include_waste_markup),
            )
            if issue is not None:
                section_issues.append(issue)
                issues.append(issue)
            elif priced is not None:
                priced_bom.append(priced)

        internal_total = sum(
            (decimal_value(line["internal_total"]) for line in priced_bom), ZERO
        )
        minimum_total = sum(
            (decimal_value(line["minimum_total"]) for line in priced_bom), ZERO
        )
        quantity = decimal_value(section.quantity, Decimal("1"))
        public_line, exact = _public_line(
            line_id=f"section-{section.id}",
            name=str(section.name or f"Секция {section.order}"),
            category="construction",
            quantity=quantity,
            unit="изд.",
            internal_total=internal_total,
            terms=terms,
        )
        sale_factor = _markup_factor(
            terms["dealer_markup_percent"]
        ) * _discount_factor(terms["construction_discount_percent"])
        public_line["section_details"] = _section_snapshot(section, calc)
        public_line["_breakdown_exact"] = _section_breakdown_exact(
            priced_bom,
            sale_factor,
            exact["total"],
        )
        if not section_issues:
            for bom_line in priced_bom:
                item_sale = money(decimal_value(bom_line["internal_total"]) * sale_factor)
                if item_sale >= decimal_value(bom_line["minimum_total"]):
                    continue
                margin_issue = {
                    "code": "below_minimum_margin",
                    "section_id": section.id,
                    "sku": bom_line["sku"],
                    "name": public_line["name"],
                }
                issues.append(margin_issue)
                section_issues.append(margin_issue)
        public_lines.append(public_line)
        exact_lines.append(exact)
        internal_sections.append(
            {
                "section_id": section.id,
                "name": public_line["name"],
                "bom": priced_bom,
                "issues": section_issues,
                "internal_total": money_text(internal_total),
                "minimum_total": money_text(minimum_total),
                "dealer_markup_percent": decimal_text(
                    terms["dealer_markup_percent"]
                ),
                "dealer_discount_percent": public_line["discount_percent"],
                "price_before_discount": public_line[
                    "line_total_before_discount"
                ],
                "final_price": public_line["line_total"],
            }
        )

    services = _json_load(state.services_payload, [])
    internal_services: list[dict[str, Any]] = []
    for index, service in enumerate(services if isinstance(services, list) else []):
        if not isinstance(service, dict):
            continue
        quantity = decimal_value(service.get("quantity"))
        base_cost = decimal_value(service.get("base_cost"))
        if quantity <= 0 or base_cost < 0:
            continue
        internal_total = money(quantity * base_cost)
        public_line, exact = _public_line(
            line_id=str(service.get("id") or f"service-{index + 1}"),
            name=str(service.get("name") or "Услуга"),
            category="service",
            quantity=quantity,
            unit=str(service.get("unit") or "услуга"),
            internal_total=internal_total,
            terms=terms,
        )
        if exact["total"] < internal_total:
            margin_issue = {
                "code": "below_minimum_margin",
                "service_id": public_line["id"],
                "name": public_line["name"],
            }
            issues.append(margin_issue)
        public_lines.append(public_line)
        exact_lines.append(exact)
        internal_services.append(
            {
                **service,
                "base_cost": money_text(base_cost),
                "internal_total": money_text(internal_total),
                "dealer_markup_percent": decimal_text(
                    terms["dealer_markup_percent"]
                ),
                "dealer_discount_percent": public_line["discount_percent"],
                "final_price": public_line["line_total"],
            }
        )

    if not slide_sections:
        issues.append(
            {
                "code": "no_slide_sections",
                "name": "В проекте нет секций СЛАЙД",
            }
        )

    vat_mode = state.vat_mode if state.vat_mode in VAT_MODES else "none"
    vat_rate = decimal_value(state.vat_rate)
    subtotal_before_discount = money(
        sum((row["before_discount"] for row in exact_lines), ZERO)
    )
    discount_total = money(
        sum((row["discount_amount"] for row in exact_lines), ZERO)
    )
    subtotal = money(sum((row["total"] for row in exact_lines), ZERO))
    vat_amount, grand_total, display_factor = _vat_values(
        subtotal,
        vat_mode,
        vat_rate,
    )

    display_before = [row["before_discount"] * display_factor for row in exact_lines]
    display_final = [row["total"] * display_factor for row in exact_lines]
    rounded_before = _allocate_whole_rubles(display_before)
    rounded_final = _allocate_whole_rubles(display_final)
    for index, public_line in enumerate(public_lines):
        quantity = decimal_value(public_line["quantity"], Decimal("1"))
        divisor = quantity if quantity > 0 else Decimal("1")
        public_line["document_line_total_before_discount"] = rounded_before[index]
        public_line["document_line_discount_amount"] = (
            rounded_before[index] - rounded_final[index]
        )
        public_line["document_line_total"] = rounded_final[index]
        public_line["document_unit_price_before_discount"] = int(
            (Decimal(rounded_before[index]) / divisor).quantize(
                WHOLE_RUBLE, rounding=ROUND_HALF_UP
            )
        )
        public_line["document_unit_discount_amount"] = int(
            (
                Decimal(
                    rounded_before[index] - rounded_final[index]
                )
                / divisor
            ).quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP)
        )
        public_line["document_unit_final_price"] = int(
            (Decimal(rounded_final[index]) / divisor).quantize(
                WHOLE_RUBLE, rounding=ROUND_HALF_UP
            )
        )
        exact_breakdown = public_line.pop("_breakdown_exact", [])
        if exact_breakdown:
            breakdown_totals = _allocate_whole_rubles_to_target(
                [row["exact_total"] * display_factor for row in exact_breakdown],
                rounded_final[index],
            )
            public_line["breakdown"] = []
            for row, line_total in zip(exact_breakdown, breakdown_totals):
                quantity = decimal_value(row["quantity"], Decimal("1"))
                divisor = quantity if quantity > 0 else Decimal("1")
                public_line["breakdown"].append(
                    {
                        "sku": row["sku"],
                        "name": row["name"],
                        "quantity": row["quantity"],
                        "unit": row["unit"],
                        "unit_price": int(
                            (Decimal(line_total) / divisor).quantize(
                                WHOLE_RUBLE,
                                rounding=ROUND_HALF_UP,
                            )
                        ),
                        "line_total": line_total,
                    }
                )
        else:
            public_line["breakdown"] = []

    margin_override = bool(str(state.margin_override_comment or "").strip())
    blocking_issues = [
        issue
        for issue in issues
        if issue["code"] in {"missing_price", "unit_mismatch", "no_slide_sections"}
        or (issue["code"] == "below_minimum_margin" and not margin_override)
    ]
    missing_by_sku: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if issue["code"] not in {"missing_price", "unit_mismatch"}:
            continue
        missing_by_sku.setdefault(
            issue["sku"],
            {
                "sku": issue["sku"],
                "name": issue["name"],
                "unit": issue["unit"],
                "reason": issue["code"],
            },
        )
    warnings = []
    if missing_by_sku:
        warnings.append("Для обязательных позиций не заданы действующие цены.")
    if any(issue["code"] == "below_minimum_margin" for issue in issues):
        warnings.append(
            "Итоговая цена ниже минимально допустимой."
            if not margin_override
            else "Исключение по минимальной цене разрешено ответственным сотрудником."
        )
    if any(issue["code"] == "no_slide_sections" for issue in issues):
        warnings.append("В проекте нет секций СЛАЙД.")

    basis_date = state.fixed_at or now
    valid_until = basis_date.date() + timedelta(days=state.validity_days)
    document_before_total = sum(rounded_before)
    document_grand_total = sum(rounded_final)
    public_payload = {
        "project": {
            "id": project.id,
            "number": project.number,
            "customer": project.customer,
        },
        "revision": state.revision,
        "status": state.status,
        "fixed_at": state.fixed_at.isoformat() if state.fixed_at else None,
        "currency": "RUB",
        "lines": public_lines,
        "totals": {
            "before_discount": money_text(subtotal_before_discount),
            "discount": money_text(discount_total),
            "subtotal": money_text(subtotal),
            "vat": money_text(vat_amount),
            "grand_total": money_text(grand_total),
            "document_before_discount": document_before_total,
            "document_discount": document_before_total - document_grand_total,
            "document_grand_total": document_grand_total,
        },
        "vat": {
            "mode": vat_mode,
            "rate": decimal_text(vat_rate),
            "amount": money_text(vat_amount),
            "document_amount": int(
                vat_amount.quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP)
            ),
        },
        "validity_days": state.validity_days,
        "valid_until": valid_until.isoformat(),
        "manufacturing_term": state.manufacturing_term,
        "payment_terms": state.payment_terms,
        "missing_price_count": len(missing_by_sku),
        "warnings": warnings,
        "export_allowed": not blocking_issues,
        "stale": False,
    }
    internal_payload = {
        "public": public_payload,
        "sections": internal_sections,
        "services": internal_services,
        "issues": issues,
        "blocking_issues": blocking_issues,
        "missing_prices": sorted(
            missing_by_sku.values(), key=lambda row: row["sku"]
        ),
        "dealer_terms": {
            key: decimal_text(value) for key, value in terms.items()
        },
        "include_waste_markup": bool(settings.include_waste_markup),
        "calculated_at": now.isoformat(),
    }
    signature = _quote_signature(db, project, state, now)
    return public_payload, internal_payload, signature


def refresh_draft_quote(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    public, internal, signature = calculate_quote(db, project, state, at=at)
    state.public_payload = json.dumps(public, ensure_ascii=False)
    state.internal_payload = json.dumps(internal, ensure_ascii=False)
    state.source_signature = signature
    state.source_project_updated_at = project.updated_at
    state.updated_at = datetime.utcnow()
    db.flush()
    return public


def quote_is_stale(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    *,
    at: datetime | None = None,
) -> bool:
    now = _normalize_datetime(at or datetime.utcnow())
    return state.source_signature != _quote_signature(db, project, state, now)


def public_quote(
    db: Session,
    project: models.Project,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    if state.status != "fixed" or not state.public_payload or state.public_payload == "{}":
        payload = refresh_draft_quote(db, project, state, at=at)
    else:
        payload = _json_load(state.public_payload, {})
    payload = safe_public_payload(payload)
    payload["revision"] = state.revision
    payload["status"] = state.status
    payload["fixed_at"] = state.fixed_at.isoformat() if state.fixed_at else None
    payload["stale"] = quote_is_stale(db, project, state, at=at)
    return payload


def freeze_quote(
    db: Session,
    project: models.Project,
    actor: models.User,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    if state.status == "fixed" and state.public_payload not in (None, "", "{}"):
        payload = safe_public_payload(_json_load(state.public_payload, {}))
        payload["stale"] = quote_is_stale(db, project, state, at=at)
        return payload
    payload = safe_public_payload(refresh_draft_quote(db, project, state, at=at))
    if not payload.get("export_allowed"):
        raise QuoteExportBlocked(payload)
    fixed_at = _normalize_datetime(at or datetime.utcnow())
    state.status = "fixed"
    state.fixed_at = fixed_at
    state.fixed_by = actor.id
    state.updated_at = datetime.utcnow()
    payload["status"] = "fixed"
    payload["fixed_at"] = fixed_at.isoformat()
    payload["valid_until"] = (
        fixed_at.date() + timedelta(days=state.validity_days)
    ).isoformat()
    state.public_payload = json.dumps(payload, ensure_ascii=False)
    db.flush()
    return payload


def refresh_quote_revision(
    db: Session,
    project: models.Project,
    actor: models.User,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    was_fixed = state.status == "fixed"
    state.revision = max(1, int(state.revision or 1)) + 1
    if was_fixed:
        state.status = "draft"
        state.fixed_at = None
        state.fixed_by = None
    payload = safe_public_payload(refresh_draft_quote(db, project, state, at=at))
    if was_fixed:
        if not payload.get("export_allowed"):
            raise QuoteExportBlocked(payload)
        fixed_at = _normalize_datetime(at or datetime.utcnow())
        state.status = "fixed"
        state.fixed_at = fixed_at
        state.fixed_by = actor.id
        payload["status"] = "fixed"
        payload["fixed_at"] = fixed_at.isoformat()
        payload["valid_until"] = (
            fixed_at.date() + timedelta(days=state.validity_days)
        ).isoformat()
        state.public_payload = json.dumps(payload, ensure_ascii=False)
    db.flush()
    return payload


def draft_quote_for_word(
    db: Session,
    project: models.Project,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    if state.status == "fixed":
        payload = safe_public_payload(_json_load(state.public_payload, {}))
        payload["stale"] = quote_is_stale(db, project, state, at=at)
    else:
        payload = safe_public_payload(refresh_draft_quote(db, project, state, at=at))
    if not payload.get("export_allowed"):
        raise QuoteExportBlocked(payload)
    return payload


def internal_quote_state(
    db: Session,
    project: models.Project,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    evaluation_at = _normalize_datetime(at or datetime.utcnow())
    state = get_or_create_quote_state(db, project)
    if state.status != "fixed" or state.internal_payload in (None, "", "{}"):
        refresh_draft_quote(db, project, state, at=evaluation_at)
    internal = _json_load(state.internal_payload, {})
    stale = quote_is_stale(db, project, state, at=evaluation_at)
    pending_internal = internal
    internal_public = internal.get("public")
    pending_warnings = list(
        internal_public.get("warnings") or []
        if isinstance(internal_public, dict)
        else []
    )
    if state.status == "fixed" and stale:
        pending_public, pending_internal, _ = calculate_quote(
            db,
            project,
            state,
            at=evaluation_at,
        )
        pending_warnings = list(pending_public.get("warnings") or [])
    return {
        "revision": state.revision,
        "status": state.status,
        "stale": stale,
        "config": {
            "vat_mode": state.vat_mode,
            "vat_rate": decimal_text(decimal_value(state.vat_rate)),
            "validity_days": state.validity_days,
            "manufacturing_term": state.manufacturing_term,
            "payment_terms": state.payment_terms,
            "services": _json_load(state.services_payload, []),
            "overrides": _json_load(state.overrides_payload, []),
            "margin_override_comment": state.margin_override_comment or "",
        },
        "missing_prices": list(pending_internal.get("missing_prices") or []),
        "pending_warnings": pending_warnings,
        "calculation": internal,
    }
