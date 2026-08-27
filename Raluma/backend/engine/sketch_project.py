"""Shared, price-free data preparation for the project sketch PDF and DOCX."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Iterable

from engine.book_calc import calculate_book
from engine.lift_calc import calculate_lift, lift_geometry_error
from engine.document_numbers import production_project_number, resolve_section_numbers
from engine.office_diagrams import render_slide_room, render_slide_top, section_diagrams
from engine.slide_calc import (
    _inter_glass_article,
    _resolve_inter_glass_profile,
    calculate_slide,
)


SUPPORTED_SKETCH_SYSTEMS = {"СЛАЙД", "КНИЖКА", "ЛИФТ"}


class SketchUnsupportedSectionsError(ValueError):
    def __init__(self, sections: list[str]):
        self.sections = sections
        super().__init__(
            "Эскизный проект недоступен: неподдерживаемые секции — "
            + ", ".join(sections)
        )


class SketchGeometryError(ValueError):
    pass


@dataclass
class SketchPanelRow:
    number: int
    position: str
    filling: str
    width_mm: float
    height_mm: float
    qty: int


def _text(value: object, fallback: str = "—") -> str:
    normalized = " ".join(str(value or "").split())
    return normalized or fallback


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _positive_int(value: object, default: int = 1) -> int:
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return default


def _format_number(value: object) -> str:
    number = round(_number(value), 1)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}".replace(".", ",")


def _section_label(section: object, fallback: int) -> str:
    return f"Секция {fallback}"


def _section_color(section: object, calc: object) -> str:
    calculated = _text(getattr(calc, "color_text", None), "")
    if calculated:
        return calculated
    painting = _text(getattr(section, "painting_type", None), "")
    ral = _text(getattr(section, "ral_color", None), "")
    if "RAL" in painting.upper():
        return _text(f"RAL {ral}" if ral else painting)
    return painting or "—"


def _book_warnings(calc: object) -> list[str]:
    return [
        str(warning)
        for warning in getattr(calc, "warnings", []) or []
        if not str(warning).startswith("ПЛ, заказ стекла, покраска и накладная")
    ]


def _slide_panels(section: object, calc: object) -> list[SketchPanelRow]:
    filling = (
        _text(getattr(calc, "glass_type", None))
        if bool(getattr(section, "glass_supplied", True))
        else "Без стекла"
    )
    quantity = _positive_int(getattr(section, "quantity", 1))
    panel_numbers = list(getattr(calc, "panel_numbers", None) or [])
    return [
        SketchPanelRow(
            number=int(
                panel_numbers[index - 1]
                if index - 1 < len(panel_numbers)
                else getattr(panel, "panel", index) or index
            ),
            position=_text(getattr(panel, "position", None), f"Панель {index}"),
            filling=filling,
            width_mm=_number(getattr(panel, "width_mm", 0)),
            height_mm=_number(getattr(panel, "height_mm", 0)),
            qty=quantity,
        )
        for index, panel in enumerate(getattr(calc, "panel_glass", []) or [], start=1)
    ]


def _book_panels(calc: object) -> list[SketchPanelRow]:
    position_names = {
        "left": "Левое",
        "middle": "Промежуточное",
        "right": "Правое",
        "door": "Дверь",
        "fixed": "Глухое",
        "moving_door": "Дополнительная дверь",
    }
    return [
        SketchPanelRow(
            number=int(getattr(panel, "number", index) or index),
            position=position_names.get(
                _text(getattr(panel, "position", None), "").lower(),
                position_names.get(
                    _text(getattr(panel, "role", None), "").lower(),
                    _text(getattr(panel, "position", None), f"Панель {index}"),
                ),
            ),
            filling=_text(getattr(panel, "glass_type", None)),
            width_mm=_number(getattr(panel, "glass_width_mm", 0)),
            height_mm=_number(getattr(panel, "glass_height_mm", 0)),
            qty=_positive_int(getattr(panel, "qty", 1)),
        )
        for index, panel in enumerate(getattr(calc, "panels", []) or [], start=1)
    ]


def _lift_panels(calc: object) -> list[SketchPanelRow]:
    return [
        SketchPanelRow(
            number=int(getattr(panel, "panel", index) or index),
            position=_text(getattr(panel, "role", None), f"Панель {index}"),
            filling=_text(getattr(panel, "filling", None)),
            width_mm=_number(getattr(panel, "width_mm", 0)),
            height_mm=_number(getattr(panel, "height_mm", 0)),
            qty=_positive_int(getattr(panel, "qty", 1)),
        )
        for index, panel in enumerate(getattr(calc, "panels", []) or [], start=1)
    ]


_EXCLUDED_COMPONENT_TERMS = (
    "щеточн",
    "щёточн",
    "саморез",
    "шуруп",
    "винт",
    "болт",
    "крепеж",
    "крепёж",
    "шайба",
    "гайка",
    "шплинт",
    "штифт",
    "заклеп",
    "заклёп",
    "скользящее покрытие",
    "заглуш",
    "наклей",
    "инструкц",
    "ответн",
)


def _is_sketch_component(article: object, name: object) -> bool:
    normalized = f"{article or ''} {name or ''}".lower()
    normalized_article = str(article or "").strip().upper()
    if normalized_article == "RS2021":
        return False
    if "стекольный профиль" in normalized and "межстекольный" not in normalized:
        return False
    return not any(term in normalized for term in _EXCLUDED_COMPONENT_TERMS)


_SLIDE_INCLUDED_HARDWARE_TERMS = (
    "ручк",
    "замок",
    "защел",
    "защёл",
    "уплотн",
    "двутавр",
)
_SLIDE_INCLUDED_HARDWARE_ARTICLES = {
    "RS205",
    "RS206",
    "RS207",
    "RS3014",
    "RS3017",
    "RS3018",
    "RS3020",
    "RS30201",
    "RS30301",
    "RU007",
    "RU008",
    "RU010",
}


def _is_calculated_hardware_for_sketch(
    system: str,
    article: object,
    name: object,
) -> bool:
    if system != "СЛАЙД":
        return _is_sketch_component(article, name)
    article_text = str(article or "").strip().upper()
    if article_text in _SLIDE_INCLUDED_HARDWARE_ARTICLES:
        return True
    if not _is_sketch_component(article, name):
        return False
    normalized = str(name or "").casefold()
    return any(term in normalized for term in _SLIDE_INCLUDED_HARDWARE_TERMS)


def _component_row(
    *,
    article: object,
    name: object,
    size: object = "",
    qty: object = "",
    unit: object = "шт",
    note: object = "",
    image: object = "",
    color: object = "",
    stage: object = "",
) -> dict:
    return {
        "article": _text(article, ""),
        "name": _text(name),
        "size": _text(size),
        "qty": _text(qty),
        "unit": _text(unit, "шт"),
        "note": _text(note, ""),
        "image": _text(image, ""),
        "color": _text(color, ""),
        "stage": _text(stage, ""),
    }


def _calculated_components(calc: object, system: str) -> list[dict]:
    rows: list[dict] = []
    for item in getattr(calc, "profiles", []) or []:
        article = getattr(item, "article", "")
        name = getattr(item, "name", "")
        qty = getattr(item, "qty", 0)
        length = getattr(item, "length_mm", 0)
        if _number(qty) <= 0 or _number(length) <= 0:
            continue
        if not _is_sketch_component(article, name):
            continue
        rows.append(
            _component_row(
                article=article,
                name=name,
                size=f"{_format_number(length)} мм",
                qty=_format_number(qty),
                unit=getattr(item, "unit", "шт"),
                note=getattr(item, "position", "") if system == "КНИЖКА" else "",
                image=getattr(item, "image", ""),
            )
        )

    for item in getattr(calc, "hardware", []) or []:
        if system == "КНИЖКА" and not bool(getattr(item, "included", True)):
            continue
        article = getattr(item, "article", "")
        name = getattr(item, "name", "")
        sub_items = getattr(item, "sub_items", None)
        if sub_items:
            for sub_item in sub_items:
                if _number(getattr(sub_item, "value", 0)) <= 0:
                    continue
                if not _is_calculated_hardware_for_sketch(
                    system,
                    getattr(sub_item, "article", ""),
                    f"{name} {getattr(sub_item, 'label', '')}",
                ):
                    continue
                rows.append(
                    _component_row(
                        article=getattr(sub_item, "article", ""),
                        name=f"{name} {getattr(sub_item, 'label', '')}",
                        qty=_format_number(getattr(sub_item, "value", 0)),
                        unit=getattr(item, "unit", "шт"),
                        image=getattr(item, "image", ""),
                    )
                )
            continue

        if not _is_calculated_hardware_for_sketch(system, article, name):
            continue

        value = getattr(item, "qty", None)
        if value is None:
            value = getattr(item, "value", 0)
        if _number(value) <= 0:
            continue
        length = getattr(item, "length_mm", None)
        rows.append(
            _component_row(
                article=article,
                name=name,
                size=(f"{_format_number(length)} мм" if length else ""),
                qty=_format_number(value),
                unit=getattr(item, "unit", "шт"),
                note=getattr(item, "note", ""),
                image=getattr(item, "image", ""),
            )
        )
    return rows


def _extra_components(owner: object, *, multiply: bool) -> list[dict]:
    raw = getattr(owner, "extra_components", None)
    if isinstance(raw, list):
        source = raw
    else:
        try:
            source = json.loads(raw or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            source = []
    if not isinstance(source, list):
        return []
    rows = []
    quantity_multiplier = (
        _positive_int(getattr(owner, "quantity", 1)) if multiply else 1
    )
    for item in source:
        if not isinstance(item, dict):
            continue
        if str(item.get("category") or "").strip().lower() == "service":
            continue
        article = item.get("article") or item.get("art") or item.get("sku") or ""
        name = item.get("name") or ""
        if not any((article, name, item.get("size"), item.get("qty"))):
            continue
        raw_qty = item.get("qty") or item.get("quantity") or ""
        total_qty = (
            _format_number(_number(raw_qty) * quantity_multiplier)
            if _number(raw_qty) > 0
            else raw_qty
        )
        stage = item.get("deliveryStage") or item.get("delivery_stage") or "both"
        rows.append(
            _component_row(
                article=article,
                name=name,
                size=item.get("size") or "",
                qty=total_qty,
                unit=item.get("unit") or "шт",
                note="",
                color=(
                    item.get("color")
                    or item.get("finish_name")
                    or item.get("finishName")
                    or ""
                ),
                image=(
                    item.get("imageFile")
                    or item.get("image_file")
                    or item.get("image")
                    or ""
                ),
                stage="1, 2" if str(stage).strip().lower() == "both" else stage,
            )
        )
    return rows


def _diagram_rows(section: object, calc: object) -> list[dict]:
    system = _text(getattr(section, "system", None), "").upper()
    # Keep the dedicated room renderer for its physical aspect ratio and overall
    # dimensions.  The top view must be identical to the production sheet: that
    # reference diagram includes the wall and side-profile assemblies.
    reference_diagrams = section_diagrams(section, calc) if system == "СЛАЙД" else []
    reference_top = next(
        (
            payload
            for title, payload in reference_diagrams
            if "сверху" in title.casefold()
        ),
        None,
    )
    diagrams = (
        [
            (
                "Вид из помещения",
                render_slide_room(
                    section,
                    calc,
                    include_title=False,
                    crop=True,
                    print_dimensions=True,
                ),
            ),
            (
                "Схема · вид сверху",
                reference_top
                or render_slide_top(
                    section,
                    calc,
                    include_title=False,
                    crop=True,
                ),
            ),
        ]
        if system == "СЛАЙД"
        else section_diagrams(section, calc)
    )
    room_views = [row for row in diagrams if "из помещения" in row[0].casefold()]
    selected = diagrams[:2] if system == "СЛАЙД" else (room_views[:1] or diagrams[:1])
    rows = []
    for title, payload in selected:
        rows.append(
            {
                "title": title,
                "kind": "top" if "сверху" in title.casefold() else "room",
                "png": payload,
                "data_uri": "data:image/png;base64,"
                + base64.b64encode(payload).decode("ascii"),
            }
        )
    return rows


def _system_text(system: str, section: object, calc: object) -> str:
    if system == "СЛАЙД":
        return _text(getattr(calc, "system_text", None), "SLIDE")
    if system == "КНИЖКА":
        book_system = (getattr(calc, "normalized_config", {}) or {}).get("book_system")
        return _text(f"BOOK {book_system}" if book_system else "BOOK")
    return _text(getattr(calc, "system_text", None), "LIFT")


def _section_data(section: object, order: int) -> dict:
    system = _text(getattr(section, "system", None), "").upper()
    if system == "СЛАЙД":
        calc = calculate_slide(section)
        panel_rows = _slide_panels(section, calc)
        warnings = list(getattr(calc, "warnings", []) or [])
        threshold = _text(getattr(calc, "threshold_text", None))
        selected_inter_glass = _resolve_inter_glass_profile(
            getattr(section, "inter_glass_profile", None)
        )
        inter_glass = (
            _text(selected_inter_glass)
            if _inter_glass_article(selected_inter_glass)
            else "—"
        )
        filling = (
            _text(getattr(calc, "glass_type", None))
            if bool(getattr(section, "glass_supplied", True))
            else "Без стекла"
        )
    elif system == "КНИЖКА":
        calc = calculate_book(section)
        panel_rows = _book_panels(calc)
        warnings = _book_warnings(calc)
        threshold = "—"
        inter_glass = "—"
        filling = _text(getattr(section, "glass_type", None))
    else:
        geometry_error = lift_geometry_error(section)
        if geometry_error:
            raise SketchGeometryError(geometry_error)
        calc = calculate_lift(section)
        panel_rows = _lift_panels(calc)
        warnings = list(getattr(calc, "warnings", []) or [])
        threshold = "—"
        inter_glass = "—"
        filling = _text(getattr(calc, "filling_text", None))

    label = _section_label(section, order)
    return {
        "order": order,
        "label": label,
        "system": system,
        "system_text": _system_text(system, section, calc),
        "width_mm": _number(getattr(section, "width", 0)),
        "height_mm": _number(getattr(section, "height", 0)),
        "color": _section_color(section, calc),
        "quantity": _positive_int(getattr(section, "quantity", 1)),
        "threshold": threshold,
        "inter_glass_profile": inter_glass,
        "filling": filling,
        "panels": panel_rows,
        "comments": _text(getattr(section, "comments", None), ""),
        "warnings": [f"{label}: {warning}" for warning in warnings],
        "diagrams": _diagram_rows(section, calc),
    }


def build_sketch_project_context(
    project: object,
    sections: Iterable[object],
) -> dict:
    resolved = resolve_section_numbers(sections)
    unsupported = [
        f"{_text(getattr(section, 'name', None), _section_label(section, number))} "
        f"({_text(getattr(section, 'system', None))})"
        for number, section in resolved
        if _text(getattr(section, "system", None), "").upper()
        not in SUPPORTED_SKETCH_SYSTEMS
    ]
    if unsupported:
        raise SketchUnsupportedSectionsError(unsupported)

    prepared = []
    for section_number, section in resolved:
        prepared.append(_section_data(section, section_number))
    order_number = _text(
        getattr(project, "order_number", None) or getattr(project, "number", None),
        "",
    )
    document_number = production_project_number(project)
    return {
        "doc_type": "sketch",
        "title": "Эскизный проект",
        "document_title": f"ЭСКИЗНЫЙ ПРОЕКТ № {document_number}",
        "project_number": document_number,
        "invoice_number": _text(getattr(project, "invoice_number", None), ""),
        "order_number": order_number,
        "sections": prepared,
        "project_components": _extra_components(project, multiply=False),
        "document_warnings": [
            warning for section in prepared for warning in section["warnings"]
        ],
    }
