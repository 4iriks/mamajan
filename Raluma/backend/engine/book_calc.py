"""Расчётный контур системы КНИЖКА.

Модуль намеренно не зависит от ``slide_calc`` и ``lift_calc``.  Он строит
результат вокруг физических панелей и для каждой формулы сохраняет источник:

1. ТЗ КНИЖКА;
2. новые расчётные Excel;
3. восстановленная логика старой программы.

Прямые секции без дополнительных панелей считаются подтверждённой
конфигурацией. Углы, дополнительная глухая панель и дополнительная дверь
остаются доступными, но весь затронутый расчёт помечается предварительным.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from typing import Any, Literal


FormulaSource = Literal["tz", "excel", "legacy"]
FormulaStatus = Literal["confirmed", "preliminary"]

SOURCE_PRIORITY: tuple[FormulaSource, ...] = ("tz", "excel", "legacy")

OPENING_LABELS = {
    "inside_in": "изнутри внутрь",
    "inside_out": "изнутри наружу",
    "outside_out": "снаружи наружу",
    "outside_in": "снаружи внутрь",
}

BOOK_SYSTEMS = {"B25", "B16", "B17", "C16", "C17"}
BOOK_SYSTEM_ALIASES = {
    "В25": "B25",
    "В16": "B16",
    "В17": "B17",
    "С16": "C16",
    "С17": "C17",
    # Эти два значения ошибочно сохраняла первая версия формы. Оба
    # рассчитывались по текущей B25-геометрии, поэтому миграция сохраняет
    # прежний результат и просит пользователя проверить систему.
    "С КАРЕТКОЙ": "B25",
    "БЕЗ КАРЕТКИ": "B25",
}
LEGACY_HEIGHT_FAMILY_SYSTEMS = {"B16", "B17", "C16", "C17"}
HEIGHT_DEDUCTIONS_MM = {
    "B25": {"lower": 135.0, "both": 115.0, "upper": 130.0, "none": 117.0},
    "B16": {"lower": 102.0, "both": 115.0, "upper": 130.0, "none": 117.0},
}


class BookCalculationError(ValueError):
    """Понятная пользователю ошибка геометрии КНИЖКИ."""


@dataclass
class BookFormulaTrace:
    key: str
    name: str
    value: float | int | str
    unit: str
    expression: str
    scope: str
    source: FormulaSource
    status: FormulaStatus
    source_reference: str


@dataclass
class BookPanelItem:
    number: int
    position: str
    role: str
    movement_direction: str
    door_side: str | None
    door_hardware: str | None
    door_opening: str | None
    door_opening_label: str | None
    glass_type: str
    glass_width_mm: float
    glass_height_mm: float
    glass_profile_article: str
    glass_profile_width_mm: float
    panel_width_mm: float
    panel_height_mm: float
    qty: int
    hardware_articles: list[str] = field(default_factory=list)
    source: FormulaSource = "tz"
    status: FormulaStatus = "confirmed"
    dimension_sources: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class BookProfileItem:
    article: str
    name: str
    length_mm: float
    qty: int
    unit: str
    position: str
    panel_number: int | None
    source: FormulaSource
    status: FormulaStatus
    formula: str


@dataclass
class BookHardwareItem:
    article: str
    name: str
    qty: float
    unit: str
    shipment_stage: int
    formula: str
    note: str
    source: FormulaSource
    status: FormulaStatus
    included: bool


@dataclass
class BookCalcResult:
    panels: list[BookPanelItem] = field(default_factory=list)
    profiles: list[BookProfileItem] = field(default_factory=list)
    hardware: list[BookHardwareItem] = field(default_factory=list)
    formulas: list[BookFormulaTrace] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized_config: dict[str, Any] = field(default_factory=dict)
    source_priority: list[str] = field(default_factory=lambda: list(SOURCE_PRIORITY))
    configuration_status: FormulaStatus = "confirmed"
    calculation_status: FormulaStatus = "preliminary"
    documents_allowed: bool = True
    production_sheet_implemented: bool = True
    documents_implemented: bool = False
    document_block_reasons: list[str] = field(default_factory=list)


def _get(section: object, name: str, default: Any = None) -> Any:
    if isinstance(section, dict):
        return section.get(name, default)
    return getattr(section, name, default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise BookCalculationError(f"Ожидалось числовое значение, получено: {value!r}") from exc


def _integer(value: Any, default: int = 0) -> int:
    number = _number(value, float(default))
    if not number.is_integer():
        raise BookCalculationError(f"Количество должно быть целым числом, получено: {value!r}")
    return int(number)


def _mm(value: float) -> float:
    """Проектная точность первого этапа — 0,1 мм, без целого округления."""
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _qty(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _require_positive(value: float, label: str) -> float:
    if value <= 0:
        raise BookCalculationError(
            f"{label} получился {value:.1f} мм. Проверьте ширину, высоту, "
            "количество панелей и дополнительные элементы."
        )
    return value


def _normalize_door_layout(section: object) -> str:
    raw = _text(_get(section, "door_side")).lower().replace("ё", "е")
    doors = _integer(_get(section, "doors"), 0)
    subtype = _text(_get(section, "book_subtype")).lower()
    if raw in {"both", "обе", "оба", "с обеих сторон", "левая и правая", "слева и справа"}:
        return "both"
    if raw in {"left", "левая", "лев", "слева"}:
        return "both" if doors >= 2 else "left"
    if raw in {"right", "правая", "прав", "справа"}:
        return "both" if doors >= 2 else "right"
    if raw in {"none", "без", "без дверей"}:
        return "none"
    if doors >= 2:
        return "both"
    if doors == 1:
        return "left"
    if subtype in {"angle", "угол", "с углом"}:
        return "none"
    return "right"


def _normalize_hardware(value: Any, legacy: Any = None) -> str:
    text = _text(value or legacy).lower()
    if "зам" in text or "тип 4" in text or text in {"lock", "key"}:
        return "lock"
    return "handle"


def _normalize_opening(value: Any, legacy: Any = None) -> str:
    text = _text(value or legacy).lower().replace("ё", "е")
    compact = " ".join(text.replace("/", " ").replace("_", " ").split())
    mapping = {
        "inside in": "inside_in",
        "inside out": "inside_out",
        "outside out": "outside_out",
        "outside in": "outside_in",
        "изнутри внутрь": "inside_in",
        "изнутри наружу": "inside_out",
        "снаружи наружу": "outside_out",
        "снаружи внутрь": "outside_in",
        "внутрь": "inside_in",
        "наружу": "inside_out",
    }
    return mapping.get(compact, "inside_in")


def _normalize_compensator(value: Any, warnings: list[str]) -> str:
    text = _text(value).lower().replace("ё", "е")
    if text in {"lower", "нижний", "снизу"}:
        return "lower"
    if text in {"upper", "верхний", "сверху"}:
        return "upper"
    if text in {"both", "оба", "нижний и верхний", "верхний и нижний"}:
        return "both"
    if text in {"none", "без", "нет"}:
        return "none"
    if text in {"левый", "правый"}:
        warnings.append(
            f"Сохранено старое значение компенсатора «{value}». "
            "Выберите нижний, верхний или оба компенсатора."
        )
        return "none"
    # В новом ТЗ компенсатор обязателен к выбору; для новой пустой секции
    # используется нижний вариант, показанный в контрольных схемах.
    return "lower"


def _normalize_book_system(value: Any, warnings: list[str]) -> str:
    raw = _text(value).upper().replace("Ё", "Е")
    if not raw:
        return "B25"
    normalized = BOOK_SYSTEM_ALIASES.get(raw, raw)
    if normalized not in BOOK_SYSTEMS:
        raise BookCalculationError(
            "Система КНИЖКИ должна быть одной из B25, B16, B17, C16 или C17"
        )
    if raw in {"С КАРЕТКОЙ", "БЕЗ КАРЕТКИ"}:
        warnings.append(
            f"Старое значение системы «{value}» перенесено в B25, чтобы сохранить "
            "результат прежнего калькулятора. Проверьте систему профиля."
        )
    return normalized


def _book_height_rules(
    book_system: str,
    compensator: str,
) -> tuple[float, float, float, FormulaSource, str]:
    family = "B16" if book_system in LEGACY_HEIGHT_FAMILY_SYSTEMS else "B25"
    deduction = HEIGHT_DEDUCTIONS_MM[family][compensator]
    if family == "B25":
        door_adjustment = 0.0
        assembly_adjustment = 33.0
    else:
        door_adjustment = -33.0
        assembly_adjustment = -33.0

    if book_system == "B25" and compensator == "lower":
        source: FormulaSource = "excel"
        reference = (
            "Расчет_книжки_29_07_26_прямые_секции.xlsx, C24/C25, C27/C28"
        )
    else:
        source = "legacy"
        reference = (
            "Восстановленная старая программа: appglass/engine/glass_calc.py; "
            "матрица высот по системе и компенсатору"
        )
    return (
        deduction,
        door_adjustment,
        assembly_adjustment,
        source,
        reference,
    )


def _position(index: int, count: int) -> str:
    if count == 1:
        return "single"
    if index == 0:
        return "left"
    if index == count - 1:
        return "right"
    return "middle"


def _movement_direction(
    index: int,
    role: str,
    door_layout: str,
    left_stack: int,
) -> str:
    if role == "fixed":
        return "none"
    if door_layout == "left":
        return "left"
    if door_layout == "right":
        return "right"
    if door_layout == "both":
        return "left" if index < left_stack else "right"
    return "left"


def _panel_hardware(role: str, hardware: str | None, opening: str | None) -> list[str]:
    if role == "door":
        articles = ["RBA0006", "RBA0005", "RBA0050", "RBA0008"]
        if hardware == "lock":
            articles.append("RBA0052")
        else:
            articles.extend(["RBA0026", "RBA0219", "RBA0021"])
        if opening in {"inside_in", "outside_in"}:
            articles.append("RBA0211")
        else:
            articles.append("RBA0212")
        return articles
    if role == "moving_door":
        return [
            "RBA0052",
            "RBA0014",
            "RBM0003",
            "RBM0004",
            "RBM0005",
            "RBM0006",
            "RBM0007",
            "RBM0008",
            "RBM0009",
            "RBM0011",
        ]
    if role == "standard":
        return ["RBA0001", "RBA0002", "RBA0003", "RBA0004"]
    return []


def _add_formula(
    result: BookCalcResult,
    *,
    key: str,
    name: str,
    value: float | int | str,
    unit: str,
    expression: str,
    scope: str,
    source: FormulaSource,
    status: FormulaStatus,
    reference: str,
) -> None:
    result.formulas.append(
        BookFormulaTrace(
            key=key,
            name=name,
            value=value,
            unit=unit,
            expression=expression,
            scope=scope,
            source=source,
            status=status,
            source_reference=reference,
        )
    )


def _add_hardware(
    result: BookCalcResult,
    *,
    article: str,
    name: str,
    qty: float,
    unit: str,
    stage: int,
    formula: str,
    note: str = "",
    source: FormulaSource = "excel",
    status: FormulaStatus = "confirmed",
) -> None:
    result.hardware.append(
        BookHardwareItem(
            article=article,
            name=name,
            qty=_qty(qty),
            unit=unit,
            shipment_stage=stage,
            formula=formula,
            note=note,
            source=source,
            status=status,
            included=qty > 0,
        )
    )


def _opening_is_visual_in(opening: str) -> bool:
    return opening in {"inside_in", "outside_in"}


def _build_hardware(
    result: BookCalcResult,
    *,
    width: float,
    quantity: int,
    panel_count: int,
    moving_panels: int,
    door_layout: str,
    left_hardware: str,
    right_hardware: str,
    left_opening: str,
    right_opening: str,
    extra_door_enabled: bool,
    extra_door_opening: str,
    extra_door_direction: str,
    angular_joints: int,
    joints_90: int,
) -> None:
    q = quantity
    doors = int(door_layout in {"left", "both"}) + int(door_layout in {"right", "both"})
    lock_doors = (
        int(door_layout in {"left", "both"} and left_hardware == "lock")
        + int(door_layout in {"right", "both"} and right_hardware == "lock")
    )
    handle_doors = doors - lock_doors
    extra_doors = int(extra_door_enabled)
    direct_joints = max(0, ceil(width / 6000) - 1)
    pivots_per_section = 2 * ceil(moving_panels / 2) if moving_panels else 0

    left_door = int(door_layout in {"left", "both"})
    right_door = int(door_layout in {"right", "both"})
    left_closers = (
        int(left_door and _opening_is_visual_in(left_opening))
        + int(right_door and not _opening_is_visual_in(right_opening))
    )
    right_closers = doors - left_closers

    # ТЗ перекрывает строку Excel RBA0009: по одному механизму на физическую
    # панель и ещё один в общем сборе, когда панелей больше четырёх.
    compensator_sets = (panel_count + int(panel_count > 4)) * q
    _add_hardware(
        result,
        article="RBP0004",
        name="Белое скользящее покрытие",
        qty=ceil(width * 2 / 1000) * q,
        unit="м.п.",
        stage=1,
        formula="ceil(W × 2 / 1000) × q",
        note="Устанавливается на производстве.",
    )
    _add_hardware(
        result,
        article="RU004",
        name="Щеточный уплотнитель 7×6, серый",
        qty=ceil(width * 2 / 1000) * q,
        unit="м.п.",
        stage=1,
        formula="ceil(W × 2 / 1000) × q",
        note="Устанавливается на производстве.",
    )
    _add_hardware(
        result,
        article="RBA0009",
        name="Компенсирующие болт и гайка",
        qty=compensator_sets,
        unit="шт.",
        stage=1,
        formula="(P + 1 при P > 4) × q",
        note="Формула ТЗ имеет приоритет над формулой Excel 3D + M.",
        source="tz",
    )
    _add_hardware(
        result,
        article="RBA0035",
        name="Упрочнитель углов",
        qty=2 * angular_joints * q,
        unit="шт.",
        stage=1,
        formula="2 × A × q",
        note="По ТЗ ставится сверху и снизу каждого угла.",
        source="tz",
    )
    _add_hardware(
        result,
        article="RBA0045",
        name="Соединительная деталь прямых конструкций",
        qty=2 * direct_joints * q,
        unit="шт.",
        stage=1,
        formula="2 × Jпрям × q",
    )
    _add_hardware(
        result,
        article="RBA0036",
        name="Угол 90°",
        qty=joints_90 * q,
        unit="шт.",
        stage=1,
        formula="J90 × q",
    )
    _add_hardware(
        result,
        article="RBA0006",
        name="Шарнир",
        qty=doors * 3 * q,
        unit="шт.",
        stage=1,
        formula="D × 3 × q",
    )
    _add_hardware(
        result,
        article="RBA0055",
        name="Заглушка на нижний направляющий профиль",
        qty=2 * q,
        unit="шт.",
        stage=1,
        formula="2 × q",
        note="В исходном Excel отмечено «Будут или нет».",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0040",
        name="h-уплотнитель жесткий 10 мм, 3 м",
        qty=moving_panels * q,
        unit="шт.",
        stage=2,
        formula="M × q",
    )
    felt_angle_joints = angular_joints
    _add_hardware(
        result,
        article="RBA0041",
        name="Уплотнитель с фетром 10 мм, 3 м",
        qty=(2 + felt_angle_joints) * q,
        unit="шт.",
        stage=2,
        formula="(2 + Jугл 90…135°) × q",
        note="В Excel есть указание заменить на фетр 7×15.",
        status="preliminary",
    )
    for article, name in (
        ("RBA0001", "Верхний поворотный механизм"),
        ("RBA0002", "Нижний поворотный механизм"),
        ("RBA0003", "Верхняя направляющая"),
        ("RBA0004", "Нижняя направляющая"),
    ):
        _add_hardware(
            result,
            article=article,
            name=name,
            qty=moving_panels * q,
            unit="шт.",
            stage=2,
            formula="M × q",
        )
    _add_hardware(
        result,
        article="RBA0005",
        name="Ось вращения двери",
        qty=doors * 2 * q,
        unit="шт.",
        stage=2,
        formula="D × 2 × q",
    )
    _add_hardware(
        result,
        article="RBA0010",
        name="Поворотный механизм",
        qty=pivots_per_section * q,
        unit="шт.",
        stage=2,
        formula="2 × ceil(M / 2) × q",
        note="Правило калькулятора Excel требует окончательного подтверждения.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0050",
        name="Выход под нижнюю направляющую",
        qty=doors * q,
        unit="шт.",
        stage=2,
        formula="D × q",
    )
    _add_hardware(
        result,
        article="RBA0211",
        name="Доводчик левый с балансиром, старый вариант",
        qty=left_closers * q,
        unit="шт.",
        stage=2,
        formula="(Dлев визуально внутрь + Dправ визуально наружу) × q",
        note="Артикул помечен в Excel как старый вариант.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0212",
        name="Доводчик правый с балансиром, старый вариант",
        qty=right_closers * q,
        unit="шт.",
        stage=2,
        formula="(Dправ визуально внутрь + Dлев визуально наружу) × q",
        note="Артикул помечен в Excel как старый вариант.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0219",
        name="Комплект верхней защелки в сборе, старый вариант",
        qty=handle_doors * q,
        unit="шт.",
        stage=2,
        formula="Dбез замка × q",
        note="Артикул помечен в Excel как старый вариант.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0021",
        name="Нижняя защелка-балансир",
        qty=handle_doors * q,
        unit="шт.",
        stage=2,
        formula="Dбез замка × q",
    )
    short_screws = (
        pivots_per_section * 2
        + doors * 3
        + direct_joints * 16
        + angular_joints * 16
    ) * q
    _add_hardware(
        result,
        article="RBA0013",
        name="Шуруп DIN 7982 3,5×9,5",
        qty=short_screws,
        unit="шт.",
        stage=2,
        formula="(Pмех × 2 + D × 3 + Jпрям × 16 + Jугл × 16) × q",
    )
    _add_hardware(
        result,
        article="RBA0013",
        name="Шуруп DIN 7982 3×16, длинный",
        qty=(doors * 2 + extra_doors * 2) * q,
        unit="шт.",
        stage=2,
        formula="(D × 2 + Dдоп × 2) × q",
        note="В Excel повторен артикул RBA0013; правильный артикул неизвестен.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBA0026",
        name="Ручка стеклянная RALUMA",
        qty=handle_doors * q,
        unit="шт.",
        stage=2,
        formula="Dсо стеклянной ручкой × q",
    )
    _add_hardware(
        result,
        article="RBA0052",
        name="Замок с нажимной ручкой и ключом",
        qty=(lock_doors + extra_doors) * q,
        unit="шт.",
        stage=2,
        formula="(Dзамок + Dдоп) × q",
    )
    _add_hardware(
        result,
        article="RBA0008",
        name="Фиксатор для панелей",
        qty=doors * q,
        unit="шт.",
        stage=2,
        formula="D × q",
    )
    _add_hardware(
        result,
        article="RBA0014",
        name="Крышка под доводчик",
        qty=extra_doors * q,
        unit="шт.",
        stage=2,
        formula="Dдоп × q",
    )

    left_stop = 0
    right_stop = 0
    if extra_door_enabled:
        visual_in = _opening_is_visual_in(extra_door_opening)
        if (extra_door_direction == "left" and visual_in) or (
            extra_door_direction == "right" and not visual_in
        ):
            left_stop = q
        else:
            right_stop = q
    _add_hardware(
        result,
        article="RBM0001",
        name="Упор 90° левый",
        qty=left_stop,
        unit="шт.",
        stage=2,
        formula="Dдоп по стороне и открыванию × q",
        note="Условие стороны в Excel неоднозначно.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBM0002",
        name="Упор 90° правый",
        qty=right_stop,
        unit="шт.",
        stage=2,
        formula="Dдоп по стороне и открыванию × q",
        note="Условие стороны в Excel неоднозначно.",
        status="preliminary",
    )
    _add_hardware(
        result,
        article="RBM00021",
        name="Клепка-заглушка доводчика",
        qty=left_stop + right_stop,
        unit="шт.",
        stage=2,
        formula="RBM0001 + RBM0002",
        note="Повторное умножение на q из текста Excel не применяется.",
        status="preliminary",
    )
    for article, name in (
        ("RBM0003", "Шпонка для двигающейся двери"),
        ("RBM0004", "Верхний шарнир для двигающейся двери"),
        ("RBM0005", "Нижний шарнир для двигающейся двери"),
        ("RBM0006", "Верхний поворотный механизм для двигающейся двери"),
        ("RBM0007", "Нижний поворотный механизм для двигающейся двери"),
        ("RBM0008", "Нижняя направляющая для двигающейся двери"),
        ("RBM0009", "Выход под нижнюю направляющую двигающейся двери"),
        ("RBM0011", "Контроль-деталь для сдвижной двери"),
    ):
        _add_hardware(
            result,
            article=article,
            name=name,
            qty=extra_doors * q,
            unit="шт.",
            stage=2,
            formula="Dдоп × q",
            status="preliminary",
        )


def calculate_book(section: object) -> BookCalcResult:
    """Рассчитать одну секцию КНИЖКИ и вернуть физические панели."""
    system = _text(_get(section, "system")).upper()
    if system != "КНИЖКА":
        raise BookCalculationError("calculate_book принимает только секции КНИЖКА")

    width = _number(_get(section, "width"))
    height = _number(_get(section, "height"))
    base_panel_count = _integer(_get(section, "panels"))
    quantity = _integer(_get(section, "quantity"), 1)
    if width <= 0 or height <= 0:
        raise BookCalculationError("Ширина и высота секции КНИЖКИ должны быть больше нуля")
    if base_panel_count < 2:
        raise BookCalculationError("Для КНИЖКИ количество панелей должно быть не меньше 2")
    if quantity <= 0:
        raise BookCalculationError("Количество одинаковых секций должно быть больше нуля")

    result = BookCalcResult()
    book_system = _normalize_book_system(_get(section, "book_system"), result.warnings)
    door_layout = _normalize_door_layout(section)
    left_hardware = _normalize_hardware(
        _get(section, "book_left_door_hardware"),
        _get(section, "door_type"),
    )
    right_hardware = _normalize_hardware(
        _get(section, "book_right_door_hardware"),
        _get(section, "door_type"),
    )
    left_opening = _normalize_opening(
        _get(section, "book_left_door_opening"),
        _get(section, "door_opening"),
    )
    right_opening = _normalize_opening(
        _get(section, "book_right_door_opening"),
        _get(section, "door_opening"),
    )
    compensator = _normalize_compensator(_get(section, "compensator"), result.warnings)

    angle_left_deg = _number(_get(section, "angle_left"), 0.0)
    angle_right_deg = _number(_get(section, "angle_right"), 0.0)
    if not 0 <= angle_left_deg <= 180 or not 0 <= angle_right_deg <= 180:
        raise BookCalculationError("Угол КНИЖКИ должен быть от 0 до 180°")
    if angle_left_deg <= 0 and bool(_get(section, "corner_left", False)):
        angle_left_deg = 90.0
    if angle_right_deg <= 0 and bool(_get(section, "corner_right", False)):
        angle_right_deg = 90.0
    angle_left = 0 < angle_left_deg < 180
    angle_right = 0 < angle_right_deg < 180
    extra_door_enabled = bool(_get(section, "book_extra_door_enabled", False))
    preliminary_features: list[str] = []
    if angle_left or angle_right or _text(_get(section, "book_subtype")).lower() in {
        "angle",
        "doors_and_angle",
    }:
        preliminary_features.append("угловая конструкция")
    if extra_door_enabled:
        preliminary_features.append("дополнительная двигающаяся дверь")
    if preliminary_features:
        result.configuration_status = "preliminary"
        result.documents_allowed = False
        result.document_block_reasons.append(
            "Предварительная конфигурация: " + ", ".join(preliminary_features) + "."
        )
        result.warnings.append(
            "Расчёт содержит неподтверждённые элементы: "
            + ", ".join(preliminary_features)
            + ". Производственные документы заблокированы."
        )
    if book_system != "B25":
        result.configuration_status = "preliminary"
        result.documents_allowed = False
        result.document_block_reasons.append(
            f"Система {book_system}: геометрия высот восстановлена из старой "
            "программы, а состав фурнитуры нового Excel ещё не подтверждён."
        )
        result.warnings.append(
            f"Для системы {book_system} применено предварительное семейство "
            "высот B16. До контрольного проекта производственные документы "
            "этой системы заблокированы."
        )

    left_door = door_layout in {"left", "both"}
    right_door = door_layout in {"right", "both"}
    door_count = int(left_door) + int(right_door)
    if door_count > base_panel_count:
        raise BookCalculationError(
            "Количество панелей должно включать обе основные двери"
        )

    fixed_fields = {
        "left_fixed_left": (
            "book_left_fixed_left_enabled",
            "book_left_fixed_left_width",
        ),
        "left_fixed_right": (
            "book_left_fixed_right_enabled",
            "book_left_fixed_right_width",
        ),
        "right_fixed_left": (
            "book_right_fixed_left_enabled",
            "book_right_fixed_left_width",
        ),
        "right_fixed_right": (
            "book_right_fixed_right_enabled",
            "book_right_fixed_right_width",
        ),
    }
    fixed_specs: dict[str, float] = {}
    has_new_fixed = any(
        bool(_get(section, enabled_field, False))
        for enabled_field, _ in fixed_fields.values()
    )
    for key, (enabled_field, width_field) in fixed_fields.items():
        if not bool(_get(section, enabled_field, False)):
            continue
        if key.startswith("left_") and not left_door:
            continue
        if key.startswith("right_") and not right_door:
            continue
        panel_width = _number(_get(section, width_field))
        if panel_width <= 3:
            raise BookCalculationError(
                "Ширина каждой включённой глухой панели должна быть больше 3 мм"
            )
        fixed_specs[key] = panel_width

    # Старое поле одной глухой панели читается без миграции данных. После
    # сохранения новая форма пишет только четыре однозначных положения.
    if not has_new_fixed and bool(_get(section, "book_extra_fixed_enabled", False)):
        legacy_width = _number(_get(section, "book_extra_fixed_width"))
        if legacy_width <= 3:
            raise BookCalculationError(
                "Ширина дополнительной глухой панели должна быть больше 3 мм"
            )
        legacy_right = _text(
            _get(section, "book_extra_fixed_side", "left")
        ).lower() in {"right", "справа", "правая"}
        if door_layout == "right":
            legacy_key = "right_fixed_right" if legacy_right else "right_fixed_left"
        elif door_layout == "both" and legacy_right:
            legacy_key = "right_fixed_right"
        else:
            legacy_key = "left_fixed_right" if legacy_right and left_door else "left_fixed_left"
        fixed_specs[legacy_key] = legacy_width

    panel_defs: list[dict[str, Any]] = []

    def add_fixed(key: str) -> None:
        if key in fixed_specs:
            panel_defs.append(
                {
                    "role": "fixed",
                    "door_side": None,
                    "fixed_key": key,
                    "specified_width": fixed_specs[key],
                }
            )

    if left_door:
        add_fixed("left_fixed_left")
        panel_defs.append({"role": "door", "door_side": "left"})
        add_fixed("left_fixed_right")
    panel_defs.extend(
        {"role": "standard", "door_side": None}
        for _ in range(base_panel_count - door_count)
    )
    if right_door:
        add_fixed("right_fixed_left")
        panel_defs.append({"role": "door", "door_side": "right"})
        add_fixed("right_fixed_right")
    if not left_door and not right_door:
        # Поддержка старых угловых сохранений без двери.
        panel_defs = [
            {"role": "standard", "door_side": None}
            for _ in range(base_panel_count)
        ]
        if fixed_specs:
            key, panel_width = next(iter(fixed_specs.items()))
            fixed_def = {
                "role": "fixed",
                "door_side": None,
                "fixed_key": key,
                "specified_width": panel_width,
            }
            if key.endswith("_right"):
                panel_defs.append(fixed_def)
            else:
                panel_defs.insert(0, fixed_def)

    roles = [str(panel["role"]) for panel in panel_defs]
    physical_count = len(panel_defs)
    folding_indices = [index for index, role in enumerate(roles) if role != "fixed"]
    fixed_indices = [index for index, role in enumerate(roles) if role == "fixed"]

    extra_door_index: int | None = None
    if extra_door_enabled:
        requested_panel = _integer(_get(section, "book_extra_door_panel"), 0)
        if requested_panel < 1 or requested_panel > physical_count:
            raise BookCalculationError(
                f"Номер дополнительной двери должен быть от 1 до {physical_count}"
            )
        extra_door_index = requested_panel - 1
        if roles[extra_door_index] != "standard":
            raise BookCalculationError(
                "Дополнительная дверь должна заменять обычную подвижную панель, "
                "а не крайнюю дверь или глухую панель"
            )
        roles[extra_door_index] = "moving_door"

    left_stack = _integer(
        _get(section, "book_left_stack_panels"),
        max(1, base_panel_count // 2),
    )
    if door_layout == "both" and not (1 <= left_stack < base_panel_count):
        raise BookCalculationError(
            "Сбор слева должен быть не меньше 1 и меньше количества подвижных панелей"
        )

    left_boundary = 27.0 if angle_left else 11.5
    right_boundary = 27.0 if angle_right else 11.5
    total_glass_span = width - left_boundary - right_boundary - 3.0 * (physical_count - 1)
    _require_positive(total_glass_span, "Суммарная ширина стекол")

    specified_glass: dict[int, float] = {
        index: _require_positive(
            float(panel["specified_width"]) - 3.0,
            "Ширина стекла глухой панели",
        )
        for index, panel in enumerate(panel_defs)
        if panel.get("role") == "fixed"
    }
    door_width_fields = {
        "left": "book_left_door_width",
        "right": "book_right_door_width",
    }
    for index, panel in enumerate(panel_defs):
        side = panel.get("door_side")
        if panel.get("role") != "door" or side not in door_width_fields:
            continue
        raw_width = _get(section, door_width_fields[side])
        if raw_width in (None, ""):
            continue
        door_width = _number(raw_width)
        if door_width <= 3:
            raise BookCalculationError(
                "Заданная ширина основной двери должна быть больше 3 мм"
            )
        specified_glass[index] = door_width - 3.0
    if extra_door_index is not None:
        extra_door_width = _number(_get(section, "book_extra_door_width"))
        if extra_door_width <= 0 or extra_door_width > 850:
            raise BookCalculationError(
                "Ширина дополнительной двигающейся двери должна быть больше 0 и не более 850 мм"
            )
        specified_glass[extra_door_index] = _require_positive(
            extra_door_width - 3.0,
            "Ширина стекла дополнительной двери",
        )

    uniform_count = physical_count - len(specified_glass)
    remaining_glass = total_glass_span - sum(specified_glass.values())
    if uniform_count <= 0:
        if abs(remaining_glass) > 0.11:
            raise BookCalculationError(
                "Сумма заданных ширин панелей не помещается в ширину секции"
            )
        uniform_glass_width = 0.0
    else:
        uniform_glass_width = _require_positive(
            remaining_glass / uniform_count,
            "Ширина стекла стандартной панели",
        )
    (
        height_deduction,
        door_height_adjustment,
        assembly_height_adjustment,
        height_source,
        height_reference,
    ) = _book_height_rules(book_system, compensator)
    glass_height = _require_positive(
        height - height_deduction,
        "Высота стекла",
    )
    door_glass_height = _require_positive(
        glass_height + door_height_adjustment,
        "Высота дверного стекла",
    )
    panel_height = _require_positive(
        glass_height + assembly_height_adjustment,
        "Высота панели при склейке",
    )

    width_status: FormulaStatus = "preliminary" if preliminary_features else "confirmed"
    width_expression = (
        "(W − Lкрай − Rкрай − 3 × (P − 1) − ΣWзаданных стекол) / Pобычных"
        if specified_glass or preliminary_features
        else "(W − 11,5 − 11,5 − 3 × (P − 1)) / P"
    )
    _add_formula(
        result,
        key="glass_width",
        name="Ширина стекла",
        value=_mm(uniform_glass_width),
        unit="мм",
        expression=width_expression,
        scope="Прямая секция; при дополнительных элементах — предварительное распределение",
        source="tz",
        status=width_status,
        reference="ТЗ КНИЖКА, стр. 9, блок «Прямая секция»",
    )
    _add_formula(
        result,
        key="glass_profile_width",
        name="Ширина стекольного профиля",
        value=_mm(uniform_glass_width + 3.0),
        unit="мм",
        expression="Wстекла + 3",
        scope="Прямая секция",
        source="tz",
        status=width_status,
        reference="ТЗ КНИЖКА, стр. 9",
    )
    _add_formula(
        result,
        key="glass_height",
        name="Высота стекла",
        value=_mm(glass_height),
        unit="мм",
        expression=f"H − {_mm(height_deduction):g}",
        scope=f"Система {book_system}; компенсатор {compensator}",
        source=height_source,
        status="preliminary",
        reference=height_reference,
    )
    if door_height_adjustment:
        _add_formula(
            result,
            key="door_glass_height",
            name="Высота дверного стекла",
            value=_mm(door_glass_height),
            unit="мм",
            expression="Hстекла − 33",
            scope=f"Двери систем семейства B16; выбрана {book_system}",
            source="legacy",
            status="preliminary",
            reference="Восстановленная старая программа: appglass/engine/glass_calc.py",
        )
    _add_formula(
        result,
        key="panel_assembly_height",
        name="Высота панели при склейке",
        value=_mm(panel_height),
        unit="мм",
        expression=(
            "Hстекла + 33"
            if assembly_height_adjustment > 0
            else "Hстекла − 33"
        ),
        scope=f"Система {book_system}",
        source=height_source,
        status="preliminary",
        reference=height_reference,
    )

    extra_door_opening = _normalize_opening(_get(section, "book_extra_door_opening"))
    moving_rank_by_index = {
        panel_index: rank
        for rank, panel_index in enumerate(folding_indices)
    }
    for index, role in enumerate(roles):
        side: str | None = panel_defs[index].get("door_side")
        hardware: str | None = None
        opening: str | None = None
        if role == "door":
            if side == "left":
                hardware = left_hardware
                opening = left_opening
            else:
                hardware = right_hardware
                opening = right_opening
        elif role == "moving_door":
            hardware = "lock"
            opening = extra_door_opening

        movement = _movement_direction(
            moving_rank_by_index.get(index, 0),
            role,
            door_layout,
            left_stack,
        )
        glass_width = specified_glass.get(index, uniform_glass_width)
        panel_glass_height = (
            door_glass_height if role in {"door", "moving_door"} else glass_height
        )
        profile_addition = 23.0 if (role == "door" and (angle_left or angle_right)) else 3.0
        profile_width = glass_width + profile_addition
        panel_status: FormulaStatus = (
            "preliminary"
            if (
                preliminary_features
                or book_system != "B25"
                or role == "moving_door"
            )
            else "confirmed"
        )
        panel_source: FormulaSource = "tz"
        dimension_sources = {
            "glass_width_mm": {
                "source": panel_source,
                "status": panel_status,
            },
            "glass_height_mm": {
                "source": height_source,
                "status": "preliminary",
            },
            "glass_profile_width_mm": {
                "source": panel_source,
                "status": panel_status,
            },
            "panel_height_mm": {
                "source": height_source,
                "status": "preliminary",
            },
        }
        result.panels.append(
            BookPanelItem(
                number=index + 1,
                position=_position(index, physical_count),
                role=role,
                movement_direction=movement,
                door_side=side,
                door_hardware=hardware,
                door_opening=opening,
                door_opening_label=OPENING_LABELS.get(opening) if opening else None,
                glass_type=_text(_get(section, "glass_type")) or "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
                glass_width_mm=_mm(glass_width),
                glass_height_mm=_mm(panel_glass_height),
                glass_profile_article="RBP002",
                glass_profile_width_mm=_mm(profile_width),
                panel_width_mm=_mm(profile_width),
                panel_height_mm=_mm(panel_height),
                qty=quantity,
                hardware_articles=_panel_hardware(role, hardware, opening),
                source=panel_source,
                status=panel_status,
                dimension_sources=dimension_sources,
            )
        )
        result.profiles.append(
            BookProfileItem(
                article="RBP002",
                name="Стекольный профиль",
                length_mm=_mm(profile_width),
                qty=2 * quantity,
                unit="шт.",
                position=f"Панель {index + 1}",
                panel_number=index + 1,
                source=panel_source,
                status=panel_status,
                formula=(
                    "Wстекла + 23"
                    if profile_addition == 23.0
                    else "Wстекла + 3"
                ),
            )
        )

    result.profiles.insert(
        0,
        BookProfileItem(
            article="RBP001",
            name="Направляющий профиль",
            length_mm=_mm(width),
            qty=2 * quantity,
            unit="шт.",
            position="Верх и низ секции",
            panel_number=None,
            source="excel",
            status="confirmed",
            formula="W × 2 × q",
        ),
    )
    compensator_count = {"none": 0, "lower": 1, "upper": 1, "both": 2}[compensator]
    result.profiles.insert(
        1,
        BookProfileItem(
            article="RBP003",
            name="Компенсирующий профиль",
            length_mm=_mm(width),
            qty=compensator_count * quantity,
            unit="шт.",
            position={
                "none": "Без компенсатора",
                "lower": "Низ",
                "upper": "Верх",
                "both": "Верх и низ",
            }[compensator],
            panel_number=None,
            source="tz",
            status="confirmed",
            formula=f"{compensator_count} × W × q",
        ),
    )

    moving_panels = sum(1 for role in roles if role == "standard")
    extra_door_direction = (
        _movement_direction(
            moving_rank_by_index.get(extra_door_index, 0),
            "moving_door",
            door_layout,
            left_stack,
        )
        if extra_door_index is not None
        else "none"
    )
    angular_joints = int(angle_left) + int(angle_right)
    joints_90 = int(
        angle_left and abs(_number(_get(section, "angle_left")) - 90.0) < 0.05
    ) + int(
        angle_right and abs(_number(_get(section, "angle_right")) - 90.0) < 0.05
    )
    _build_hardware(
        result,
        width=width,
        quantity=quantity,
        panel_count=physical_count,
        moving_panels=moving_panels,
        door_layout=door_layout,
        left_hardware=left_hardware,
        right_hardware=right_hardware,
        left_opening=left_opening,
        right_opening=right_opening,
        extra_door_enabled=extra_door_enabled,
        extra_door_opening=extra_door_opening,
        extra_door_direction=extra_door_direction,
        angular_joints=angular_joints,
        joints_90=joints_90,
    )
    if book_system != "B25":
        for item in result.hardware:
            if item.source == "excel":
                item.status = "preliminary"
                item.note = (
                    f"{item.note} Формула нового Excel не подтверждена для "
                    f"системы {book_system}."
                ).strip()

    if any(item.status == "preliminary" for item in result.formulas):
        result.calculation_status = "preliminary"
    else:
        result.calculation_status = "confirmed"
    if any(item.status == "preliminary" and item.included for item in result.hardware):
        result.warnings.append(
            "В активной комплектации есть фурнитура с предварительной формулой "
            "или неподтверждённым артикулом."
        )

    obstacle_distance = _number(_get(section, "book_obstacle_distance"), 0.0)
    if obstacle_distance < 0:
        raise BookCalculationError("Расстояние до препятствия не может быть отрицательным")
    handle_height = _number(_get(section, "book_handle_height"), 0.0)
    if handle_height < 0 or handle_height > height:
        raise BookCalculationError(
            "Высота ручки должна быть от 0 до высоты секции"
        )
    result.normalized_config = {
        "width_mm": _mm(width),
        "height_mm": _mm(height),
        "book_system": book_system,
        "height_family": (
            "B16" if book_system in LEGACY_HEIGHT_FAMILY_SYSTEMS else "B25"
        ),
        "base_panel_count": base_panel_count,
        "physical_panel_count": physical_count,
        "quantity": quantity,
        "door_layout": door_layout,
        "left_door_hardware": left_hardware if door_layout in {"left", "both"} else None,
        "right_door_hardware": right_hardware if door_layout in {"right", "both"} else None,
        "left_door_opening": left_opening if door_layout in {"left", "both"} else None,
        "right_door_opening": right_opening if door_layout in {"right", "both"} else None,
        "left_door_width_mm": (
            _mm(_number(_get(section, "book_left_door_width")))
            if left_door and _get(section, "book_left_door_width") not in (None, "")
            else None
        ),
        "right_door_width_mm": (
            _mm(_number(_get(section, "book_right_door_width")))
            if right_door and _get(section, "book_right_door_width") not in (None, "")
            else None
        ),
        "glass_supplied": bool(_get(section, "glass_supplied", True)),
        "compensator": compensator,
        "obstacle_distance_mm": _mm(obstacle_distance),
        "left_stack_panels": left_stack if door_layout == "both" else None,
        "handle_height_mm": _mm(handle_height) if handle_height else None,
        "angle_left_deg": _mm(angle_left_deg) if angle_left else None,
        "angle_right_deg": _mm(angle_right_deg) if angle_right else None,
        "fixed_panel_numbers": [index + 1 for index in fixed_indices],
        "fixed_panels": {
            str(panel.get("fixed_key")): index + 1
            for index, panel in enumerate(panel_defs)
            if panel.get("role") == "fixed"
        },
        "extra_fixed_panel_number": fixed_indices[0] + 1 if fixed_indices else None,
        "extra_door_panel_number": (
            extra_door_index + 1 if extra_door_index is not None else None
        ),
        "extra_fixed_panel": bool(fixed_indices),
        "extra_moving_door": extra_door_enabled,
    }
    return result


def book_configuration_is_preliminary(section: object) -> bool:
    """Быстрая проверка для блокировки проектных производственных документов."""
    result = calculate_book(section)
    return not result.documents_allowed
