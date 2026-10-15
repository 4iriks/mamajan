"""Optional glass edge treatment. Never feeds back into CS quantities or sizes."""

from math import acos, atan2, cos, hypot, pi, sin, tan


def triangle_rounding(points, radius):
    """Round only the sharpest corner, with a circle tangent to both edges.

    Input and financial/manufacturing calculation polygons remain untouched.
    The returned outline is for drawing; its radius must not be silently reduced.
    """
    if not radius or len(points) != 3:
        return None
    candidates = []
    for index, point in enumerate(points):
        prev, following = points[index - 1], points[(index + 1) % 3]
        a = (prev["x"] - point["x"], prev["y"] - point["y"])
        b = (following["x"] - point["x"], following["y"] - point["y"])
        la, lb = hypot(*a), hypot(*b)
        if min(la, lb) <= 1e-7:
            raise ValueError("Невозможно скруглить вырожденный треугольник")
        u, v = (a[0] / la, a[1] / la), (b[0] / lb, b[1] / lb)
        angle = acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1])))
        candidates.append((angle, index, la, lb, u, v))
    angle, index, la, lb, u, v = min(
        candidates,
        key=lambda c: (round(c[0], 10), points[c[1]]["y"], points[c[1]]["x"]),
    )
    if angle <= 1e-7:
        raise ValueError("Невозможно скруглить вырожденный треугольник")
    distance = radius / tan(angle / 2)
    if distance >= min(la, lb) - 1e-7:
        raise ValueError(
            f"Скругление R{radius:g} не помещается на стекле: уменьшите радиус или измените размеры"
        )
    point = points[index]
    start = {"x": point["x"] + u[0] * distance, "y": point["y"] + u[1] * distance}
    end = {"x": point["x"] + v[0] * distance, "y": point["y"] + v[1] * distance}
    bisector_length = hypot(u[0] + v[0], u[1] + v[1])
    center_distance = radius / sin(angle / 2)
    center = {
        "x": point["x"] + (u[0] + v[0]) / bisector_length * center_distance,
        "y": point["y"] + (u[1] + v[1]) / bisector_length * center_distance,
    }
    winding = (
        1
        if sum(
            p["x"] * points[(i + 1) % 3]["y"] - points[(i + 1) % 3]["x"] * p["y"]
            for i, p in enumerate(points)
        )
        > 0
        else -1
    )
    start_angle = atan2(start["y"] - center["y"], start["x"] - center["x"])
    # <= 0.013 mm sagitta at R10. SVG consumers use the exact circle instead.
    arc = [
        {
            "x": center["x"]
            + radius * cos(start_angle + winding * (pi - angle) * i / 32),
            "y": center["y"]
            + radius * sin(start_angle + winding * (pi - angle) * i / 32),
        }
        for i in range(33)
    ]
    return {
        "vertex_index": index,
        "radius_mm": radius,
        "start": start,
        "end": end,
        "center": center,
        "arc_midpoint": {
            "x": center["x"] + (point["x"] - center["x"]) * radius / center_distance,
            "y": center["y"] + (point["y"] - center["y"]) * radius / center_distance,
        },
        "sweep": 1 if winding > 0 else 0,
        "outline": [*points[:index], *arc, *points[index + 1 :]],
    }
