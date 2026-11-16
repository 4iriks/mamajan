"""Preliminary BOOK machining from the supplied Word brief.

Coordinates are per physical section, never multiplied by section quantity.
Missing rules stay empty. The document layer supplies editable text fields.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from engine.book_calc import BookCalcResult


@dataclass
class BookMachiningOperation:
    key: str
    profile_article: str
    position: str
    reference_side: str
    kind: str
    coordinates_mm: list[float] = field(default_factory=list)
    status: Literal["preliminary", "manual_required"] = "preliminary"
    note: str = ""


def build_book_operations(calc: "BookCalcResult") -> list[BookMachiningOperation]:
    config = calc.normalized_config
    if not calc.documents_allowed or config["door_layout"] == "none":
        return []
    width = config["width_mm"]
    layout = config["door_layout"]
    reference = "right" if layout == "right" else "left"
    compensator = config["compensator"]
    has_fixed = bool(config["fixed_panel_numbers"])
    operations: list[BookMachiningOperation] = []

    def add(
        key, position, kind, coordinates=(), note="", side=reference, article="RBP001"
    ):
        coords = sorted({round(value, 1) for value in coordinates if 0 < value < width})
        operations.append(
            BookMachiningOperation(
                key=key,
                profile_article=article,
                position=position,
                reference_side=side,
                kind=kind,
                coordinates_mm=coords,
                status="preliminary" if coords else "manual_required",
                note=note,
            )
        )

    d13, d6, drains = [], [], []
    for side in ("left", "right"):
        door = next((p for p in calc.panels if p.door_side == side), None)
        if door is None:
            continue

        # A right-only section uses distances from the right end. With two
        # parking stacks all drilling coordinates share the left-end origin.
        def coordinate(distance):
            return (
                width - distance if layout == "both" and side == "right" else distance
            )

        wall_fixed = config["fixed_panels"].get(f"{side}_fixed_{side}")
        d13.append(coordinate(93))
        d6.append(coordinate(124))
        if not wall_fixed:
            d13.append(coordinate(185))
            d6.append(coordinate(246))
        drains.append(coordinate(277))
        stack = [p for p in calc.panels if p.movement_direction == side]
        if side == "right":
            stack.reverse()
        if not has_fixed:
            cumulative = 0.0
            for panel in stack:
                cumulative += panel.glass_profile_width_mm
                d13.append(coordinate(cumulative - 30))
                d6.append(coordinate(cumulative - 70))
        moving = [p for p in stack if p.role == "standard"]
        closer = []
        if moving and not has_fixed:
            panel_width = moving[0].glass_profile_width_mm
            closer = [
                min(
                    panel_width + 30
                    if door.panel_width_mm > panel_width
                    else panel_width - 15,
                    708,
                )
            ]
        add(
            f"closer_{side}",
            "upper",
            "Фрезеровка под доводчик",
            closer,
            "От края со стороны двери до дальней грани выреза. Размер выреза — уточнить по доводчику.",
            side=side,
        )
        add(
            f"outlet_{side}",
            "lower",
            "Выход под нижнюю направляющую",
            note="Ввести координату и размеры вручную. Дополнительные выходы проверить по схеме.",
            side=side,
        )

    for position in ("upper", "lower"):
        if compensator in (position, "both"):
            add(
                f"d13_{position}",
                position,
                "D13 под компенсирующие механизмы",
                d13,
                "Базовые правила Word; проверить отверстия по сечению профиля.",
            )
        add(
            f"d6_{position}",
            position,
            "Крепёжные отверстия D6",
            d6,
            "Базовые правила Word: 124, 246 и D13 − 40 от стороны двери.",
        )
        if has_fixed:
            add(
                f"panel_holes_{position}",
                position,
                "Отверстия у глухих панелей",
                note="Положение отверстий между панелями при глухих вставках уточнить вручную.",
            )
    add(
        "drain_d13",
        "lower",
        "Слив D13 у дверей",
        drains,
        "Проверить применимость к нижнему профилю.",
    )
    add(
        "drain_extra",
        "lower",
        "Остальные сливы",
        note="Ввести координаты и размеры: правило в ТЗ не завершено.",
    )
    if compensator != "none":
        add(
            "compensator_holes",
            compensator,
            "Обработка компенсирующего профиля",
            note="Сечение и крепёжные отверстия компенсатора проверить по сборке.",
            article="RBP003",
        )
    return operations
