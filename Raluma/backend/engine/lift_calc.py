"""Independent calculation engine for the LIFT system.

The formulas in this module are transcribed from the eight customer-provided
LIFT workbooks.  Nothing here imports or mutates the SLIDE calculation path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, pi

from engine.lift_config import LIFT_SPLIT_OPENING, lift_filling_text


GLASS_PANEL_KIND = "glass"
IGU_PANEL_KIND = "igu"


@dataclass
class LiftProfileItem:
    article: str
    name: str
    length_mm: float
    qty: int
    painted: bool
    image: str | None = None
    field_key: str = ""
    note: str = ""
    section_width_mm: float = 0
    section_height_mm: float = 0
    paint_mode: str = ""
    color_variants: list[str] = field(default_factory=list)
    paint_note: str = ""
    glass_positions: str = ""


@dataclass
class LiftPanelItem:
    panel: int
    role: str
    filling: str
    width_mm: float
    height_mm: float
    qty: int
    glued_width_mm: float
    glued_height_mm: float


@dataclass
class LiftHardwareItem:
    article: str
    name: str
    value: float
    unit: str
    image: str | None = None
    field_key: str = ""
    note: str = ""
    length_mm: float | None = None


@dataclass
class LiftTorqueResult:
    moving_panels: int
    largest_panel_width_mm: float
    largest_panel_height_mm: float
    equivalent_glass_thickness_mm: int
    moving_weight_kg: float
    torque_nm: float
    drive_count: int
    warning: str = ""


@dataclass
class LiftCalcResult:
    profiles: list[LiftProfileItem] = field(default_factory=list)
    panels: list[LiftPanelItem] = field(default_factory=list)
    hardware: list[LiftHardwareItem] = field(default_factory=list)
    fasteners: list[LiftHardwareItem] = field(default_factory=list)
    color_text: str = ""
    filling_text: str = ""
    filling_kind: str = GLASS_PANEL_KIND
    system_text: str = "LIFT"
    opening_text: str = ""
    cable_side: str = ""
    control_type: str = ""
    torque: LiftTorqueResult | None = None
    warnings: list[str] = field(default_factory=list)


PROFILE_NAMES = {
    "RL101-1": "Крышка верхнего короба",
    "RL101": "Верхний короб",
    "RL102": "Боковой профиль рамы",
    "RL103": "Боковой профиль рамы",
    "RL103-1": "Боковой профиль рамы",
    "RL103-2": "Боковой профиль рамы",
    "RL104": "Нижний профиль рамы",
    "RL105": "Вертикальный профиль панели",
    "RL112": "Профиль панели под стекло 8 мм",
    "RL113": "Профиль панели под стекло 8 мм",
    "RL114": "Профиль панели под стекло 8 мм",
    "RL115": "Профиль панели под стекло 8 мм",
    "RL1211": "Профиль панели под стеклопакет 20 мм",
    "RL122": "Профиль панели под стеклопакет 20 мм",
    "RL123": "Профиль панели под стеклопакет 20 мм",
    "RL1241": "Профиль панели под стеклопакет 20 мм",
}


def _is_igu(section: object) -> bool:
    filling_type = str(getattr(section, "lift_filling_type", "") or "").upper()
    return "20ММ" in filling_type


def _is_painted(section: object) -> bool:
    return "RAL" in str(getattr(section, "painting_type", "") or "").upper()


def _color_text(section: object) -> str:
    painting_type = str(getattr(section, "painting_type", "") or "").strip()
    if "АНОД" in painting_type.upper():
        return "Анодированный"
    return str(getattr(section, "ral_color", "") or painting_type).strip()


def _ceil_tenth(value: float) -> float:
    return ceil(float(value) * 10 - 1e-9) / 10


def _ceil_hundred(value: float) -> int:
    return int(ceil(float(value) / 100 - 1e-9) * 100)


def _panel_roles(panels: int, opening: str) -> list[str]:
    if panels == 4 and opening == LIFT_SPLIT_OPENING:
        return ["Глухая", "Подвижная", "Подвижная", "Глухая"]
    if opening == "Сдвиг вверх":
        return ["Глухая", *(["Подвижная"] * (panels - 1))]
    return [*(["Подвижная"] * (panels - 1)), "Глухая"]


def _special_panel_index(panels: int, opening: str) -> int:
    if panels == 4 and opening == LIFT_SPLIT_OPENING:
        return 1
    if opening == "Сдвиг вверх":
        return panels - 1
    return 0


def _build_panels(
    section: object,
    *,
    filling_kind: str,
) -> list[LiftPanelItem]:
    width = float(getattr(section, "width", 0) or 0)
    height = float(getattr(section, "height", 0) or 0)
    panels = int(getattr(section, "panels", 0) or 0)
    quantity = int(getattr(section, "quantity", 0) or 0)
    opening = str(getattr(section, "lift_opening_type", "") or "Сдвиг вниз")
    split = panels == 4 and opening == LIFT_SPLIT_OPENING
    is_igu = filling_kind == IGU_PANEL_KIND

    if panels == 2:
        base_height = (height - 213 - 11.5) / 2 - 1
        special_height = base_height + 11.5
        base_width = width - 135
        special_width = width - 133
        glue_width_add = 47
        glue_height_add = 46
    elif panels == 3:
        base_height = (height - 216 - 11.5) / 3 - 1
        special_height = base_height + 11.5
        base_width = width - (133 if is_igu else 135)
        special_width = width - 133
        glue_width_add = 47
        glue_height_add = 46
    elif panels == 4 and split:
        base_height = (height - 161 - 116 - 11) / 4 - 1
        special_height = base_height + 11
        base_width = width - 133
        special_width = base_width
        glue_width_add = 47
        glue_height_add = 47
    elif panels == 4:
        base_height = (height - 160 - 110 - 11) / 4 - (1 if is_igu else 0)
        special_height = base_height + 11
        base_width = width - (135 if is_igu else 134)
        special_width = base_width
        glue_width_add = 48
        glue_height_add = 46
    else:
        raise ValueError("Для ЛИФТ поддерживаются только 2, 3 или 4 панели")

    roles = _panel_roles(panels, opening)
    special_index = _special_panel_index(panels, opening)
    filling = lift_filling_text(section)
    result: list[LiftPanelItem] = []
    for index, role in enumerate(roles):
        panel_width = special_width if index == special_index else base_width
        panel_height = special_height if index == special_index else base_height
        result.append(
            LiftPanelItem(
                panel=index + 1,
                role=role,
                filling=filling,
                width_mm=panel_width,
                height_mm=panel_height,
                qty=quantity,
                glued_width_mm=panel_width + glue_width_add,
                glued_height_mm=panel_height + glue_height_add,
            )
        )
    return result


def _add_profile(
    result: LiftCalcResult,
    section: object,
    article: str,
    length_mm: float,
    qty: int,
    *,
    painted: bool | None = None,
    note: str = "",
) -> None:
    if qty <= 0:
        return
    if length_mm <= 0:
        result.warnings.append(
            f"{article}: расчетная длина {length_mm:g} мм недопустима"
        )
        return
    painted_value = _is_painted(section) if painted is None else painted
    normalized_length = round(float(length_mm), 3)
    for item in result.profiles:
        if (
            item.article == article
            and item.length_mm == normalized_length
            and item.painted == painted_value
            and item.note == note
        ):
            item.qty += qty
            return
    result.profiles.append(
        LiftProfileItem(
            article=article,
            name=PROFILE_NAMES.get(article, f"Профиль {article}"),
            length_mm=normalized_length,
            qty=qty,
            painted=painted_value,
            image=f"{article}.png",
            field_key=f"lift_profile_{len(result.profiles) + 1}",
            note=note,
            section_width_mm=float(getattr(section, "width", 0) or 0),
            section_height_mm=float(getattr(section, "height", 0) or 0),
            paint_mode=str(getattr(section, "painting_type", "") or ""),
        )
    )


def _add_common_profiles(result: LiftCalcResult, section: object) -> None:
    width = float(getattr(section, "width", 0) or 0)
    height = float(getattr(section, "height", 0) or 0)
    quantity = int(getattr(section, "quantity", 0) or 0)
    for article, length, multiplier in (
        ("RL101-1", width - 6, 3),
        ("RL101", width - 6, 1),
        ("RL102", height - 161, 1),
        ("RL103", height - 161, 1),
        ("RL103-1", height - 161, 2),
        ("RL103-2", height - 161, 1),
        ("RL104", width - 155, 1),
    ):
        _add_profile(result, section, article, length, multiplier * quantity)


def _add_two_panel_profiles(
    result: LiftCalcResult,
    section: object,
    *,
    is_igu: bool,
) -> None:
    width = float(getattr(section, "width", 0) or 0)
    height = float(getattr(section, "height", 0) or 0)
    quantity = int(getattr(section, "quantity", 0) or 0)
    special = max(result.panels, key=lambda panel: panel.height_mm)
    base = min(result.panels, key=lambda panel: panel.height_mm)

    if is_igu:
        rows = (
            ("RL123", width - 177, quantity),
            ("RL123", base.height_mm - 45, 2 * quantity),
            ("RL122", special.height_mm - 45, 2 * quantity),
            ("RL1241", width - 176, 2 * quantity),
            ("RL1211", width - 176, quantity),
        )
    else:
        rows = (
            ("RL113", base.width_mm - 45, quantity),
            ("RL113", base.height_mm - 46, 2 * quantity),
            ("RL112", special.height_mm - 46, 2 * quantity),
            ("RL115", base.width_mm - 45, quantity),
            ("RL115", special.width_mm - 45, quantity),
            ("RL114", special.width_mm - 45, quantity),
        )
    for article, length, qty in rows:
        _add_profile(result, section, article, length, qty)

    _add_profile(result, section, "RL105", height - 162, 2 * quantity)
    _add_profile(
        result,
        section,
        "RL105",
        height - base.glued_height_mm - 162,
        2 * quantity,
    )
    _add_profile(
        result,
        section,
        "RL104",
        width - 62,
        quantity,
        painted=False,
    )


def _add_three_panel_profiles(
    result: LiftCalcResult,
    section: object,
    *,
    is_igu: bool,
) -> None:
    width = float(getattr(section, "width", 0) or 0)
    height = float(getattr(section, "height", 0) or 0)
    quantity = int(getattr(section, "quantity", 0) or 0)
    special = max(result.panels, key=lambda panel: panel.height_mm)
    base = min(result.panels, key=lambda panel: panel.height_mm)

    if is_igu:
        rows = (
            ("RL123", special.width_mm - 45, quantity),
            ("RL123", base.height_mm - 46, 4 * quantity),
            ("RL122", special.height_mm - 46, 2 * quantity),
            ("RL1241", special.width_mm - 45, 4 * quantity),
            ("RL1211", special.width_mm - 45, quantity),
        )
    else:
        rows = (
            ("RL113", width - 177, quantity),
            ("RL113", base.height_mm - 45, 4 * quantity),
            ("RL112", special.height_mm - 45, 2 * quantity),
            ("RL115", width - 177, 3 * quantity),
            ("RL115", width - 174, quantity),
            ("RL114", width - 174, quantity),
        )
    for article, length, qty in rows:
        _add_profile(result, section, article, length, qty)

    _add_profile(
        result,
        section,
        "RL105",
        height - 2 * base.height_mm - 207,
        2 * quantity,
    )
    _add_profile(
        result,
        section,
        "RL105",
        height - base.height_mm - 207,
        2 * quantity,
    )
    _add_profile(
        result,
        section,
        "RL104",
        width - 62,
        quantity,
        painted=False,
    )


def _add_four_panel_profiles(
    result: LiftCalcResult,
    section: object,
    *,
    split: bool,
) -> None:
    width = float(getattr(section, "width", 0) or 0)
    quantity = int(getattr(section, "quantity", 0) or 0)
    special = max(result.panels, key=lambda panel: panel.height_mm)
    base = min(result.panels, key=lambda panel: panel.height_mm)
    horizontal_width = special.width_mm - 45 if split else width - 174

    if split:
        _add_profile(
            result,
            section,
            "RL103-2",
            special.width_mm + 25,
            quantity,
            note="Срезать под уплотнение 4-й створки",
        )
    for article, length, qty in (
        ("RL113", horizontal_width, 3 * quantity),
        (
            "RL113",
            (base.height_mm if split else special.height_mm) - 45,
            6 * quantity,
        ),
        (
            "RL112",
            (special.height_mm if split else base.height_mm) - 45,
            2 * quantity,
        ),
        ("RL115", horizontal_width, 4 * quantity),
        ("RL114", horizontal_width, quantity),
        # These two source workbooks contain fixed cut values rather than formulas.
        ("RL105", 1903, 2 * quantity),
        ("RL105", 2823, 2 * quantity),
    ):
        _add_profile(result, section, article, length, qty)
    _add_profile(
        result,
        section,
        "RL104",
        width - 62,
        quantity,
        painted=False,
    )


def _add_hardware(
    rows: list[LiftHardwareItem],
    article: str,
    name: str,
    value: float,
    unit: str = "шт",
    *,
    image: str | None = None,
    note: str = "",
    length_mm: float | None = None,
) -> None:
    if value <= 0:
        return
    rows.append(
        LiftHardwareItem(
            article=article,
            name=name,
            value=value,
            unit=unit,
            image=image or (f"{article}.png" if article.startswith("RL") else None),
            field_key=f"lift_item_{len(rows) + 1}",
            note=note,
            length_mm=length_mm,
        )
    )


def _calculate_torque(
    section: object,
    panels: list[LiftPanelItem],
    *,
    is_igu: bool,
) -> LiftTorqueResult:
    opening = str(getattr(section, "lift_opening_type", "") or "Сдвиг вниз")
    moving_panels = len(panels) - (2 if opening == LIFT_SPLIT_OPENING else 1)
    largest = max(panels, key=lambda panel: panel.glued_width_mm * panel.glued_height_mm)
    thickness = 12 if is_igu else 8
    area_m2 = largest.glued_width_mm * largest.glued_height_mm / 1_000_000
    weight = _ceil_tenth(area_m2 * moving_panels * thickness * 2.5 * 1.1)
    torque = _ceil_tenth(weight * 9.81 * 51 / 1000)
    drive_count = 1 if torque <= 80 else 2
    warning = ""
    if torque > 160:
        warning = "ВНИМАНИЕ! ПРЕВЫШЕНИЕ ДОПУСТИМОГО УСИЛИЯ ПРИВОДА!"
    return LiftTorqueResult(
        moving_panels=moving_panels,
        largest_panel_width_mm=largest.glued_width_mm,
        largest_panel_height_mm=largest.glued_height_mm,
        equivalent_glass_thickness_mm=thickness,
        moving_weight_kg=weight,
        torque_nm=torque,
        drive_count=drive_count,
        warning=warning,
    )


def _add_lift_hardware(
    result: LiftCalcResult,
    section: object,
    *,
    is_igu: bool,
) -> None:
    quantity = int(getattr(section, "quantity", 0) or 0)
    panels = int(getattr(section, "panels", 0) or 0)
    width = float(getattr(section, "width", 0) or 0)
    height = float(getattr(section, "height", 0) or 0)
    cable_side = str(getattr(section, "lift_cable_side", "") or "Справа")
    control = str(getattr(section, "lift_control_type", "") or "Пульт ДУ")
    torque = result.torque
    if torque is None:
        return
    drives = torque.drive_count

    _add_hardware(result.hardware, "RL201", "Угловой соединитель рамы", 2 * quantity)
    connector_article = "RL011" if is_igu else "RL001"
    connector_name = (
        "Угловой соединитель панели 20 мм"
        if is_igu
        else "Угловой соединитель панели 8 мм"
    )
    _add_hardware(
        result.hardware,
        connector_article,
        connector_name,
        4 * panels * quantity,
    )
    _add_hardware(
        result.hardware,
        "RL203",
        "Заглушка вала",
        (2 - drives) * quantity,
    )

    if cable_side == "Справа":
        _add_hardware(
            result.hardware,
            "RL20901",
            "Боковая крышка короба под подшипник левая",
            (2 - drives) * quantity,
        )
        _add_hardware(
            result.hardware,
            "RL20902",
            "Боковая крышка короба под мотор правая",
            quantity,
        )
    else:
        _add_hardware(
            result.hardware,
            "RL20903",
            "Боковая крышка короба под подшипник правая",
            (2 - drives) * quantity,
        )
        _add_hardware(
            result.hardware,
            "RL20904",
            "Боковая крышка короба под мотор левая",
            quantity,
        )

    _add_hardware(result.hardware, "RL206", "Шестерня под цепь", 2 * quantity)
    if control == "Пульт ДУ" and drives == 1:
        _add_hardware(
            result.hardware,
            "RL2085",
            "Привод с радиосвязью",
            quantity,
        )
    else:
        _add_hardware(
            result.hardware,
            "RL2095",
            "Привод фазный",
            drives * quantity,
        )
    _add_hardware(
        result.hardware,
        "RL2098",
        "Блок синхронизации приводов",
        quantity if drives == 2 else 0,
    )
    _add_hardware(
        result.hardware,
        "RL2096",
        "Комплект переходников для привода",
        drives * quantity,
    )
    _add_hardware(
        result.hardware,
        "RL2097",
        "Крепление для привода",
        drives * quantity,
    )

    chain_factor = {2: 1 / 2, 3: 2 / 3, 4: 3 / 4}[panels]
    chain_length = _ceil_hundred(chain_factor * height + 350 + pi * 110 / 2 + 200)
    _add_hardware(
        result.hardware,
        "RL210",
        "Цепь",
        2 * quantity,
        length_mm=chain_length,
        note=f"{chain_length:g} мм",
    )
    _add_hardware(
        result.hardware,
        "RL207",
        "Подшипник",
        (2 - drives) * quantity,
    )
    if control == "Пульт ДУ":
        _add_hardware(
            result.hardware,
            "RL2087",
            "Пульт 1-канальный",
            int(getattr(section, "lift_remote_1ch_qty", 0) or 0),
        )
        _add_hardware(
            result.hardware,
            "RL2088",
            "Пульт 6-канальный",
            int(getattr(section, "lift_remote_6ch_qty", 0) or 0),
        )
    else:
        _add_hardware(result.hardware, "RL2092", "Кнопка", quantity)

    _add_hardware(
        result.hardware,
        "RU004",
        "Щеточный уплотнитель 7×6 мм",
        ceil(width * panels * 2 * quantity / 1000),
        "м",
        image="RU004_RU006.png",
    )
    _add_hardware(
        result.hardware,
        "RU006",
        "Щеточный уплотнитель 7×12 мм",
        ceil(height * 12 * quantity / 1000),
        "м",
        image="RU004_RU006.png",
    )
    _add_hardware(result.hardware, "RL005", "Успокоитель цепи", 2 * quantity)
    _add_hardware(result.hardware, "RL002", "Заглушка панели", 2 * quantity)
    _add_hardware(result.hardware, "RU1039", "Наклейка RALUMA", quantity)
    _add_hardware(result.hardware, "RL150", "Инструкция LIFT", 1)

    for article, name, qty, image in (
        ("DIN7982", "Саморез 4,2×16 A2", 6 * quantity, None),
        ("DIN7982", "Саморез 4,2×80 A2", 2 * quantity, None),
        ("DIN7982", "Саморез 4,8×16 A2", 6 * quantity, None),
        ("DIN7504O", "Саморез со сверлом 4,8×16 A2", 6 * quantity, None),
        ("DIN7985", "Винт M4×20", 8 * quantity, None),
        ("DIN125", "Шайба ø4 A2", 8 * quantity, "lift_washer.png"),
        ("DIN985", "Гайка M4 A2", 8 * quantity, "lift_nut.png"),
        ("DIN965", "Винт M6×10", 4 * quantity if panels >= 3 else 0, None),
        (
            "DIN965",
            "Винт M6×20",
            (8 if panels < 3 else 4 * (panels - 1)) * quantity,
            None,
        ),
        (
            "DIN7504O",
            "Саморез со сверлом 3,9×13 A2",
            (ceil(height / 300) * 3 + 5) * quantity,
            None,
        ),
    ):
        _add_hardware(
            result.fasteners,
            article,
            name,
            qty,
            image=image,
        )


def calculate_lift(section: object) -> LiftCalcResult:
    """Calculate profiles, fillings and hardware for one LIFT section."""
    if str(getattr(section, "system", "") or "").upper() != "ЛИФТ":
        raise ValueError("calculate_lift принимает только секции ЛИФТ")

    panels = int(getattr(section, "panels", 0) or 0)
    opening = str(getattr(section, "lift_opening_type", "") or "Сдвиг вниз")
    split = panels == 4 and opening == LIFT_SPLIT_OPENING
    is_igu = _is_igu(section)
    result = LiftCalcResult(
        color_text=_color_text(section),
        filling_text=lift_filling_text(section),
        filling_kind=IGU_PANEL_KIND if is_igu else GLASS_PANEL_KIND,
        opening_text=opening,
        cable_side=str(getattr(section, "lift_cable_side", "") or "Справа"),
        control_type=str(getattr(section, "lift_control_type", "") or "Пульт ДУ"),
    )
    result.panels = _build_panels(section, filling_kind=result.filling_kind)
    _add_common_profiles(result, section)
    if panels == 2:
        _add_two_panel_profiles(result, section, is_igu=is_igu)
    elif panels == 3:
        _add_three_panel_profiles(result, section, is_igu=is_igu)
    elif panels == 4:
        _add_four_panel_profiles(result, section, split=split)
    else:
        raise ValueError("Для ЛИФТ поддерживаются только 2, 3 или 4 панели")

    result.torque = _calculate_torque(section, result.panels, is_igu=is_igu)
    if result.torque.warning:
        result.warnings.append(result.torque.warning)
    _add_lift_hardware(result, section, is_igu=is_igu)
    return result
