"""Shared row preparation for editable section Office exports."""

from __future__ import annotations

from typing import Any

from engine.office_common import format_dimension, format_number
from engine.pdf import display_hardware, display_profiles


def section_summary_rows(section: object, calc: object) -> list[tuple[str, str]]:
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "ЦС":
        cs_system = getattr(calc, "system", None)
        system_name = str(getattr(cs_system, "name", "") or "Система не выбрана")
        panes = list(getattr(calc, "panes", None) or [])
        return [
            ("Монтажный проём, мм", f"{format_number(calc.installation_width_mm)} × {format_number(calc.installation_height_mm)}"),
            ("Световой проём, мм", f"{format_number(calc.clear_width_mm)} × {format_number(calc.clear_height_mm)}"),
            ("Количество секций, шт", str(getattr(section, "quantity", 1) or 1)),
            ("Количество стекол, шт", str(sum(int(getattr(pane, "qty", 1) or 1) for pane in panes))),
            ("Система ЦС", system_name),
            ("Стекло", str(getattr(section, "glass_type", "") or "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ")),
            ("Площадь стекла, м²", format_number(getattr(calc, "glass_area_m2", 0), 3)),
            ("Статус", "ПРЕДВАРИТЕЛЬНЫЙ РАСЧЁТ"),
        ]
    rows = [
        ("Ширина секции, мм", format_dimension(getattr(section, "width", 0))),
        ("Высота секции, мм", format_dimension(getattr(section, "height", 0))),
        ("Количество панелей, шт", str(getattr(section, "panels", 0))),
        ("Количество секций, шт", str(getattr(section, "quantity", 0))),
        ("Цвет", str(getattr(calc, "color_text", "") or "")),
    ]
    if system == "ЛИФТ":
        rows.extend(
            [
                ("Заполнение", str(getattr(calc, "filling_text", "") or "")),
                ("Открывание", str(getattr(calc, "opening_text", "") or "")),
                ("Управление", str(getattr(calc, "control_type", "") or "")),
                ("Ввод кабеля", str(getattr(calc, "cable_side", "") or "")),
            ]
        )
    else:
        rows.extend(
            [
                ("Стекло", str(getattr(calc, "glass_type", "") or "")),
                ("Порог", str(getattr(calc, "threshold_text", "") or "")),
                ("Система", str(getattr(calc, "system_text", "") or "")),
            ]
        )
    return rows


def profile_rows(calc: object) -> list[object]:
    profiles = list(getattr(calc, "profiles", None) or [])
    if hasattr(calc, "glass"):
        return display_profiles(profiles)
    return profiles


def hardware_rows(
    calc: object,
) -> list[tuple[str, str, Any, str, str | None, str, str]]:
    rows: list[tuple[str, str, Any, str, str | None, str, str]] = []
    if hasattr(calc, "screws"):
        for index, item in enumerate(display_hardware(calc.hardware), start=1):
            sub_items = list(getattr(item, "sub_items", None) or [])
            if sub_items:
                for sub in sub_items:
                    rows.append(
                        (
                            str(sub.article),
                            f"{item.name} {sub.label}".strip(),
                            sub.value,
                            "м" if str(sub.article) in {"RU007", "RU008"} else item.unit,
                            getattr(sub, "image", None) or item.image,
                            getattr(sub, "field_key", ""),
                            "",
                        )
                    )
            else:
                rows.append(
                    (
                        str(item.article),
                        str(item.name),
                        item.value,
                        str(item.unit),
                        item.image,
                        item.field_key or f"hw_{index}_val",
                        "",
                    )
                )
        for index, screw in enumerate(calc.screws, start=1):
            rows.append(
                (
                    str(screw.article),
                    str(screw.name),
                    screw.qty,
                    "шт",
                    screw.image,
                    f"screw_{index}",
                    str(screw.note or ""),
                )
            )
    else:
        for index, item in enumerate(getattr(calc, "hardware", None) or [], start=1):
            rows.append(
                (
                    str(item.article),
                    str(item.name),
                    getattr(item, "value", getattr(item, "qty", 0)),
                    str(item.unit),
                    item.image,
                    f"lift_hardware_{index}_value",
                    str(getattr(item, "note", "") or ""),
                )
            )
        for index, item in enumerate(getattr(calc, "fasteners", None) or [], start=1):
            rows.append(
                (
                    str(item.article),
                    str(item.name),
                    item.value,
                    str(item.unit),
                    item.image,
                    f"lift_fastener_{index}_value",
                    str(getattr(item, "note", "") or ""),
                )
            )
    return rows
