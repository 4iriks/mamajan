"""
Расчётный движок для системы СЛАЙД (1 ряд).
Входные данные: models.Section
Выходные данные: SlideCalcResult
"""

from dataclasses import dataclass, field
from math import ceil

from engine.profile_catalog import apply_profile_catalog


MAX_PROFILE_LENGTH_MM = 5950


@dataclass
class ProfileItem:
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
class GlassItem:
    position: str  # "Левое" | "Промежуточное" | "Правое"
    width_mm: float
    height_mm: float
    qty: int
    glass_profile_length: float = 0  # длина RS2021 для этого стекла


@dataclass
class GlassProfileGroup:
    qty: int = 0
    positions: list[str] = field(default_factory=list)


@dataclass
class HardwareSubItem:
    label: str  # "7×6мм" / "7×12мм"
    article: str
    value: float
    field_key: str = ""


@dataclass
class HardwareItem:
    article: str
    name: str
    value: float
    unit: str  # "шт" | "м"
    image: str | None = None
    field_key: str = ""
    sub_items: list[HardwareSubItem] | None = None


@dataclass
class ScrewItem:
    name: str
    article: str
    qty: int
    image: str | None = None
    note: str = ""


@dataclass
class SlideCalcResult:
    profiles: list[ProfileItem] = field(default_factory=list)
    glass: list[GlassItem] = field(default_factory=list)
    hardware: list[HardwareItem] = field(default_factory=list)
    screws: list[ScrewItem] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    color_text: str = ""
    glass_type: str = ""
    threshold_text: str = ""
    system_text: str = ""
    panel_rails: list[int] = field(default_factory=list)  # panel i → rail index


def _is_standard_threshold(threshold: str | None) -> bool:
    """True если порог стандартный (анод или окраш), False если накладной."""
    if not threshold:
        return True
    return "накладной" not in threshold.lower()


def _is_painted(painting_type: str | None) -> bool:
    """True если профиль красится (RAL стандарт или нестандарт)."""
    if not painting_type:
        return False
    pt = painting_type.lower()
    return "рал" in pt or "ral" in pt


def _format_color_text(
    painting_type: str | None, ral_color: str | None, threshold: str | None
) -> str:
    """Текст цвета для производственного листа без служебного стандарт/нестандарт."""
    if _is_painted(painting_type):
        ral = " ".join((ral_color or "").split())
        return f"RAL {ral}" if ral else "RAL"
    if "анод" in (threshold or "").lower():
        return "Анодированный"
    return painting_type or "—"


def _threshold_profile_name(rails: int, standard_threshold: bool) -> str:
    base = f"Порог {rails}-рельсовый"
    return base if standard_threshold else f"{base} накладной"


def _threshold_profile_image(article: str) -> str:
    if article in ("RS23231", "RS23251"):
        return f"{article}.svg"
    if article == "RS2325":
        return "RS1325.jpg"
    return f"{article}.jpg"


def _is_no_inter_glass_profile(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return not text or "без" in text


def _inter_glass_article(value: str | None) -> str:
    if _is_no_inter_glass_profile(value):
        return ""
    text = (value or "").lower()
    if "rs1006" in text:
        return "RS1006"
    if "rs1004" in text:
        return "RS1004"
    if "rs2061" in text:
        return "RS2061"
    return ""


def calculate_slide(section) -> SlideCalcResult:
    rows = int(getattr(section, "slide_rows", 1) or 1)
    if rows == 2:
        return _calculate_slide_2row(section)
    return _calculate_slide_1row(section)


def _get(section, name: str, default=None):
    return getattr(section, name, default)


def _is_deaf_panel(handle: str | None, lock: str | None, has_handle_bar: bool) -> bool:
    handle_text = (handle or "Без").lower()
    lock_text = lock or "Без"
    return (
        ("глух" in handle_text or handle_text == "без")
        and lock_text == "Без"
        and not has_handle_bar
    )


def _split_profile_lengths(length_mm: float) -> list[float]:
    normalized_length = max(0, int(ceil(length_mm)))
    if normalized_length <= MAX_PROFILE_LENGTH_MM:
        return [float(normalized_length)]

    part_count = ceil(normalized_length / MAX_PROFILE_LENGTH_MM)
    base_length = normalized_length // part_count
    remainder = normalized_length % part_count

    return [
        float(base_length + (1 if idx >= part_count - remainder else 0))
        for idx in range(part_count)
    ]


def _append_profile_with_splits(
    result: SlideCalcResult,
    *,
    article: str,
    name: str,
    length_mm: float,
    qty: int,
    painted: bool,
    image: str | None,
    field_key: str,
    note: str = "",
) -> None:
    lengths = _split_profile_lengths(length_mm)
    for idx, part_length in enumerate(lengths, start=1):
        part_note = note
        if len(lengths) > 1:
            part_label = f"часть {idx}/{len(lengths)}"
            part_note = f"{part_label}; {note}" if note else part_label

        result.profiles.append(
            ProfileItem(
                article=article,
                name=name,
                length_mm=part_length,
                qty=qty,
                painted=painted,
                image=image,
                field_key=field_key if len(lengths) == 1 else f"{field_key}_part_{idx}",
                note=part_note,
            )
        )


def _rs2081_screws_per_side(height_mm: float) -> int:
    return ceil(max(height_mm - 200, 0) / 300)


def _aggregate_glass_profiles(
    result: SlideCalcResult, *, painted: bool = False
) -> None:
    glass_profile_items: dict[float, GlassProfileGroup] = {}
    for glass in result.glass:
        if glass.qty <= 0:
            continue
        key = round(glass.glass_profile_length, 1)
        if key not in glass_profile_items:
            glass_profile_items[key] = GlassProfileGroup()
        group = glass_profile_items[key]
        group.qty += glass.qty
        if glass.position not in group.positions:
            group.positions.append(glass.position)

    for length, group in glass_profile_items.items():
        result.profiles.append(
            ProfileItem(
                article="RS2021",
                name="Стекольный профиль",
                length_mm=length,
                qty=group.qty,
                painted=painted,
                image="RS2021.jpg",
                field_key=f"glass_profile_{length}",
                note="прикрутить ролики и заглушки",
                glass_positions=", ".join(group.positions),
            )
        )


def _calculate_slide_2row(section) -> SlideCalcResult:
    """
    Расчёт для системы СЛАЙД стандарт 2 ряда.
    1 ряд оставлен отдельной веткой, чтобы не смешивать формулы.
    """
    result = SlideCalcResult()

    W = float(_get(section, "width", 2000) or 2000)
    H = float(_get(section, "height", 2400) or 2400)
    P = int(_get(section, "panels", 4) or 4)
    Q = int(_get(section, "quantity", 1) or 1)
    rails = int(_get(section, "rails", 3) or 3)
    threshold = _get(section, "threshold", "") or ""
    painting_type = _get(section, "painting_type", "") or ""
    ral_color = _get(section, "ral_color", "") or ""

    std = _is_standard_threshold(threshold)
    painted = _is_painted(painting_type)

    result.color_text = _format_color_text(painting_type, ral_color, threshold)

    result.glass_type = (
        _get(section, "glass_type", None) or "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    )
    result.threshold_text = threshold
    result.system_text = "SLIDE-стандарт 2 ряда"

    # Панели идут симметрично от левого края к центру и от центра к правому краю.
    half = max(P // 2, 1)
    active_rails = max(1, min(rails, half))
    unused_track = _get(section, "unused_track", None) or "Внешний"
    if active_rails >= rails:
        available = list(range(rails))
    elif unused_track == "Внешний":
        available = list(range(rails - active_rails, rails))
    else:
        available = list(range(active_rails))

    left_rails = available[:half]
    if len(left_rails) < half:
        left_rails.extend([available[-1]] * (half - len(left_rails)))
    result.panel_rails = left_rails + list(reversed(left_rails))[: P - half]

    wall_l = bool(_get(section, "profile_left_wall", False))
    wall_r = bool(_get(section, "profile_right_wall", False))
    lock_bar_l = bool(_get(section, "profile_left_lock_bar", False))
    lock_bar_r = bool(_get(section, "profile_right_lock_bar", False))
    p_bar_l = bool(_get(section, "profile_left_p_bar", False))
    p_bar_r = bool(_get(section, "profile_right_p_bar", False))
    handle_bar_l = bool(_get(section, "profile_left_handle_bar", False))
    handle_bar_r = bool(_get(section, "profile_right_handle_bar", False))
    bubble_l = bool(_get(section, "profile_left_bubble", False))
    bubble_r = bool(_get(section, "profile_right_bubble", False))

    ppl = 16 if wall_l else 0
    ppr = 16 if wall_r else 0

    if handle_bar_l and lock_bar_l:
        rpl = 59.5
    elif handle_bar_l and p_bar_l:
        rpl = 27
    else:
        rpl = 0

    if handle_bar_r and lock_bar_r:
        rpr = 59.5
    elif handle_bar_r and p_bar_r:
        rpr = 27
    else:
        rpr = 0

    pzl = 5 if bubble_l else 0
    pzr = 5 if bubble_r else 0
    krlr = 8 if handle_bar_l else 0
    krrr = 8 if handle_bar_r else 0
    krlp = 16 if (p_bar_l and bubble_l) else 0
    krrp = 16 if (p_bar_r and bubble_r) else 0

    a = int(_get(section, "handle_offset_left", 0) or 0)
    b = int(_get(section, "handle_offset_right", 0) or 0)

    handle_l = _get(section, "handle_left", None) or "Без"
    handle_r = _get(section, "handle_right", None) or "Без"
    lock_l = _get(section, "lock_left", None) or "Без"
    lock_r = _get(section, "lock_right", None) or "Без"

    left_is_deaf = _is_deaf_panel(handle_l, lock_l, handle_bar_l)
    right_is_deaf = _is_deaf_panel(handle_r, lock_r, handle_bar_r)

    center_handle = _get(section, "center_handle", None) or "Без ручки (глухие)"
    center_lock = _get(section, "center_lock", None) or "Без"
    center_is_deaf = center_handle == "Без ручки (глухие)" or center_handle == ""
    center_is_rs112 = center_handle == "Ручки-профиль RS112 (2шт)"
    center_offset = int(_get(section, "center_handle_offset", 0) or 0)
    center_rs112_count = 2 if center_is_rs112 else 0
    centr1 = 43.5 if center_is_rs112 else 0
    centr2 = 8 if center_is_rs112 else 0

    wall_count = (1 if wall_l else 0) + (1 if wall_r else 0)
    threshold_len = W - 16 * wall_count

    if std:
        inter_glass_len = H - 162
        lock_bar_len = H - 65
        handle_bar_len = H - 162
        p_bar_len = H - 65
        glass_H = H - 106
    else:
        inter_glass_len = H - 150
        lock_bar_len = H - 55
        handle_bar_len = H - 150
        p_bar_len = H - 55
        glass_H = H - 94

    inter_glass_type = _get(section, "inter_glass_profile", None) or "Без"

    middle_W = (
        W
        - 3
        - ppr
        - ppl
        - rpr
        - rpl
        - pzl
        - pzr
        - krlr
        - krlp
        - krrr
        - krrp
        - centr1
        - centr2
        - a
        - b
        - center_offset * 2
        + 9.5 * (P - 2)
    ) / P
    left_W = middle_W + a + krlr + krlp
    right_W = middle_W + b + krrr + krrp
    center_W = middle_W + center_offset + centr2

    result.glass.append(GlassItem("Левое", round(left_W, 1), round(glass_H, 1), Q))
    middle_qty = max(P - 4, 0) * Q
    if middle_qty > 0:
        result.glass.append(
            GlassItem(
                "Промежуточные", round(middle_W, 1), round(glass_H, 1), middle_qty
            )
        )
    result.glass.append(
        GlassItem("Центральные", round(center_W, 1), round(glass_H, 1), 2 * Q)
    )
    result.glass.append(GlassItem("Правое", round(right_W, 1), round(glass_H, 1), Q))

    threshold_articles = {
        (3, True): "RS2323",
        (3, False): "RS23231",
        (5, True): "RS2325",
        (5, False): "RS23251",
    }
    threshold_article = threshold_articles.get((rails, std), "RS2323")
    _append_profile_with_splits(
        result,
        article=threshold_article,
        name=_threshold_profile_name(rails, std),
        length_mm=threshold_len,
        qty=Q,
        painted=painted,
        image=_threshold_profile_image(threshold_article),
        field_key="threshold_length",
        note="рассверлить дренажные отверстия",
    )

    top_article = "RS1313" if rails == 3 else "RS1315"
    top_len = threshold_len
    _append_profile_with_splits(
        result,
        article=top_article,
        name="Верхний направляющий",
        length_mm=top_len,
        qty=Q,
        painted=painted,
        image=f"{top_article}.png",
        field_key="top_guide_length",
        note="вставить фетровое уплотнение",
    )

    if wall_l or wall_r:
        wall_article = "RS2333" if rails == 3 else "RS2335"
        result.profiles.append(
            ProfileItem(
                article=wall_article,
                name="Пристеночный профиль",
                length_mm=round(H, 1),
                qty=Q * wall_count,
                painted=painted,
                image=f"{wall_article}.jpg",
                field_key="wall_profile_length",
                note="рассверлить крепежные отверстия",
            )
        )

    ig_article = _inter_glass_article(inter_glass_type)
    if ig_article and P > 1:
        result.profiles.append(
            ProfileItem(
                article=ig_article,
                name="Межстекольный профиль (штапик)",
                length_mm=round(inter_glass_len, 1),
                qty=(P - 1) * Q,
                painted=(painted and ig_article == "RS2061"),
                image=f"{ig_article}.jpg",
                field_key="inter_glass_length",
                note="вставить фетровое уплотнение"
                if ig_article in ("RS2061", "RS1006")
                else "",
            )
        )

    lb_count = (1 if lock_bar_l else 0) + (1 if lock_bar_r else 0)
    if lb_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS2081",
                name="Боковой профиль-замок",
                length_mm=round(lock_bar_len, 1),
                qty=lb_count * Q,
                painted=painted,
                image="RS2081.jpg",
                field_key="lock_bar_length",
                note="рассверлить крепежные отверстия, фрезеровать паз в нижней части, врезать защёлку",
            )
        )

    side_rs112_count = (1 if handle_bar_l else 0) + (1 if handle_bar_r else 0)
    total_rs112_count = side_rs112_count + center_rs112_count
    if total_rs112_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS112",
                name="Профиль-ручка",
                length_mm=round(handle_bar_len, 1),
                qty=total_rs112_count * Q,
                painted=painted,
                image="RS112.jpg",
                field_key="handle_bar_length",
                note="вставить фетровое уплотнение",
            )
        )

    pb_count = (1 if p_bar_l else 0) + (1 if p_bar_r else 0)
    if pb_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS1082",
                name="Боковой П-профиль",
                length_mm=round(p_bar_len, 1),
                qty=pb_count * Q,
                painted=painted,
                image="RS1082.jpg",
                field_key="p_bar_length",
                note="",
            )
        )

    bub_count = (1 if bubble_l else 0) + (1 if bubble_r else 0)
    if bub_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS1002",
                name="Пузырьковый уплотнитель",
                length_mm=round(glass_H - 17, 1),
                qty=bub_count * Q,
                painted=False,
                image="RS1002.jpg",
                field_key="bubble_length",
                note="",
            )
        )

    if center_is_rs112:
        result.profiles.append(
            ProfileItem(
                article="RS1083",
                name="Двутавр 30×20×30",
                length_mm=round(handle_bar_len + 17, 1),
                qty=Q,
                painted=painted,
                image="RS1083.jpg",
                field_key="center_double_t_length",
                note="для центральных ручек-профилей RS112",
            )
        )
        result.profiles.append(
            ProfileItem(
                article="RU010",
                name="Магнитный уплотнитель",
                length_mm=round(handle_bar_len, 1),
                qty=2 * Q,
                painted=False,
                image=None,
                field_key="center_magnetic_seal_length",
                note="для центральных ручек-профилей RS112",
            )
        )

    latch_count = (
        (1 if _get(section, "floor_latches_left", False) else 0)
        + (1 if _get(section, "floor_latches_right", False) else 0)
        + (1 if _get(section, "center_floor_latches_left", False) else 0)
        + (1 if _get(section, "center_floor_latches_right", False) else 0)
    )
    if latch_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS205",
                name="Защёлка в пол",
                length_mm=0,
                qty=latch_count * Q,
                painted=False,
                image="RS205.jpg",
                field_key="floor_latches_qty",
                note="",
            )
        )

    for glass in result.glass:
        base_len = glass.width_mm
        if glass.position == "Левое":
            if handle_bar_l:
                base_len += 16
            if bubble_l and not left_is_deaf:
                base_len -= 3
        elif glass.position == "Правое":
            if handle_bar_r:
                base_len += 16
            if bubble_r and not right_is_deaf:
                base_len -= 3
        elif glass.position == "Центральные":
            if center_is_rs112:
                base_len += 16
            else:
                base_len -= 3
        elif glass.position == "Промежуточные":
            if ig_article:
                base_len -= 3
        glass.glass_profile_length = round(base_len, 1)

    _aggregate_glass_profiles(result, painted=painted)

    handle_bar_len_m = handle_bar_len / 1000
    top_len_m = top_len / 1000
    ru008_m = round(
        top_len_m * P * 2 * Q + (handle_bar_len_m + 0.03) * total_rs112_count * Q,
        3,
    )

    inter_glass_count_each = (P - 1) if P > 1 else 0
    inter_glass_cnt = inter_glass_count_each * Q
    ru007_m = 0.0
    if inter_glass_cnt > 0 and ig_article in ("RS2061", "RS1006"):
        ru007_m = round((inter_glass_len / 1000 + 0.03) * inter_glass_cnt, 3)

    result.hardware.append(
        HardwareItem(
            article="",
            name="Щёточный уплотнитель, м",
            value=0,
            unit="м",
            image="RU007.jpg",
            field_key="brush",
            sub_items=[
                HardwareSubItem("7×6мм", "RU008", ru008_m, "ru008"),
                HardwareSubItem("7×12мм", "RU007", ru007_m, "ru007"),
            ],
        )
    )

    damper_qty = max(P - 2, 0) * 2 * Q
    if damper_qty > 0:
        result.hardware.append(
            HardwareItem("RSD1", "Демпфер", damper_qty, "шт", "RSD1.jpg", "rsd1")
        )
        result.hardware.append(
            HardwareItem("RSD2", "Компенсатор", damper_qty, "шт", "RSD2.jpg", "rsd2")
        )

    if total_rs112_count > 0:
        result.hardware.append(
            HardwareItem(
                "RS1121",
                "Накладка на ручку-профиль",
                total_rs112_count * Q,
                "шт",
                "RS1121.png",
                "rs1121",
            )
        )

    lock3018 = 0
    lock3019 = 0
    lock3018_sides: list[str] = []
    lock3019_sides: list[str] = []
    for lock, side_name in [(lock_l, "слева"), (lock_r, "справа")]:
        if "1стор" in lock or "1-сторон" in lock.lower():
            lock3018 += 1
            lock3018_sides.append(side_name)
        elif "2стор" in lock or "2-сторон" in lock.lower() or "ключ" in lock.lower():
            lock3019 += 1
            lock3019_sides.append(side_name)

    if lock3018 > 0:
        result.hardware.append(
            HardwareItem(
                "RS3018",
                f"Замок-защёлка 1-стор ({' и '.join(lock3018_sides)})",
                lock3018 * Q,
                "шт",
                "RS3018.jpg",
                "rs3018",
            )
        )
    if lock3019 > 0:
        result.hardware.append(
            HardwareItem(
                "RS3019",
                f"Замок-защёлка 2-стор с ключом ({' и '.join(lock3019_sides)})",
                lock3019 * Q,
                "шт",
                "RS3019.jpg",
                "rs3019",
            )
        )

    rs122_qty = (lock3018 + lock3019) * Q
    if rs122_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS122", "Ответная планка замка", rs122_qty, "шт", "RS122.jpg", "rs122"
            )
        )
        result.hardware.append(
            HardwareItem(
                "RS3020", "Проставка замка", rs122_qty, "шт", "RS3020.jpg", "rs3020"
            )
        )

    if (
        "RS206" in center_lock
        or "защёлка" in center_lock.lower()
        or "защелка" in center_lock.lower()
    ):
        result.hardware.append(
            HardwareItem(
                "RS206", "Накидная защёлка на 2 створки", Q, "шт", "RS206.jpg", "rs206"
            )
        )

    if "стекло-стекло" in center_lock.lower() or "RS30301" in center_lock:
        result.hardware.append(
            HardwareItem(
                "RS30301", "Замок стекло-стекло", Q, "шт", "RS30301.jpg", "rs30301"
            )
        )

    ru005_qty = P * 2 * Q
    result.hardware.append(
        HardwareItem("RU005", "Ролик", ru005_qty, "шт", "RU005.jpg", "ru005")
    )

    rs3017_qty = 0
    rs3014_qty = 0
    for handle in [handle_l, handle_r]:
        if "стеклян" in handle.lower() or "RS3017" in handle:
            rs3017_qty += 1
        elif "кноб" in handle.lower() or "RS3014" in handle:
            rs3014_qty += 1
    if "стеклян" in center_handle.lower() or "RS3017" in center_handle:
        rs3017_qty += 2
    elif "кноб" in center_handle.lower() or "RS3014" in center_handle:
        rs3014_qty += 2

    if rs3017_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS3017",
                "Стеклянная ручка",
                rs3017_qty * Q,
                "шт",
                "RS3017.jpg",
                "rs3017",
            )
        )
    if rs3014_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS3014", "Ручка-кноб", rs3014_qty * Q, "шт", "RS3014.jpg", "rs3014"
            )
        )

    if inter_glass_cnt > 0 and ig_article in ("RS2061", "RS1006"):
        plug_qty_per_side = max(0, (P // 2 - 1) * Q)
        if plug_qty_per_side > 0:
            result.hardware.append(
                HardwareItem(
                    "RS107L",
                    "Заглушка межстекольного (лев)",
                    plug_qty_per_side,
                    "шт",
                    "RS107L.jpg",
                    "rs107l",
                )
            )
            result.hardware.append(
                HardwareItem(
                    "RS107R",
                    "Заглушка межстекольного (прав)",
                    plug_qty_per_side,
                    "шт",
                    "RS107R.jpg",
                    "rs107r",
                )
            )

    middle_panels = max(P - 4, 0)
    rs105_qty = (middle_panels + 1) * 2 * Q

    if total_rs112_count > 0:
        rs106_qty = total_rs112_count * Q
    else:
        non_deaf = (0 if left_is_deaf else 1) + (0 if right_is_deaf else 1)
        if not center_is_deaf:
            non_deaf += 2
        rs106_qty = non_deaf * Q

    if rs105_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS105",
                "Заглушка стекольного (внутр)",
                rs105_qty,
                "шт",
                "RS105.jpg",
                "rs105",
            )
        )
    if rs106_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS106",
                "Заглушка стекольного (крайн)",
                rs106_qty,
                "шт",
                "RS106.jpg",
                "rs106",
            )
        )

    rs107_qty = rs105_qty + rs106_qty
    if rs107_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS107", "Заглушка запорная", rs107_qty, "шт", "RS107.jpg", "rs107"
            )
        )

    if not center_is_rs112:
        result.hardware.append(
            HardwareItem(
                "RS3110",
                "h-уплотнитель центрального стыка",
                Q,
                "шт",
                "RS3110.jpg",
                "rs3110",
            )
        )

    result.screws.append(
        ScrewItem(
            "Саморез 4,8×19 A2 (DIN7982)",
            "4,8×19 A2",
            (rs105_qty + rs106_qty) * 2,
            "DIN7982.png",
            note="Прикрутить заглушки RS105, RS106",
        )
    )

    screw3913m = ru005_qty * 2 + _rs2081_screws_per_side(H) * lb_count * Q
    result.screws.append(
        ScrewItem(
            "Саморез 3,9×13 A2 (DIN7504M)",
            "3,9×13 A2 DIN7504M",
            screw3913m,
            "DIN7504M.png",
            note="Прикрутить ролики, RS2081 к направляющим",
        )
    )

    screw4838_map = {(3, True): 8, (5, True): 12, (3, False): 4, (5, False): 6}
    result.screws.append(
        ScrewItem(
            "Саморез 4,8×38 A2 (DIN7982)",
            "4,8×38 A2",
            screw4838_map.get((rails, std), 8),
            "DIN7982.png",
            note="Прикрутить верхний профиль к порогу",
        )
    )

    screw3913o = pb_count * Q * 7
    if screw3913o > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 3,9×13 A2 (DIN7504О)",
                "3,9×13 A2 DIN7504O",
                screw3913o,
                "DIN7504O.png",
                note="Прикрутить швеллер RM701 к RS1333/1335",
            )
        )

    deaf_count = (
        (1 if left_is_deaf else 0)
        + (1 if right_is_deaf else 0)
        + (2 if center_is_deaf else 0)
    )
    screw5425 = deaf_count * Q
    if screw5425 > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 5,4×25 A2 (DIN912SW)", "5,4×25 A2", screw5425, "DIN912SW.png"
            )
        )

    screw3513 = rs122_qty * 2
    if screw3513 > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 3,5×13 A2 (DIN7982)",
                "3,5×13 A2",
                screw3513,
                "DIN7982.png",
                note="Прикрутить ответные планки RS122",
            )
        )

    result.screws.append(ScrewItem("Наклейка RALUMA", "RU1039", Q))
    result.screws.append(ScrewItem("Инструкция СЛАЙД", "RS150", Q))

    if ig_article in ("RS2061", "RS1006") and P > 1:
        result.checklist.append(f"Вставить фетровое уплотнение 7×12 в {ig_article}")
    result.checklist.append(f"Вставить фетровое уплотнение 7×6 в {top_article}")
    if total_rs112_count > 0:
        result.checklist.append("Вставить фетровое уплотнение 7×6 в RS112")
    result.checklist.append("Установить ролики")
    if (
        lock3018 > 0
        or lock3019 > 0
        or "RS206" in center_lock
        or "RS30301" in center_lock
    ):
        result.checklist.append("Сделать фрезеровку под защелки")
    if lb_count > 0:
        result.checklist.append("Отфрезеровать пазы в RS2081")
    if center_is_rs112:
        result.checklist.append("Установить RS1083 и магнитный уплотнитель RU010")
    result.checklist.append("Рассверлить крепежные отверстия")
    result.checklist.append("Установить заглушки")
    result.checklist.append("Поклеить стекла")
    result.checklist.append("Приклеить наклейку РАЛЮМА (верх, право)")

    for profile in result.profiles:
        apply_profile_catalog(profile)

    return result


def _calculate_slide_1row(section) -> SlideCalcResult:
    """
    Основной расчёт для системы СЛАЙД 1 ряд.
    section — объект models.Section или любой объект с теми же полями.
    """
    result = SlideCalcResult()

    W = float(section.width or 2000)
    H = float(section.height or 2400)
    P = int(section.panels or 3)
    Q = int(section.quantity or 1)
    rails = int(section.rails or 3)
    threshold = section.threshold or ""
    painting_type = section.painting_type or ""
    ral_color = section.ral_color or ""

    std = _is_standard_threshold(threshold)
    painted = _is_painted(painting_type)

    # ── Текстовые описания ────────────────────────────────────────────────────

    result.color_text = _format_color_text(painting_type, ral_color, threshold)

    result.glass_type = section.glass_type or "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    result.threshold_text = threshold
    result.system_text = "SLIDE-стандарт 1 ряд"

    # ── Маппинг панелей → рельсы (для схемы вид сверху) ──────────────────────
    first_right = (section.first_panel_inside or "Справа") == "Справа"
    unused_track = section.unused_track or ("Внутренний" if P < rails else "")
    unused_count = max(0, rails - P)
    if unused_track == "Внешний":
        available = list(range(unused_count, rails))
    elif unused_track == "Внутренний":
        available = list(range(0, rails - unused_count))
    else:
        available = list(range(rails))
    for pi in range(P):
        ri_idx = (len(available) - 1 - pi) if not first_right else pi
        ri_idx = max(0, min(ri_idx, len(available) - 1))
        result.panel_rails.append(available[ri_idx])

    # ── Профильные переменные (для расчёта стёкол) ────────────────────────────

    wall_l = bool(section.profile_left_wall)
    wall_r = bool(section.profile_right_wall)
    lock_bar_l = bool(section.profile_left_lock_bar)
    lock_bar_r = bool(section.profile_right_lock_bar)
    p_bar_l = bool(section.profile_left_p_bar)
    p_bar_r = bool(section.profile_right_p_bar)
    handle_bar_l = bool(section.profile_left_handle_bar)
    handle_bar_r = bool(section.profile_right_handle_bar)
    bubble_l = bool(section.profile_left_bubble)
    bubble_r = bool(section.profile_right_bubble)

    ppl = 16 if wall_l else 0
    ppr = 16 if wall_r else 0

    if handle_bar_l and lock_bar_l:
        rpl = 59.5
    elif handle_bar_l and p_bar_l:
        rpl = 27
    else:
        rpl = 0

    if handle_bar_r and lock_bar_r:
        rpr = 59.5
    elif handle_bar_r and p_bar_r:
        rpr = 27
    else:
        rpr = 0

    pzl = 5 if bubble_l else 0
    pzr = 5 if bubble_r else 0
    krlr = 8 if handle_bar_l else 0
    krrr = 8 if handle_bar_r else 0
    krlp = 16 if (p_bar_l and bubble_l) else 0
    krrp = 16 if (p_bar_r and bubble_r) else 0

    a = int(section.handle_offset_left or 0)
    b = int(section.handle_offset_right or 0)

    # ── Определяем глухие панели ─────────────────────────────────────────────

    handle_l = section.handle_left or "Без"
    handle_r = section.handle_right or "Без"
    lock_l = section.lock_left or "Без"
    lock_r = section.lock_right or "Без"

    left_is_deaf = (
        (handle_l.lower() == "глухая" or handle_l == "Без")
        and lock_l == "Без"
        and not handle_bar_l
    )
    right_is_deaf = (
        (handle_r.lower() == "глухая" or handle_r == "Без")
        and lock_r == "Без"
        and not handle_bar_r
    )

    # ── Длины профилей ────────────────────────────────────────────────────────

    wall_count = (1 if wall_l else 0) + (1 if wall_r else 0)
    threshold_len = W - 16 * wall_count

    if std:
        inter_glass_len = H - 162
        lock_bar_len = H - 65
        handle_bar_len = H - 162
        p_bar_len = H - 65
        glass_H = H - 106
    else:
        inter_glass_len = H - 150
        lock_bar_len = H - 55
        handle_bar_len = H - 150
        p_bar_len = H - 55
        glass_H = H - 94

    # ── Расчёт стёкол ─────────────────────────────────────────────────────────

    inter_glass_type = section.inter_glass_profile or "Без"

    if P == 1:
        # Особый случай: одна глухая панель
        middle_W = W - ppr - ppl - pzl - pzr
        result.glass.append(
            GlassItem("Промежуточное", round(middle_W, 1), round(glass_H, 1), Q)
        )
    else:
        middle_W = (
            W
            - ppr
            - ppl
            - rpr
            - rpl
            - pzl
            - pzr
            - krlr
            - krlp
            - krrr
            - krrp
            - a
            - b
            + 9.5 * (P - 1)
        ) / P
        left_W = middle_W + a + krlr + krlp
        right_W = middle_W + b + krrr + krrp

        if round(left_W, 1) == round(right_W, 1):
            result.glass.append(
                GlassItem("Крайние", round(left_W, 1), round(glass_H, 1), 2 * Q)
            )
            result.glass.append(
                GlassItem(
                    "Промежуточные",
                    round(middle_W, 1),
                    round(glass_H, 1),
                    (P - 2) * Q if P > 2 else 0,
                )
            )
        else:
            result.glass.append(
                GlassItem("Левое", round(left_W, 1), round(glass_H, 1), Q)
            )
            result.glass.append(
                GlassItem(
                    "Промежуточные",
                    round(middle_W, 1),
                    round(glass_H, 1),
                    (P - 2) * Q if P > 2 else 0,
                )
            )
            result.glass.append(
                GlassItem("Правое", round(right_W, 1), round(glass_H, 1), Q)
            )

    # ── Профили ───────────────────────────────────────────────────────────────

    # Порог
    threshold_articles = {
        (3, True): "RS2323",
        (3, False): "RS23231",
        (5, True): "RS2325",
        (5, False): "RS23251",
    }
    threshold_article = threshold_articles.get((rails, std), "RS2323")
    _append_profile_with_splits(
        result,
        article=threshold_article,
        name=_threshold_profile_name(rails, std),
        length_mm=threshold_len,
        qty=Q,
        painted=painted,
        image=_threshold_profile_image(threshold_article),
        field_key="threshold_length",
        note="рассверлить дренажные отверстия",
    )

    # Верхний направляющий
    top_article = "RS1313" if rails == 3 else "RS1315"
    top_len = threshold_len
    _append_profile_with_splits(
        result,
        article=top_article,
        name="Верхний направляющий",
        length_mm=top_len,
        qty=Q,
        painted=painted,
        image=f"{top_article}.png",
        field_key="top_guide_length",
        note="вставить фетровое уплотнение",
    )

    # Пристеночный
    if wall_l or wall_r:
        wall_article = "RS2333" if rails == 3 else "RS2335"
        wall_qty = Q * wall_count
        result.profiles.append(
            ProfileItem(
                article=wall_article,
                name="Пристеночный профиль",
                length_mm=round(H, 1),
                qty=wall_qty,
                painted=painted,
                image=f"{wall_article}.jpg",
                field_key="wall_profile_length",
                note="рассверлить крепежные отверстия",
            )
        )

    # Межстекольный
    ig_article = _inter_glass_article(inter_glass_type)
    if ig_article and P > 1:
        ig_note = (
            "вставить фетровое уплотнение" if ig_article in ("RS2061", "RS1006") else ""
        )
        result.profiles.append(
            ProfileItem(
                article=ig_article,
                name="Межстекольный профиль (штапик)",
                length_mm=round(inter_glass_len, 1),
                qty=(P - 1) * Q,
                painted=(painted and ig_article == "RS2061"),
                image=f"{ig_article}.jpg",
                field_key="inter_glass_length",
                note=ig_note,
            )
        )

    # Боковой профиль-замок RS2081
    lb_count = (1 if lock_bar_l else 0) + (1 if lock_bar_r else 0)
    if lb_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS2081",
                name="Боковой профиль-замок",
                length_mm=round(lock_bar_len, 1),
                qty=lb_count * Q,
                painted=painted,
                image="RS2081.jpg",
                field_key="lock_bar_length",
                note="рассверлить крепежные отверстия, фрезеровать паз в нижней части, врезать защёлку",
            )
        )

    # Ручка-профиль RS112
    hb_count = (1 if handle_bar_l else 0) + (1 if handle_bar_r else 0)
    if hb_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS112",
                name="Профиль-ручка",
                length_mm=round(handle_bar_len, 1),
                qty=hb_count * Q,
                painted=painted,
                image="RS112.jpg",
                field_key="handle_bar_length",
                note="вставить фетровое уплотнение",
            )
        )

    # П-профиль RS1082
    pb_count = (1 if p_bar_l else 0) + (1 if p_bar_r else 0)
    if pb_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS1082",
                name="Боковой П-профиль",
                length_mm=round(p_bar_len, 1),
                qty=pb_count * Q,
                painted=painted,
                image="RS1082.jpg",
                field_key="p_bar_length",
                note="",
            )
        )

    # Пузырьковый RS1002
    bub_count = (1 if bubble_l else 0) + (1 if bubble_r else 0)
    if bub_count > 0:
        bub_len = glass_H - 17
        result.profiles.append(
            ProfileItem(
                article="RS1002",
                name="Пузырьковый уплотнитель",
                length_mm=round(bub_len, 1),
                qty=bub_count * Q,
                painted=False,
                image="RS1002.jpg",
                field_key="bubble_length",
                note="",
            )
        )

    # Защёлка в пол RS205
    latch_count = (1 if section.floor_latches_left else 0) + (
        1 if section.floor_latches_right else 0
    )
    if latch_count > 0:
        result.profiles.append(
            ProfileItem(
                article="RS205",
                name="Защёлка в пол",
                length_mm=0,
                qty=latch_count * Q,
                painted=False,
                image="RS205.jpg",
                field_key="floor_latches_qty",
                note="",
            )
        )

    # Стекольный профиль RS2021
    for g in result.glass:
        base_len = g.width_mm
        if g.position == "Левое":
            if handle_bar_l:
                base_len += 16
            if bubble_l and not left_is_deaf:
                base_len -= 3
        elif g.position == "Правое":
            if handle_bar_r:
                base_len += 16
            if bubble_r and not right_is_deaf:
                base_len -= 3
        elif g.position == "Крайние":
            if handle_bar_l:
                base_len += 16
            if bubble_l and not left_is_deaf:
                base_len -= 3
        elif g.position == "Промежуточные" or g.position == "Промежуточное":
            if ig_article:
                base_len -= 3
        g.glass_profile_length = round(base_len, 1)

    _aggregate_glass_profiles(result, painted=painted)

    # ── Фурнитура ─────────────────────────────────────────────────────────────

    # Щёточный уплотнитель (RU008 + RU007 в одной ячейке)
    handle_bar_len_m = handle_bar_len / 1000
    top_len_m = top_len / 1000
    ru008_m = round(top_len_m * P * 2 * Q + (handle_bar_len_m + 0.03) * hb_count * Q, 3)

    inter_glass_cnt = (P - 1) * Q if P > 1 else 0
    ru007_m = 0.0
    if inter_glass_cnt > 0 and ig_article in ("RS2061", "RS1006"):
        ig_len_m = inter_glass_len / 1000
        ru007_m = round((ig_len_m + 0.03) * inter_glass_cnt, 3)

    result.hardware.append(
        HardwareItem(
            article="",
            name="Щёточный уплотнитель, м",
            value=0,
            unit="м",
            image="RU007.jpg",
            field_key="brush",
            sub_items=[
                HardwareSubItem("7×6мм", "RU008", ru008_m, "ru008"),
                HardwareSubItem("7×12мм", "RU007", ru007_m, "ru007"),
            ],
        )
    )

    # RSD1 демпфер + RSD2 компенсатор
    damper_qty = (P - 1) * 2 * Q if P > 1 else 0
    if damper_qty > 0:
        result.hardware.append(
            HardwareItem("RSD1", "Демпфер", damper_qty, "шт", "RSD1.jpg", "rsd1")
        )
        result.hardware.append(
            HardwareItem("RSD2", "Компенсатор", damper_qty, "шт", "RSD2.jpg", "rsd2")
        )

    # RS1121 накладка на ручку-профиль
    if hb_count > 0:
        result.hardware.append(
            HardwareItem(
                "RS1121",
                "Накладка на ручку-профиль",
                hb_count * Q,
                "шт",
                "RS1121.png",
                "rs1121",
            )
        )

    # RS3018 защёлка 1-сторонняя
    lock3018 = 0
    lock3019 = 0
    lock3018_sides: list[str] = []
    lock3019_sides: list[str] = []
    for lk, side_name in [(lock_l, "слева"), (lock_r, "справа")]:
        if "1стор" in lk or "1-сторон" in lk.lower():
            lock3018 += 1
            lock3018_sides.append(side_name)
        elif "2стор" in lk or "2-сторон" in lk.lower() or "ключ" in lk.lower():
            lock3019 += 1
            lock3019_sides.append(side_name)

    def _side_comment(sides: list[str]) -> str:
        return " и ".join(sides) if sides else ""

    if lock3018 > 0:
        side_text = _side_comment(lock3018_sides)
        result.hardware.append(
            HardwareItem(
                "RS3018",
                f"Замок-защёлка 1-стор ({side_text})",
                lock3018 * Q,
                "шт",
                "RS3018.jpg",
                "rs3018",
            )
        )
    if lock3019 > 0:
        side_text = _side_comment(lock3019_sides)
        result.hardware.append(
            HardwareItem(
                "RS3019",
                f"Замок-защёлка 2-стор с ключом ({side_text})",
                lock3019 * Q,
                "шт",
                "RS3019.jpg",
                "rs3019",
            )
        )

    rs122_qty = (lock3018 + lock3019) * Q
    rs3020_qty = rs122_qty
    if rs122_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS122", "Ответная планка замка", rs122_qty, "шт", "RS122.jpg", "rs122"
            )
        )
        result.hardware.append(
            HardwareItem(
                "RS3020", "Проставка замка", rs3020_qty, "шт", "RS3020.jpg", "rs3020"
            )
        )

    # RU005 ролики
    ru005_qty = P * 2 * Q
    result.hardware.append(
        HardwareItem("RU005", "Ролик", ru005_qty, "шт", "RU005.jpg", "ru005")
    )

    # Стеклянные ручки RS3017 и кнобы RS3014
    rs3017_qty = 0
    rs3014_qty = 0
    for h in [handle_l, handle_r]:
        if "стеклян" in h.lower() or "RS3017" in h:
            rs3017_qty += 1
        elif "кноб" in h.lower() or "RS3014" in h:
            rs3014_qty += 1

    if rs3017_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS3017",
                "Стеклянная ручка",
                rs3017_qty * Q,
                "шт",
                "RS3017.jpg",
                "rs3017",
            )
        )
    if rs3014_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS3014", "Ручка-кноб", rs3014_qty * Q, "шт", "RS3014.jpg", "rs3014"
            )
        )

    # RS107R/L заглушка межстекольного
    first_panel = section.first_panel_inside or "Справа"
    if inter_glass_cnt > 0 and ig_article in ("RS2061", "RS1006"):
        if first_panel == "Справа":
            # 1-я панель справа → сдвиг влево → RS107L
            result.hardware.append(
                HardwareItem(
                    "RS107L",
                    "Заглушка межстекольного (лев)",
                    inter_glass_cnt,
                    "шт",
                    "RS107L.jpg",
                    "rs107l",
                )
            )
        else:
            # 1-я панель слева → сдвиг вправо → RS107R
            result.hardware.append(
                HardwareItem(
                    "RS107R",
                    "Заглушка межстекольного (прав)",
                    inter_glass_cnt,
                    "шт",
                    "RS107R.jpg",
                    "rs107r",
                )
            )

    # RS105 заглушка стекольного
    rs105_qty = (P - 1) * 2 * Q if P > 1 else 0

    # RS106 — на крайние панели если они не глухие
    rs106_qty = ((0 if left_is_deaf else 1) + (0 if right_is_deaf else 1)) * Q

    if rs105_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS105",
                "Заглушка стекольного (внутр)",
                rs105_qty,
                "шт",
                "RS105.jpg",
                "rs105",
            )
        )
    if rs106_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS106",
                "Заглушка стекольного (крайн)",
                rs106_qty,
                "шт",
                "RS106.jpg",
                "rs106",
            )
        )

    # RS107 заглушка запорная
    rs107_qty = rs105_qty + rs106_qty
    if rs107_qty > 0:
        result.hardware.append(
            HardwareItem(
                "RS107", "Заглушка запорная", rs107_qty, "шт", "RS107.jpg", "rs107"
            )
        )

    # ── Саморезы ─────────────────────────────────────────────────────────────

    # 4,8×19 A2
    screw4819 = (rs105_qty + rs106_qty) * 2
    result.screws.append(
        ScrewItem(
            "Саморез 4,8×19 A2 (DIN7982)",
            "4,8×19 A2",
            screw4819,
            "DIN7982.png",
            note="Прикрутить заглушки RS105, RS106",
        )
    )

    # 3,9×13 A2 (DIN7504M) — для роликов + профиля-замка RS2081
    screw3913m = ru005_qty * 2 + _rs2081_screws_per_side(H) * lb_count * Q
    result.screws.append(
        ScrewItem(
            "Саморез 3,9×13 A2 (DIN7504M)",
            "3,9×13 A2 DIN7504M",
            screw3913m,
            "DIN7504M.png",
            note="Прикрутить ролики, RS2081 к RS2323/2335",
        )
    )

    # 4,8×38 A2
    screw4838_map = {(3, True): 8, (5, True): 12, (3, False): 4, (5, False): 6}
    screw4838 = screw4838_map.get((rails, std), 8)
    result.screws.append(
        ScrewItem(
            "Саморез 4,8×38 A2 (DIN7982)",
            "4,8×38 A2",
            screw4838,
            "DIN7982.png",
            note="Прикрутить RS1333/1335 к RS1313/1315 и порогу",
        )
    )

    # 3,9×13 A2 (DIN7504О) — для П-профиля RS1082
    screw3913o = pb_count * Q * 7
    if screw3913o > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 3,9×13 A2 (DIN7504О)",
                "3,9×13 A2 DIN7504O",
                screw3913o,
                "DIN7504O.png",
                note="Прикрутить швеллер RM701 к RS1333/1335",
            )
        )

    # 5,4×25 A2 — глухие панели
    deaf_count = (1 if left_is_deaf else 0) + (1 if right_is_deaf else 0)
    screw5425 = deaf_count * Q
    if screw5425 > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 5,4×25 A2 (DIN912SW)", "5,4×25 A2", screw5425, "DIN912SW.png"
            )
        )

    # 3,5×13 A2 — ответная планка
    screw3513 = rs122_qty * 2
    if screw3513 > 0:
        result.screws.append(
            ScrewItem(
                "Саморез 3,5×13 A2 (DIN7982)",
                "3,5×13 A2",
                screw3513,
                "DIN7982.png",
                note="Прикрутить ответные планки RS122",
            )
        )

    # Наклейка и инструкция
    result.screws.append(ScrewItem("Наклейка RALUMA", "RU1039", Q))
    result.screws.append(ScrewItem("Инструкция СЛАЙД", "RS150", Q))

    # ── Чеклист ───────────────────────────────────────────────────────────────

    if ig_article in ("RS2061", "RS1006") and P > 1:
        result.checklist.append(f"Вставить фетровое уплотнение 7×12 в {ig_article}")

    result.checklist.append(f"Вставить фетровое уплотнение 7×6 в {top_article}")

    if hb_count > 0:
        result.checklist.append("Вставить фетровое уплотнение 7×6 в RS112")

    result.checklist.append("Установить ролики")

    if lock3018 > 0 or lock3019 > 0:
        result.checklist.append("Сделать фрезеровку под защелки")

    if lb_count > 0:
        result.checklist.append("Отфрезеровать пазы в RS2081")

    result.checklist.append("Рассверлить крепежные отверстия")

    result.checklist.append("Установить заглушки")
    result.checklist.append("Поклеить стекла")
    result.checklist.append("Приклеить наклейку РАЛЮМА (верх, право)")

    for profile in result.profiles:
        apply_profile_catalog(profile)

    return result
