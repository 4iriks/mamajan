"""BOOK presentation geometry, mirrored by the editor's BookDiagrams.tsx.

The 480-unit canvas and section bounds stay identical for both views. Panel
lengths are read from the calculator; drawing never changes manufacturing sizes.
"""

from __future__ import annotations

import math
from xml.etree.ElementTree import Element, SubElement, tostring

import cairosvg

from engine.pdf import glass_fill

LEFT, RIGHT, WIDTH = 20, 436, 480
SPAN = RIGHT - LEFT
CENTER = (LEFT + RIGHT) / 2
INK = "#123F47"


class Drawing:
    def __init__(self, min_y: float, height: float):
        self.root = Element(
            "svg",
            xmlns="http://www.w3.org/2000/svg",
            viewBox=f"0 {min_y:g} {WIDTH} {height:g}",
        )
        self.add("rect", x=0, y=min_y, width=WIDTH, height=height, fill="white")
        marker = SubElement(
            SubElement(self.root, "defs"),
            "marker",
            id="arrow",
            markerWidth="7",
            markerHeight="7",
            refX="5.5",
            refY="3",
            orient="auto",
        )
        SubElement(marker, "path", d="M0,0 L0,6 L6,3 z", fill=INK)

    def add(self, tag: str, **attrs):
        return SubElement(
            self.root, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()}
        )

    def line(self, x1, y1, x2, y2, **attrs):
        self.add(
            "line",
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            **{"stroke": INK, "stroke_width": 1, **attrs},
        )

    def text(self, x, y, value, size=11.5, **attrs):
        self.add(
            "text",
            x=x,
            y=y,
            **{
                "text_anchor": "middle",
                "fill": INK,
                "font_family": "Arial, Liberation Sans, sans-serif",
                "font_size": size,
                "font_weight": "700",
                **attrs,
            },
        ).text = str(value)

    def dimension(self, y, width):
        self.line(LEFT, y, RIGHT, y)
        for x in (LEFT, RIGHT):
            self.line(x, y - 4, x, y + 4)
        self.text(CENTER, y - 6, f"{float(width):g} мм", 13)

    def svg(self):
        return tostring(self.root, encoding="unicode")


def _panels(calc):
    panels = list(getattr(calc, "panels", []) or [])
    total = sum(p.panel_width_mm for p in panels) or 1
    x = LEFT
    result = []
    for index, panel in enumerate(panels):
        width = (
            RIGHT - x
            if index == len(panels) - 1
            else panel.panel_width_mm / total * SPAN
        )
        result.append((panel, x, width))
        x += width
    return result


def book_room_svg(section, calc) -> str:
    top = 12
    height = max(
        150, min(250, SPAN * float(section.height) / max(float(section.width), 1))
    )
    bottom = top + height
    drawing = Drawing(0, bottom + 64)
    config = getattr(calc, "normalized_config", {}) or {}
    handle_height = config.get("handle_height_mm")
    handle_height = 1000 if handle_height is None else float(handle_height)
    handle_y = (
        bottom - max(0, min(1, handle_height / max(float(section.height), 1))) * height
    )
    for panel, x, width in _panels(calc):
        role = panel.role
        stroke = (
            "#b7791f"
            if role == "fixed"
            else "#c05621"
            if role == "moving_door"
            else INK
        )
        drawing.add(
            "rect",
            x=x,
            y=top + 6,
            width=width,
            height=height - 12,
            fill=glass_fill(panel.glass_type),
            fill_opacity=0.5 if role == "fixed" else 0.78,
            stroke=stroke,
            stroke_width=0.8,
        )
        for y in (top, bottom - 6):
            drawing.add(
                "rect",
                x=x,
                y=y,
                width=width,
                height=6,
                fill=INK,
                fill_opacity=0.25,
                stroke=stroke,
                stroke_width=1,
            )
        center = x + width / 2
        if role == "fixed":
            drawing.add(
                "path",
                d=f"M{x + 5},{top + 10} L{x + width - 5},{bottom - 10} M{x + width - 5},{top + 10} L{x + 5},{bottom - 10}",
                stroke=stroke,
                stroke_width=0.8,
                opacity=0.55,
            )
            drawing.text(center, top + 48, "ГЛУХАЯ", 9, fill=stroke)
        drawing.text(center, top + 28, panel.number, 14)
        drawing.text(center, bottom + 18, f"{panel.glass_width_mm:g}")
        if panel.movement_direction != "none":
            sign = 1 if panel.movement_direction == "right" else -1
            drawing.line(
                center - sign * 10,
                bottom - 32,
                center + sign * 10,
                bottom - 32,
                stroke_width=1.4,
                marker_end="url(#arrow)",
            )
        if role in {"door", "moving_door"}:
            converges_right = (
                panel.door_side == "left"
                if panel.door_side
                else panel.movement_direction == "left"
            )
            outer = x + 5 if converges_right else x + width - 5
            inner = x + width - 5 if converges_right else x + 5
            drawing.add(
                "path",
                d=f"M{outer},{top + height * 0.3} L{inner},{top + height * 0.5} L{outer},{top + height * 0.7}",
                fill="none",
                stroke=INK,
                stroke_width=1,
            )
            handle_x = x + width * (0.72 if converges_right else 0.28)
            if panel.door_hardware == "handle":
                drawing.add(
                    "rect",
                    x=handle_x - 3,
                    y=handle_y - 3,
                    width=6,
                    height=6,
                    fill=INK,
                    fill_opacity=0.3,
                    stroke=INK,
                    stroke_width=0.8,
                )
            else:
                drawing.add(
                    "circle", cx=handle_x, cy=handle_y, r=3.5, fill="none", stroke=INK
                )
    drawing.dimension(bottom + 42, section.width)
    drawing.line(452, top, 452, bottom)
    for y in (top, bottom):
        drawing.line(448, y, 456, y)
    drawing.text(
        470,
        (top + bottom) / 2,
        f"{float(section.height):g} мм",
        13,
        transform=f"rotate(-90 470 {(top + bottom) / 2})",
    )
    drawing.text(CENTER, bottom + 59, "ПОМЕЩЕНИЕ", 10)
    return drawing.svg()


def book_top_svg(section, calc) -> str:
    panels = _panels(calc)
    config = getattr(calc, "normalized_config", {}) or {}

    def length(panel):
        return panel.panel_width_mm / max(float(section.width), 1) * SPAN

    groups = []
    for direction in ("left", "right"):
        stack = [
            p
            for p in panels
            if p[0].role != "fixed" and p[0].movement_direction == direction
        ]
        if direction == "right":
            stack.reverse()
        if not stack:
            continue
        door = next((p[0] for p in stack if p[0].role in {"door", "moving_door"}), None)
        room = door is None or door.door_opening in {"inside_in", "outside_in"}
        base = stack[0][1] if direction == "left" else stack[0][1] + stack[0][2]
        groups.append(
            (direction, stack, door, room, base, 1 if direction == "left" else -1)
        )
    inside = max(
        [0]
        + [length(p) for _, stack, _, room, _, _ in groups if room for p, _, _ in stack]
    )
    outside = max(
        [0]
        + [
            length(p)
            for _, stack, _, room, _, _ in groups
            if not room
            for p, _, _ in stack
        ]
    )
    obstacle = float(config.get("obstacle_distance_mm") or 0)
    angles = [
        float(config.get("angle_left_deg") or 0),
        float(config.get("angle_right_deg") or 0),
    ]
    top_extent = max(outside, 55 if any(a > 0 for a in angles) else 0)
    room_obstacle, street_obstacle = (
        obstacle > 0 and inside > 0,
        obstacle > 0 and outside > 0,
    )
    below = outside > 0
    dimension_y = inside + (48 if room_obstacle else 0) + 28 if below else -24
    room_y = max(
        inside + (48 if room_obstacle else 0) + 20, dimension_y + 22 if below else 0
    )
    street_y = min(-top_extent - (48 if street_obstacle else 18), -18 if below else -48)
    drawing = Drawing(street_y - 16, room_y - street_y + 28)
    drawing.text(CENTER, street_y, "УЛИЦА", 10)
    for y in (-4, 4):
        drawing.line(LEFT, y, RIGHT, y, stroke_width=1.2)
    for x in (LEFT, RIGHT):
        drawing.line(x, -9, x, 9, stroke_width=1.2)
    for index, angle in enumerate(angles):
        if angle > 0:
            x = RIGHT if index else LEFT
            drawing.line(
                x,
                0,
                x + (-1 if index else 1) * math.cos(math.radians(180 - angle)) * 55,
                -math.sin(math.radians(180 - angle)) * 55,
                stroke="#b7791f",
                stroke_width=2,
            )
    for panel, x, width in panels:
        if panel.role == "fixed":
            drawing.add(
                "rect",
                x=x,
                y=-5,
                width=width,
                height=10,
                fill="#f6d89b",
                stroke="#b7791f",
            )
            drawing.text(x + width / 2, 3, "Г", 9, fill="#8b5a14")
    for direction, stack, door, room, base, sign in groups:
        for index, (panel, _, _) in enumerate(stack):
            x = base + sign * index * min(6, SPAN / 4 / len(stack))
            attrs = {"stroke_dasharray": "5 3"} if panel.role == "moving_door" else {}
            drawing.line(
                x,
                0,
                x,
                (1 if room else -1) * length(panel),
                stroke="#c05621" if panel.role == "moving_door" else INK,
                stroke_width=2 if panel.role == "door" else 1,
                data_book_panel=panel.number,
                data_book_length=f"{length(panel):.3f}",
                **attrs,
            )
        drawing.line(
            CENTER + (-12 if direction == "left" else 12),
            16,
            base + sign * (len(stack) * 6 + 18),
            16,
            stroke_width=1.2,
            marker_end="url(#arrow)",
        )
        if door:
            size = length(door)
            drawing.add(
                "path",
                d=f"M{base + sign * size},0 A{size},{size} 0 0 {int((sign > 0) == room)} {base},{(1 if room else -1) * size}",
                fill="none",
                stroke=INK,
                stroke_width=0.7,
                stroke_dasharray="4 3",
            )
    for room, visible, extent in (
        (True, room_obstacle, inside),
        (False, street_obstacle, outside),
    ):
        if visible:
            y = (1 if room else -1) * (extent + 20)
            drawing.line(LEFT, y, RIGHT, y, stroke="#dc2626", stroke_dasharray="6 4")
            drawing.text(
                CENTER,
                extent + 35 if room else -extent - 28,
                f"до препятствия {obstacle:g} мм",
                10,
                fill="#dc2626",
            )
    drawing.dimension(dimension_y, section.width)
    drawing.text(CENTER, room_y, "ПОМЕЩЕНИЕ", 10)
    return drawing.svg()


def render_book_diagram(section, calc, *, top=False) -> bytes:
    svg = book_top_svg(section, calc) if top else book_room_svg(section, calc)
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1920)
