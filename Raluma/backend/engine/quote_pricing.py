"""Точный расчёт стоимости коммерческого предложения СЛАЙД.

Публичный результат намеренно отделён от внутренней расшифровки: наружу не
попадают себестоимость, коэффициенты, дилерская наценка, маржа и BOM.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP, localcontext
from typing import Any, Iterable

from sqlalchemy.orm import Session

import models
from engine.glass_types import normalize_slide_glass_type
from engine.slide_calc import calculate_slide
from engine.cs_cover_cutting import build_cover_plan, section_allocation_m
from engine.pricing_rules import resolve_effective_price
from engine.construction_pricing import (
    system_code,
    component_key,
    current_components,
    current_global,
    settings_values,
    resolve_cs_kit,
)


MONEY = Decimal("0.01")
WHOLE_RUBLE = Decimal("1")
HUNDRED = Decimal("100")
ZERO = Decimal("0")

PRICE_CATEGORIES = {"profile", "construction", "component", "service"}
MANUAL_SERVICE_UNITS = (
    "п.м.",
    "шт.",
    "кв.м.",
)
QUOTE_SNAPSHOT_VERSION = 9

PUBLIC_QUOTE_FIELDS = {
    "cs_cover_cutting",
    "money_presentation_version",
    "pricing_issues",
    "document_layout_version",
    "project",
    "revision",
    "status",
    "fixed_at",
    "quote_date",
    "manager",
    "total_area_m2",
    "currency",
    "lines",
    "totals",
    "validity_days",
    "valid_until",
    "manufacturing_term",
    "payment_terms",
    "discounts",
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
    "component_details",
    "breakdown",
}
PUBLIC_PROJECT_FIELDS = {
    "id",
    "number",
    "invoice_number",
    "order_number",
    "customer",
}
PUBLIC_TOTAL_FIELDS = {
    "rounding_adjustment",
    "before_discount",
    "discount",
    "subtotal",
    "grand_total",
    "document_before_discount",
    "document_discount",
    "document_grand_total",
}
PUBLIC_SECTION_DETAIL_FIELDS = {
    "cs_geometry",
    "system_name",
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
    "glass_supplied",
    "glass_weight_kg",
    "area_m2",
    "weight_kg",
    "comments",
    "technical_left",
    "technical_right",
    "technical_common",
    "side_projection_mm",
    "side_projection_segments",
    "threshold",
    "rails",
    "slide_rows",
    "first_panel_inside",
    "unused_track",
    "first_panels_placement",
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
PUBLIC_COMPONENT_DETAIL_FIELDS = {
    "pricing_quantity",
    "pricing_unit",
    "pricing_unit_final_price",
    "catalog_item_id",
    "finish_variant_id",
    "sku",
    "name",
    "size",
    "finish",
    "color",
    "unit",
    "stage",
}
PUBLIC_BREAKDOWN_FIELDS = {
    "sku",
    "name",
    "quantity",
    "unit",
    "unit_price",
    "line_total",
}
PUBLIC_DISCOUNT_FIELDS = {"id", "name", "scope", "mode", "value"}


class QuotePricingError(ValueError):
    pass


class QuoteExportBlocked(QuotePricingError):
    def __init__(self, public_payload: dict[str, Any]):
        super().__init__("Коммерческое предложение нельзя экспортировать")
        self.public_payload = public_payload


class MarginOverrideNotRequired(QuotePricingError):
    pass


def safe_public_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply an allow-list at every dealer-facing API/document boundary."""
    if not isinstance(payload, dict):
        payload = {}
    payload = json.loads(json.dumps(payload, ensure_ascii=False))
    payload.pop("vat", None)
    totals = payload.get("totals")
    legacy_money = payload.get("money_presentation_version", 1) < 2
    if isinstance(totals, dict) and legacy_money:
        totals.pop("vat", None)
        totals["grand_total"] = totals.get(
            "subtotal", totals.get("grand_total", "0.00")
        )
    document_before_total = 0
    document_grand_total = 0
    for line in (payload.get("lines") or []) if legacy_money else []:
        if not isinstance(line, dict):
            continue
        quantity = max(decimal_value(line.get("quantity"), Decimal("1")), Decimal("1"))
        before = int(
            decimal_value(line.get("line_total_before_discount")).quantize(
                WHOLE_RUBLE, rounding=ROUND_HALF_UP
            )
        )
        total = int(
            decimal_value(line.get("line_total")).quantize(
                WHOLE_RUBLE, rounding=ROUND_HALF_UP
            )
        )
        line["document_line_total_before_discount"] = before
        line["document_line_discount_amount"] = before - total
        line["document_line_total"] = total
        line["document_unit_price_before_discount"] = int(
            (Decimal(before) / quantity).quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP)
        )
        line["document_unit_discount_amount"] = int(
            (Decimal(before - total) / quantity).quantize(
                WHOLE_RUBLE, rounding=ROUND_HALF_UP
            )
        )
        line["document_unit_final_price"] = int(
            (Decimal(total) / quantity).quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP)
        )
        document_before_total += before
        document_grand_total += total
    if isinstance(totals, dict) and legacy_money:
        totals["document_before_discount"] = document_before_total
        totals["document_discount"] = document_before_total - document_grand_total
        totals["document_grand_total"] = document_grand_total
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
        component_details = line.get("component_details")
        if isinstance(component_details, dict):
            safe_line["component_details"] = {
                key: value
                for key, value in component_details.items()
                if key in PUBLIC_COMPONENT_DETAIL_FIELDS
            }
        else:
            safe_line.pop("component_details", None)
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
    safe["discounts"] = [
        {key: value for key, value in row.items() if key in PUBLIC_DISCOUNT_FIELDS}
        for row in payload.get("discounts") or []
        if isinstance(row, dict)
    ]
    safe["pricing_issues"] = [
        {
            key: value
            for key, value in row.items()
            if key in {"code", "section_id", "project_extra_index", "service_id"}
        }
        for row in payload.get("pricing_issues") or []
        if isinstance(row, dict)
    ]
    for field, allowed in (
        ("project", PUBLIC_PROJECT_FIELDS),
        ("totals", PUBLIC_TOTAL_FIELDS),
    ):
        value = payload.get(field)
        safe[field] = (
            {key: item for key, item in value.items() if key in allowed}
            if isinstance(value, dict)
            else {}
        )
    if "missing_price_count" not in safe:
        legacy_missing = payload.get("missing_prices", [])
        safe["missing_price_count"] = (
            len(legacy_missing) if isinstance(legacy_missing, list) else 0
        )
    safe["warnings"] = [
        str(warning)
        for warning in payload.get("warnings", [])
        if "SLIDE:" in str(warning) or not legacy_money
    ]
    if not bool(payload.get("export_allowed")):
        safe["warnings"].insert(
            0, "Расчёт не прошёл проверку. Причины блокировки указаны ниже."
        )
    return safe


def decimal_value(value: Any, default: Decimal = ZERO) -> Decimal:
    if isinstance(value, Decimal):
        return (
            value
            if value.is_finite() and value.copy_abs() < Decimal("1e100")
            else default
        )
    if value in (None, ""):
        return default
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
        return (
            parsed
            if parsed.is_finite() and parsed.copy_abs() < Decimal("1e100")
            else default
        )
    except (InvalidOperation, ValueError, TypeError):
        return default


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError, OverflowError):
        return None


def money(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = max(context.prec, value.adjusted() + 3)
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
        current = active.get(item.sku)
        if current is None or (
            current[1].finish_variant_id is not None
            and version.finish_variant_id is None
        ):
            active[item.sku] = (item, version)
    return active


def calculate_standalone_sale(
    db: Session,
    rows: Iterable[object],
    *,
    buyer_discount_mode: str | None = None,
    buyer_discount_value: Any = ZERO,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Price profiles/components sold on their own.

    This contour deliberately excludes construction waste, fabrication,
    cutting, gluing and construction-group markup.  Only item cost, explicit
    item markup/discount and the buyer discount are applied.
    """

    now = _normalize_datetime(at or datetime.utcnow())
    active = _active_price_versions(db, now)
    active_by_id = {pair[0].id: pair for pair in active.values()}
    requested = list(rows)
    item_ids = {
        item_id
        for row in requested
        if (item_id := _optional_int(getattr(row, "catalog_item_id", None))) is not None
    }
    items = {
        item.id: item
        for item in db.query(models.CatalogItem)
        .filter(models.CatalogItem.id.in_(item_ids))
        .all()
    }
    public_lines: list[dict[str, Any]] = []
    exact_lines: list[dict[str, Decimal]] = []
    for index, row in enumerate(requested, start=1):
        item_id = _optional_int(getattr(row, "catalog_item_id", None))
        item = items.get(item_id)
        if item is None or not item.is_active:
            raise QuotePricingError(f"Позиция каталога {item_id} не найдена")
        quantity = decimal_value(getattr(row, "quantity", None))
        if quantity <= 0:
            raise QuotePricingError("Количество должно быть больше нуля")
        pair = active_by_id.get(item.id)
        version = pair[1] if pair is not None else None
        variant_id = _optional_int(getattr(row, "finish_variant_id", None))
        variant = next(
            (
                candidate
                for candidate in item.finish_variants
                if candidate.id == variant_id and candidate.is_active
            ),
            None,
        )
        if variant_id is not None and variant is None:
            raise QuotePricingError("Исполнение не относится к выбранному артикулу")
        active_variants = [
            candidate for candidate in item.finish_variants if candidate.is_active
        ]
        visible_variants = [
            candidate
            for candidate in active_variants
            if _normalized_finish(candidate.name) != "без цвета"
        ]
        if variant is None and visible_variants:
            raise QuotePricingError("Выберите исполнение из каталога")
        if variant is None and active_variants:
            variant = active_variants[0]

        version = resolve_effective_price(db, item, variant, at=now)
        if version is None or not getattr(version, "cost_is_set", True):
            raise QuotePricingError("Для выбранной позиции не задана действующая цена")
        cost = decimal_value(version.cost)
        markup = decimal_value(version.profile_markup_percent)
        item_discount = decimal_value(version.profile_discount_percent)
        unit_before_buyer = money(
            cost * _markup_factor(markup) * _discount_factor(item_discount)
        )
        internal_total = money(unit_before_buyer * quantity)
        category = (
            version.category
            if version is not None and version.category in {"profile", "component"}
            else "profile"
            if _canonical_unit(item.unit) == "m"
            else "component"
        )
        public, exact = _public_line(
            line_id=f"sale-{index}",
            name=item.name,
            category=category,
            quantity=quantity,
            unit=item.unit,
            internal_total=internal_total,
            terms={
                "dealer_markup_percent": ZERO,
                "profile_discount_percent": ZERO,
                "construction_discount_percent": ZERO,
                "component_discount_percent": ZERO,
                "service_discount_percent": ZERO,
            },
        )
        public["component_details"] = {
            "catalog_item_id": item.id,
            "finish_variant_id": variant.id if variant else None,
            "sku": item.sku,
            "name": item.name,
            "size": "",
            "finish": variant.name if variant else "",
            "unit": item.unit,
            "stage": "",
        }
        public_lines.append(public)
        exact_lines.append(exact)

    if buyer_discount_mode in {"percent", "fixed"}:
        _apply_quote_discount_rules(
            public_lines,
            exact_lines,
            [
                {
                    "scope": "order",
                    "mode": buyer_discount_mode,
                    "value": decimal_text(
                        max(ZERO, decimal_value(buyer_discount_value))
                    ),
                }
            ],
        )
    before = money(sum((row["before_discount"] for row in exact_lines), ZERO))
    total = money(sum((row["total"] for row in exact_lines), ZERO))
    return {
        "currency": "RUB",
        "lines": public_lines,
        "totals": {
            "before_discount": money_text(before),
            "discount": money_text(before - total),
            "grand_total": money_text(total),
        },
    }


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
    return {key: decimal_value(getattr(terms, key)) for key in zeros}


def _discount_for_category(terms: dict[str, Decimal], category: str) -> Decimal:
    field = {
        "profile": "profile_discount_percent",
        "construction": "construction_discount_percent",
        "component": "component_discount_percent",
        "service": "service_discount_percent",
    }[category]
    return terms[field]


def _construction_group(
    db: Session, section: object
) -> models.ConstructionPriceGroup | None:
    group_id = getattr(section, "price_group_id", None)
    if group_id:
        selected = (
            db.query(models.ConstructionPriceGroup)
            .filter(
                models.ConstructionPriceGroup.id == group_id,
                models.ConstructionPriceGroup.is_active == True,  # noqa: E712
            )
            .first()
        )
        if selected is not None:
            return selected
    system = str(getattr(section, "system", "") or "").strip().upper()
    code = (
        "SLIDE_2"
        if system == "СЛАЙД" and int(getattr(section, "slide_rows", 1) or 1) == 2
        else "SLIDE_1"
        if system == "СЛАЙД"
        else None
    )
    if not code:
        return None
    return (
        db.query(models.ConstructionPriceGroup)
        .filter(
            models.ConstructionPriceGroup.code == code,
            models.ConstructionPriceGroup.is_active == True,  # noqa: E712
        )
        .first()
    )


def _paint_color(section: object, calc: object) -> str:
    color = " ".join(str(getattr(calc, "color_text", "") or "").split())
    if color:
        return color
    painting_type = " ".join(str(getattr(section, "painting_type", "") or "").split())
    return painting_type or "Без цвета"


def _catalog_finish_name(section: object, *, painted: bool) -> str:
    """Map a SLIDE finish to the catalog execution used for costing."""

    painting_type = " ".join(
        str(getattr(section, "painting_type", "") or "").strip().split()
    )
    if not painted:
        return "Анод/неокрас"
    aliases = {
        "Анод": "Анод/неокрас",
        "Анодированный": "Анод/неокрас",
        "Без окраски": "Анод/неокрас",
        "RAL нестандарт": "RAL муар",
    }
    normalized = aliases.get(painting_type, painting_type)
    if normalized in {"Анод/неокрас", "RAL стандарт", "RAL муар", "Сублимация"}:
        return normalized
    return "Анод/неокрас"


def _normalized_finish(value: object) -> str:
    normalized = " ".join(str(value or "").strip().casefold().split())
    aliases = {
        "анод": "анод/неокрас",
        "анодированный": "анод/неокрас",
        "анодирование": "анод/неокрас",
        "неокрас": "анод/неокрас",
        "без окраски": "анод/неокрас",
        "ral нестандарт": "ral муар",
    }
    return aliases.get(normalized, normalized)


def _finish_variant_cost(
    item: models.CatalogItem,
    requested_finish: object,
) -> tuple[Decimal | None, int | None, str]:
    active_variants = [row for row in item.finish_variants if row.is_active]
    if not active_variants:
        return None, None, ""

    requested = _normalized_finish(requested_finish)
    candidates = {_normalized_finish(row.name): row for row in active_variants}
    variant = candidates.get(requested)
    if variant is None and requested == "анод/неокрас":
        variant = next(
            (row for row in active_variants if "анод" in _normalized_finish(row.name)),
            None,
        )
    if variant is None and len(active_variants) == 1:
        only = active_variants[0]
        if _normalized_finish(only.name) == "без цвета":
            variant = only
    if variant is None:
        return None, None, ""
    return (
        decimal_value(variant.cost if variant.cost is not None else variant.price),
        variant.id,
        variant.name,
    )


def _price_sku(prefix: str, *parts: object) -> str:
    normalized = [" ".join(str(part or "").strip().upper().split()) for part in parts]
    return "|".join((prefix, *normalized))


def _parse_extra_components(raw: str | None) -> list[dict[str, Any]]:
    parsed = _json_load(raw, [])
    return (
        [row for row in parsed if isinstance(row, dict)]
        if isinstance(parsed, list)
        else []
    )


def _extra_catalog_pair(extra, active, active_by_id):
    """Shared catalogue selection for calculating and fingerprinting extras."""
    item_id = _optional_int(extra.get("catalog_item_id") or extra.get("catalogItemId"))
    variant_id = _optional_int(
        extra.get("finish_variant_id") or extra.get("finishVariantId")
    )
    if (
        item_id is None
        and variant_id is None
        and ("unit_price" in extra or "unitPrice" in extra)
    ):
        return None  # A freely entered manual article may match a catalogue SKU.
    sku = str(extra.get("sku") or extra.get("art") or "").strip()
    return active_by_id.get(item_id) if item_id else active.get(sku)


def _extra_catalog_variant(item, variant_id):
    if item is None:
        return None, variant_id
    variants = [row for row in item.finish_variants if row.is_active]
    if variant_id is None:
        colorless = [
            row for row in variants if _normalized_finish(row.name) == "без цвета"
        ]
        if len(colorless) == 1:
            return colorless[0], colorless[0].id
    return next((row for row in variants if row.id == variant_id), None), variant_id


def _extra_profile_length_metres(size: Any) -> Decimal | None:
    """A profile blank's size is millimetres, not its billable quantity.

    Accept the numeric editor input and older values such as ``1 200,5 мм``.
    Do not guess a length from an arbitrary description or a multi-axis size.
    """
    text = re.sub(r"\s+", "", str(size or "")).lower()
    if not re.fullmatch(r"\d+(?:[.,]\d+)?(?:мм|mm)?", text):
        return None
    length = decimal_value(re.sub(r"(?:мм|mm)$", "", text))
    return length / Decimal("1000") if length > ZERO else None


def _slide_panel_widths(
    calc: object, panels: int, fallback_width: Decimal
) -> list[Decimal]:
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


def _glass_supplied(section: object) -> bool:
    if str(getattr(section, "system", "") or "").strip().upper() not in {"СЛАЙД", "ЦС"}:
        return True
    return bool(getattr(section, "glass_supplied", True))


def _technical_item(article: str, name: str) -> dict[str, str]:
    return {"article": article.strip(), "name": name.strip()}


def _selected_catalog_item(value: object) -> dict[str, str] | None:
    text = " ".join(str(value or "").strip().split())
    if _is_no_option(text):
        return None
    article_match = re.search(r"\b(?:RS|RU)\d+[A-ZА-Я]*\b", text, flags=re.I)
    article = article_match.group(0).upper() if article_match else ""
    name = text
    if article_match:
        name = f"{text[: article_match.start()]} {text[article_match.end() :]}".strip()
    return _technical_item(article, name or text)


def _append_technical(
    target: list[dict[str, str]],
    article: str,
    name: str,
) -> None:
    item = _technical_item(article, name)
    if item not in target:
        target.append(item)


def _section_technical_components(section: object) -> dict[str, list[dict[str, str]]]:
    rails = 5 if int(getattr(section, "rails", 3) or 3) == 5 else 3
    left: list[dict[str, str]] = []
    right: list[dict[str, str]] = []
    common: list[dict[str, str]] = []

    for side, target in (("left", left), ("right", right)):
        if bool(getattr(section, f"profile_{side}_wall", False)):
            _append_technical(
                target,
                "RS2335" if rails == 5 else "RS2333",
                f"Пристеночный профиль {rails}-рельсовый",
            )
        if bool(getattr(section, f"profile_{side}_lock_bar", False)):
            _append_technical(target, "RS2081", "Боковой профиль-замок")
        if bool(getattr(section, f"profile_{side}_p_bar", False)):
            _append_technical(target, "RS1082", "Боковой П-профиль")
        if bool(getattr(section, f"profile_{side}_handle_bar", False)):
            _append_technical(target, "RS112", "Профиль-ручка")
        if bool(getattr(section, f"profile_{side}_bubble", False)):
            _append_technical(target, "RS1002", "Пузырьковый уплотнитель")
        for field in (f"lock_{side}", f"handle_{side}"):
            selected = _selected_catalog_item(getattr(section, field, None))
            if selected and selected not in target:
                target.append(selected)
        if bool(getattr(section, f"floor_latches_{side}", False)):
            _append_technical(target, "RS205", "Защелка в пол")

    inter_glass = _selected_catalog_item(getattr(section, "inter_glass_profile", None))
    if inter_glass:
        common.append(inter_glass)
    if inter_glass and inter_glass["article"] == "RS2061":
        _append_technical(common, "RU007", "Фетровый уплотнитель 7x12 мм")

    if int(getattr(section, "slide_rows", 1) or 1) == 2:
        for field in ("center_handle", "center_lock"):
            selected = _selected_catalog_item(getattr(section, field, None))
            if selected and selected not in common:
                common.append(selected)
        if "RS112" in str(getattr(section, "center_handle", "") or ""):
            _append_technical(common, "RS1083", "Соединительный профиль 30x20x30")
        if bool(getattr(section, "center_floor_latches_left", False)):
            _append_technical(common, "RS205", "Центральная защелка в пол слева")
        if bool(getattr(section, "center_floor_latches_right", False)):
            _append_technical(common, "RS205", "Центральная защелка в пол справа")

    return {"left": left, "right": right, "common": common}


def _section_snapshot(section: object, calc: object) -> dict[str, Any]:
    """Capture only dealer-safe inputs needed to reproduce both quote sketches."""

    if system_code(section) == "CS":
        supplied = _glass_supplied(section)
        return {
            "section_id": int(getattr(section, "id", 0) or 0),
            "name": str(getattr(section, "name", "") or "Секция"),
            "system": "ЦС",
            "system_name": calc.system.name,
            "width_mm": decimal_text(decimal_value(calc.installation_width_mm)),
            "height_mm": decimal_text(decimal_value(calc.installation_height_mm)),
            "quantity": max(int(getattr(section, "quantity", 1) or 1), 1),
            "panels": len(calc.panes),
            "glass_area_m2": decimal_text(decimal_value(calc.glass_area_m2)),
            "glass_supplied": supplied,
            "glass_type": calc.glass_type if supplied else "Без стекла",
            "color": calc.color_text,
            "glass_weight_kg": "0",
            "comments": str(getattr(section, "comments", "") or ""),
            "cs_geometry": calc.frozen_geometry,
        }

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
                    (getattr(calc, "panel_numbers", []) or list(range(1, panels + 1)))[
                        index
                    ]
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
    supplied = _glass_supplied(section)
    calculated_glass_type = normalize_slide_glass_type(
        getattr(calc, "glass_type", None) or getattr(section, "glass_type", None)
    )
    technical = _section_technical_components(section)
    from engine.side_projection import side_projection, side_segments

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
        "glass_type": calculated_glass_type if supplied else "Без стекла",
        "glass_supplied": supplied,
        # The actual weight is filled from the selected GLASS catalog item
        # after the BOM has been priced. Geometry remains available even when
        # glass is not supplied.
        "glass_weight_kg": "0",
        "comments": str(getattr(section, "comments", "") or "").strip(),
        "technical_left": technical["left"],
        "technical_right": technical["right"],
        "technical_common": technical["common"],
        "side_projection_mm": side_projection(section, calc),
        "side_projection_segments": side_segments(section),
        "threshold": str(
            getattr(calc, "threshold_text", "")
            or getattr(section, "threshold", "")
            or ""
        ),
        "rails": max(int(getattr(section, "rails", 0) or 0), 1),
        "slide_rows": slide_rows,
        "first_panel_inside": first_inside,
        "unused_track": str(getattr(section, "unused_track", "") or ""),
        "first_panels_placement": getattr(section, "first_panels_placement", None)
        or (
            "center"
            if (getattr(section, "unused_track", None) or "Внешний") == "Внешний"
            else "outside"
        ),
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
    public_sources = {"profile", "component", "extra_component", "glass"}
    public_total = ZERO
    for row in priced_bom:
        if row.get("source") not in public_sources:
            continue
        key = (
            ("", "Стекло", "компл.")
            if row.get("source") == "glass"
            else (str(row["sku"]), str(row["name"]), str(row["unit"]))
        )
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
        if row.get("source") == "glass":
            grouped_row["quantity_exact"] = Decimal("1")
        else:
            grouped_row["quantity_exact"] += decimal_value(row["quantity"])
        grouped_row["total_exact"] += decimal_value(row["internal_total"]) * sale_factor

    result = []
    for row in sorted(
        grouped.values(),
        key=lambda item: (not bool(item["sku"]), item["sku"], item["name"]),
    ):
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
    if public_total > 0:
        for row in result:
            row["exact_total"] = row["exact_total"] / public_total * section_total
    return result


def _section_requirements(section: object) -> tuple[object, list[dict[str, Any]]]:
    calc = calculate_slide(section)
    required: list[dict[str, Any]] = []
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
                "finish": _catalog_finish_name(
                    section,
                    painted=bool(getattr(profile, "painted", False)),
                ),
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
    if glass_area > 0 and _glass_supplied(section):
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

    # calc.screws намеренно не включаются: крепёж не продаётся
    # отдельно в составе готовой конструкции.
    return calc, required


def construction_requirements(
    db: Session, section: object
) -> tuple[object, list[dict[str, Any]]]:
    if system_code(section) != "CS":
        return _section_requirements(section)
    from engine.cs_calc import calculate_cs, cs_result_namespace

    kit = resolve_cs_kit(db, section)
    raw = calculate_cs(section, system=kit, outer_profile=kit.outer_profile)
    if raw["normalized_config"].get("doors"):
        raise ValueError("Двери ЦС пока не поддерживаются в расчёте стоимости")
    if any(row["role"] == "bubble" for row in raw["profiles"]) and not kit.bubble_seal:
        raise ValueError("В выбранном составе ЦС не задан пузырьковый уплотнитель")
    required = []
    for row in raw["profiles"]:
        required.append(
            {
                "sku": row["article"],
                "name": row["name"],
                "category": "profile",
                "unit": "м",
                "quantity": decimal_value(row["total_length_mm"]) / 1000,
                "source": "profile",
                "finish": _catalog_finish_name(section, painted=True)
                if row["role"] == "cover"
                else "Без цвета",
                "role": row["role"],
            }
        )
    for row in raw["hardware"]:
        required.append(
            {
                "sku": "CS-JOINT-TAPE" if row["role"] == "tape" else row["article"],
                "name": row["name"],
                "category": "component",
                "unit": row["unit"],
                "quantity": decimal_value(row["qty"]),
                "source": "component",
                "finish": "Без цвета",
                "role": row["role"],
            }
        )
    if _glass_supplied(section) and raw["glass_area_m2"] > 0:
        required.append(
            {
                "sku": _price_sku("GLASS", raw["glass_type"]),
                "name": raw["glass_type"],
                "category": "component",
                "unit": "м²",
                "source": "glass",
                "quantity": decimal_value(raw["glass_area_m2"]),
            }
        )
    # Store only geometry and technical kit identity; never private prices.
    geometry = {
        key: raw[key]
        for key in (
            "system",
            "installation_polygon",
            "clear_polygon",
            "panes",
            "normalized_config",
            "installation_width_mm",
            "installation_height_mm",
            "clear_width_mm",
            "clear_height_mm",
            "profiles",
            "hardware",
        )
    }
    geometry["normalized_config"] = {
        key: raw["normalized_config"][key]
        for key in ("vertices", "profiledEdges")
        if key in raw["normalized_config"]
    }
    raw["warnings"] = []
    calc = cs_result_namespace(raw)
    calc.frozen_geometry = geometry
    calc.kit_dependency = {
        "id": kit.id,
        "code": kit.code,
        "name": kit.name,
        "is_active": kit.is_active,
        "parts": {row["role"]: row["sku"] for row in required if "role" in row},
    }
    return calc, required


def _project_cs_requirements(db: Session, sections: Iterable[object]):
    """Prepare project quantities once, before any section prices are evaluated."""
    prepared, entries = {}, []
    for section in sections:
        if system_code(section) != "CS":
            continue
        try:
            prepared[id(section)] = construction_requirements(db, section)
            entries.append((section, prepared[id(section)][0]))
        except ValueError as exc:
            prepared[id(section)] = exc
    plan = build_cover_plan(entries)
    for index, (section, calc) in enumerate(entries):
        allocated = section_allocation_m(plan, index)
        _, requirements = prepared[id(section)]
        for row in requirements:
            if row.get("role") == "cover":
                row["quantity"] = allocated
        # Keep the technical single-section BOM intact. Only quote composition
        # carries the billable share, so 4+6+8 cannot appear as an 18-stick sale.
        geometry = dict(calc.frozen_geometry)
        geometry["profiles"] = []
        for profile in calc.frozen_geometry["profiles"]:
            row = dict(profile)
            if row["role"] == "cover":
                for key in ("pieces", "cut_lengths_mm", "cutting_text", "length_mm"):
                    row.pop(key, None)
                row["total_length_mm"] = float(allocated * 1000)
                row["allocation_m"] = str(allocated)
                row["allocation_note"] = "Доля общего раскроя заказа"
            geometry["profiles"].append(row)
        calc.frozen_geometry = geometry
    return prepared, plan


def price_construction_section(
    db: Session,
    section: object,
    *,
    at=None,
    active=None,
    overrides=None,
    draft: dict | None = None,
    prepared=None,
) -> dict:
    """The single read-only pricing path for samples and actual quote sections."""
    when = _normalize_datetime(at or datetime.utcnow())
    code = system_code(section)
    settings = current_components(db, code, when)
    settings.update((draft or {}).get("components", {}))
    general = current_global(db, code, when)
    general_values = {
        "markup_percent": decimal_text(
            decimal_value(general.markup_percent if general else 0)
        ),
        "discount_percent": decimal_text(
            decimal_value(general.discount_percent if general else 0)
        ),
    }
    general_values.update((draft or {}).get("general", {}))
    if prepared is None and code == "CS":
        inputs, _ = _project_cs_requirements(db, [section])
        prepared = inputs[id(section)]
    if isinstance(prepared, ValueError):
        raise prepared
    calc, requirements = (
        prepared if prepared is not None else construction_requirements(db, section)
    )
    active = active if active is not None else _active_price_versions(db, when)
    bom, issues = [], []
    for required in requirements:
        priced, issue = _price_requirement(
            required,
            active,
            overrides or {},
            mode="construction",
            db=db,
            at=when,
            system_settings=settings,
            pricing_system=code,
        )
        if issue:
            issues.append(
                {
                    **issue,
                    "quantity": decimal_text(decimal_value(required["quantity"])),
                    "unit": required["unit"],
                }
            )
        elif priced:
            bom.append(priced)
    subtotal = money(sum((decimal_value(row["internal_total"]) for row in bom), ZERO))
    after_markup = money(subtotal * _markup_factor(general_values["markup_percent"]))
    total = money(after_markup * _discount_factor(general_values["discount_percent"]))
    return {
        "calc": calc,
        "bom": bom,
        "issues": issues,
        "system_code": code,
        "stages": {
            "subtotal": money_text(subtotal),
            **general_values,
            "after_markup": money_text(after_markup),
            "total": money_text(total),
        },
        "dependency": {
            "general": general_values,
            "kit": getattr(calc, "kit_dependency", None),
        },
        "minimum_total": money_text(
            sum((decimal_value(row["minimum_total"]) for row in bom), ZERO)
        ),
    }


def _price_requirement(
    required: dict[str, Any],
    active: dict[str, tuple[models.CatalogItem, models.CatalogPriceVersion]],
    overrides: dict[str, dict[str, Any]],
    *,
    mode: str = "legacy",
    db: Session | None = None,
    at: datetime | None = None,
    system_settings: dict | None = None,
    pricing_system: str | None = None,
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

    item = None
    finish_variant_id = None
    finish_name = ""
    # The legacy override payload calls its sale price "cost". It must never
    # replace the actual purchase cost or erase the catalogue's minimum markup.
    version = None
    cost = ZERO
    price_unit = required["unit"]
    category = required["category"]
    profile_markup = profile_discount = waste_markup = ZERO
    construction_markup = construction_discount = min_margin = ZERO
    cost_known = False
    if item_and_version is not None:
        item, version = item_and_version
        cost = decimal_value(version.cost)
        requested_finish = str(required.get("finish") or "").strip()
        if requested_finish or (
            len(item.finish_variants) == 1
            and _normalized_finish(item.finish_variants[0].name) == "без цвета"
        ):
            variant_cost, finish_variant_id, finish_name = _finish_variant_cost(
                item,
                requested_finish,
            )
            if item.finish_variants and finish_variant_id is None and override is None:
                return None, {
                    "code": "missing_finish_price",
                    "sku": sku,
                    "name": required["name"],
                    "finish": requested_finish,
                }
            if variant_cost is not None:
                cost = variant_cost
        finish_variant = next(
            (
                row
                for row in item.finish_variants
                if row.id == finish_variant_id and row.is_active
            ),
            None,
        )
        unresolved_finish = bool(
            requested_finish and item.finish_variants and finish_variant_id is None
        )
        if db is not None:
            version = (
                None
                if unresolved_finish
                else resolve_effective_price(db, item, finish_variant, at=at)
            )
            if version is None and override is None:
                return None, {
                    "code": "missing_price",
                    "sku": sku,
                    "name": required["name"],
                    "unit": required["unit"],
                }
        if unresolved_finish:
            version = None
        if version is not None and not _units_compatible(
            required["unit"], version.unit
        ):
            return None, {
                "code": "unit_mismatch",
                "sku": sku,
                "name": required["name"],
                "unit": required["unit"],
                "priced_unit": version.unit,
            }
    if version is not None:
        if db is not None:
            cost = decimal_value(version.cost)
        cost_known = getattr(version, "cost_is_set", True) is not False
        price_unit = version.unit
        category = version.category
        profile_markup = decimal_value(
            finish_variant.profile_markup_percent
            if finish_variant is not None and db is None
            else version.profile_markup_percent
        )
        profile_discount = decimal_value(
            finish_variant.profile_discount_percent
            if finish_variant is not None and db is None
            else version.profile_discount_percent
        )
        waste_markup = decimal_value(
            finish_variant.waste_markup_percent
            if finish_variant is not None and db is None
            else version.waste_markup_percent
        )
        construction_markup = decimal_value(
            finish_variant.construction_markup_percent
            if finish_variant is not None and db is None
            else version.construction_markup_percent
        )
        construction_discount = decimal_value(
            finish_variant.construction_discount_percent
            if finish_variant is not None and db is None
            else version.construction_discount_percent
        )
        min_margin = decimal_value(version.min_margin_percent)
    else:
        cost = ZERO

    if version is not None and not cost_known:
        return None, {
            "code": "missing_price",
            "sku": sku,
            "name": required["name"],
            "unit": required["unit"],
            "detail": "Себестоимость не заполнена",
            "component_key": component_key(item.id, finish_variant_id),
        }
    system_setting = None
    if mode == "construction" and system_settings is not None:
        key = component_key(item.id, finish_variant_id) if item is not None else ""
        system_setting = system_settings.get(key)
        values = settings_values(system_setting)
        if values is None and override is None:
            return None, {
                "code": "missing_price",
                "sku": sku,
                "name": required["name"],
                "unit": required["unit"],
                "detail": "Не настроена цена в выбранной системе",
                "system_code": pricing_system,
                "component_key": key,
            }
        if values:
            waste_markup = decimal_value(values["waste_percent"])
            construction_markup = decimal_value(values["markup_percent"])
            construction_discount = decimal_value(values["discount_percent"])

    quantity = decimal_value(required["quantity"])
    base_cost = cost * quantity
    profile_after_markup = base_cost * _markup_factor(profile_markup)
    profile_after_discount = profile_after_markup * _discount_factor(profile_discount)
    construction_after_waste = base_cost * _markup_factor(waste_markup)
    construction_after_markup = construction_after_waste * _markup_factor(
        construction_markup
    )
    construction_after_discount = construction_after_markup * _discount_factor(
        construction_discount
    )
    waste_markup_applied = False
    if override is not None:
        internal_total = money(decimal_value(override.get("cost")) * quantity)
    elif mode == "construction":
        # The two price chains are deliberately independent.  A construction
        # starts from cost and never inherits standalone profile markup/discount.
        waste_markup_applied = waste_markup > 0
        internal_total = money(construction_after_discount)
    else:
        internal_total = money(profile_after_discount)
    minimum_total = money(base_cost * _markup_factor(min_margin))
    return {
        **required,
        "quantity": decimal_text(quantity),
        "component_key": component_key(item.id, finish_variant_id)
        if getattr(item, "id", None) is not None
        else None,
        "system_code": pricing_system,
        "system_component_version_id": getattr(system_setting, "id", None),
        "catalog_category": category,
        "price_unit": price_unit,
        "price_version_id": version.id if version is not None else None,
        "price_source": getattr(version, "source", None),
        "finish_variant_id": finish_variant_id,
        "finish": finish_name or str(required.get("finish") or ""),
        "override_comment": str(override.get("comment") or "") if override else "",
        "sale_price_override": money_text(decimal_value(override.get("cost")))
        if override is not None
        else None,
        "cost": money_text(cost),
        "cost_known": cost_known,
        "base_cost_total": money_text(base_cost),
        "profile_markup_percent": decimal_text(profile_markup),
        "profile_discount_percent": decimal_text(profile_discount),
        "waste_markup_percent": decimal_text(waste_markup),
        "waste_markup_applied": waste_markup_applied,
        "construction_markup_percent": decimal_text(construction_markup),
        "construction_discount_percent": decimal_text(construction_discount),
        "price_stages": {
            "profile": {
                "base_cost": money_text(base_cost),
                "after_markup": money_text(profile_after_markup),
                "after_discount": money_text(profile_after_discount),
            },
            "construction": {
                "base_cost": money_text(base_cost),
                "after_waste": money_text(construction_after_waste),
                "after_markup": money_text(construction_after_markup),
                "after_discount": money_text(construction_after_discount),
            },
        },
        "min_margin_percent": decimal_text(min_margin),
        "internal_total": money_text(internal_total),
        "minimum_total": money_text(minimum_total),
        "unit_weight_kg": decimal_text(
            decimal_value(getattr(item, "weight", 0)) if item is not None else ZERO
        ),
        "weight_total_kg": decimal_text(
            (decimal_value(getattr(item, "weight", 0)) * quantity)
            if item is not None
            else ZERO
        ),
    }, None


def _allocate_whole_rubles(values: Iterable[Decimal]) -> list[int]:
    source = [max(ZERO, value) for value in values]
    if not source:
        return []
    floors = [
        int(value.quantize(WHOLE_RUBLE, rounding=ROUND_FLOOR)) for value in source
    ]
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
    floors = [
        int(value.quantize(WHOLE_RUBLE, rounding=ROUND_FLOOR)) for value in source
    ]
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


def _refresh_public_discount(public: dict[str, Any], exact: dict[str, Decimal]) -> None:
    before = money(exact["before_discount"])
    total = money(max(ZERO, exact["total"]))
    discount = money(max(ZERO, before - total))
    exact["discount_amount"] = discount
    exact["total"] = total
    quantity = decimal_value(public.get("quantity"), Decimal("1"))
    divisor = quantity if quantity > 0 else Decimal("1")
    effective_percent = (
        (discount * HUNDRED / before).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        if before > 0
        else ZERO
    )
    public.update(
        {
            "discount_percent": decimal_text(effective_percent),
            "unit_discount_amount": money_text(discount / divisor),
            "unit_final_price": money_text(total / divisor),
            "line_discount_amount": money_text(discount),
            "line_total": money_text(total),
        }
    )
    details = public.get("component_details")
    if isinstance(details, dict) and decimal_value(details.get("pricing_quantity")) > 0:
        details["pricing_unit_final_price"] = money_text(
            total / decimal_value(details["pricing_quantity"])
        )


def _allocate_money(values: Iterable[Decimal], target: Decimal) -> list[Decimal]:
    """Proportionally allocate a non-negative cent amount, without a residual loss.

    When target <= sum(values), each share is bounded by that cent-valued row.
    Stable largest remainders make the result deterministic even for tiny rows.
    """
    weights = [max(ZERO, money(decimal_value(value))) for value in values]
    total = sum(weights, ZERO)
    if not weights or total <= 0:
        return [ZERO for _ in weights]
    cents = int(max(ZERO, money(target)) / MONEY)
    raw = [Decimal(cents) * weight / total for weight in weights]
    shares = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
    order = sorted(
        range(len(raw)),
        key=lambda index: (raw[index] - shares[index], -index),
        reverse=True,
    )
    for index in order[: cents - sum(shares)]:
        shares[index] += 1
    return [MONEY * value for value in shares]


def _prepare_money_presentation(lines: list[dict[str, Any]]) -> dict[str, str]:
    """New quotes retain cents per line; only the payable order total is rounded."""
    before = ZERO
    subtotal = ZERO
    for line in lines:
        quantity = decimal_value(line.get("quantity"), Decimal("1"))
        divisor = quantity if quantity > 0 else Decimal("1")
        line_before = money(decimal_value(line["line_total_before_discount"]))
        line_total = money(decimal_value(line["line_total"]))
        before += line_before
        subtotal += line_total
        line.update(
            {
                "document_line_total_before_discount": money_text(line_before),
                "document_line_discount_amount": money_text(line_before - line_total),
                "document_line_total": money_text(line_total),
                "document_unit_price_before_discount": money_text(
                    line_before / divisor
                ),
                "document_unit_discount_amount": money_text(
                    (line_before - line_total) / divisor
                ),
                "document_unit_final_price": money_text(line_total / divisor),
            }
        )
        breakdown = line.pop("_breakdown_exact", [])
        allocated = _allocate_money(
            (decimal_value(row["exact_total"]) for row in breakdown), line_total
        )
        line["breakdown"] = [
            {
                "sku": row["sku"],
                "name": row["name"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "unit_price": money_text(
                    total / (decimal_value(row["quantity"]) or Decimal("1"))
                ),
                "line_total": money_text(total),
            }
            for row, total in zip(breakdown, allocated)
        ]
    grand_total = subtotal.quantize(WHOLE_RUBLE, rounding=ROUND_HALF_UP)
    return {
        "before_discount": money_text(before),
        "discount": money_text(before - subtotal),
        "subtotal": money_text(subtotal),
        "grand_total": money_text(grand_total),
        "rounding_adjustment": money_text(grand_total - subtotal),
        "document_before_discount": money_text(before),
        "document_discount": money_text(before - subtotal),
        "document_grand_total": money_text(grand_total),
    }


def _apply_quote_discount_rules(
    public_lines: list[dict[str, Any]],
    exact_lines: list[dict[str, Decimal]],
    raw_rules: object,
) -> None:
    """Apply category rules, then order percent, then order rubles."""

    rules = _canonical_discounts(
        json.dumps(raw_rules, ensure_ascii=False)
        if isinstance(raw_rules, list)
        else str(raw_rules or "[]")
    )
    for rule in rules:
        scope = rule["scope"]
        indices = [
            index
            for index, line in enumerate(public_lines)
            if scope == "order" or line.get("category") == scope
        ]
        if not indices:
            continue
        value = decimal_value(rule["value"])
        if rule["mode"] == "percent":
            factor = _discount_factor(min(value, HUNDRED))
            for index in indices:
                exact_lines[index]["total"] = money(
                    exact_lines[index]["total"] * factor
                )
                _refresh_public_discount(public_lines[index], exact_lines[index])
            continue

        available = sum((exact_lines[index]["total"] for index in indices), ZERO)
        fixed = min(money(value), money(available))
        if fixed <= 0 or available <= 0:
            continue
        shares = _allocate_money(
            (exact_lines[index]["total"] for index in indices), fixed
        )
        for index, share in zip(indices, shares):
            exact_lines[index]["total"] = money(
                max(ZERO, exact_lines[index]["total"] - share)
            )
            _refresh_public_discount(public_lines[index], exact_lines[index])


def _signature_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _normalize_datetime(value).isoformat()
    if isinstance(value, Decimal):
        return decimal_text(value)
    return value


def _canonical_services(raw: str | None) -> list[dict[str, Any]]:
    rows = _json_load(raw, [])
    return [
        {
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or "").strip(),
            "quantity": decimal_text(decimal_value(row.get("quantity"))),
            "unit": str(row.get("unit") or "").strip(),
            "base_cost": money_text(
                decimal_value(row.get("sale_price", row.get("base_cost")))
            ),
            "sale_price": money_text(
                decimal_value(row.get("sale_price", row.get("base_cost")))
            ),
            "actual_cost": money_text(decimal_value(row["actual_cost"]))
            if row.get("actual_cost") not in (None, "")
            else None,
        }
        for row in rows
        if isinstance(row, dict)
    ]


def _canonical_discounts(raw: str | None) -> list[dict[str, Any]]:
    rows = _json_load(raw, [])
    allowed_scopes = {*PRICE_CATEGORIES, "order"}
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        scope = str(row.get("scope") or "").strip().lower()
        mode = str(row.get("mode") or "").strip().lower()
        value = max(ZERO, decimal_value(row.get("value")))
        if scope not in allowed_scopes or mode not in {"percent", "fixed"}:
            continue
        if mode == "percent":
            value = min(value, HUNDRED)
        result.append(
            {
                "id": str(row.get("id") or f"discount-{len(result) + 1}"),
                "name": str(row.get("name") or "Скидка").strip() or "Скидка",
                "scope": scope,
                "mode": mode,
                "value": decimal_text(value),
            }
        )
    # Quick fields may arrive in any editing order. Keep all additional rules
    # and their relative order within each stage, but always deduct order
    # rubles last. Frozen quotes are read from their saved payload, not here.
    return sorted(
        result,
        key=lambda rule: (
            0 if rule["scope"] != "order" else 1 if rule["mode"] == "percent" else 2
        ),
    )


def _canonical_overrides(raw: str | None) -> list[dict[str, Any]]:
    rows = _json_load(raw, [])
    result = [
        {
            "sku": str(row.get("sku") or "").strip(),
            "cost": decimal_text(decimal_value(row.get("cost"))),
            "comment": str(row.get("comment") or "").strip(),
        }
        for row in rows
        if isinstance(row, dict) and str(row.get("sku") or "").strip()
    ]
    return sorted(result, key=lambda row: row["sku"])


def _pricing_context_payload(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    at: datetime,
) -> dict[str, Any]:
    """Fingerprint only inputs actually consumed by this order at ``at``.

    Mutable catalogue caches are not effective-dated prices. In particular,
    activating a scheduled finish version must invalidate a quote even if a
    generic article version and its compatibility cache have not changed.
    Unrelated articles, rule history and bindings must not invalidate it.
    """
    active = _active_price_versions(db, at)
    terms = _dealer_terms(db, project.owner)
    price_fields = (
        "cost",
        "profile_markup_percent",
        "profile_discount_percent",
        "cost_is_set",
        "category",
        "unit",
        "min_margin_percent",
    )
    section_fields = [
        column.name
        for column in models.Section.__table__.columns
        if column.name
        not in {"document_overrides", "updated_at", "created_at", "price_group_id"}
    ]
    used_overrides = set()
    overrides = {
        row["sku"]: row for row in _canonical_overrides(state.overrides_payload)
    }
    catalog: list[dict[str, Any]] = []
    prepared_cs, cover_plan = _project_cs_requirements(
        db,
        sorted(
            project.sections, key=lambda row: (int(row.order or 0), int(row.id or 0))
        ),
    )
    for section in sorted(
        project.sections, key=lambda row: (int(row.order or 0), int(row.id or 0))
    ):
        if system_code(section) is None:
            continue
        try:
            priced_section = price_construction_section(
                db,
                section,
                at=at,
                active=active,
                overrides=overrides,
                prepared=prepared_cs.get(id(section)),
            )
            used_overrides.update(row["sku"] for row in priced_section["bom"])
            used_overrides.update(
                row["sku"] for row in priced_section["issues"] if row.get("sku")
            )
            # Standalone-sale percentages and their version IDs do not affect
            # construction prices. Only consumed inputs invalidate an order.
            fingerprint_rows = [
                {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "price_version_id",
                        "price_source",
                        "profile_markup_percent",
                        "profile_discount_percent",
                        "price_stages",
                    }
                }
                for row in priced_section["bom"]
            ]
            catalog.append(
                {
                    "section_id": section.id,
                    "bom": fingerprint_rows,
                    "issues": priced_section["issues"],
                    "system": priced_section["dependency"],
                }
            )
        except ValueError as exc:
            catalog.append({"section_id": section.id, "error": str(exc)})

    active_by_id = {pair[0].id: pair for pair in active.values()}
    for index, extra in enumerate(
        _parse_extra_components(getattr(project, "extra_components", None)), start=1
    ):
        variant_id = _optional_int(
            extra.get("finish_variant_id") or extra.get("finishVariantId")
        )
        pair = _extra_catalog_pair(extra, active, active_by_id)
        item = pair[0] if pair else None
        variant, _ = _extra_catalog_variant(item, variant_id)
        if item is not None:
            resolved = resolve_effective_price(db, item, variant, at=at)
        else:
            resolved = None
        catalog.append(
            {
                "project_extra_index": index,
                "item": {
                    "id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "unit": item.unit,
                }
                if item
                else None,
                "finish": {"id": variant.id, "name": variant.name} if variant else None,
                "price": {
                    **{
                        field: _signature_value(getattr(resolved, field))
                        for field in price_fields
                    },
                }
                if resolved
                else None,
            }
        )
    return {
        "engine_version": QUOTE_SNAPSHOT_VERSION,
        "cs_cover_cutting": cover_plan,
        "project": {
            "id": project.id,
            "number": project.number,
            "invoice_number": getattr(project, "invoice_number", None),
            "order_number": getattr(project, "order_number", None),
            "customer": project.customer,
            "created_by": project.created_by,
            "extra_components": _json_load(
                getattr(project, "extra_components", None), []
            ),
            "sections": [
                {
                    field: _signature_value(getattr(section, field))
                    for field in section_fields
                }
                for section in sorted(
                    project.sections,
                    key=lambda row: (int(row.order or 0), int(row.id or 0)),
                )
            ],
        },
        "catalog": catalog,
        "dealer_terms": {
            "user_id": project.owner.id
            if project.owner is not None and project.owner.role == "dealer"
            else None,
            **{key: decimal_text(value) for key, value in terms.items()},
        },
        "services": _canonical_services(state.services_payload),
        "discounts": _canonical_discounts(state.discounts_payload),
        "overrides": [
            row for sku, row in sorted(overrides.items()) if sku in used_overrides
        ],
    }


def _hash_signature_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _margin_context_signature(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    at: datetime,
) -> str:
    return _hash_signature_payload(_pricing_context_payload(db, project, state, at))


def _quote_signature(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    at: datetime,
) -> str:
    payload = {
        "pricing_context": _pricing_context_payload(db, project, state, at),
        "quote_config": {
            "validity_days": state.validity_days,
            "manufacturing_term": state.manufacturing_term,
            "payment_terms": state.payment_terms,
        },
        "margin_approval": {
            "comment": state.margin_override_comment or "",
            "context_signature": state.margin_override_context_signature or "",
            "target_revision": state.margin_override_target_revision,
            "approved_by": state.margin_override_approved_by,
            "approved_at": _signature_value(state.margin_override_approved_at),
        },
    }
    return _hash_signature_payload(payload)


def current_quote_preview_token(
    db: Session,
    project: models.Project,
    *,
    at: datetime | None = None,
) -> str:
    """Opaque fingerprint for confirming the exact current calculation.

    Includes private cost/floor dependencies without exposing them to the
    client. Merely reading it never changes a fixed quote or its revisions.
    """
    state = get_or_create_quote_state(db, project)
    evaluation_at = _normalize_datetime(at or datetime.utcnow())
    return _hash_signature_payload(
        {
            "signature": _quote_signature(db, project, state, evaluation_at),
            "status": state.status,
            "revision": state.revision,
            "quote_date": evaluation_at.date().isoformat(),
        }
    )


def quote_target_revision(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    *,
    at: datetime,
) -> int:
    current_revision = max(1, int(state.revision or 1))
    if state.status != "fixed":
        return 1
    if state.source_signature != _quote_signature(db, project, state, at):
        return current_revision + 1
    return current_revision


def _margin_approval_details(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    issues: list[dict[str, Any]],
    *,
    at: datetime,
) -> dict[str, Any]:
    required = any(issue.get("code") == "below_minimum_margin" for issue in issues)
    context_signature = _margin_context_signature(db, project, state, at)
    target_revision = quote_target_revision(db, project, state, at=at)
    comment = str(state.margin_override_comment or "").strip()
    valid = bool(
        required
        and comment
        and state.margin_override_context_signature == context_signature
        and state.margin_override_target_revision == target_revision
        and state.margin_override_approved_by is not None
        and state.margin_override_approved_at is not None
    )
    return {
        "required": required,
        "valid": valid,
        "context_signature": context_signature,
        "target_revision": target_revision,
        "approved_revision": state.margin_override_target_revision,
        "comment": comment,
        "approved_by": state.margin_override_approved_by,
        "approved_at": (
            state.margin_override_approved_at.isoformat()
            if state.margin_override_approved_at
            else None
        ),
    }


def invalidate_margin_override(
    state: models.ProjectQuoteState,
    *,
    clear_comment: bool = False,
) -> None:
    if clear_comment:
        state.margin_override_comment = None
    state.margin_override_context_signature = None
    state.margin_override_target_revision = None
    state.margin_override_approved_by = None
    state.margin_override_approved_at = None


def approve_margin_override(
    db: Session,
    project: models.Project,
    state: models.ProjectQuoteState,
    actor: models.User,
    comment: str,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    now = _normalize_datetime(at or datetime.utcnow())
    clean_comment = str(comment or "").strip()
    _, current_internal, _ = calculate_quote(db, project, state, at=now)
    current = current_internal["margin_approval"]
    if not current["required"]:
        raise MarginOverrideNotRequired(
            "Исключение можно согласовать только при нарушении минимальной маржи"
        )
    if current["valid"] and current["comment"] == clean_comment:
        return current

    state.margin_override_comment = clean_comment
    invalidate_margin_override(state)
    context_signature = _margin_context_signature(db, project, state, now)
    target_revision = quote_target_revision(db, project, state, at=now)
    state.margin_override_context_signature = context_signature
    state.margin_override_target_revision = target_revision
    state.margin_override_approved_by = actor.id
    state.margin_override_approved_at = now
    state.updated_at = datetime.utcnow()
    _, approved_internal, _ = calculate_quote(db, project, state, at=now)
    return approved_internal["margin_approval"]


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
    state = models.ProjectQuoteState(
        project_id=project.id,
        revision=1,
        status="draft",
        public_payload="{}",
        internal_payload="{}",
        services_payload="[]",
        discounts_payload="[]",
        overrides_payload="[]",
        vat_mode="none",
        vat_rate=ZERO,
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
    terms = _dealer_terms(db, project.owner)
    override_rows = _json_load(state.overrides_payload, [])
    overrides = {
        str(row.get("sku") or "").strip(): row
        for row in override_rows
        if isinstance(row, dict) and str(row.get("sku") or "").strip()
    }

    public_lines: list[dict[str, Any]] = []
    exact_lines: list[dict[str, Decimal]] = []
    line_minimums: list[tuple[Decimal, dict[str, Any]]] = []
    internal_sections: list[dict[str, Any]] = []
    internal_project_extras: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    slide_warnings: list[str] = []

    ordered_sections = sorted(
        project.sections,
        key=lambda row: (int(row.order or 0), int(row.id or 0)),
    )
    slide_sections = [
        section for section in ordered_sections if system_code(section) is not None
    ]
    unsupported_sections = [
        section for section in ordered_sections if system_code(section) is None
    ]
    prepared_cs, cover_plan = _project_cs_requirements(db, ordered_sections)
    for section in slide_sections:
        try:
            priced_section = price_construction_section(
                db,
                section,
                at=now,
                active=active,
                overrides=overrides,
                prepared=prepared_cs.get(id(section)),
            )
        except ValueError as exc:
            issues.append(
                {
                    "code": "unsupported_section_pricing",
                    "name": str(exc),
                    "section_ids": [section.id],
                }
            )
            continue
        calc = priced_section["calc"]
        slide_warnings.extend(
            f"{section.name or f'Секция {section.order}'}: {warning}"
            for warning in getattr(calc, "warnings", []) or []
        )
        priced_bom = priced_section["bom"]
        section_issues = priced_section["issues"]
        issues.extend(section_issues)

        bom_total = sum(
            (decimal_value(line["internal_total"]) for line in priced_bom), ZERO
        )
        internal_total = decimal_value(priced_section["stages"]["total"])
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
        sale_factor = _markup_factor(terms["dealer_markup_percent"]) * _discount_factor(
            terms["construction_discount_percent"]
        )
        section_details = _section_snapshot(section, calc)
        section_area = (
            decimal_value(getattr(section, "width", 0))
            * decimal_value(getattr(section, "height", 0))
            / Decimal("1000000")
        )
        catalog_weight = sum(
            (decimal_value(line.get("weight_total_kg")) for line in priced_bom),
            ZERO,
        )
        glass_catalog_weight = sum(
            (
                decimal_value(line.get("weight_total_kg"))
                for line in priced_bom
                if line.get("source") == "glass"
            ),
            ZERO,
        )
        glass_fallback_weight = (
            decimal_value(section_details.get("glass_area_m2")) * Decimal("25")
            if section_details.get("glass_supplied") and glass_catalog_weight <= 0
            else ZERO
        )
        section_details["glass_weight_kg"] = decimal_text(
            (glass_catalog_weight or glass_fallback_weight).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        calculated_weight = catalog_weight + glass_fallback_weight
        section_details["area_m2"] = decimal_text(
            section_area.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        )
        section_details["weight_kg"] = decimal_text(
            (calculated_weight / max(quantity, Decimal("1"))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        public_line["section_details"] = section_details
        public_line["_breakdown_exact"] = _section_breakdown_exact(
            priced_bom,
            sale_factor,
            exact["total"],
        )
        public_lines.append(public_line)
        exact_lines.append(exact)
        line_minimums.append(
            (
                money(minimum_total),
                {
                    "code": "below_minimum_margin",
                    "section_id": section.id,
                    "name": public_line["name"],
                },
            )
        )
        internal_sections.append(
            {
                "section_id": section.id,
                "name": public_line["name"],
                "bom": priced_bom,
                "issues": section_issues,
                "internal_total": money_text(internal_total),
                "bom_total": money_text(bom_total),
                "minimum_total": money_text(minimum_total),
                "system_code": priced_section["system_code"],
                "system_stages": priced_section["stages"],
                "dealer_discount_percent": public_line["discount_percent"],
                "price_before_discount": public_line["line_total_before_discount"],
                "final_price": public_line["line_total"],
            }
        )

    project_extras = _parse_extra_components(getattr(project, "extra_components", None))
    active_by_id = {pair[0].id: pair for pair in active.values()}
    for index, extra in enumerate(project_extras, start=1):
        quantity = decimal_value(
            extra.get("qty") if "qty" in extra else extra.get("quantity")
        )
        if quantity <= 0:
            issues.append(
                {
                    "code": "invalid_extra_quantity",
                    "project_extra_index": index,
                    "name": str(extra.get("name") or "Доп. комплектующее"),
                }
            )
            continue
        catalog_item_id = _optional_int(
            extra.get("catalog_item_id") or extra.get("catalogItemId")
        )
        finish_variant_id = _optional_int(
            extra.get("finish_variant_id") or extra.get("finishVariantId")
        )
        sku = str(extra.get("sku") or extra.get("art") or "").strip()
        pair = _extra_catalog_pair(extra, active, active_by_id)
        item = pair[0] if pair is not None else None
        version = pair[1] if pair is not None else None
        variant, finish_variant_id = _extra_catalog_variant(item, finish_variant_id)
        if item is not None:
            version = resolve_effective_price(db, item, variant, at=now)

        snapshot_value = next(
            (
                extra.get(key)
                for key in ("price_snapshot", "unit_price", "unitPrice", "price")
                if extra.get(key) not in (None, "")
            ),
            None,
        )
        # A catalog position is always repriced from the active catalog data.
        # The legacy snapshot fallback is retained only for old manual rows
        # which have no catalog link.
        if (
            item is None
            and catalog_item_id is None
            and finish_variant_id is None
            and snapshot_value is not None
        ):
            unit_sale = decimal_value(snapshot_value, Decimal("-1"))
            raw_actual_cost = extra.get("actual_cost", extra.get("actualCost"))
            selected_cost = (
                decimal_value(raw_actual_cost, Decimal("-1"))
                if raw_actual_cost not in (None, "")
                else ZERO
            )
            if unit_sale < 0 or selected_cost < 0:
                issues.append(
                    {
                        "code": "invalid_extra_price",
                        "project_extra_index": index,
                        "name": str(extra.get("name") or "Доп. комплектующее"),
                    }
                )
                continue
            category = str(extra.get("category") or "component").strip().lower()
            if category not in {"profile", "component", "service"}:
                category = "component"
        elif finish_variant_id is not None and variant is None:
            issue = {
                "code": "missing_finish_price",
                "sku": sku or f"PROJECT-EXTRA-{index}",
                "name": str(extra.get("name") or sku or "Доп. комплектующее"),
                "finish": str(
                    extra.get("finish_name")
                    or extra.get("finishName")
                    or extra.get("color")
                    or ""
                ),
            }
            issues.append(issue)
            continue
        elif (
            item is not None
            and version is not None
            and getattr(version, "cost_is_set", True)
        ):
            selected_cost = decimal_value(version.cost)
            unit_sale = money(
                selected_cost
                * _markup_factor(version.profile_markup_percent)
                * _discount_factor(version.profile_discount_percent)
            )
            category = (
                version.category
                if version.category in {"profile", "component", "service"}
                else "component"
            )
        else:
            issue = {
                "code": "missing_price",
                "sku": sku or f"PROJECT-EXTRA-{index}",
                "name": str(extra.get("name") or sku or "Доп. комплектующее"),
                "unit": str(extra.get("unit") or "шт"),
            }
            issues.append(issue)
            continue

        name = str(getattr(item, "name", "") or extra.get("name") or sku).strip()
        line_unit = str(getattr(item, "unit", "") or extra.get("unit") or "шт")
        pricing_unit = str(getattr(version, "unit", "") or line_unit)
        length_factor = Decimal("1")
        if (
            item is not None
            and category == "profile"
            and _canonical_unit(pricing_unit) == "m"
        ):
            length_metres = _extra_profile_length_metres(extra.get("size"))
            if length_metres is None:
                issues.append(
                    {
                        "code": "invalid_extra_length",
                        "project_extra_index": index,
                        "sku": sku or item.sku,
                        "name": name,
                    }
                )
                continue
            length_factor = length_metres
            # Documents still show the original number of physical blanks.
            # Only the pricing basis is converted to metres.
            line_unit = "шт"
        pricing_quantity = quantity * length_factor
        internal_total = money(max(ZERO, unit_sale) * pricing_quantity)
        public_line, exact = _public_line(
            line_id=f"project-extra-{index}",
            name=name,
            category=category,
            quantity=quantity,
            unit=line_unit,
            internal_total=internal_total,
            terms=terms,
        )
        finish_name = str(
            extra.get("finish_name")
            or extra.get("finishName")
            or getattr(variant, "name", "")
            or ""
        ).strip()
        actual_color = str(extra.get("color") or "").strip()
        public_line["component_details"] = {
            "catalog_item_id": catalog_item_id,
            "finish_variant_id": finish_variant_id,
            "sku": sku or str(getattr(item, "sku", "") or ""),
            "name": name,
            "size": str(extra.get("size") or ""),
            "finish": finish_name,
            "color": actual_color,
            "unit": public_line["unit"],
            "stage": str(
                extra.get("deliveryStage") or extra.get("delivery_stage") or "both"
            ),
            "pricing_quantity": decimal_text(pricing_quantity),
            "pricing_unit": pricing_unit,
            "pricing_unit_final_price": money_text(exact["total"] / pricing_quantity),
        }
        minimum_total = (
            money(
                selected_cost
                * pricing_quantity
                * _markup_factor(version.min_margin_percent)
            )
            if version is not None
            else money(selected_cost * pricing_quantity)
        )
        if exact["total"] < minimum_total:
            issues.append(
                {
                    "code": "below_minimum_margin",
                    "project_extra_index": index,
                    "sku": sku,
                    "name": name,
                }
            )
        public_lines.append(public_line)
        exact_lines.append(exact)
        line_minimums.append(
            (
                money(minimum_total),
                {
                    "code": "below_minimum_margin",
                    "project_extra_index": index,
                    "sku": sku,
                    "name": name,
                },
            )
        )
        internal_project_extras.append(
            {
                "line_id": f"project-extra-{index}",
                "index": index,
                "catalog_item_id": catalog_item_id,
                "finish_variant_id": finish_variant_id,
                "sku": sku or str(getattr(item, "sku", "") or ""),
                "name": name,
                "category": category,
                "quantity": decimal_text(quantity),
                "unit": line_unit,
                "finish": finish_name,
                "cost": money_text(selected_cost * length_factor),
                "base_cost_total": money_text(selected_cost * pricing_quantity),
                "unit_sale": money_text(unit_sale * length_factor),
                "pricing_quantity": decimal_text(pricing_quantity),
                "pricing_unit": pricing_unit,
                "catalog_unit_cost": money_text(selected_cost),
                "price_version_id": version.id if version is not None else None,
                "price_source": getattr(version, "source", None),
                "cost_known": item is not None
                or extra.get("actual_cost", extra.get("actualCost")) not in (None, ""),
                "internal_total": money_text(internal_total),
                "final_price": public_line["line_total"],
                "minimum_total": money_text(minimum_total),
            }
        )

    services = _json_load(state.services_payload, [])
    internal_services: list[dict[str, Any]] = []
    for index, service in enumerate(services if isinstance(services, list) else []):
        if not isinstance(service, dict):
            continue
        quantity = decimal_value(service.get("quantity"))
        sale_price = decimal_value(
            service.get("sale_price", service.get("base_cost")), Decimal("-1")
        )
        actual_cost_raw = service.get("actual_cost")
        actual_cost = (
            decimal_value(actual_cost_raw, Decimal("-1"))
            if actual_cost_raw not in (None, "")
            else None
        )
        if (
            quantity <= 0
            or sale_price < 0
            or (actual_cost is not None and actual_cost < 0)
        ):
            issues.append(
                {
                    "code": "invalid_service",
                    "service_id": str(service.get("id") or index),
                    "name": str(service.get("name") or "Услуга"),
                }
            )
            continue
        internal_total = money(quantity * sale_price)
        service_minimum = (
            money(quantity * actual_cost) if actual_cost is not None else ZERO
        )
        public_line, exact = _public_line(
            line_id=str(service.get("id") or f"service-{index + 1}"),
            name=str(service.get("name") or "Услуга"),
            category="service",
            quantity=quantity,
            unit=str(service.get("unit") or "услуга"),
            internal_total=internal_total,
            terms=terms,
        )
        if exact["total"] < service_minimum:
            margin_issue = {
                "code": "below_minimum_margin",
                "service_id": public_line["id"],
                "name": public_line["name"],
            }
            issues.append(margin_issue)
        public_lines.append(public_line)
        exact_lines.append(exact)
        line_minimums.append(
            (
                service_minimum,
                {
                    "code": "below_minimum_margin",
                    "service_id": public_line["id"],
                    "name": public_line["name"],
                },
            )
        )
        internal_services.append(
            {
                **service,
                "base_cost": money_text(sale_price),
                "sale_price": money_text(sale_price),
                "actual_cost": money_text(actual_cost)
                if actual_cost is not None
                else None,
                "cost_known": actual_cost is not None,
                "base_cost_total": money_text(service_minimum)
                if actual_cost is not None
                else None,
                "internal_total": money_text(internal_total),
                "dealer_markup_percent": decimal_text(terms["dealer_markup_percent"]),
                "dealer_discount_percent": public_line["discount_percent"],
                "final_price": public_line["line_total"],
            }
        )

    _apply_quote_discount_rules(
        public_lines,
        exact_lines,
        _json_load(state.discounts_payload, []),
    )

    # Keep the private trace in agreement with the price after every order rule.
    final_lines = {line["id"]: line for line in public_lines}
    for source in [*internal_project_extras, *internal_services]:
        line = final_lines.get(source.get("line_id") or source.get("id"))
        if line:
            after_dealer = decimal_value(source["final_price"])
            source["after_dealer_terms"] = money_text(after_dealer)
            source["final_price"] = line["line_total"]
            source["order_discount_amount"] = money_text(
                max(ZERO, after_dealer - decimal_value(line["line_total"]))
            )
    for section_source in internal_sections:
        line = final_lines[f"section-{section_source['section_id']}"]
        section_source["after_dealer_terms"] = section_source["final_price"]
        section_source["order_discount_amount"] = money_text(
            max(
                ZERO,
                decimal_value(section_source["final_price"])
                - decimal_value(line["line_total"]),
            )
        )
        section_source["final_price"] = line["line_total"]
        bom = section_source["bom"]
        allocated = _allocate_money(
            (decimal_value(row["internal_total"]) for row in bom),
            decimal_value(line["line_total"]),
        )
        for row, total in zip(bom, allocated):
            row["client_total"] = money_text(total)
            if total < decimal_value(row["minimum_total"]):
                issue = {
                    "code": "below_minimum_margin",
                    "section_id": section_source["section_id"],
                    "sku": row["sku"],
                    "name": line["name"],
                }
                issues.append(issue)
                section_source["issues"].append(issue)

    # Explicit category/order discounts are applied after the base buyer
    # terms. Re-check every line afterwards so neither a percentage nor a
    # fixed discount can silently drive the sale below its configured floor.
    for exact, (minimum_total, issue) in zip(exact_lines, line_minimums):
        if exact["total"] >= minimum_total:
            continue
        identity = {
            key: value for key, value in issue.items() if key not in {"code", "name"}
        }
        already_reported = any(
            row.get("code") == "below_minimum_margin"
            and all(row.get(key) == value for key, value in identity.items())
            for row in issues
        )
        if not already_reported:
            issues.append(issue)

    if unsupported_sections:
        issues.append(
            {
                "code": "unsupported_section_pricing",
                "name": "Расчёт стоимости поддерживает Слайд 1, Слайд 2 и ЦС без дверей",
                "section_ids": [section.id for section in unsupported_sections],
            }
        )
    if not slide_sections and not public_lines:
        issues.append(
            {
                "code": "no_slide_sections",
                "name": "В проекте нет позиций для расчёта стоимости",
            }
        )

    presented_totals = _prepare_money_presentation(public_lines)
    if decimal_value(presented_totals["grand_total"]) < sum(
        (floor for floor, _ in line_minimums), ZERO
    ):
        issues.append(
            {
                "code": "below_minimum_margin",
                "scope": "order",
                "name": "Итог с учётом округления",
            }
        )

    margin_approval = _margin_approval_details(
        db,
        project,
        state,
        issues,
        at=now,
    )
    margin_override = bool(margin_approval["valid"])
    blocking_issues = [
        issue
        for issue in issues
        if issue["code"]
        in {
            "missing_price",
            "missing_finish_price",
            "unit_mismatch",
            "invalid_extra_length",
            "invalid_extra_quantity",
            "invalid_extra_price",
            "invalid_service",
            "no_slide_sections",
            "unsupported_section_pricing",
        }
        or (issue["code"] == "below_minimum_margin" and not margin_override)
    ]
    missing_by_sku: dict[str, dict[str, Any]] = {}
    for issue in issues:
        if issue["code"] not in {
            "missing_price",
            "missing_finish_price",
            "unit_mismatch",
        }:
            continue
        missing_by_sku.setdefault(
            issue["sku"],
            {
                "sku": issue["sku"],
                "name": issue["name"],
                "unit": issue.get("unit", ""),
                "reason": issue["code"],
            },
        )
    warnings = []
    if missing_by_sku:
        warnings.append("Для обязательных позиций не заданы действующие цены.")
    for issue in issues:
        if issue["code"] == "invalid_extra_quantity":
            warnings.append(
                f"Доп. комплектующее №{issue['project_extra_index']}: укажите положительное количество."
            )
        if issue["code"] == "invalid_extra_price":
            warnings.append(
                f"Доп. комплектующее №{issue['project_extra_index']}: проверьте числовые поля цены."
            )
        if issue["code"] == "invalid_service":
            warnings.append("Проверьте количество и цену услуги.")
        if issue["code"] == "invalid_extra_length":
            warnings.append(
                f"Доп. комплектующее №{issue['project_extra_index']} «{issue['name']}»: "
                "укажите положительную длину детали в мм для расчёта цены за метр."
            )
    if any(issue["code"] == "below_minimum_margin" for issue in issues):
        warnings.append(
            "Итоговая цена ниже минимально допустимой."
            if not margin_override
            else "Исключение по минимальной цене разрешено ответственным сотрудником."
        )
    if any(issue["code"] == "no_slide_sections" for issue in issues):
        warnings.append("В проекте нет позиций для расчёта стоимости.")
    if any(issue["code"] == "unsupported_section_pricing" for issue in issues):
        warnings.append(
            "В проекте есть конфигурации без полного расчёта стоимости. Поддерживаются Слайд 1, Слайд 2 и ЦС без дверей."
        )
    warnings.extend(slide_warnings)

    basis_date = state.fixed_at or now
    valid_until = basis_date.date() + timedelta(days=state.validity_days)
    total_area = sum(
        (
            decimal_value(line.get("section_details", {}).get("area_m2"))
            * decimal_value(line.get("quantity"), Decimal("1"))
            for line in public_lines
            if isinstance(line.get("section_details"), dict)
        ),
        ZERO,
    )
    public_payload = {
        "cs_cover_cutting": cover_plan,
        "document_layout_version": 2,
        "money_presentation_version": 2,
        "project": {
            "id": project.id,
            "number": project.number,
            "invoice_number": getattr(project, "invoice_number", None),
            "order_number": getattr(project, "order_number", None),
            "customer": project.customer,
        },
        "revision": state.revision,
        "status": state.status,
        "fixed_at": state.fixed_at.isoformat() if state.fixed_at else None,
        "quote_date": basis_date.date().isoformat(),
        "manager": str(
            getattr(getattr(project, "owner", None), "display_name", "") or ""
        ),
        "total_area_m2": decimal_text(
            total_area.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        ),
        "currency": "RUB",
        "lines": public_lines,
        "totals": presented_totals,
        "validity_days": state.validity_days,
        "valid_until": valid_until.isoformat(),
        "manufacturing_term": state.manufacturing_term,
        "payment_terms": state.payment_terms,
        "discounts": _canonical_discounts(state.discounts_payload),
        "missing_price_count": len(missing_by_sku),
        "warnings": warnings,
        "pricing_issues": blocking_issues,
        "export_allowed": not blocking_issues,
        "stale": False,
    }
    internal_payload = {
        "public": public_payload,
        "sections": internal_sections,
        "services": internal_services,
        "project_extras": internal_project_extras,
        "issues": issues,
        "blocking_issues": blocking_issues,
        "missing_prices": sorted(missing_by_sku.values(), key=lambda row: row["sku"]),
        "dealer_terms": {key: decimal_text(value) for key, value in terms.items()},
        "margin_approval": margin_approval,
        "calculated_at": now.isoformat(),
        "cost_warnings": [
            {
                "line_id": row.get("line_id") or row.get("id"),
                "name": row.get("name"),
                "code": "unknown_actual_cost",
            }
            for row in [*internal_project_extras, *internal_services]
            if not row.get("cost_known")
        ]
        + [
            {
                "section_id": section["section_id"],
                "sku": row["sku"],
                "name": row["name"],
                "code": "unknown_actual_cost",
            }
            for section in internal_sections
            for row in section["bom"]
            if not row.get("cost_known")
        ],
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
    state.revision = 1
    state.status = "draft"
    state.fixed_at = None
    state.fixed_by = None
    public, internal, signature = calculate_quote(db, project, state, at=at)
    public["revision"] = 1
    public["status"] = "draft"
    public["fixed_at"] = None
    internal_public = internal.get("public")
    if isinstance(internal_public, dict):
        internal_public.update(
            {
                "revision": 1,
                "status": "draft",
                "fixed_at": None,
            }
        )
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
    if state.status != "fixed":
        payload = refresh_draft_quote(db, project, state, at=at)
    else:
        payload = _json_load(state.public_payload, {})
    payload = safe_public_payload(payload)
    payload["revision"] = state.revision
    payload["status"] = state.status
    payload["fixed_at"] = state.fixed_at.isoformat() if state.fixed_at else None
    payload["stale"] = quote_is_stale(db, project, state, at=at)
    return payload


def _archive_quote(db: Session, state: models.ProjectQuoteState) -> None:
    """Persist each fixed edition once; later revisions cannot replace it."""
    if state.status != "fixed" or state.public_payload in (None, "", "{}"):
        return
    existing = (
        db.query(models.ProjectQuoteRevision)
        .filter_by(project_id=state.project_id, revision=state.revision)
        .first()
    )
    if existing is None:
        db.add(
            models.ProjectQuoteRevision(
                project_id=state.project_id,
                revision=state.revision,
                public_payload=state.public_payload,
                internal_payload=state.internal_payload or "{}",
                source_signature=state.source_signature,
                fixed_at=state.fixed_at,
                fixed_by=state.fixed_by,
            )
        )
        db.flush()


def quote_revision_snapshot(
    db: Session,
    project: models.Project,
    revision: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read-only access to public/private frozen data, with current legacy fallback."""
    saved = (
        db.query(models.ProjectQuoteRevision)
        .filter_by(project_id=project.id, revision=revision)
        .first()
    )
    if saved is None:
        saved = (
            db.query(models.ProjectQuoteState)
            .filter_by(project_id=project.id, revision=revision, status="fixed")
            .first()
        )
    if saved is None or saved.public_payload in (None, "", "{}"):
        raise QuotePricingError("Сохранённая редакция КП не найдена")
    public = safe_public_payload(_json_load(saved.public_payload, {}))
    public.update({"revision": revision, "status": "fixed", "stale": False})
    return public, _json_load(saved.internal_payload, {})


def quote_revision_list(db: Session, project: models.Project) -> list[dict[str, Any]]:
    saved_rows = (
        db.query(models.ProjectQuoteRevision).filter_by(project_id=project.id).all()
    )
    current = (
        db.query(models.ProjectQuoteState)
        .filter_by(project_id=project.id, status="fixed")
        .first()
    )
    if current is not None and current.revision not in {
        row.revision for row in saved_rows
    }:
        saved_rows.append(current)
    return [
        {
            "revision": row.revision,
            "status": "fixed",
            "fixed_at": row.fixed_at.isoformat() if row.fixed_at else None,
            "fixed_by": row.fixed_by,
            "currency": "RUB",
            "grand_total": money_text(
                decimal_value(
                    safe_public_payload(_json_load(row.public_payload, {}))
                    .get("totals", {})
                    .get("document_grand_total", "0.00")
                )
            ),
        }
        for row in sorted(saved_rows, key=lambda row: row.revision, reverse=True)
    ]


def freeze_quote(
    db: Session,
    project: models.Project,
    actor: models.User,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    if state.status == "fixed" and state.public_payload not in (None, "", "{}"):
        _archive_quote(db, state)
        payload = safe_public_payload(_json_load(state.public_payload, {}))
        payload["stale"] = quote_is_stale(db, project, state, at=at)
        return payload
    evaluation_at = _normalize_datetime(at or datetime.utcnow())
    state.revision = 1
    state.status = "draft"
    state.fixed_at = None
    state.fixed_by = None
    public, internal, signature = calculate_quote(
        db,
        project,
        state,
        at=evaluation_at,
    )
    payload = safe_public_payload(public)
    if not payload.get("export_allowed"):
        raise QuoteExportBlocked(payload)
    fixed_at = evaluation_at
    state.status = "fixed"
    state.revision = 1
    state.fixed_at = fixed_at
    state.fixed_by = actor.id
    state.updated_at = datetime.utcnow()
    state.source_signature = signature
    state.source_project_updated_at = project.updated_at
    payload["status"] = "fixed"
    payload["revision"] = 1
    payload["fixed_at"] = fixed_at.isoformat()
    payload["valid_until"] = (
        fixed_at.date() + timedelta(days=state.validity_days)
    ).isoformat()
    public.update(
        {
            "status": "fixed",
            "revision": 1,
            "fixed_at": fixed_at.isoformat(),
            "valid_until": payload["valid_until"],
        }
    )
    internal_public = internal.get("public")
    if isinstance(internal_public, dict):
        internal_public.update(public)
    state.public_payload = json.dumps(payload, ensure_ascii=False)
    state.internal_payload = json.dumps(internal, ensure_ascii=False)
    db.flush()
    _archive_quote(db, state)
    return payload


def refresh_quote_revision(
    db: Session,
    project: models.Project,
    actor: models.User,
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    state = get_or_create_quote_state(db, project)
    evaluation_at = _normalize_datetime(at or datetime.utcnow())
    if state.status != "fixed":
        return safe_public_payload(
            refresh_draft_quote(db, project, state, at=evaluation_at)
        )
    if not quote_is_stale(db, project, state, at=evaluation_at):
        payload = safe_public_payload(_json_load(state.public_payload, {}))
        payload["revision"] = max(1, int(state.revision or 1))
        payload["status"] = "fixed"
        payload["fixed_at"] = state.fixed_at.isoformat() if state.fixed_at else None
        payload["stale"] = False
        return payload

    _archive_quote(db, state)
    next_revision = max(1, int(state.revision or 1)) + 1
    public, internal, signature = calculate_quote(
        db,
        project,
        state,
        at=evaluation_at,
    )
    payload = safe_public_payload(public)
    if not payload.get("export_allowed"):
        raise QuoteExportBlocked(payload)

    fixed_at = evaluation_at
    valid_until = (fixed_at.date() + timedelta(days=state.validity_days)).isoformat()
    public.update(
        {
            "revision": next_revision,
            "status": "fixed",
            "fixed_at": fixed_at.isoformat(),
            "valid_until": valid_until,
            "stale": False,
        }
    )
    payload.update(
        {
            "revision": next_revision,
            "status": "fixed",
            "fixed_at": fixed_at.isoformat(),
            "valid_until": valid_until,
            "stale": False,
        }
    )
    internal_public = internal.get("public")
    if isinstance(internal_public, dict):
        internal_public.update(public)
    state.revision = next_revision
    state.status = "fixed"
    state.fixed_at = fixed_at
    state.fixed_by = actor.id
    state.public_payload = json.dumps(payload, ensure_ascii=False)
    state.internal_payload = json.dumps(internal, ensure_ascii=False)
    state.source_signature = signature
    state.source_project_updated_at = project.updated_at
    state.updated_at = datetime.utcnow()
    db.flush()
    _archive_quote(db, state)
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
    if state.status != "fixed":
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
    margin_approval = pending_internal.get("margin_approval")
    if not isinstance(margin_approval, dict):
        margin_approval = _margin_approval_details(
            db,
            project,
            state,
            list(pending_internal.get("issues") or []),
            at=evaluation_at,
        )
    return {
        "revision": state.revision,
        "status": state.status,
        "stale": stale,
        "config": {
            "validity_days": state.validity_days,
            "manufacturing_term": state.manufacturing_term,
            "payment_terms": state.payment_terms,
            "services": _json_load(state.services_payload, []),
            "discounts": _canonical_discounts(state.discounts_payload),
            "overrides": _json_load(state.overrides_payload, []),
            "margin_override_comment": (
                (state.margin_override_comment or "")
                if margin_approval.get("valid")
                else ""
            ),
        },
        "missing_prices": list(pending_internal.get("missing_prices") or []),
        "pending_warnings": pending_warnings,
        "margin_approval": margin_approval,
        "calculation": pending_internal,
    }
