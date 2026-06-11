from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from jinja2 import Environment, FileSystemLoader

from engine.pdf import TEMPLATES_DIR, _img_b64
from engine.slide_calc import calculate_slide


DOC_TITLES = {
    "commercial": "Коммерческое предложение",
    "paint": "Заявка на покраску",
    "glass": "Заказ стекла",
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


def _iter_slide_sections(sections: Iterable[object]) -> list[CalculatedSection]:
    rows: list[CalculatedSection] = []
    sorted_sections = sorted(
        list(sections),
        key=lambda section: _section_order(section, 999999),
    )
    for index, section in enumerate(sorted_sections, start=1):
        if getattr(section, "system", None) != "СЛАЙД":
            continue
        rows.append(
            CalculatedSection(
                order=_section_order(section, index),
                section=section,
                calc=calculate_slide(section),
            )
        )
    return rows


def _format_mm(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded).replace(".", ",")


def _has_drawing_hardware(*values: object) -> bool:
    combined = " ".join(str(value or "") for value in values).lower()
    return any(
        token in combined
        for token in (
            "зам",
            "защёл",
            "защел",
            "ключ",
            "кноб",
            "скоб",
            "rs3014",
            "rs3017",
            "rs3018",
            "rs3019",
            "rs30301",
        )
    )


def _side_has_glass_drawing(section: object, side: str) -> bool:
    return _has_drawing_hardware(
        getattr(section, f"lock_{side}", None),
        getattr(section, f"handle_{side}", None),
    ) or bool(getattr(section, f"floor_latches_{side}", False))


def _center_has_glass_drawing(section: object) -> bool:
    return (
        _has_drawing_hardware(
            getattr(section, "center_lock", None),
            getattr(section, "center_handle", None),
        )
        or bool(getattr(section, "center_floor_latches_left", False))
        or bool(getattr(section, "center_floor_latches_right", False))
    )


def _legacy_has_glass_drawing(section: object) -> bool:
    return _has_drawing_hardware(
        getattr(section, "lock", None),
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
        if center is not None:
            for _ in range(2):
                result.append(
                    _physical_glass(center, _glass_note_for_role(section, "center"))
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


def _build_paint_pages(calculated: list[CalculatedSection]) -> list[dict]:
    grouped: dict[str, dict[tuple, dict]] = defaultdict(dict)

    for item in calculated:
        color = item.calc.color_text or "Без цвета"
        for profile in item.calc.profiles:
            if not profile.painted or profile.length_mm <= 0:
                continue
            clean = round(float(profile.length_mm), 1)
            allowance = clean + 50
            note = profile.paint_note
            key = (
                profile.article,
                profile.name,
                clean,
                profile.image or "",
                note,
            )
            row = grouped[color].setdefault(
                key,
                {
                    "article": profile.article,
                    "name": profile.name,
                    "image": profile.image,
                    "qty": 0,
                    "clean": clean,
                    "allowance": allowance,
                    "total_m": 0.0,
                    "note": note,
                },
            )
            row["qty"] += int(profile.qty)
            row["total_m"] = round(row["qty"] * allowance / 1000, 1)

    pages = []
    for color, rows_by_key in grouped.items():
        rows = sorted(
            rows_by_key.values(),
            key=lambda row: (row["article"], row["clean"]),
        )
        total_qty = sum(row["qty"] for row in rows)
        total_m = round(sum(row["total_m"] for row in rows), 1)
        pages.append(
            {
                "color": color,
                "rows": rows,
                "total_qty": total_qty,
                "total_m": total_m,
            }
        )
    return sorted(pages, key=lambda page: page["color"])


def _build_glass_rows(
    project: object, calculated: list[CalculatedSection]
) -> list[dict]:
    grouped: dict[tuple, dict] = {}

    for item in calculated:
        for glass_index, glass in enumerate(
            _expand_glass_for_order(item.section, item.calc), start=1
        ):
            width = int(round(glass.width_mm))
            height = int(round(glass.height_mm))
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
            row["markings"].append(
                f"{getattr(project, 'number', '')} {item.order},{glass_index}"
            )
            row["qty"] += 1
            row["area"] = round(width * height * row["qty"] / 1_000_000, 3)

    rows = sorted(
        grouped.values(),
        key=lambda row: (row["glass_type"], row["width"], row["height"], row["note"]),
    )
    for index, row in enumerate(rows, start=1):
        row["index"] = index
        row["marking"] = ", ".join(row["markings"])
    return rows


def build_project_document_context(
    project: object,
    sections: Iterable[object],
    doc_type: str,
) -> dict:
    if doc_type not in DOC_TITLES:
        raise ValueError("unknown project document type")

    calculated = _iter_slide_sections(sections)
    commercial_rows = _build_commercial_rows(calculated)
    paint_pages = _build_paint_pages(calculated)
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
    }


def render_project_document_html(
    project: object,
    sections: Iterable[object],
    doc_type: str,
) -> str:
    context = build_project_document_context(project, sections, doc_type)
    template = _get_env().get_template("project_document.html")
    return template.render(**context)
