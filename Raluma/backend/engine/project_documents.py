from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from math import ceil
import re
from typing import Iterable

from jinja2 import Environment, FileSystemLoader

from engine.book_calc import calculate_book
from engine.glass_types import default_glass_type
from engine.lift_calc import PENOPLEX_20MM, calculate_lift
from engine.pdf import TEMPLATES_DIR, _img_b64, glass_mm
from engine.slide_calc import calculate_slide


DOC_TITLES = {
    "commercial": "Коммерческое предложение",
    "paint": "Заявка на покраску",
    "glass": "Заказ стекла",
    "delivery": "Накладная",
    "hardware_order": "Наряд-заказ на фурнитуру",
}


@dataclass
class CalculatedSection:
    order: int
    section: object
    calc: object


@dataclass
class PhysicalGlassItem:
    width_mm: float
    height_mm: float
    note: str = ""


def _get_env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["img_b64"] = _img_b64
    return env


def _section_order(section: object, fallback: int) -> int:
    try:
        order = int(getattr(section, "order", 0) or 0)
    except (TypeError, ValueError):
        order = 0
    return order or fallback


def _section_name_number(section: object) -> int | None:
    match = re.search(r"\d+", str(getattr(section, "name", "") or ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _section_sort_key(section: object, fallback: int) -> tuple[int, int, int]:
    order = _section_order(section, fallback)
    name_number = _section_name_number(section)
    return name_number if name_number is not None else order, order, fallback


def _iter_slide_sections(sections: Iterable[object]) -> list[CalculatedSection]:
    rows: list[CalculatedSection] = []
    sorted_sections = sorted(
        list(sections),
        key=lambda section: _section_sort_key(section, 999999),
    )
    slide_sections = [
        section
        for section in sorted_sections
        if getattr(section, "system", None) == "СЛАЙД"
    ]
    for index, section in enumerate(slide_sections, start=1):
        rows.append(
            CalculatedSection(
                order=index,
                section=section,
                calc=calculate_slide(section),
            )
        )
    return rows


def _iter_calculated_sections(
    sections: Iterable[object],
) -> list[CalculatedSection]:
    """Calculate document-capable systems without sharing their formula paths."""
    rows: list[CalculatedSection] = []
    sorted_sections = sorted(
        list(sections),
        key=lambda section: _section_sort_key(section, 999999),
    )
    for index, section in enumerate(sorted_sections, start=1):
        system = str(getattr(section, "system", "") or "").strip().upper()
        if system not in {"СЛАЙД", "ЛИФТ"}:
            continue
        calc = calculate_slide(section) if system == "СЛАЙД" else calculate_lift(section)
        rows.append(
            CalculatedSection(
                order=index,
                section=section,
                calc=calc,
            )
        )
    return rows


def _format_mm(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded).replace(".", ",")


def _drawing_hardware_text(value: object) -> str:
    text = str(value or "").strip().lower().strip("—- ")
    if not text or text == "none" or text.startswith(("без", "нет")):
        return ""
    return text


def _has_drawing_handle(*values: object) -> bool:
    combined = " ".join(
        text for text in (_drawing_hardware_text(value) for value in values) if text
    )
    return any(
        token in combined
        for token in (
            "кноб",
            "скоб",
            "rs3014",
        )
    )


def _side_has_glass_drawing(section: object, side: str) -> bool:
    return _has_drawing_handle(
        getattr(section, f"handle_{side}", None),
    )


def _center_has_glass_drawing(section: object, side: str | None = None) -> bool:
    return _has_drawing_handle(
        getattr(section, "center_handle", None),
    )


def _legacy_has_glass_drawing(section: object) -> bool:
    return _has_drawing_handle(
        getattr(section, "handle", None),
    )


def _glass_note_for_role(section: object, role: str) -> str:
    has_drawing = False
    if role == "left":
        has_drawing = _side_has_glass_drawing(section, "left")
    elif role == "right":
        has_drawing = _side_has_glass_drawing(section, "right")
    elif role == "center":
        has_drawing = _center_has_glass_drawing(section)
    elif role == "center_left":
        has_drawing = _center_has_glass_drawing(section, "left")
    elif role == "center_right":
        has_drawing = _center_has_glass_drawing(section, "right")
    elif role == "single":
        has_drawing = (
            _side_has_glass_drawing(section, "left")
            or _side_has_glass_drawing(section, "right")
            or _center_has_glass_drawing(section)
        )

    if role in ("left", "right", "single"):
        has_drawing = has_drawing or _legacy_has_glass_drawing(section)

    return "(чертеж)" if has_drawing else ""


def _positive_int(value: object, default: int = 0) -> int:
    try:
        return max(0, int(value or default))
    except (TypeError, ValueError):
        return default


def _glass_by_position(calc: object) -> dict[str, object]:
    rows = {}
    for glass in getattr(calc, "glass", []) or []:
        if getattr(glass, "qty", 0) <= 0:
            continue
        rows.setdefault(getattr(glass, "position", ""), glass)
    return rows


def _physical_glass(glass: object, note: str) -> PhysicalGlassItem:
    return PhysicalGlassItem(
        width_mm=float(getattr(glass, "width_mm", 0) or 0),
        height_mm=float(getattr(glass, "height_mm", 0) or 0),
        note=note,
    )


def _expand_1row_glass(section: object, calc: object) -> list[PhysicalGlassItem]:
    rows = _glass_by_position(calc)
    panels = _positive_int(getattr(section, "panels", 0), 1)
    quantity = _positive_int(getattr(section, "quantity", 0), 1)
    result: list[PhysicalGlassItem] = []

    if panels <= 1:
        single = rows.get("Промежуточное") or next(iter(rows.values()), None)
        if single is None:
            return result
        for _ in range(quantity):
            result.append(
                _physical_glass(single, _glass_note_for_role(section, "single"))
            )
        return result

    edge = rows.get("Крайние")
    left = rows.get("Левое") or edge
    middle = rows.get("Промежуточные")
    right = rows.get("Правое") or edge

    for _ in range(quantity):
        if left is not None:
            result.append(_physical_glass(left, _glass_note_for_role(section, "left")))
        if middle is not None:
            for _ in range(max(panels - 2, 0)):
                result.append(_physical_glass(middle, ""))
        if right is not None:
            result.append(
                _physical_glass(right, _glass_note_for_role(section, "right"))
            )

    return result


def _expand_2row_glass(section: object, calc: object) -> list[PhysicalGlassItem]:
    rows = _glass_by_position(calc)
    panels = _positive_int(getattr(section, "panels", 0), 4)
    quantity = _positive_int(getattr(section, "quantity", 0), 1)
    result: list[PhysicalGlassItem] = []

    left = rows.get("Левое")
    middle = rows.get("Промежуточные")
    center_left = rows.get("Центральное левое")
    center_right = rows.get("Центральное правое")
    center = rows.get("Центральные")
    right = rows.get("Правое")
    middle_count = max(panels - 4, 0)
    left_middle_count = middle_count // 2
    right_middle_count = middle_count - left_middle_count

    for _ in range(quantity):
        if left is not None:
            result.append(_physical_glass(left, _glass_note_for_role(section, "left")))
        if middle is not None:
            for _ in range(left_middle_count):
                result.append(_physical_glass(middle, ""))
        if center_left is not None:
            result.append(
                _physical_glass(
                    center_left, _glass_note_for_role(section, "center_left")
                )
            )
        elif center is not None:
            result.append(
                _physical_glass(center, _glass_note_for_role(section, "center_left"))
            )
        if center_right is not None:
            result.append(
                _physical_glass(
                    center_right, _glass_note_for_role(section, "center_right")
                )
            )
        elif center is not None:
            result.append(
                _physical_glass(center, _glass_note_for_role(section, "center_right"))
            )
        if middle is not None:
            for _ in range(right_middle_count):
                result.append(_physical_glass(middle, ""))
        if right is not None:
            result.append(
                _physical_glass(right, _glass_note_for_role(section, "right"))
            )

    return result


def _expand_glass_for_order(section: object, calc: object) -> list[PhysicalGlassItem]:
    rows = _positive_int(getattr(section, "slide_rows", 1), 1)
    if rows == 2:
        return _expand_2row_glass(section, calc)
    return _expand_1row_glass(section, calc)


def _build_commercial_rows(calculated: list[CalculatedSection]) -> list[dict]:
    rows = []
    for item in calculated:
        glass_area = sum(
            (glass.width_mm * glass.height_mm * glass.qty) / 1_000_000
            for glass in item.calc.glass
            if glass.qty > 0
        )
        rows.append(
            {
                "order": item.order,
                "name": getattr(item.section, "name", f"Секция {item.order}"),
                "system": f"Raluma Slide RS {getattr(item.section, 'rails', 3) or 3}-рельсовая",
                "size": f"{_format_mm(getattr(item.section, 'width', 0))}×{_format_mm(getattr(item.section, 'height', 0))}",
                "panels": getattr(item.section, "panels", 0) or 0,
                "qty": getattr(item.section, "quantity", 1) or 1,
                "color": item.calc.color_text or "—",
                "glass": item.calc.glass_type,
                "threshold": item.calc.threshold_text or "—",
                "area": round(glass_area, 2),
            }
        )
    return rows


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _parse_paint_manual_rows(raw_rows: object) -> list[dict]:
    if isinstance(raw_rows, list):
        rows = raw_rows
    else:
        try:
            rows = json.loads(raw_rows or "[]")
        except (TypeError, json.JSONDecodeError):
            rows = []
    return [row for row in rows if isinstance(row, dict)]


def _paint_color_key(value: object) -> str:
    normalized = " ".join(str(value or "").split()).casefold()
    if normalized.startswith("ral "):
        normalized = normalized[4:].strip()
    return normalized


def _manual_paint_row(raw: dict) -> tuple[str, dict] | None:
    article = str(raw.get("article") or raw.get("sku") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not article and not name:
        return None
    color = " ".join(str(raw.get("color") or "").split())
    qty = max(0, int(_safe_float(raw.get("qty") or raw.get("quantity"), 0)))
    clean = _safe_float(raw.get("clean") or raw.get("cleanSize"), 0)
    allowance = _safe_float(raw.get("allowance") or raw.get("allowanceSize"), 0)
    if allowance <= 0 and clean > 0:
        allowance = clean + 50
    total_m = _safe_float(raw.get("totalM") or raw.get("total_m"), 0)
    if total_m <= 0 and qty > 0 and allowance > 0:
        total_m = round(qty * allowance / 1000, 1)
    row = {
        "article": article,
        "name": name,
        "image": str(raw.get("imageFile") or raw.get("image") or "").strip(),
        "image_data": str(raw.get("imageData") or raw.get("image_data") or "").strip(),
        "paint_marker": False,
        "paint_marker_class": "",
        "qty": qty,
        "clean": clean,
        "allowance": allowance,
        "total_m": total_m,
        "note": str(raw.get("note") or "").strip(),
    }
    return color, row


def _build_paint_pages(
    calculated: list[CalculatedSection], manual_rows: object | None = None
) -> list[dict]:
    grouped: dict[str, dict[tuple, dict]] = defaultdict(dict)

    for item in calculated:
        color = item.calc.color_text or "Без цвета"
        for profile in item.calc.profiles:
            if not profile.painted or profile.length_mm <= 0:
                continue
            clean = _ceil_to_step(profile.length_mm, 50)
            allowance = clean + 50
            note = profile.paint_note
            paint_image = _paint_request_image(profile.article, profile.image)
            has_baked_marker = paint_image != profile.image
            key = (
                profile.article,
                profile.name,
                clean,
                paint_image or "",
                "",
                note,
            )
            row = grouped[color].setdefault(
                key,
                {
                    "article": profile.article,
                    "name": profile.name,
                    "image": paint_image,
                    "image_data": "",
                    "paint_marker": profile.paint_mode == "Частично"
                    and not has_baked_marker,
                    "paint_marker_class": ""
                    if has_baked_marker
                    else _paint_marker_class(profile.article),
                    "qty": 0,
                    "clean": clean,
                    "allowance": allowance,
                    "total_m": 0.0,
                    "note": note,
                },
            )
            row["qty"] += int(profile.qty)
            row["total_m"] = round(row["qty"] * allowance / 1000, 1)

    calculated_colors = list(grouped)
    for manual_index, raw in enumerate(_parse_paint_manual_rows(manual_rows), start=1):
        parsed = _manual_paint_row(raw)
        if parsed is None:
            continue
        color, row = parsed
        if color:
            color_key = _paint_color_key(color)
            color = next(
                (
                    existing
                    for existing in calculated_colors
                    if _paint_color_key(existing) == color_key
                ),
                color,
            )
        elif len(calculated_colors) == 1:
            color = calculated_colors[0]
        else:
            color = "Без цвета"
        row["_manual"] = True
        row["_manual_order"] = manual_index
        key = (
            f"manual-{manual_index}",
            row["article"],
            row["name"],
            row["clean"],
            row["image"],
            row["image_data"],
            row["note"],
        )
        grouped[color][key] = row

    pages = []
    for color, rows_by_key in grouped.items():
        rows = sorted(
            rows_by_key.values(),
            key=lambda row: (
                1 if row.get("_manual") else 0,
                int(row.get("_manual_order") or 0),
                row["article"] if not row.get("_manual") else "",
                row["clean"] if not row.get("_manual") else 0,
            ),
        )
        groups = _group_paint_rows(rows)
        total_qty = sum(row["qty"] for row in rows)
        total_m = round(sum(row["total_m"] for row in rows), 1)
        pages.append(
            {
                "color": color,
                "rows": rows,
                "groups": groups,
                "total_qty": total_qty,
                "total_m": total_m,
            }
        )
    return sorted(pages, key=lambda page: page["color"])


def _group_paint_rows(rows: list[dict]) -> list[dict]:
    groups: list[dict] = []
    by_key: dict[tuple, dict] = {}
    for row in rows:
        if row.get("_manual"):
            key = ("manual", int(row.get("_manual_order") or 0))
        else:
            key = (
                "calculated",
                row["article"],
                row["name"],
                row["image"] or "",
                row.get("image_data") or "",
                row["note"] or "",
                bool(row["paint_marker"]),
                row["paint_marker_class"] or "",
            )
        group = by_key.get(key)
        if group is None:
            group = {
                "article": row["article"],
                "name": row["name"],
                "image": row["image"],
                "image_data": row.get("image_data") or "",
                "note": row["note"],
                "paint_marker": row["paint_marker"],
                "paint_marker_class": row["paint_marker_class"],
                "rows": [],
            }
            by_key[key] = group
            groups.append(group)
        group["rows"].append(row)
    return groups


def _paint_marker_class(article: str) -> str:
    normalized = str(article or "").lower()
    if normalized in {"rs2323", "rs2325"}:
        return "paint-marker-standard-threshold"
    if normalized in {"rs23231", "rs23251"}:
        return "paint-marker-overlay-threshold"
    return ""


def _paint_request_image(article: str, fallback: str | None) -> str | None:
    images = {
        "RS2323": "PAINT_RS2323.png",
        "RS23231": "PAINT_RS23231.png",
        "RS2325": "PAINT_RS2325.png",
        "RS23251": "PAINT_RS23251.png",
    }
    return images.get(str(article or "").upper(), fallback)


def _ceil_to_step(value: float, step: int) -> int:
    return int(ceil(float(value) / step) * step)


def _marking_key(marking: str) -> tuple[int, int]:
    try:
        section_part, glass_part = marking.split(",", 1)
        return int(section_part), int(glass_part)
    except (ValueError, TypeError):
        return 999999, 999999


def _build_glass_rows(
    project: object, calculated: list[CalculatedSection]
) -> list[dict]:
    grouped: dict[tuple, dict] = {}

    for item in calculated:
        system = str(getattr(item.section, "system", "") or "").strip().upper()
        if system == "ЛИФТ":
            glass_index = 0
            for panel in item.calc.panels:
                if panel.filling == PENOPLEX_20MM:
                    continue
                glass_index += 1
                width = glass_mm(panel.width_mm)
                height = glass_mm(panel.height_mm)
                note = ""
                key = (panel.filling, width, height, note)
                row = grouped.setdefault(
                    key,
                    {
                        "markings": [],
                        "glass_type": panel.filling,
                        "width": width,
                        "height": height,
                        "qty": 0,
                        "area": 0.0,
                        "note": note,
                    },
                )
                row["markings"].append(f"{item.order},{glass_index}")
                row["qty"] += max(1, int(panel.qty or 0))
                row["area"] = round(width * height * row["qty"] / 1_000_000, 3)
            continue

        for glass_index, glass in enumerate(
            _expand_glass_for_order(item.section, item.calc), start=1
        ):
            width = glass_mm(glass.width_mm)
            height = glass_mm(glass.height_mm)
            note = glass.note
            key = (item.calc.glass_type, width, height, note)
            row = grouped.setdefault(
                key,
                {
                    "markings": [],
                    "glass_type": item.calc.glass_type,
                    "width": width,
                    "height": height,
                    "qty": 0,
                    "area": 0.0,
                    "note": note,
                },
            )
            row["markings"].append(f"{item.order},{glass_index}")
            row["qty"] += 1
            row["area"] = round(width * height * row["qty"] / 1_000_000, 3)

    for row in grouped.values():
        row["markings"].sort(key=_marking_key)

    rows = sorted(
        grouped.values(),
        key=lambda row: _marking_key(row["markings"][0] if row["markings"] else ""),
    )
    for index, row in enumerate(rows, start=1):
        row["index"] = index
        row["marking"] = row["markings"][0] if row["markings"] else ""
    return rows


def _parse_json_object(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _delivery_settings(project: object) -> dict:
    raw = _parse_json_object(getattr(project, "delivery_note_data", None))
    date_mode = str(raw.get("dateMode") or "blank")
    if date_mode not in {"blank", "today", "custom"}:
        date_mode = "blank"

    raw_places = raw.get("places")
    places = (
        {str(key): str(value or "") for key, value in raw_places.items()}
        if isinstance(raw_places, dict)
        else {}
    )
    return {
        "dateMode": date_mode,
        "date": str(raw.get("date") or ""),
        "note": str(raw.get("note") or ""),
        "contact": str(raw.get("contact") or ""),
        "delivery": str(raw.get("delivery") or ""),
        "places": places,
    }


def _delivery_date_text(settings: dict) -> str:
    mode = settings["dateMode"]
    if mode == "today":
        value = date.today()
    elif mode == "custom":
        try:
            value = datetime.strptime(settings["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            value = None
    else:
        value = None
    if value is None:
        return f"___ __________ {date.today().year} г."
    return value.strftime("%d.%m.%Y")


def _project_delivery_stage(project: object) -> tuple[int, int]:
    stages = 2 if _positive_int(getattr(project, "production_stages", 1), 1) == 2 else 1
    if stages == 1:
        return 1, 1
    current = (
        2 if _positive_int(getattr(project, "current_stage", 1), 1) == 2 else 1
    )
    return stages, current


def _extra_delivery_stage(extra: dict) -> str:
    stage = str(extra.get("deliveryStage") or extra.get("delivery_stage") or "both")
    return stage if stage in {"1", "2"} else "both"


def _extra_matches_delivery_stage(extra: dict, stage: int | None) -> bool:
    if stage is None:
        return True
    return _extra_delivery_stage(extra) in {"both", str(stage)}


def _delivery_key(prefix: str, *parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}-{digest}"


def _delivery_place(places: dict[str, str], key: str) -> str:
    return str(places.get(key) or "")


def _format_quantity(value: float) -> str:
    numeric = float(value or 0)
    if numeric.is_integer():
        return str(int(numeric))
    return str(round(numeric, 3)).replace(".", ",")


def _section_color(section: object, calc: object | None = None) -> str:
    def normalize(value: str) -> str:
        value = value.strip()
        if re.match(r"^\d{4}(?:\s|$)", value):
            return f"RAL {value}"
        return value

    painting = str(getattr(section, "painting_type", "") or "").strip()
    if "анод" in painting.lower():
        return "Анодированный"

    if calc is not None:
        color = str(getattr(calc, "color_text", "") or "").strip()
        if color:
            return normalize(color)

    ral = str(getattr(section, "ral_color", "") or "").strip()
    if ral:
        return normalize(ral)
    return painting or "Без цвета"


def _section_variant(section: object) -> tuple:
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "СЛАЙД":
        return (
            _positive_int(getattr(section, "slide_rows", 1), 1),
            _positive_int(getattr(section, "rails", 3), 3),
        )
    if system == "КНИЖКА":
        return (
            str(getattr(section, "book_system", "") or "").strip(),
            str(getattr(section, "book_subtype", "") or "").strip(),
        )
    if system == "ЛИФТ":
        return (
            _positive_int(getattr(section, "panels", 2), 2),
            str(getattr(section, "lift_opening_type", "") or "Сдвиг вниз").strip(),
        )
    if system == "ЦС":
        return (str(getattr(section, "cs_shape", "") or "").strip(),)
    return ()


def _construction_name(section: object) -> str:
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "СЛАЙД":
        rows = _positive_int(getattr(section, "slide_rows", 1), 1)
        rails = _positive_int(getattr(section, "rails", 3), 3)
        row_label = "1 ряд" if rows == 1 else "2 ряда"
        return f"Raluma SLIDE, {rails}-полозная система, {row_label}"
    if system == "КНИЖКА":
        variant = str(getattr(section, "book_system", "") or "").strip()
        return f"Raluma КНИЖКА{f' {variant}' if variant else ''}"
    if system == "ЛИФТ":
        panels = _positive_int(getattr(section, "panels", 2), 2)
        return f"Raluma ЛИФТ, {panels} панели"
    if system == "ЦС":
        variant = str(getattr(section, "cs_shape", "") or "").strip()
        return f"Raluma ЦС{f', {variant}' if variant else ''}"
    return system or "Секция"


def _delivery_threshold_text(value: object) -> str:
    threshold = " ".join(str(value or "").split())
    if not threshold:
        return ""
    if threshold.lower().startswith("порог"):
        return threshold
    return f"Порог {threshold[:1].lower()}{threshold[1:]}"


def _delivery_profile_set_name(system: object, stages: int) -> str:
    """Return the profile-set label after normalizing legacy stage data."""
    if stages == 1:
        return "КОМПЛЕКТ ПРОФИЛЕЙ"
    if str(system or "").strip().upper() == "СЛАЙД":
        return "Комплект направляющих и пристеночных профилей"
    return "Комплект профилей"


def _build_delivery_construction_rows(
    sections: list[object], places: dict[str, str]
) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for section in sections:
        system = str(getattr(section, "system", "") or "").strip().upper()
        if not system or system == "КОМПЛЕКТАЦИЯ":
            continue
        color = _section_color(section)
        variant = _section_variant(section)
        key = (system, variant, color)
        group = grouped.setdefault(
            key,
            {
                "system": system,
                "name": _construction_name(section),
                "color": color,
                "thresholds": [],
                "dimensions": {},
                "qty": 0,
            },
        )
        threshold = _delivery_threshold_text(getattr(section, "threshold", ""))
        if threshold and threshold not in group["thresholds"]:
            group["thresholds"].append(threshold)
        width = _format_mm(_safe_float(getattr(section, "width", 0)))
        height = _format_mm(_safe_float(getattr(section, "height", 0)))
        quantity = max(1, _positive_int(getattr(section, "quantity", 1), 1))
        dimension_key = (f"{width}×{height} мм", threshold)
        group["dimensions"][dimension_key] = (
            group["dimensions"].get(dimension_key, 0) + quantity
        )
        group["qty"] += quantity

    rows = []
    for group_key, group in grouped.items():
        place_key = _delivery_key("construction", *group_key)
        thresholds = group.pop("thresholds")
        if len(thresholds) == 1:
            threshold_text = thresholds[0]
        elif len(thresholds) > 1:
            threshold_text = "Пороги согласно ТЗ"
        else:
            threshold_text = ""
        rows.append(
            {
                **group,
                "dimensions": [
                    {"size": size, "threshold": threshold, "qty": qty}
                    for (size, threshold), qty in group["dimensions"].items()
                ],
                "threshold": threshold_text,
                "place_key": place_key,
                "places": _delivery_place(places, place_key),
            }
        )
    return rows


def _delivery_section_number(section: object, fallback: int) -> int:
    return _section_name_number(section) or _section_order(section, fallback)


def _build_delivery_glass_rows(
    project: object, sections: list[object], places: dict[str, str]
) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for fallback, section in enumerate(sections, start=1):
        system = str(getattr(section, "system", "") or "").strip().upper()
        if not system or system == "КОМПЛЕКТАЦИЯ":
            continue

        section_rows: dict[tuple, dict] = {}
        if system == "СЛАЙД":
            calc = calculate_slide(section)
            glass_type = calc.glass_type
            color = _section_color(section, calc)
            for glass in _expand_glass_for_order(section, calc):
                width = glass_mm(glass.width_mm)
                height = glass_mm(glass.height_mm)
                key = (glass_type, width, height, glass.note)
                row = section_rows.setdefault(
                    key,
                    {
                        "glass_type": glass_type,
                        "width": width,
                        "height": height,
                        "qty": 0,
                        "note": glass.note,
                    },
                )
                row["qty"] += 1
        elif system == "ЛИФТ":
            calc = calculate_lift(section)
            color = _section_color(section, calc)
            for panel in calc.panels:
                glass_type = panel.filling
                width = glass_mm(panel.width_mm)
                height = glass_mm(panel.height_mm)
                key = (glass_type, width, height, "")
                row = section_rows.setdefault(
                    key,
                    {
                        "glass_type": glass_type,
                        "width": width,
                        "height": height,
                        "qty": 0,
                        "note": "",
                    },
                )
                row["qty"] += max(1, int(panel.qty or 0))
        else:
            glass_type = str(
                getattr(section, "glass_type", "")
                or default_glass_type(getattr(section, "system", None))
            ).strip()
            color = _section_color(section)
            panel_count = max(1, _positive_int(getattr(section, "panels", 1), 1))
            section_qty = max(1, _positive_int(getattr(section, "quantity", 1), 1))
            section_rows[(glass_type, None, None, "Размеры согласно ТЗ")] = {
                "glass_type": glass_type,
                "width": None,
                "height": None,
                "qty": panel_count * section_qty,
                "note": "Размеры согласно ТЗ",
            }

        section_number = _delivery_section_number(section, fallback)
        project_number = str(getattr(project, "number", "") or "").strip()
        for row_index, row in enumerate(section_rows.values(), start=1):
            row_glass_type = row["glass_type"]
            outer_key = (color, row_glass_type)
            is_penoplex = row_glass_type == PENOPLEX_20MM
            outer = grouped.setdefault(
                outer_key,
                {
                    "name": (
                        f"ПАНЕЛИ ПЕНОПЛЕКС 20 ММ, {color.upper()}, РАЗМЕРЫ ПАНЕЛЕЙ:"
                        if is_penoplex
                        else f"СТЕКЛЯННЫЕ ПАНЕЛИ, {color.upper()}, РАЗМЕРЫ СТЕКОЛ:"
                    ),
                    "color": color,
                    "glass_type": row_glass_type,
                    "rows": [],
                    "qty": 0,
                },
            )
            prefix = f"{project_number} " if project_number else ""
            row["marking"] = f"{prefix}{section_number},{row_index}"
            outer["rows"].append(row)
            outer["qty"] += row["qty"]

    rows = []
    for group_key, group in grouped.items():
        place_key = _delivery_key("glass", *group_key)
        rows.append(
            {
                **group,
                "place_key": place_key,
                "places": _delivery_place(places, place_key),
            }
        )
    return rows


def _parse_extra_components(raw: object) -> list[dict]:
    if isinstance(raw, list):
        parsed = raw
    else:
        try:
            parsed = json.loads(raw or "[]")
        except (TypeError, json.JSONDecodeError):
            parsed = []
    return [row for row in parsed if isinstance(row, dict)]


def _is_no_option(value: object) -> bool:
    text = str(value or "").strip().lower().strip("—- ")
    return not text or text.startswith(("без", "нет"))


def _article_from_text(value: object) -> str:
    match = re.search(r"\b(?:RS|RU|RSD)\d+[A-ZА-Я]*\b", str(value or ""), re.I)
    return match.group(0).upper() if match else ""


def _add_delivery_component(
    grouped: dict[tuple, dict],
    *,
    article: str,
    name: str,
    qty: float,
    color: str = "",
    size: str = "",
    note: str = "",
) -> None:
    if qty <= 0 or not (article or name):
        return
    base_key = (article.strip(), name.strip(), color.strip(), size.strip())
    normalized_note = note.strip()
    # Preserve existing place keys for rows that do not have a processing note.
    key = (*base_key, normalized_note) if normalized_note else base_key
    row = grouped.setdefault(
        key,
        {
            "article": base_key[0],
            "name": base_key[1],
            "color": base_key[2],
            "size": base_key[3],
            "note": normalized_note,
            "qty": 0.0,
        },
    )
    row["qty"] += float(qty)


def _add_raw_special_hardware(
    grouped: dict[tuple, dict], section: object, section_qty: int
) -> None:
    handles = [
        getattr(section, "handle_left", None),
        getattr(section, "handle_right", None),
        getattr(section, "center_handle", None),
    ]
    if not any(value for value in handles):
        handles = [getattr(section, "handle", None)]
    for value in handles:
        if _is_no_option(value):
            continue
        article = _article_from_text(value)
        lower = str(value or "").lower()
        if article not in {"RS3014", "RS3017", "RS30201"} and not any(
            token in lower for token in ("кноб", "офис", "скоба")
        ):
            continue
        _add_delivery_component(
            grouped,
            article=article,
            name=str(value).strip(),
            qty=section_qty,
        )

    locks = [
        getattr(section, "lock_left", None),
        getattr(section, "lock_right", None),
        getattr(section, "center_lock", None),
    ]
    if not any(value for value in locks):
        locks = [getattr(section, "lock", None)]
    for value in locks:
        if _is_no_option(value):
            continue
        article = _article_from_text(value)
        if article in {"RS3018", "RS3020"}:
            continue
        if "замок" not in str(value or "").lower():
            continue
        _add_delivery_component(
            grouped,
            article=article,
            name=str(value).strip(),
            qty=section_qty,
        )

    latch_qty = sum(
        1
        for field in (
            "floor_latches_left",
            "floor_latches_right",
            "center_floor_latches_left",
            "center_floor_latches_right",
        )
        if bool(getattr(section, field, False))
    )
    if latch_qty:
        _add_delivery_component(
            grouped,
            article="RS205",
            name="Защёлка в пол",
            qty=latch_qty * section_qty,
        )


def _build_delivery_hardware_rows(
    sections: list[object],
    places: dict[str, str],
    *,
    include_calculated_specials: bool,
    extra_stage: int | None,
) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    bubble_seal_qty = 0.0
    lift_remote_controls: dict[str, dict] = {}
    special_articles = {"RS3014", "RS3017", "RS30201", "RS205"}
    excluded_locks = {"RS3018", "RS3020"}

    for section in sections:
        section_qty = max(1, _positive_int(getattr(section, "quantity", 1), 1))
        system = str(getattr(section, "system", "") or "").strip().upper()
        if system == "СЛАЙД" and include_calculated_specials:
            calc = calculate_slide(section)
            for item in calc.hardware:
                article = str(getattr(item, "article", "") or "").strip().upper()
                name = str(getattr(item, "name", "") or "").strip()
                is_lock = name.lower().startswith("замок")
                if article in excluded_locks:
                    continue
                if article not in special_articles and not is_lock:
                    continue
                _add_delivery_component(
                    grouped,
                    article=article,
                    name=name,
                    qty=_safe_float(getattr(item, "value", 0)),
                )
            bubble_seal_qty += (
                int(bool(getattr(section, "profile_left_bubble", False)))
                + int(bool(getattr(section, "profile_right_bubble", False)))
            ) * section_qty
            for profile in calc.profiles:
                article = str(getattr(profile, "article", "") or "").strip().upper()
                if article not in {"RS1002", "RS3110"}:
                    continue
                if article == "RS1002":
                    continue
                _add_delivery_component(
                    grouped,
                    article=article,
                    name=str(getattr(profile, "name", "") or article).strip(),
                    color="",
                    size="",
                    qty=_safe_float(getattr(profile, "qty", 0)),
                )
        elif system == "ЛИФТ" and include_calculated_specials:
            calc = calculate_lift(section)
            for item in calc.hardware:
                article = str(getattr(item, "article", "") or "").strip().upper()
                if article in {"RL2087", "RL2088"}:
                    row = lift_remote_controls.setdefault(
                        article,
                        {
                            "article": article,
                            "name": str(getattr(item, "name", "") or article).strip(),
                            "qty": 0.0,
                        },
                    )
                    # Количество пультов синхронизировано на уровне всего проекта.
                    row["qty"] = max(
                        row["qty"],
                        _safe_float(getattr(item, "value", 0)),
                    )
                elif article == "RL2092":
                    _add_delivery_component(
                        grouped,
                        article=article,
                        name=str(getattr(item, "name", "") or article).strip(),
                        qty=_safe_float(getattr(item, "value", 0)),
                    )
        elif include_calculated_specials:
            _add_raw_special_hardware(grouped, section, section_qty)

        for extra in _parse_extra_components(
            getattr(section, "extra_components", None)
        ):
            if not _extra_matches_delivery_stage(extra, extra_stage):
                continue
            qty = _safe_float(extra.get("qty") or extra.get("quantity"), 0)
            _add_delivery_component(
                grouped,
                article=str(extra.get("sku") or extra.get("article") or ""),
                name=str(extra.get("name") or "Дополнительная комплектующая"),
                color=str(extra.get("color") or ""),
                size=str(extra.get("size") or ""),
                qty=qty * section_qty,
            )

    if bubble_seal_qty > 0:
        _add_delivery_component(
            grouped,
            article="RS1002",
            name="Пузырьковый уплотнитель",
            qty=bubble_seal_qty,
        )
    for remote in lift_remote_controls.values():
        _add_delivery_component(
            grouped,
            article=remote["article"],
            name=remote["name"],
            qty=remote["qty"],
        )

    rows = []
    kit_key = _delivery_key("hardware", "base-kit")
    rows.append(
        {
            "article": "",
            "name": "Комплект фурнитуры согласно ТЗ",
            "color": "",
            "size": "",
            "note": "",
            "qty": 1.0,
            "qty_text": "1",
            "place_key": kit_key,
            "places": _delivery_place(places, kit_key),
        }
    )
    for component_key, component in sorted(
        grouped.items(), key=lambda item: (item[1]["name"], item[1]["article"])
    ):
        place_key = _delivery_key("hardware", *component_key)
        rows.append(
            {
                **component,
                "qty_text": _format_quantity(component["qty"]),
                "place_key": place_key,
                "places": _delivery_place(places, place_key),
            }
        )
    return rows


def _build_delivery_context(project: object, sections: Iterable[object]) -> dict:
    sorted_sections = sorted(
        list(sections), key=lambda section: _section_sort_key(section, 999999)
    )
    settings = _delivery_settings(project)
    places = settings["places"]
    stages, current_stage = _project_delivery_stage(project)
    include_constructions = stages == 1 or current_stage == 1
    include_glass = stages == 1 or current_stage == 2
    include_calculated_specials = stages == 1 or current_stage == 2
    extra_stage = None if stages == 1 else current_stage
    construction_rows = (
        _build_delivery_construction_rows(sorted_sections, places)
        if include_constructions
        else []
    )
    glass_rows = (
        _build_delivery_glass_rows(project, sorted_sections, places)
        if include_glass
        else []
    )
    hardware_rows = _build_delivery_hardware_rows(
        sorted_sections,
        places,
        include_calculated_specials=include_calculated_specials,
        extra_stage=extra_stage,
    )
    item1_rows = [
        *(
            {
                **row,
                "kind": "construction",
                "qty_text": str(row["qty"]),
                "profile_set_name": _delivery_profile_set_name(
                    row.get("system"), stages
                ),
            }
            for row in construction_rows
        ),
        *({**row, "kind": "glass", "qty_text": str(row["qty"])} for row in glass_rows),
    ]
    total_qty = sum(float(row["qty"]) for row in item1_rows) + sum(
        float(row["qty"]) for row in hardware_rows
    )
    return {
        "doc_type": "delivery",
        "title": DOC_TITLES["delivery"],
        "project": project,
        "sections": sorted_sections,
        "delivery": {
            **settings,
            "dateText": _delivery_date_text(settings),
            "productionStages": stages,
            "currentStage": current_stage,
            "includeConstructions": include_constructions,
            "includeGlass": include_glass,
        },
        "delivery_item1_rows": item1_rows,
        "delivery_item2_rows": hardware_rows,
        "delivery_total_qty": _format_quantity(total_qty),
        "delivery_names_count": 2,
    }


HARDWARE_ORDER_SYSTEMS = ("СЛАЙД", "ЛИФТ", "КНИЖКА", "ЦС")


SLIDE_HARDWARE_STAGES = {
    "RU008": "1",
    "RU007": "2",
    "RU010": "1",
    "RSD1": "2",
    "RSD2": "2",
    "RU005": "2",
    "RS105": "2",
    "RS106": "2",
    "RS107": "2",
    "RS107L": "2",
    "RS107R": "2",
    "RS108": "2",
    "RS122": "2",
    "RS123": "2",
    "RS205": "2",
    "RS3110": "2",
    "RS3014": "2",
    "RS3017": "2",
    "RS3018": "2",
    "RS3020": "2",
    "RS30201": "2",
    "RU1039": "2",
    "RS150": "1",
}


LIFT_HARDWARE_STAGES = {
    "RL201": "1",
    "RL203": "1",
    "RL20901": "1",
    "RL20902": "1",
    "RL20903": "1",
    "RL20904": "1",
    "RL206": "1",
    "RL2095": "1",
    "RL2085": "1",
    "RL2098": "1",
    "RL2096": "1",
    "RL2097": "1",
    "RL207": "1",
    "RU004": "1, 2",
    "RU006": "1",
    "RL001": "2",
    "RL011": "2",
    "RL210": "2",
    "RL2087": "2",
    "RL2088": "2",
    "RL2092": "2",
    "RL005": "2",
    "RL002": "2",
    "RU1039": "2",
    "RL150": "1",
}


def _hardware_order_stage(system: str, article: str, name: str) -> str:
    article_upper = article.strip().upper()
    if system == "СЛАЙД":
        if article_upper == "DIN7982":
            return "1" if "4,8×38" in name else "2"
        if article_upper in {"DIN7504M", "DIN7504O"}:
            return "2" if "3,5×13" in name else "1"
        if article_upper == "DIN912SW":
            return "2"
        return SLIDE_HARDWARE_STAGES.get(article_upper, "2")
    if system == "ЛИФТ":
        if article_upper in {"DIN7982", "DIN7504O"}:
            return "1"
        if article_upper.startswith("DIN"):
            return "2"
        return LIFT_HARDWARE_STAGES.get(article_upper, "2")
    return ""


def _stage_tokens(stage: object) -> set[str]:
    text = str(stage or "").strip().lower()
    if not text:
        return set()
    if text in {"both", "оба", "1, 2", "1/2"}:
        return {"1", "2"}
    return {token for token in re.findall(r"[12]", text)}


def _canonical_hardware_order_name(article: str, name: str) -> str:
    if article.upper() == "RS3018":
        return "Замок-защёлка 1-сторонний RS3018"
    return name


def _add_hardware_order_row(
    grouped: dict[tuple[str, str, str, str], dict],
    *,
    article: object,
    name: object,
    qty: object,
    unit: object = "шт",
    image: object = "",
    stage: object = "",
    aggregate: str = "sum",
) -> None:
    numeric_qty = _safe_float(qty, 0)
    article_text = str(article or "").strip()
    name_text = _canonical_hardware_order_name(
        article_text, str(name or article_text).strip()
    )
    if numeric_qty <= 0 or not (article_text or name_text):
        return

    unit_text = str(unit or "шт").strip() or "шт"
    image_text = str(image or "").strip()
    key = (article_text, name_text, unit_text, image_text)
    row = grouped.setdefault(
        key,
        {
            "article": article_text,
            "name": name_text,
            "qty": 0.0,
            "unit": unit_text,
            "image": image_text,
            "stages": set(),
        },
    )
    row["stages"].update(_stage_tokens(stage))
    if aggregate == "max":
        row["qty"] = max(float(row["qty"]), numeric_qty)
    elif aggregate == "once":
        row["qty"] = 1.0
    else:
        row["qty"] += numeric_qty


def _add_hardware_order_extras(
    grouped: dict[tuple[str, str, str, str], dict],
    section: object,
) -> None:
    section_qty = max(1, _positive_int(getattr(section, "quantity", 1), 1))
    for extra in _parse_extra_components(getattr(section, "extra_components", None)):
        qty = _safe_float(extra.get("qty") or extra.get("quantity"), 0)
        _add_hardware_order_row(
            grouped,
            article=extra.get("sku") or extra.get("article"),
            name=extra.get("name") or "Дополнительная комплектующая",
            qty=qty * section_qty,
            unit=extra.get("unit") or "шт",
            image=(
                extra.get("imageFile")
                or extra.get("image_file")
                or extra.get("image")
                or ""
            ),
            stage=_extra_delivery_stage(extra),
        )


def _build_hardware_order_page(system: str, sections: list[object]) -> dict:
    grouped: dict[tuple[str, str, str, str], dict] = {}
    warning = ""

    if system == "СЛАЙД":
        for section in sections:
            calc = calculate_slide(section)
            for item in calc.hardware:
                sub_items = getattr(item, "sub_items", None) or []
                if sub_items:
                    for sub_item in sub_items:
                        _add_hardware_order_row(
                            grouped,
                            article=getattr(sub_item, "article", ""),
                            name=f"{getattr(item, 'name', '')} {getattr(sub_item, 'label', '')}".strip(),
                            qty=getattr(sub_item, "value", 0),
                            unit=getattr(item, "unit", "шт"),
                            image=getattr(item, "image", ""),
                            stage=_hardware_order_stage(
                                system,
                                str(getattr(sub_item, "article", "") or ""),
                                f"{getattr(item, 'name', '')} {getattr(sub_item, 'label', '')}".strip(),
                            ),
                        )
                    continue
                _add_hardware_order_row(
                    grouped,
                    article=getattr(item, "article", ""),
                    name=getattr(item, "name", ""),
                    qty=getattr(item, "value", 0),
                    unit=getattr(item, "unit", "шт"),
                    image=getattr(item, "image", ""),
                    stage=_hardware_order_stage(
                        system,
                        str(getattr(item, "article", "") or ""),
                        str(getattr(item, "name", "") or ""),
                    ),
                )
            for item in calc.screws:
                _add_hardware_order_row(
                    grouped,
                    article=getattr(item, "article", ""),
                    name=getattr(item, "name", ""),
                    qty=getattr(item, "qty", 0),
                    unit="шт",
                    image=getattr(item, "image", ""),
                    stage=_hardware_order_stage(
                        system,
                        str(getattr(item, "article", "") or ""),
                        str(getattr(item, "name", "") or ""),
                    ),
                )
            _add_hardware_order_extras(grouped, section)
    elif system == "ЛИФТ":
        for section in sections:
            calc = calculate_lift(section)
            for item in [*calc.hardware, *calc.fasteners]:
                article = str(getattr(item, "article", "") or "").strip().upper()
                aggregate = (
                    "max"
                    if article in {"RL2087", "RL2088"}
                    else "once"
                    if article == "RL150"
                    else "sum"
                )
                _add_hardware_order_row(
                    grouped,
                    article=article,
                    name=getattr(item, "name", ""),
                    qty=getattr(item, "value", 0),
                    unit=getattr(item, "unit", "шт"),
                    image=getattr(item, "image", ""),
                    stage=_hardware_order_stage(
                        system,
                        article,
                        str(getattr(item, "name", "") or ""),
                    ),
                    aggregate=aggregate,
                )
            _add_hardware_order_extras(grouped, section)
    elif system == "КНИЖКА":
        for section in sections:
            calc = calculate_book(section)
            for item in calc.hardware:
                if not getattr(item, "included", False):
                    continue
                article = str(getattr(item, "article", "") or "").strip().upper()
                _add_hardware_order_row(
                    grouped,
                    article=article,
                    name=getattr(item, "name", ""),
                    qty=getattr(item, "qty", 0),
                    unit=getattr(item, "unit", "шт"),
                    image=f"{article}.png",
                    stage=getattr(item, "shipment_stage", ""),
                )
            _add_hardware_order_extras(grouped, section)
    else:
        warning = (
            f"Расчёт фурнитуры для системы {system} пока не реализован. "
            "Позиции из дополнительных комплектующих показаны ниже."
        )
        for section in sections:
            _add_hardware_order_extras(grouped, section)

    rows = sorted(
        grouped.values(),
        key=lambda row: (row["article"], row["name"], row["unit"]),
    )
    for index, row in enumerate(rows, start=1):
        article = str(row["article"] or "").upper()
        if article in {"RU004", "RU006", "RU007", "RU008"} and str(
            row["unit"]
        ).lower() == "м":
            row["qty"] = ceil(float(row["qty"]) * 10 - 1e-9) / 10
        row["index"] = index
        row["qty_text"] = _format_quantity(row["qty"])
        row["stage_text"] = ", ".join(sorted(row.pop("stages", set()))) or "—"
    return {
        "system": system,
        "rows": rows,
        "warning": warning,
    }


def _build_hardware_order_context(
    project: object,
    sections: Iterable[object],
) -> dict:
    section_rows = list(sections)
    grouped_sections: dict[str, list[object]] = defaultdict(list)
    for section in sorted(
        section_rows,
        key=lambda section: _section_sort_key(section, 999999),
    ):
        system = str(getattr(section, "system", "") or "").strip().upper()
        if not system or system == "КОМПЛЕКТАЦИЯ":
            continue
        grouped_sections[system].append(section)

    ordered_systems = [
        system for system in HARDWARE_ORDER_SYSTEMS if system in grouped_sections
    ]
    ordered_systems.extend(
        sorted(system for system in grouped_sections if system not in ordered_systems)
    )
    return {
        "doc_type": "hardware_order",
        "title": DOC_TITLES["hardware_order"],
        "project": project,
        "sections": section_rows,
        "hardware_order_pages": [
            _build_hardware_order_page(system, grouped_sections[system])
            for system in ordered_systems
        ],
    }


def build_project_document_context(
    project: object,
    sections: Iterable[object],
    doc_type: str,
) -> dict:
    if doc_type not in DOC_TITLES:
        raise ValueError("unknown project document type")

    if doc_type == "delivery":
        return _build_delivery_context(project, sections)
    if doc_type == "hardware_order":
        return _build_hardware_order_context(project, sections)

    section_rows = list(sections)
    excluded_book_sections = [
        section
        for section in section_rows
        if str(getattr(section, "system", "") or "").strip().upper() == "КНИЖКА"
    ]
    document_warnings = []
    if doc_type in {"glass", "paint"} and excluded_book_sections:
        labels = ", ".join(
            str(getattr(section, "name", "") or f"Секция {index}")
            for index, section in enumerate(excluded_book_sections, start=1)
        )
        document_warnings.append(
            f"КНИЖКА не включена в документ первого этапа: {labels}. "
            "Документ сформирован только для поддерживаемых секций СЛАЙД/ЛИФТ."
        )
    slide_calculated = _iter_slide_sections(section_rows)
    calculated = (
        slide_calculated
        if doc_type == "commercial"
        else _iter_calculated_sections(section_rows)
    )
    commercial_rows = _build_commercial_rows(slide_calculated)
    paint_pages = _build_paint_pages(
        calculated, getattr(project, "paint_manual_rows", None)
    )
    glass_rows = _build_glass_rows(project, calculated)

    return {
        "doc_type": doc_type,
        "title": DOC_TITLES[doc_type],
        "project": project,
        "sections": [item.section for item in calculated],
        "commercial_rows": commercial_rows,
        "paint_pages": paint_pages,
        "glass_rows": glass_rows,
        "glass_total_qty": sum(row["qty"] for row in glass_rows),
        "glass_total_area": round(sum(row["area"] for row in glass_rows), 3),
        "document_warnings": document_warnings,
    }


def render_project_document_html(
    project: object,
    sections: Iterable[object],
    doc_type: str,
    is_pdf: bool = False,
) -> str:
    context = build_project_document_context(project, sections, doc_type)
    context["is_pdf"] = is_pdf
    template_name = {
        "delivery": "delivery_note.html",
        "hardware_order": "hardware_order.html",
    }.get(doc_type, "project_document.html")
    template = _get_env().get_template(template_name)
    return template.render(**context)
