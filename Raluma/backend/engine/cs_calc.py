"""Preliminary deterministic geometry calculation for all-glass (ЦС) sections.

Phase one intentionally calculates geometry, glass and a profile BOM only.
Commercial pricing remains blocked until the customer confirms the formulas.
"""

from __future__ import annotations

from math import hypot
from types import SimpleNamespace
from typing import Any


EPS = 1e-7


class CsCalculationError(ValueError):
    pass


def cs_result_namespace(value: Any) -> Any:
    """Convert a JSON-shaped result into attribute-access rows for documents."""

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
    except (TypeError, ValueError):
        return fallback
    return result


def _area(points: list[dict[str, float]]) -> float:
    return abs(
        sum(
            point["x"] * points[(index + 1) % len(points)]["y"]
            - points[(index + 1) % len(points)]["x"] * point["y"]
            for index, point in enumerate(points)
        )
    ) / 2


def _signed_area(points: list[dict[str, float]]) -> float:
    return sum(
        point["x"] * points[(index + 1) % len(points)]["y"]
        - points[(index + 1) % len(points)]["x"] * point["y"]
        for index, point in enumerate(points)
    ) / 2


def _orientation(a: dict, b: dict, c: dict) -> float:
    return (b["x"] - a["x"]) * (c["y"] - a["y"]) - (
        b["y"] - a["y"]
    ) * (c["x"] - a["x"])


def _segments_cross(a: dict, b: dict, c: dict, d: dict) -> bool:
    first = _orientation(a, b, c)
    second = _orientation(a, b, d)
    third = _orientation(c, d, a)
    fourth = _orientation(c, d, b)
    return first * second < -EPS and third * fourth < -EPS


def _validate_polygon(points: list[dict[str, float]]) -> None:
    if len(points) < 3:
        raise CsCalculationError("Контур ЦС должен содержать не менее трёх точек")
    count = len(points)
    for index in range(count):
        a = points[index]
        b = points[(index + 1) % count]
        if hypot(b["x"] - a["x"], b["y"] - a["y"]) <= EPS:
            raise CsCalculationError("В контуре ЦС есть совпадающие соседние точки")
        for other in range(index + 1, count):
            if other in {index, (index + 1) % count}:
                continue
            if index == 0 and other == count - 1:
                continue
            c = points[other]
            d = points[(other + 1) % count]
            if _segments_cross(a, b, c, d):
                raise CsCalculationError("Контур ЦС не должен пересекать сам себя")
    if _area(points) <= EPS:
        raise CsCalculationError("Площадь контура ЦС должна быть больше нуля")


def _preset_vertices(shape: str, width: float, height: float, width2: float) -> list[dict[str, float]]:
    normalized = str(shape or "").casefold()
    if "треуг" in normalized:
        return [{"x": 0, "y": 0}, {"x": width, "y": 0}, {"x": width / 2, "y": height}]
    if "трап" in normalized:
        top = min(width, max(1, width2 or width * 0.7))
        offset = (width - top) / 2
        return [
            {"x": 0, "y": 0},
            {"x": width, "y": 0},
            {"x": offset + top, "y": height},
            {"x": offset, "y": height},
        ]
    if "слож" in normalized:
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


def _split_positions(raw: Any, low: float, high: float) -> tuple[dict, list[float]]:
    source = raw if isinstance(raw, dict) else {}
    count = max(0, min(20, int(_number(source.get("count"), 0))))
    mode = str(source.get("mode") or "equal")
    if mode not in {"equal", "from-left", "from-right", "manual"}:
        mode = "equal"
    span = max(0, high - low)
    positions: list[float]
    if mode == "manual":
        positions = sorted(
            {
                _number(value)
                for value in source.get("positions", [])
                if low + EPS < _number(value) < high - EPS
            }
        )[:20]
        count = len(positions)
    elif mode in {"from-left", "from-right"}:
        step = max(0, _number(source.get("step"), span / (count + 1) if count else 0))
        if step <= EPS:
            positions = []
            count = 0
        elif mode == "from-left":
            positions = [low + step * index for index in range(1, count + 1)]
        else:
            positions = [high - step * index for index in range(1, count + 1)]
        positions = sorted(value for value in positions if low + EPS < value < high - EPS)
        count = len(positions)
    else:
        positions = [low + span * index / (count + 1) for index in range(1, count + 1)]
        step = span / (count + 1) if count else 0
    return {
        "count": count,
        "mode": mode,
        "step": round(step, 3) if mode != "manual" else None,
        "positions": [round(value, 3) for value in positions],
    }, positions


def _clip_half_plane(
    polygon: list[dict[str, float]], axis: str, boundary: float, keep_greater: bool
) -> list[dict[str, float]]:
    if not polygon:
        return []

    def inside(point: dict[str, float]) -> bool:
        value = point[axis]
        return value >= boundary - EPS if keep_greater else value <= boundary + EPS

    def intersection(start: dict[str, float], end: dict[str, float]) -> dict[str, float]:
        delta = end[axis] - start[axis]
        ratio = 0 if abs(delta) <= EPS else (boundary - start[axis]) / delta
        return {
            "x": start["x"] + (end["x"] - start["x"]) * ratio,
            "y": start["y"] + (end["y"] - start["y"]) * ratio,
        }

    output: list[dict[str, float]] = []
    previous = polygon[-1]
    previous_inside = inside(previous)
    for current in polygon:
        current_inside = inside(current)
        if current_inside != previous_inside:
            output.append(intersection(previous, current))
        if current_inside:
            output.append(dict(current))
        previous = current
        previous_inside = current_inside
    return output


def _clip_cell(
    polygon: list[dict[str, float]], left: float, right: float, bottom: float, top: float
) -> list[dict[str, float]]:
    result = _clip_half_plane(polygon, "x", left, True)
    result = _clip_half_plane(result, "x", right, False)
    result = _clip_half_plane(result, "y", bottom, True)
    result = _clip_half_plane(result, "y", top, False)
    return result if len(result) >= 3 and _area(result) > EPS else []


def _point_inside(point: dict[str, float], polygon: list[dict[str, float]]) -> bool:
    inside = False
    x, y = point["x"], point["y"]
    previous = polygon[-1]
    for current in polygon:
        crosses = (current["y"] > y) != (previous["y"] > y)
        if crosses:
            crossing_x = (previous["x"] - current["x"]) * (y - current["y"]) / (
                previous["y"] - current["y"]
            ) + current["x"]
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _line_length_inside(
    polygon: list[dict[str, float]], axis: str, position: float
) -> float:
    other = "y" if axis == "x" else "x"
    intersections: list[float] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        start_delta = start[axis] - position
        end_delta = end[axis] - position
        if abs(start_delta) <= EPS:
            intersections.append(start[other])
        if start_delta * end_delta < -EPS:
            ratio = (position - start[axis]) / (end[axis] - start[axis])
            intersections.append(start[other] + ratio * (end[other] - start[other]))
    ordered: list[float] = []
    for value in sorted(intersections):
        if not ordered or abs(value - ordered[-1]) > EPS:
            ordered.append(value)
    total = 0.0
    for low, high in zip(ordered, ordered[1:]):
        midpoint = (low + high) / 2
        probe = {axis: position, other: midpoint}
        if _point_inside(probe, polygon):
            total += high - low
    return total


def calculate_cs(
    section: object,
    *,
    system: object | None = None,
    outer_profile: object | None = None,
    joint_profile: object | None = None,
) -> dict:
    width = _number(getattr(section, "width", 0))
    height = _number(getattr(section, "height", 0))
    quantity = max(1, int(_number(getattr(section, "quantity", 1), 1)))
    if width <= 0 or height <= 0:
        raise CsCalculationError("Ширина и высота ЦС должны быть больше нуля")
    raw_config = getattr(section, "cs_config", None)
    config = raw_config if isinstance(raw_config, dict) else {}
    raw_vertices = config.get("vertices") if isinstance(config, dict) else None
    vertices = [
        {"x": _number(point.get("x")), "y": _number(point.get("y"))}
        for point in raw_vertices or []
        if isinstance(point, dict)
    ]
    if not vertices:
        vertices = _preset_vertices(
            str(getattr(section, "cs_shape", "") or ""),
            width,
            height,
            _number(getattr(section, "cs_width2", 0)),
        )
    if _signed_area(vertices) < 0:
        vertices.reverse()
    _validate_polygon(vertices)

    min_x = min(point["x"] for point in vertices)
    max_x = max(point["x"] for point in vertices)
    min_y = min(point["y"] for point in vertices)
    max_y = max(point["y"] for point in vertices)
    vertical_config, vertical_positions = _split_positions(config.get("vertical"), min_x, max_x)
    horizontal_config, horizontal_positions = _split_positions(config.get("horizontal"), min_y, max_y)

    panes: list[dict] = []
    x_boundaries = [min_x, *vertical_positions, max_x]
    y_boundaries = [min_y, *horizontal_positions, max_y]
    for row in range(len(y_boundaries) - 1):
        for column in range(len(x_boundaries) - 1):
            clipped = _clip_cell(
                vertices,
                x_boundaries[column],
                x_boundaries[column + 1],
                y_boundaries[row],
                y_boundaries[row + 1],
            )
            if not clipped:
                continue
            pane_min_x = min(point["x"] for point in clipped)
            pane_max_x = max(point["x"] for point in clipped)
            pane_min_y = min(point["y"] for point in clipped)
            pane_max_y = max(point["y"] for point in clipped)
            panes.append(
                {
                    "column": column + 1,
                    "row": row + 1,
                    "width_mm": round(pane_max_x - pane_min_x, 1),
                    "height_mm": round(pane_max_y - pane_min_y, 1),
                    "area_m2": round(_area(clipped) / 1_000_000, 4),
                    "qty": quantity,
                    "polygon": [
                        {"x": round(point["x"], 2), "y": round(point["y"], 2)}
                        for point in clipped
                    ],
                    "centroid": {
                        "x": sum(point["x"] for point in clipped) / len(clipped),
                        "y": sum(point["y"] for point in clipped) / len(clipped),
                    },
                }
            )
    panes.sort(key=lambda pane: (-pane["centroid"]["y"], pane["centroid"]["x"]))
    for number, pane in enumerate(panes, start=1):
        pane["number"] = number
        pane.pop("centroid", None)

    edge_lengths = [
        hypot(
            vertices[(index + 1) % len(vertices)]["x"] - point["x"],
            vertices[(index + 1) % len(vertices)]["y"] - point["y"],
        )
        for index, point in enumerate(vertices)
    ]
    default_edges = [
        index
        for index, point in enumerate(vertices)
        if not (
            abs(point["y"] - min_y) <= EPS
            and abs(vertices[(index + 1) % len(vertices)]["y"] - min_y) <= EPS
        )
    ]
    profiled_edges = sorted(
        {
            int(value)
            for value in config.get("profiledEdges", default_edges)
            if str(value).lstrip("-").isdigit() and 0 <= int(value) < len(vertices)
        }
    )
    outer_length = sum(edge_lengths[index] for index in profiled_edges)
    divider_lengths = [
        _line_length_inside(vertices, "x", position) for position in vertical_positions
    ] + [_line_length_inside(vertices, "y", position) for position in horizontal_positions]
    joint_length = sum(divider_lengths)

    normalized_config = {
        "version": 1,
        "vertices": [
            {"x": round(point["x"], 3), "y": round(point["y"], 3)}
            for point in vertices
        ],
        "vertical": vertical_config,
        "horizontal": horizontal_config,
        "profiledEdges": profiled_edges,
        "doors": config.get("doors", []),
    }
    system_name = str(getattr(system, "name", "") or "Система ЦС не выбрана")
    outer_sku = str(getattr(outer_profile, "sku", "") or "артикул уточняется")
    joint_sku = str(getattr(joint_profile, "sku", "") or "артикул уточняется")
    warnings = ["Расчёт ЦС предварительный: коммерческая цена не формируется."]
    if outer_profile is None:
        warnings.append("Для системы ЦС не выбран внешний зажимной профиль.")
    if divider_lengths and joint_profile is None:
        warnings.append("Для системы ЦС не выбран профиль стыка стекол.")
    bom = [
        {
            "role": "outer",
            "article": outer_sku,
            "name": str(getattr(outer_profile, "name", "") or "Зажимной профиль внешнего контура"),
            "length_mm": round(outer_length, 1),
            "total_length_mm": round(outer_length * quantity, 1),
            "pieces": len(profiled_edges) * quantity,
            "unit": "м.п.",
            "preliminary": True,
        }
    ]
    if divider_lengths:
        bom.append(
            {
                "role": "joint",
                "article": joint_sku,
                "name": str(getattr(joint_profile, "name", "") or "Профиль стыка стекол"),
                "length_mm": round(joint_length, 1),
                "total_length_mm": round(joint_length * quantity, 1),
                "pieces": len(divider_lengths) * quantity,
                "unit": "м.п.",
                "preliminary": True,
            }
        )
    painting_code = str(getattr(section, "painting_type", "") or "").strip()
    painting_names = {
        "ANOD_UNPAINTED": "Анод/неокрас",
        "RAL_STANDARD": "RAL стандарт",
        "RAL_MOIRE": "RAL муар",
        "SUBLIMATION": "Сублимация",
        "COLORLESS": "Без цвета",
    }
    finish_name = painting_names.get(painting_code, painting_code)
    ral_color = str(getattr(section, "ral_color", "") or "").strip()
    color_text = " ".join(part for part in (finish_name, ral_color) if part).strip()
    glass_type = str(
        getattr(section, "glass_type", "") or "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    )
    return {
        "system": {
            "id": getattr(system, "id", None),
            "code": str(getattr(system, "code", "") or ""),
            "name": system_name,
        },
        "normalized_config": normalized_config,
        "panes": panes,
        "profiles": bom,
        "system_text": f"ЦС · {system_name}",
        "glass_type": glass_type,
        "color_text": color_text or "Без цвета",
        "outer_edge_lengths_mm": [round(edge_lengths[index], 1) for index in profiled_edges],
        "divider_lengths_mm": [round(value, 1) for value in divider_lengths],
        "glass_area_m2": round(sum(pane["area_m2"] * pane["qty"] for pane in panes), 4),
        "warnings": warnings,
        "status": "preliminary",
        "commercial_price_allowed": False,
        "doors_phase": "planned",
    }
