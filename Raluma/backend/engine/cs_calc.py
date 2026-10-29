"""CS geometry according to the customer's T40T specification, September 2026.

All distances are millimetres. Contours retain precision; glass cutting sizes
are rounded down to whole millimetres before documents and pricing consume them.
No commercial price is inferred from incomplete catalogue costs.
"""

from __future__ import annotations

from collections import Counter
from math import ceil, floor, hypot, isfinite
from types import SimpleNamespace
from typing import Any

from shapely.geometry import LineString, Polygon, box
from engine.glass_types import normalize_slide_glass_type
from engine.cs_rounding import triangle_rounding
from engine.cs_cover_cutting import (
    cover_cuts,
    pack_cuts,
    INDIVIDUAL_COVER_NOTE,
    STOCK_MM,
)

EPS = 1e-7
GAP = 3.0
GLASS_TYPES = (
    "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
    "10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ",
    "10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ",
    "10ММ ЗАКАЛЕННОЕ МАТОВОЕ",
    "10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ",
)


class CsCalculationError(ValueError):
    pass


def cs_result_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: cs_result_namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return [cs_result_namespace(item) for item in value]
    return value


def _number(value: Any, fallback: float = 0) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError):
        return fallback
    if not isfinite(result):
        raise CsCalculationError("Размеры и координаты должны быть конечными числами")
    return result


def _signed_area(points):
    return (
        sum(
            p["x"] * points[(i + 1) % len(points)]["y"]
            - points[(i + 1) % len(points)]["x"] * p["y"]
            for i, p in enumerate(points)
        )
        / 2
    )


def _polygon(points):
    if not 3 <= len(points) <= 128:
        raise CsCalculationError("Контур должен содержать от 3 до 128 вершин")
    for index, point in enumerate(points):
        end = points[(index + 1) % len(points)]
        if hypot(end["x"] - point["x"], end["y"] - point["y"]) <= EPS:
            raise CsCalculationError("Соседние углы не должны совпадать")
    polygon = Polygon([(p["x"], p["y"]) for p in points])
    if not polygon.is_valid:
        raise CsCalculationError("Контур не должен пересекать сам себя")
    if polygon.area <= EPS:
        raise CsCalculationError("Площадь контура должна быть больше нуля")
    return polygon


def _clip_convex_inset(points, lines, orientation):
    """Clip against all inward half-planes; short sides may disappear."""
    result = [dict(point) for point in points]
    for x, y, dx, dy in lines:
        length = hypot(dx, dy)

        def signed(point):
            return (
                orientation * (dx * (point["y"] - y) - dy * (point["x"] - x)) / length
            )

        clipped = []
        for index, start in enumerate(result):
            end = result[(index + 1) % len(result)]
            a, b = signed(start), signed(end)
            if a >= -EPS:
                clipped.append(start)
            if (a >= -EPS) != (b >= -EPS):
                factor = a / (a - b)
                clipped.append(
                    {
                        "x": start["x"] + factor * (end["x"] - start["x"]),
                        "y": start["y"] + factor * (end["y"] - start["y"]),
                    }
                )
        result = []
        for point in clipped:
            if (
                not result
                or hypot(point["x"] - result[-1]["x"], point["y"] - result[-1]["y"])
                > EPS
            ):
                result.append(point)
        if (
            len(result) > 1
            and hypot(
                result[0]["x"] - result[-1]["x"], result[0]["y"] - result[-1]["y"]
            )
            <= EPS
        ):
            result.pop()
        if len(result) < 3:
            raise CsCalculationError("Вычеты не оставляют места для стекла")
    _polygon(result)
    return result


def offset_contour(points, distances):
    """Intersect adjacent offset lines; retain vertex/edge numbering and winding."""
    original = _polygon(points)
    orientation = 1 if _signed_area(points) > 0 else -1
    lines = []
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        dx, dy = end["x"] - start["x"], end["y"] - start["y"]
        length = hypot(dx, dy)
        nx, ny = -dy / length * orientation, dx / length * orientation
        distance = distances[index]
        lines.append((start["x"] + nx * distance, start["y"] + ny * distance, dx, dy))
    result = []
    for index, current in enumerate(lines):
        ax, ay, ux, uy = lines[index - 1]
        bx, by, vx, vy = current
        determinant = ux * vy - uy * vx
        if abs(determinant) <= EPS:
            if (
                abs(distances[index - 1] - distances[index]) > EPS
                or ux * vx + uy * vy <= 0
            ):
                raise CsCalculationError(
                    "На одной прямой задайте одинаковую комплектацию соседних сторон"
                )
            point = {"x": bx, "y": by}
        else:
            factor = ((bx - ax) * vy - (by - ay) * vx) / determinant
            point = {"x": ax + factor * ux, "y": ay + factor * uy}
        result.append(point)
    try:
        shifted = _polygon(result)
        for index, point in enumerate(result):
            end = result[(index + 1) % len(result)]
            _, _, dx, dy = lines[index]
            if (end["x"] - point["x"]) * dx + (end["y"] - point["y"]) * dy <= EPS:
                raise CsCalculationError(
                    "Вычеты схлопывают сторону: увеличьте проём или измените комплектацию"
                )
    except CsCalculationError:
        if all(d >= 0 for d in distances) and original.equals(original.convex_hull):
            return _clip_convex_inset(points, lines, orientation)
        raise
    if all(d >= 0 for d in distances) and not original.buffer(1e-5).covers(shifted):
        raise CsCalculationError("Вычеты образуют недопустимый контур стекла")
    if all(d <= 0 for d in distances) and not shifted.buffer(1e-5).covers(original):
        raise CsCalculationError("Не удалось восстановить монтажный контур")
    return result


def _offset_edge_length(installation, contour, index, distance):
    """Measure the surviving source side, without reusing shifted vertex indexes."""
    start, end = installation[index], installation[(index + 1) % len(installation)]
    dx, dy = end["x"] - start["x"], end["y"] - start["y"]
    length = hypot(dx, dy)
    winding = 1 if _signed_area(installation) > 0 else -1

    def on_line(point):
        return (
            abs(
                winding
                * (dx * (point["y"] - start["y"]) - dy * (point["x"] - start["x"]))
                / length
                - distance
            )
            < 1e-5
        )

    return sum(
        hypot(b["x"] - a["x"], b["y"] - a["y"])
        for a, b in zip(contour, contour[1:] + contour[:1])
        if on_line(a) and on_line(b)
    )


def split_profile_lengths(lengths):
    """Split physical T40T cuts, without changing side lengths used by covers."""
    result = []
    for length in lengths:
        full = int(length // STOCK_MM)
        result.extend([float(STOCK_MM)] * full)
        tail = length - full * STOCK_MM
        if tail > EPS:
            result.append(tail)
    return result


def _preset(section, width, height):
    shape = str(getattr(section, "cs_shape", "") or "").lower()
    if "треуг" in shape:
        return [{"x": 0, "y": 0}, {"x": width, "y": 0}, {"x": width / 2, "y": height}]
    if "трап" in shape:
        top = min(
            width, max(1, _number(getattr(section, "cs_width2", 0)) or width * 0.7)
        )
        left = (width - top) / 2
        return [
            {"x": 0, "y": 0},
            {"x": width, "y": 0},
            {"x": left + top, "y": height},
            {"x": left, "y": height},
        ]
    if "слож" in shape:
        return [
            {"x": 0, "y": 0},
            {"x": width, "y": 0},
            {"x": width, "y": height * 0.65},
            {"x": width * 0.62, "y": height},
            {"x": 0, "y": height},
        ]
    return [
        {"x": 0, "y": 0},
        {"x": width, "y": 0},
        {"x": width, "y": height},
        {"x": 0, "y": height},
    ]


def _split_positions(raw, low, high):
    config = raw if isinstance(raw, dict) else {}
    count = max(0, min(20, int(_number(config.get("count")))))
    mode = config.get("mode", "equal")
    span = high - low
    if mode == "manual":
        if not isinstance(config.get("positions", []), list):
            raise CsCalculationError("Координаты стыков должны быть списком чисел")
        positions = sorted(set(_number(v) for v in config.get("positions", [])))
        if len(positions) > 20 or any(
            v <= low + GAP / 2 or v >= high - GAP / 2 for v in positions
        ):
            raise CsCalculationError(
                "Координаты стыков должны находиться внутри светового проёма с запасом на зазор 3 мм"
            )
    elif mode in ("from-left", "from-right"):
        step = _number(config.get("step"), span / (count + 1))
        positions = (
            sorted(
                low + step * i if mode == "from-left" else high - step * i
                for i in range(1, count + 1)
            )
            if step > 0
            else []
        )
        positions = [v for v in positions if low + GAP / 2 < v < high - GAP / 2]
    else:
        mode = "equal"
        pane = (span - GAP * count) / (count + 1)
        if pane <= EPS:
            raise CsCalculationError(
                "Слишком много стёкол для заданного светового проёма"
            )
        positions = [low + pane * i + GAP * (i - 0.5) for i in range(1, count + 1)]
    if any(b - a <= GAP + EPS for a, b in zip(positions, positions[1:])):
        raise CsCalculationError(
            "Между линиями деления должно оставаться место для стекла и зазора 3 мм"
        )
    return {
        **config,
        "mode": mode,
        "count": len(positions),
        "positions": positions,
    }, positions


def _parts(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry] if geometry.area > EPS else []
    return [part for child in getattr(geometry, "geoms", []) for part in _parts(child)]


def _points(polygon):
    return [{"x": x, "y": y} for x, y in list(polygon.exterior.coords)[:-1]]


def _joint_length(polygon, position, perpendicular_cuts, axis):
    """Only length with glass on BOTH sides; crossing air gaps need no tape."""
    bounds = polygon.bounds

    def intervals(geometry):
        if geometry.geom_type == "LineString":
            values = [p[1 - axis] for p in geometry.coords]
            return [(min(values), max(values))]
        return [
            interval
            for child in getattr(geometry, "geoms", [])
            for interval in intervals(child)
        ]

    def at(value):
        line = (
            LineString([(value, bounds[1]), (value, bounds[3])])
            if axis == 0
            else LineString([(bounds[0], value), (bounds[2], value)])
        )
        return intervals(polygon.intersection(line))

    total = 0.0
    for a, b in at(position - GAP / 2):
        for c, d in at(position + GAP / 2):
            start, end = max(a, c), min(b, d)
            if end > start:
                total += (
                    end
                    - start
                    - sum(
                        max(0, min(end, cut + GAP / 2) - max(start, cut - GAP / 2))
                        for cut in perpendicular_cuts
                    )
                )
    return max(0, total)


def calculate_cs(section, *, system=None, outer_profile=None, joint_profile=None):
    width, height = (
        _number(getattr(section, "width", 0)),
        _number(getattr(section, "height", 0)),
    )
    quantity = max(1, int(_number(getattr(section, "quantity", 1), 1)))
    if width <= 0 or height <= 0:
        raise CsCalculationError("Ширина и высота ЦС должны быть больше нуля")
    raw = getattr(section, "cs_config", None)
    config = raw if isinstance(raw, dict) else {}
    radius = _number(config.get("triangleCornerRadiusMm", 0), -1)
    if radius not in (0, 8, 10):
        raise CsCalculationError(
            "Скругление треугольника: выберите без скругления, R8 или R10"
        )
    raw_vertices = config.get("vertices", [])
    if not isinstance(raw_vertices, list) or any(
        not isinstance(p, dict) for p in raw_vertices
    ):
        raise CsCalculationError("Углы должны быть списком координат X и Y")
    vertices = [
        {"x": _number(p.get("x")), "y": _number(p.get("y"))} for p in raw_vertices
    ] or _preset(section, width, height)
    _polygon(vertices)
    mode = config.get("dimensionMode", "installation")
    if mode not in ("installation", "clear"):
        raise CsCalculationError("Неизвестный тип размеров проёма")
    if "edgeTreatments" in config:
        treatments = config["edgeTreatments"]
        if (
            not isinstance(treatments, list)
            or len(treatments) != len(vertices)
            or any(v not in ("clamp", "bubble", "none") for v in treatments)
        ):
            raise CsCalculationError(
                "Для каждой стороны выберите профиль, уплотнитель или свободную сторону"
            )
    elif "profiledEdges" in config:
        if not isinstance(config["profiledEdges"], list):
            raise CsCalculationError("Стороны с профилем должны быть списком индексов")
        treatments = [
            "clamp" if i in config["profiledEdges"] else "none"
            for i in range(len(vertices))
        ]
    else:
        treatments = ["clamp"] * len(vertices)
    bubble = _number(config.get("bubbleDeductionMm"), 6)
    if not 0 <= bubble <= 50:
        raise CsCalculationError("Вычет RS1002 должен быть от 0 до 50 мм")
    light_distances = [
        40 if t == "clamp" else bubble if t == "bubble" else 0 for t in treatments
    ]
    glass_distances = [
        26 if t == "clamp" else bubble if t == "bubble" else 0 for t in treatments
    ]
    installation = (
        vertices
        if mode == "installation"
        else offset_contour(vertices, [-d for d in light_distances])
    )
    light = offset_contour(installation, light_distances)
    glass = offset_contour(installation, glass_distances)
    light_polygon, glass_polygon = _polygon(light), _polygon(glass)
    min_x, min_y, max_x, max_y = light_polygon.bounds
    vertical, xs = _split_positions(config.get("vertical"), min_x, max_x)
    horizontal, ys = _split_positions(config.get("horizontal"), min_y, max_y)
    gx0, gy0, gx1, gy1 = glass_polygon.bounds
    x_boundaries, y_boundaries = [gx0, *xs, gx1], [gy0, *ys, gy1]
    panes = []
    for row in range(len(y_boundaries) - 1):
        for col in range(len(x_boundaries) - 1):
            left = x_boundaries[col] + (GAP / 2 if col else 0)
            right = x_boundaries[col + 1] - (GAP / 2 if col < len(xs) else 0)
            bottom = y_boundaries[row] + (GAP / 2 if row else 0)
            top = y_boundaries[row + 1] - (GAP / 2 if row < len(ys) else 0)
            if right <= left or top <= bottom:
                raise CsCalculationError(
                    "Деление не оставляет положительного размера стекла"
                )
            for pane in _parts(
                glass_polygon.intersection(box(left, bottom, right, top))
            ):
                px0, py0, px1, py1 = pane.bounds
                width_mm = floor(px1 - px0 + EPS)
                height_mm = floor(py1 - py0 + EPS)
                if min(width_mm, height_mm) < 1:
                    raise CsCalculationError(
                        "Размер стекла после округления должен быть не менее 1 мм"
                    )
                is_rectangle = abs(pane.area - (px1 - px0) * (py1 - py0)) < EPS
                panes.append(
                    {
                        "column": col + 1,
                        "row": row + 1,
                        "width_mm": width_mm,
                        "height_mm": height_mm,
                        "area_m2": (width_mm * height_mm if is_rectangle else pane.area)
                        / 1e6,
                        "is_rectangle": is_rectangle,
                        "qty": quantity,
                        "polygon": _points(pane),
                        "centroid": (pane.centroid.x, pane.centroid.y),
                    }
                )
    if not panes:
        raise CsCalculationError("В результате деления не осталось стёкол")
    panes.sort(
        key=lambda pane: (
            -pane["row"],
            pane["column"],
            -round(pane["centroid"][1], 6),
            round(pane["centroid"][0], 6),
        )
    )
    for index, pane in enumerate(panes, 1):
        pane["number"] = index
        del pane["centroid"]
        try:
            rounding = triangle_rounding(pane["polygon"], radius)
        except ValueError as error:
            raise CsCalculationError(f"Стекло З{index}: {error}") from error
        if rounding:
            pane["rounded_corner"] = rounding
            pane["treatment_note"] = (
                f"Скругление R{radius:g}; расчётные размеры до скругления"
            )
    cuts = [_joint_length(glass_polygon, x, ys, 0) for x in xs]
    cuts += [_joint_length(glass_polygon, y, xs, 1) for y in ys]
    profiled = [i for i, t in enumerate(treatments) if t == "clamp"]

    def length(points, i):
        return hypot(
            points[(i + 1) % len(points)]["x"] - points[i]["x"],
            points[(i + 1) % len(points)]["y"] - points[i]["y"],
        )

    outer_lengths = [length(installation, i) for i in profiled]
    cover_blanks = cover_cuts(outer_lengths)
    cover_stocks = pack_cuts(cover_blanks)
    bubble_lengths = [
        (
            length(glass, i)
            if len(glass) == len(installation)
            else _offset_edge_length(installation, glass, i, bubble)
        )
        for i, t in enumerate(treatments)
        if t == "bubble"
    ]
    bubble_lengths = [value for value in bubble_lengths if value > EPS]
    cover = getattr(system, "cover_profile", None)
    seal = getattr(system, "bubble_seal", None)
    pad = getattr(system, "glass_pad", None)
    outer_profile = outer_profile or getattr(system, "outer_profile", None)
    profiles = []

    def profile(role, item, sku, name, lengths, paint, image):
        if not lengths:
            return
        profiles.append(
            {
                "role": role,
                "article": getattr(item, "sku", None) or sku,
                "name": getattr(item, "name", None) or name,
                "length_mm": sum(lengths),
                "total_length_mm": sum(lengths) * quantity,
                "pieces": len(lengths) * quantity,
                "cut_lengths_mm": lengths,
                "cutting_text": "; ".join(
                    f"{size:g} мм × {count * quantity} шт."
                    for size, count in Counter(round(v, 1) for v in lengths).items()
                ),
                "unit": "м.п.",
                "preliminary": True,
                "requires_paint": paint,
                "image": getattr(item, "image_file", None) or image,
            }
        )

    profile(
        "outer",
        outer_profile,
        "Т40Т",
        "Зажимной профиль Т40Т в сборе",
        split_profile_lengths(outer_lengths),
        False,
        "T40T-section.jpg",
    )
    profile(
        "cover",
        cover,
        "Т40К",
        "Крышка зажимного профиля Т40К",
        [3000.0] * len(cover_stocks),
        True,
        "T40K-section.jpg",
    )
    profile(
        "bubble",
        seal,
        "RS1002",
        "Пузырьковый уплотнитель RS1002",
        bubble_lengths,
        False,
        "RS1002.png",
    )
    hardware = [
        {
            "article": getattr(pad, "sku", None) or "CS-PVC-PAD",
            "name": getattr(pad, "name", None) or "Подкладка ПВХ под ЦС-стекло",
            "qty": len(panes) * quantity * 2,
            "unit": "шт",
            "image": "",
            "role": "pad",
        }
    ]
    if sum(cuts) > EPS:
        hardware.append(
            {
                "article": "",
                "name": "Двухсторонний скотч для соединения стёкол",
                "qty": ceil(sum(cuts) * 2 * quantity / 1000 - EPS),
                "unit": "м",
                "image": "",
                "role": "tape",
            }
        )
    glass_type = normalize_slide_glass_type(getattr(section, "glass_type", ""))
    if glass_type not in GLASS_TYPES:
        raise CsCalculationError(
            "Для ЦС разрешено только закалённое стекло 10 мм: прозрачное, бронза, серое, матовое или просветлённое"
        )
    finish = str(getattr(section, "painting_type", "") or "Анод/неокрас")
    color_text = " ".join(
        v for v in [finish, str(getattr(section, "ral_color", "") or "")] if v
    )
    for item in profiles:
        item["requires_paint"] = (
            item["role"] == "cover"
            and "анод" not in finish.casefold()
            and "неокрас" not in finish.casefold()
        )
    system_name = getattr(system, "name", None) or "ЦС — Т40Т / Т40К"
    return {
        "system": {
            "id": getattr(system, "id", None),
            "code": getattr(system, "code", "") or "",
            "name": system_name,
        },
        "normalized_config": {
            **config,
            "version": 2,
            "vertices": vertices,
            "dimensionMode": mode,
            "edgeTreatments": treatments,
            "bubbleDeductionMm": bubble,
            "vertical": vertical,
            "horizontal": horizontal,
            "profiledEdges": profiled,
            "doors": config.get("doors", []),
        },
        "installation_polygon": installation,
        "clear_polygon": light,
        "glass_polygon": glass,
        "installation_width_mm": _polygon(installation).bounds[2]
        - _polygon(installation).bounds[0],
        "installation_height_mm": _polygon(installation).bounds[3]
        - _polygon(installation).bounds[1],
        "clear_width_mm": max_x - min_x,
        "clear_height_mm": max_y - min_y,
        "panes": panes,
        "profiles": profiles,
        "hardware": hardware,
        "system_text": f"ЦС · {system_name}",
        "glass_type": glass_type,
        "color_text": color_text,
        "outer_edge_lengths_mm": outer_lengths,
        "cover_cuts": cover_blanks,
        "cover_stocks": cover_stocks,
        "divider_lengths_mm": cuts,
        "glass_area_m2": sum(pane["area_m2"] * pane["qty"] for pane in panes),
        "warnings": [
            "Геометрия ЦС рассчитана по ТЗ Т40Т/Т40К. Стоимость проверяется отдельно по настройкам системы.",
            "Т40Т — длины без припуска. Т40К — целые палки 3000 мм, запас 50 мм на каждую крышку учтён. Вес и цены новых деталей требуют заполнения.",
            INDIVIDUAL_COVER_NOTE,
        ],
        "status": "preliminary",
        "commercial_price_allowed": False,
        "doors_phase": "planned",
    }
