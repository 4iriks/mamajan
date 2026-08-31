"""Shared presentation data for the preliminary BOOK production sheet.

The calculator remains the single source of geometry.  This module only groups
physical items for manufacturing documents and deliberately exposes no drilling
coordinates while the drilling brief is unfinished.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BOOK_SHEET_WARNING = (
    "ПРЕДВАРИТЕЛЬНЫЙ ПРОИЗВОДСТВЕННЫЙ ЛИСТ. Сверловка D13/D6, отверстия "
    "для слива, вывод под нижнюю направляющую и расстояние под доводчик "
    "в этот документ не включены. Эти операции выполнять только по отдельному "
    "согласованному чертежу."
)


BOOK_CHECKLIST_ROWS = (
    ("1", "Проверить размеры секции и состав панелей по схеме", ""),
    ("2", "Нарезать направляющие и компенсирующие профили по ПЛ", "Без сверловки"),
    ("3", "Нарезать стекольные профили RBP002 по сгруппированным размерам", ""),
    ("4", "Склеить панели по размерам ПЛ", "Сверить номера панелей"),
    ("5", "Установить ручки, замки, защёлки и прочую фурнитуру", "По комплектации"),
    ("6", "Проверить комплектность профилей и фурнитуры", ""),
    ("7", "Упаковать панели и комплектующие", ""),
)


PROFILE_IMAGES = {
    "RBP001": "RBP001.png",
    "RBP002": "RBP002.png",
    "RBP003": "RBP003.png",
}


@dataclass
class BookSheetGlassRow:
    field_prefix: str
    glass_type: str
    width_mm: float
    height_mm: float
    qty: int
    positions: list[int] = field(default_factory=list)

    @property
    def positions_text(self) -> str:
        return ", ".join(str(value) for value in self.positions)


@dataclass
class BookSheetAssemblyRow:
    field_prefix: str
    width_mm: float
    height_mm: float
    qty: int
    positions: list[int] = field(default_factory=list)

    @property
    def positions_text(self) -> str:
        return ", ".join(str(value) for value in self.positions)


@dataclass
class BookSheetProfileRow:
    field_prefix: str
    article: str
    name: str
    length_mm: float
    qty: int
    unit: str
    positions: list[str] = field(default_factory=list)
    image: str | None = None
    formula: str = ""
    status: str = "confirmed"

    @property
    def positions_text(self) -> str:
        return ", ".join(self.positions)


@dataclass
class BookSheetHardwareRow:
    field_prefix: str
    article: str
    name: str
    qty: float
    unit: str
    shipment_stage: int
    note: str = ""
    status: str = "confirmed"


@dataclass
class BookSheetData:
    system_label: str
    warning: str
    summary_rows: list[tuple[str, str]]
    glass_rows: list[BookSheetGlassRow]
    assembly_rows: list[BookSheetAssemblyRow]
    profile_rows: list[BookSheetProfileRow]
    hardware_rows: list[BookSheetHardwareRow]
    checklist_rows: tuple[tuple[str, str, str], ...]
    glass_supplied: bool
    calculation_status: str


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(values: list[str]) -> str:
    return "preliminary" if "preliminary" in values else "confirmed"


def _position_number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _group_glass(calc: object) -> list[BookSheetGlassRow]:
    grouped: dict[tuple[str, float, float], dict[str, Any]] = {}
    for panel in list(getattr(calc, "panels", None) or []):
        key = (
            str(getattr(panel, "glass_type", "") or ""),
            _number(getattr(panel, "glass_width_mm", 0)),
            _number(getattr(panel, "glass_height_mm", 0)),
        )
        row = grouped.setdefault(key, {"qty": 0, "positions": []})
        row["qty"] += int(getattr(panel, "qty", 0) or 0)
        row["positions"].append(_position_number(getattr(panel, "number", 0)))

    result: list[BookSheetGlassRow] = []
    for index, ((glass_type, width, height), values) in enumerate(grouped.items()):
        result.append(
            BookSheetGlassRow(
                field_prefix=f"book_glass_{index}",
                glass_type=glass_type,
                width_mm=width,
                height_mm=height,
                qty=values["qty"],
                positions=sorted(value for value in values["positions"] if value),
            )
        )
    return result


def _group_assemblies(calc: object) -> list[BookSheetAssemblyRow]:
    grouped: dict[tuple[float, float], dict[str, Any]] = {}
    for panel in list(getattr(calc, "panels", None) or []):
        key = (
            _number(getattr(panel, "panel_width_mm", 0)),
            _number(getattr(panel, "panel_height_mm", 0)),
        )
        row = grouped.setdefault(key, {"qty": 0, "positions": []})
        row["qty"] += int(getattr(panel, "qty", 0) or 0)
        row["positions"].append(_position_number(getattr(panel, "number", 0)))

    result: list[BookSheetAssemblyRow] = []
    for index, ((width, height), values) in enumerate(grouped.items()):
        result.append(
            BookSheetAssemblyRow(
                field_prefix=f"book_assembly_{index}",
                width_mm=width,
                height_mm=height,
                qty=values["qty"],
                positions=sorted(value for value in values["positions"] if value),
            )
        )
    return result


def _group_profiles(calc: object) -> list[BookSheetProfileRow]:
    grouped: dict[tuple[str, str, float, str], dict[str, Any]] = {}
    for profile in list(getattr(calc, "profiles", None) or []):
        key = (
            str(getattr(profile, "article", "") or ""),
            str(getattr(profile, "name", "") or ""),
            _number(getattr(profile, "length_mm", 0)),
            str(getattr(profile, "unit", "шт.") or "шт."),
        )
        row = grouped.setdefault(
            key,
            {
                "qty": 0,
                "positions": [],
                "statuses": [],
                "formula": str(getattr(profile, "formula", "") or ""),
            },
        )
        row["qty"] += int(getattr(profile, "qty", 0) or 0)
        position = str(getattr(profile, "position", "") or "").strip()
        if position and position not in row["positions"]:
            row["positions"].append(position)
        row["statuses"].append(str(getattr(profile, "status", "confirmed") or "confirmed"))

    result: list[BookSheetProfileRow] = []
    for index, ((article, name, length, unit), values) in enumerate(grouped.items()):
        result.append(
            BookSheetProfileRow(
                field_prefix=f"book_profile_{index}",
                article=article,
                name=name,
                length_mm=length,
                qty=values["qty"],
                unit=unit,
                positions=values["positions"],
                image=PROFILE_IMAGES.get(article.upper()),
                formula=values["formula"],
                status=_status(values["statuses"]),
            )
        )
    return result


def _group_hardware(calc: object) -> list[BookSheetHardwareRow]:
    grouped: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    for item in list(getattr(calc, "hardware", None) or []):
        if not bool(getattr(item, "included", True)):
            continue
        qty = _number(getattr(item, "qty", 0))
        if qty <= 0:
            continue
        key = (
            str(getattr(item, "article", "") or ""),
            str(getattr(item, "name", "") or ""),
            str(getattr(item, "unit", "шт.") or "шт."),
            int(getattr(item, "shipment_stage", 0) or 0),
            str(getattr(item, "note", "") or ""),
        )
        row = grouped.setdefault(key, {"qty": 0.0, "statuses": []})
        row["qty"] += qty
        row["statuses"].append(str(getattr(item, "status", "confirmed") or "confirmed"))

    result: list[BookSheetHardwareRow] = []
    for index, ((article, name, unit, stage, note), values) in enumerate(grouped.items()):
        result.append(
            BookSheetHardwareRow(
                field_prefix=f"book_hardware_{index}",
                article=article,
                name=name,
                qty=values["qty"],
                unit=unit,
                shipment_stage=stage,
                note=note,
                status=_status(values["statuses"]),
            )
        )
    return result


def build_book_sheet_data(section: object, calc: object) -> BookSheetData:
    config = dict(getattr(calc, "normalized_config", None) or {})
    book_system = str(config.get("book_system") or getattr(section, "book_system", "") or "B25")
    door_layout = str(config.get("door_layout") or "none")
    compensator = str(config.get("compensator") or "none")
    door_labels = {
        "none": "Без основной двери",
        "left": "Дверь слева",
        "right": "Дверь справа",
        "both": "Двери слева и справа",
    }
    compensator_labels = {
        "none": "Без компенсирующего профиля",
        "lower": "Нижний",
        "upper": "Верхний",
        "both": "Верхний и нижний",
    }
    glass_rows = _group_glass(calc)
    glass_supplied = bool(config.get("glass_supplied", getattr(section, "glass_supplied", True)))
    summary_rows = [
        ("Система", book_system),
        ("Ширина секции", f"{_number(getattr(section, 'width', 0)):g} мм"),
        ("Высота секции", f"{_number(getattr(section, 'height', 0)):g} мм"),
        ("Физических панелей", f"{len(list(getattr(calc, 'panels', None) or []))} шт."),
        ("Количество секций", f"{int(getattr(section, 'quantity', 1) or 1)} шт."),
        ("Двери", door_labels.get(door_layout, door_layout)),
        ("Компенсатор", compensator_labels.get(compensator, compensator)),
        ("Стекло", glass_rows[0].glass_type if glass_rows else "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"),
        ("Поставка стекла", "В комплекте" if glass_supplied else "Не входит в комплект"),
    ]
    return BookSheetData(
        system_label=f"КНИЖКА {book_system}",
        warning=BOOK_SHEET_WARNING,
        summary_rows=summary_rows,
        glass_rows=glass_rows,
        assembly_rows=_group_assemblies(calc),
        profile_rows=_group_profiles(calc),
        hardware_rows=_group_hardware(calc),
        checklist_rows=BOOK_CHECKLIST_ROWS,
        glass_supplied=glass_supplied,
        calculation_status=str(getattr(calc, "calculation_status", "preliminary") or "preliminary"),
    )
