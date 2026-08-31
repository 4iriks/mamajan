"""Raster diagrams used by editable Office exports.

The PDF/HTML documents keep their native SVG diagrams. Office files receive
high-resolution PNG equivalents so tables remain editable while schemes stay
stable in Word and Excel.
"""

from __future__ import annotations

import io
import math
import re
from types import SimpleNamespace

import cairosvg
from PIL import Image, ImageChops, ImageDraw

from engine.office_common import load_font
from engine.pdf import (
    expand_glass_widths,
    glass_fill,
    glass_is_matte,
    glass_mm,
    render_pdf_html,
)


INK = "#123F47"
MUTED = "#77979D"
GRID = "#A8BBC0"
RED = "#D00000"
BACKGROUND = "#FFFFFF"

_OFFICE_SVG_RE = re.compile(
    r'(<svg\b(?=[^>]*\bdata-office-diagram="([^"]+)")[^>]*>.*?</svg>)',
    re.DOTALL,
)
_VIEWBOX_RE = re.compile(
    r'\bviewBox="[-+0-9.eE]+\s+[-+0-9.eE]+\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)"'
)
_DIAGRAM_TITLES = {
    "slide-room": "Вид из помещения",
    "slide-top": "Схема · вид сверху",
    "lift-front": "Вид из помещения",
    "lift-kinematic": "Кинематическая схема",
}


def _reference_diagrams(
    section: object,
    calc: object,
) -> list[tuple[str, bytes]]:
    """Rasterize the exact SVGs used by the PDF/HTML production sheet."""
    html = render_pdf_html(SimpleNamespace(number=""), section, calc)
    rendered: list[tuple[str, bytes]] = []
    for svg, name in _OFFICE_SVG_RE.findall(html):
        viewbox = _VIEWBOX_RE.search(svg)
        source_width = float(viewbox.group(1)) if viewbox else 1
        source_height = float(viewbox.group(2)) if viewbox else 1
        output_width = 1800 if name.startswith("slide-") else 1200
        output_height = max(1, round(output_width * source_height / source_width))
        png = cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=output_width,
            output_height=output_height,
        )
        rendered.append((_DIAGRAM_TITLES[name], png))
    return rendered


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _cropped_png(image: Image.Image, *, padding: int = 20) -> bytes:
    """Trim unused white canvas while retaining a small printable margin."""
    background = Image.new(image.mode, image.size, BACKGROUND)
    bounds = ImageChops.difference(image, background).getbbox()
    if bounds is None:
        return _png(image)
    left, top, right, bottom = bounds
    cropped = image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )
    return _png(cropped)


def _boxed_png(image: Image.Image, box: tuple[int, int, int, int]) -> bytes:
    """Crop to a deterministic box so print font sizing has a known scale."""

    return _png(image.crop(box))


def _print_font_pixels(
    point_size: float,
    crop_width_px: int,
    crop_height_px: int,
    *,
    max_width_mm: float = 176,
    max_height_mm: float = 82,
) -> int:
    """Convert a desired final point size to source pixels after fit-to-page."""

    millimeters_per_pixel = min(
        max_width_mm / max(crop_width_px, 1),
        max_height_mm / max(crop_height_px, 1),
    )
    desired_height_mm = point_size * 25.4 / 72
    return max(13, round(desired_height_mm / millimeters_per_pixel))


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font,
    fill=INK,
) -> None:
    width, height = _text_size(draw, text, font)
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text, font=font, fill=fill)


def _center_vertical_text(
    image: Image.Image,
    xy: tuple[float, float],
    text: str,
    font,
    fill=INK,
) -> None:
    label_draw = ImageDraw.Draw(image)
    width, height = _text_size(label_draw, text, font)
    label = Image.new("RGBA", (width + 12, height + 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(label)
    bounds = draw.textbbox((0, 0), text, font=font)
    draw.text(
        (6 - bounds[0], 6 - bounds[1]),
        text,
        font=font,
        fill=fill,
    )
    rotated = label.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    image.paste(
        rotated,
        (
            round(xy[0] - rotated.width / 2),
            round(xy[1] - rotated.height / 2),
        ),
        rotated,
    )


def _fitted_font(draw: ImageDraw.ImageDraw, text: str, max_width: float, preferred: int):
    for size in range(preferred, 12, -1):
        font = load_font(size, bold=True)
        if _text_size(draw, text, font)[0] <= max(max_width, 1):
            return font
    return load_font(13, bold=True)


def _arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color=INK,
    width=4,
    start_head: bool = False,
    end_head: bool = True,
) -> None:
    draw.line((start, end), fill=color, width=width)

    def head(tip: tuple[float, float], tail: tuple[float, float]) -> None:
        dx = tip[0] - tail[0]
        dy = tip[1] - tail[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        size = 13
        p1 = (
            tip[0] - ux * size + px * size * 0.55,
            tip[1] - uy * size + py * size * 0.55,
        )
        p2 = (
            tip[0] - ux * size - px * size * 0.55,
            tip[1] - uy * size - py * size * 0.55,
        )
        draw.polygon((tip, p1, p2), fill=color)

    if end_head:
        head(end, start)
    if start_head:
        head(start, end)


def _is_no_option(value: object) -> bool:
    text = " ".join(str(value or "").strip().lower().strip("—- ").split())
    return not text or text.startswith(("без", "нет"))


def _matte_pattern(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
) -> None:
    for y in range(box[1] + 8, box[3] - 4, 13):
        for x in range(box[0] + 8, box[2] - 4, 13):
            draw.ellipse((x, y, x + 2, y + 2), fill="#A7B4B6")


def _fit_rect(
    source_width: float,
    source_height: float,
    max_width: int,
    max_height: int,
) -> tuple[int, int]:
    source_width = max(float(source_width or 1), 1)
    source_height = max(float(source_height or 1), 1)
    scale = min(max_width / source_width, max_height / source_height)
    return max(1, round(source_width * scale)), max(1, round(source_height * scale))


def _slide_handle_kind(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if _is_no_option(text) or "глух" in text or "подвижн" in text:
        return None
    if "кноб" in text or "rs3014" in text:
        return "knob"
    if "скоб" in text or "rs30201" in text:
        return "brace"
    if "стеклян" in text or "rs3017" in text:
        return "glass_handle"
    return None


def _slide_lock_kind(value: object, *, center: bool = False) -> str | None:
    text = str(value or "").strip().casefold()
    if _is_no_option(text):
        return None
    if center:
        return "overhead_latch" if "rs206" in text or "накидн" in text else "center_lock"
    if "2стор" in text or "2-сторон" in text or "ключ" in text:
        return "two_way_lock"
    if "1стор" in text or "1-сторон" in text or "замок" in text or "защ" in text:
        return "one_way_lock"
    return None


def _slide_room_hardware_markers(
    section: object,
    panel_boxes: list[tuple[int, int]],
    *,
    top: int,
    bottom: int,
) -> list[dict[str, float | str]]:
    """Return the same visible hardware markers as the editable section diagram."""
    if not panel_boxes:
        return []

    markers: list[dict[str, float | str]] = []
    center_y = (top + bottom) / 2
    left_edge, right_edge = panel_boxes[0][0], panel_boxes[-1][1]
    left_panel_width = max(1, panel_boxes[0][1] - panel_boxes[0][0])
    right_panel_width = max(1, panel_boxes[-1][1] - panel_boxes[-1][0])
    left_inset = min(44, max(18, left_panel_width * 0.18))
    right_inset = min(44, max(18, right_panel_width * 0.18))

    for side, x, handle_value, lock_value in (
        (
            "left",
            left_edge + left_inset,
            getattr(section, "handle_left", None),
            getattr(section, "lock_left", None),
        ),
        (
            "right",
            right_edge - right_inset,
            getattr(section, "handle_right", None),
            getattr(section, "lock_right", None),
        ),
    ):
        handle_kind = _slide_handle_kind(handle_value)
        if handle_kind:
            markers.append(
                {"kind": handle_kind, "role": f"{side}_handle", "x": x, "y": center_y}
            )
        lock_kind = _slide_lock_kind(lock_value)
        if lock_kind:
            markers.append(
                {
                    "kind": lock_kind,
                    "role": f"{side}_lock",
                    "x": left_edge + 5 if side == "left" else right_edge - 5,
                    "y": center_y,
                    "direction": 1 if side == "left" else -1,
                }
            )

    slide_rows = int(getattr(section, "slide_rows", 1) or 1)
    if slide_rows == 2 and len(panel_boxes) >= 2:
        center_left = len(panel_boxes) // 2 - 1
        center_right = len(panel_boxes) // 2
        center_kind = _slide_handle_kind(getattr(section, "center_handle", None))
        if center_kind:
            seam_x = panel_boxes[center_left][1]
            center_inset = min(
                34,
                max(
                    15,
                    min(
                        panel_boxes[center_left][1] - panel_boxes[center_left][0],
                        panel_boxes[center_right][1] - panel_boxes[center_right][0],
                    )
                    * 0.14,
                ),
            )
            markers.extend(
                [
                    {
                        "kind": center_kind,
                        "role": "center_left_handle",
                        "x": seam_x - center_inset,
                        "y": center_y,
                    },
                    {
                        "kind": center_kind,
                        "role": "center_right_handle",
                        "x": seam_x + center_inset,
                        "y": center_y,
                    },
                ]
            )
        center_lock_kind = _slide_lock_kind(
            getattr(section, "center_lock", None), center=True
        )
        if center_lock_kind:
            markers.append(
                {
                    "kind": center_lock_kind,
                    "role": "center_lock",
                    "x": panel_boxes[center_left][1],
                    "y": bottom - 14 if center_lock_kind == "overhead_latch" else center_y + 38,
                }
            )

    latch_fields = (
        ("floor_latches_left", "left_floor_latch", left_edge + 18),
        ("floor_latches_right", "right_floor_latch", right_edge - 18),
    )
    for field, role, x in latch_fields:
        if bool(getattr(section, field, False)):
            markers.append({"kind": "floor_latch", "role": role, "x": x, "y": bottom - 5})

    if slide_rows == 2 and len(panel_boxes) >= 2:
        seam_x = panel_boxes[len(panel_boxes) // 2 - 1][1]
        for field, role, x in (
            ("center_floor_latches_left", "center_left_floor_latch", seam_x - 15),
            ("center_floor_latches_right", "center_right_floor_latch", seam_x + 15),
        ):
            if bool(getattr(section, field, False)):
                markers.append(
                    {"kind": "floor_latch", "role": role, "x": x, "y": bottom - 5}
                )
    return markers


def _draw_slide_room_hardware_marker(
    draw: ImageDraw.ImageDraw,
    marker: dict[str, float | str],
    *,
    color: str,
) -> None:
    kind = str(marker["kind"])
    x, y = float(marker["x"]), float(marker["y"])
    if kind == "knob":
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=color, outline="#000000", width=2)
    elif kind == "brace":
        draw.line((x, y - 40, x, y + 40), fill=color, width=6)
        draw.ellipse((x - 5, y - 43, x + 5, y - 33), fill=color)
        draw.ellipse((x - 5, y + 33, x + 5, y + 43), fill=color)
    elif kind == "glass_handle":
        draw.rectangle((x - 9, y - 9, x + 9, y + 9), fill=color, outline="#000000", width=2)
    elif kind in {"one_way_lock", "two_way_lock"}:
        draw.line((x, y - 22, x, y + 22), fill=color, width=5)
        if kind == "two_way_lock":
            direction = float(marker.get("direction", 1))
            key_x = x + direction * 20
            draw.ellipse((key_x - 7, y - 16, key_x + 7, y - 2), outline=color, width=3)
            draw.line((key_x, y - 2, key_x, y + 20), fill=color, width=3)
            draw.line((key_x, y + 11, key_x + direction * 7, y + 11), fill=color, width=3)
            draw.line((key_x, y + 17, key_x + direction * 5, y + 17), fill=color, width=3)
    elif kind in {"center_lock", "overhead_latch"}:
        draw.rounded_rectangle((x - 11, y - 7, x + 11, y + 7), radius=3, fill=color)
    elif kind == "floor_latch":
        draw.rectangle((x - 7, y - 7, x + 7, y + 7), fill=color, outline="#000000", width=2)


def render_slide_room(
    section: object,
    calc: object,
    *,
    include_title: bool = True,
    crop: bool = False,
    print_dimensions: bool = False,
) -> bytes:
    canvas = Image.new("RGB", (1740, 850), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)

    if include_title:
        _center_text(draw, (870, 34), "ВИД ИЗ ПОМЕЩЕНИЯ", title_font)
    section_width = float(getattr(section, "width", 0) or 1)
    section_height = float(getattr(section, "height", 0) or 1)
    drawing_width, drawing_height = _fit_rect(section_width, section_height, 1340, 470)
    left = (1740 - drawing_width) // 2
    top = 80 + max(0, (470 - drawing_height) // 2)
    right = left + drawing_width
    bottom = top + drawing_height
    print_crop_box = (
        max(0, left - 24),
        max(0, top - 60),
        min(canvas.width, right + 195),
        min(canvas.height, bottom + 255),
    )
    print_crop_width = print_crop_box[2] - print_crop_box[0]
    print_crop_height = print_crop_box[3] - print_crop_box[1]
    if print_dimensions:
        print_max_width_mm = 72 if section_width < section_height else 176
        number_font_size = _print_font_pixels(
            7,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
        panel_font_size = _print_font_pixels(
            8.5,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
        dimension_font_size = _print_font_pixels(
            9.5,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
        small_font_size = _print_font_pixels(
            12,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
    else:
        number_font_size = 30
        panel_font_size = 23
        dimension_font_size = 23
        small_font_size = 19
    number_font = load_font(number_font_size, bold=True)
    dim_font = load_font(dimension_font_size, bold=True)
    dimension_color = "#000000" if print_dimensions else INK
    dimension_line_color = "#000000" if print_dimensions else GRID
    small_font = load_font(small_font_size, bold=print_dimensions)

    draw.rectangle((left, top, right, bottom), outline=INK, width=7)
    draw.rectangle(
        (left + 10, top + 10, right - 10, bottom - 10), outline=GRID, width=2
    )

    panels = max(int(getattr(section, "panels", 0) or 0), 1)
    widths = [
        max(float(value or 0), 1)
        for value in expand_glass_widths(calc, panels, section_width)
    ]
    width_sum = sum(widths) or panels
    glass_supplied = bool(getattr(section, "glass_supplied", True))
    fill = glass_fill(getattr(calc, "glass_type", "")) if glass_supplied else BACKGROUND
    matte = glass_supplied and glass_is_matte(getattr(calc, "glass_type", ""))
    slide_rows = int(getattr(section, "slide_rows", 1) or 1)
    first_value = str(getattr(section, "first_panel_inside", "") or "")
    first_right = first_value == "Справа"
    panel_numbers = list(getattr(calc, "panel_numbers", None) or [])

    left_handle = str(getattr(section, "handle_left", "") or "Без").lower()
    right_handle = str(getattr(section, "handle_right", "") or "Без").lower()
    left_deaf = (
        ("глух" in left_handle or _is_no_option(left_handle))
        and _is_no_option(getattr(section, "lock_left", None))
        and not bool(getattr(section, "profile_left_handle_bar", False))
    )
    right_deaf = (
        ("глух" in right_handle or _is_no_option(right_handle))
        and _is_no_option(getattr(section, "lock_right", None))
        and not bool(getattr(section, "profile_right_handle_bar", False))
    )
    center_handle = str(getattr(section, "center_handle", "") or "").lower()
    center_deaf = slide_rows == 2 and (
        not center_handle or "глух" in center_handle
    )
    center_left = panels // 2 - 1
    center_right = panels // 2
    room_bidirectional = slide_rows == 1 and not left_deaf and not right_deaf

    x = left + 12
    inner_width = drawing_width - 24
    panel_boxes: list[tuple[int, int]] = []
    for index, panel_width in enumerate(widths):
        panel_px = inner_width * panel_width / width_sum
        panel_left = round(x)
        panel_right = round(x + panel_px)
        panel_boxes.append((panel_left, panel_right))
        box = (panel_left, top + 12, panel_right, bottom - 12)
        draw.rectangle(box, fill=fill, outline=GRID, width=2)
        if matte:
            _matte_pattern(draw, box)

        if slide_rows == 2:
            number = panel_numbers[index] if index < len(panel_numbers) else index + 1
            arrow_left = index < panels / 2
            bidirectional = (
                (index < panels / 2 and not left_deaf)
                or (index >= panels / 2 and not right_deaf)
            )
        else:
            number = panels - index if first_right else index + 1
            arrow_left = first_right
            bidirectional = room_bidirectional

        is_center = slide_rows == 2 and index in {center_left, center_right}
        deaf = (
            (index == 0 and left_deaf)
            or (index == panels - 1 and right_deaf)
            or (is_center and center_deaf)
        )

        cx = (panel_left + panel_right) / 2
        cy = (top + bottom) / 2
        _center_text(
            draw,
            (cx, cy - 30),
            str(number),
            number_font,
            dimension_color,
        )
        if deaf:
            draw.line(
                (panel_left + 12, top + 22, panel_right - 12, bottom - 22),
                fill=GRID,
                width=3,
            )
            draw.line(
                (panel_right - 12, top + 22, panel_left + 12, bottom - 22),
                fill=GRID,
                width=3,
            )
        else:
            _arrow(
                draw,
                (cx - 28, cy + 18),
                (cx + 28, cy + 18),
                width=4,
                start_head=arrow_left or bidirectional,
                end_head=(not arrow_left) or bidirectional,
            )
        dimension = str(glass_mm(panel_width))
        panel_font = _fitted_font(
            draw,
            dimension,
            panel_px - 8,
            panel_font_size,
        )
        _center_text(
            draw,
            (cx, bottom + 50),
            dimension,
            panel_font,
            dimension_color,
        )
        if not glass_supplied:
            no_glass_font = _fitted_font(draw, "БЕЗ СТЕКЛА", panel_px - 10, 18)
            _center_text(draw, (cx, cy + 62), "БЕЗ СТЕКЛА", no_glass_font, MUTED)
        x += panel_px

    for marker in _slide_room_hardware_markers(
        section,
        panel_boxes,
        top=top + 12,
        bottom=bottom - 12,
    ):
        _draw_slide_room_hardware_marker(
            draw,
            marker,
            color="#000000" if print_dimensions else INK,
        )

    width_dimension_y = bottom + 100
    draw.line(
        (left, width_dimension_y, right, width_dimension_y),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    draw.line(
        (left, width_dimension_y - 9, left, width_dimension_y + 9),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    draw.line(
        (right, width_dimension_y - 9, right, width_dimension_y + 9),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    _center_text(
        draw,
        ((left + right) / 2, bottom + 155),
        str(glass_mm(section_width)),
        dim_font,
        dimension_color,
    )
    height_dimension_x = right + 40
    draw.line(
        (height_dimension_x, top, height_dimension_x, bottom),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    draw.line(
        (height_dimension_x - 9, top, height_dimension_x + 9, top),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    draw.line(
        (height_dimension_x - 9, bottom, height_dimension_x + 9, bottom),
        fill=dimension_line_color,
        width=3 if print_dimensions else 2,
    )
    _center_vertical_text(
        canvas,
        (right + 75, (top + bottom) / 2),
        str(glass_mm(section_height)),
        dim_font,
        dimension_color,
    )
    _center_text(
        draw, ((left + right) / 2, bottom + 230), "ПОМЕЩЕНИЕ", small_font, MUTED
    )
    if crop and print_dimensions:
        return _boxed_png(canvas, print_crop_box)
    return _cropped_png(canvas) if crop else _png(canvas)


def render_slide_top(
    section: object,
    calc: object,
    *,
    include_title: bool = True,
    crop: bool = False,
) -> bytes:
    canvas = Image.new("RGB", (1600, 620), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)
    label_font = load_font(20, bold=True)
    small_font = load_font(18)
    if include_title:
        _center_text(draw, (800, 34), "СХЕМА · ВИД СВЕРХУ", title_font)

    left, top, right, bottom = 110, 92, 1490, 485
    rails = max(int(getattr(section, "rails", 3) or 3), 1)
    panels = max(int(getattr(section, "panels", 0) or 0), 1)
    row_height = (bottom - top) / rails
    draw.rectangle((left, top, right, bottom), outline=INK, width=4)
    for rail in range(1, rails):
        y = top + rail * row_height
        draw.line((left, y, right, y), fill=GRID, width=2)

    widths = [
        max(float(value or 0), 1)
        for value in expand_glass_widths(
            calc, panels, float(getattr(section, "width", 0) or 1)
        )
    ]
    total = sum(widths) or panels
    rails_for_panels = list(getattr(calc, "panel_rails", None) or [])
    panel_numbers = list(getattr(calc, "panel_numbers", None) or [])
    fill = glass_fill(getattr(calc, "glass_type", ""))
    matte = glass_is_matte(getattr(calc, "glass_type", ""))
    x = left
    for index, panel_width in enumerate(widths):
        panel_px = (right - left) * panel_width / total
        rail = (
            rails_for_panels[index] if index < len(rails_for_panels) else index % rails
        )
        cy = top + (rail + 0.5) * row_height
        x1 = round(x + 4)
        x2 = round(x + panel_px - 4)
        y1 = round(cy - min(19, row_height * 0.27))
        y2 = round(cy + min(19, row_height * 0.27))
        draw.rectangle((x1, y1, x2, y2), fill=fill, outline=INK, width=3)
        if matte:
            _matte_pattern(draw, (x1, y1, x2, y2))
        _center_text(
            draw,
            ((x1 + x2) / 2, (y1 + y2) / 2),
            f"{glass_mm(panel_width)} · №{panel_numbers[index] if index < len(panel_numbers) else index + 1}",
            label_font,
        )
        x += panel_px

    _center_text(draw, (800, 70), "УЛИЦА", small_font, MUTED)
    _center_text(draw, (800, 518), "ПОМЕЩЕНИЕ", small_font, MUTED)
    _arrow(draw, (735, 560), (865, 560), color=INK, width=3)
    return _cropped_png(canvas) if crop else _png(canvas)


def render_lift_front(section: object, calc: object) -> bytes:
    canvas = Image.new("RGB", (1050, 980), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)
    number_font = load_font(28, bold=True)
    dim_font = load_font(22, bold=True)
    small_font = load_font(18, bold=True)
    _center_text(draw, (525, 35), "ВИД ИЗ ПОМЕЩЕНИЯ", title_font)

    section_width = float(getattr(section, "width", 0) or 1)
    section_height = float(getattr(section, "height", 0) or 1)
    drawing_width, drawing_height = _fit_rect(section_width, section_height, 720, 760)
    left = (1050 - drawing_width) // 2
    top = 90 + max(0, (760 - drawing_height) // 2)
    right = left + drawing_width
    bottom = top + drawing_height
    draw.rectangle((left, top, right, bottom), outline=INK, width=8)
    draw.rectangle(
        (left + 12, top + 12, right - 12, bottom - 12), outline=GRID, width=2
    )
    draw.rectangle((left, top, right, top + 22), fill="#DCE4E6", outline=INK, width=2)
    draw.rectangle(
        (left, bottom - 20, right, bottom), fill="#E6EAEB", outline=INK, width=2
    )

    panels = list(getattr(calc, "panels", None) or [])
    total_height = sum(max(float(panel.height_mm or 0), 1) for panel in panels) or 1
    fill = glass_fill(getattr(calc, "filling_text", ""))
    matte = glass_is_matte(getattr(calc, "filling_text", ""))
    y = top + 22
    usable_height = drawing_height - 42
    opening = str(getattr(calc, "opening_text", "") or "")
    for panel in panels:
        panel_height = (
            usable_height * max(float(panel.height_mm or 0), 1) / total_height
        )
        box = (left + 12, round(y), right - 12, round(y + panel_height))
        draw.rectangle(box, fill=fill, outline=GRID, width=2)
        if matte:
            _matte_pattern(draw, box)
        cy = (box[1] + box[3]) / 2
        _center_text(draw, ((left + right) / 2, cy - 18), str(panel.panel), number_font)
        if str(panel.role).lower().startswith("глух"):
            _center_text(draw, ((left + right) / 2, cy + 24), "ГЛУХАЯ", small_font)
        elif "вверх" in opening.lower():
            _arrow(
                draw,
                ((left + right) / 2, cy + 40),
                ((left + right) / 2, cy - 40),
                width=4,
            )
        else:
            _arrow(
                draw,
                ((left + right) / 2, cy - 40),
                ((left + right) / 2, cy + 40),
                width=4,
            )
        y += panel_height

    cable = str(getattr(calc, "cable_side", "") or "")
    cable_x = left if cable == "Слева" else right
    anchor = "СЛЕВА" if cable == "Слева" else "СПРАВА"
    draw.text(
        (cable_x - 5 if cable == "Слева" else cable_x - 235, top - 42),
        f"ВВОД КАБЕЛЯ {anchor}",
        font=small_font,
        fill=RED,
    )
    draw.line((left, bottom + 36, right, bottom + 36), fill=RED, width=2)
    _center_text(
        draw,
        ((left + right) / 2, bottom + 68),
        f"{glass_mm(section_width)} × {glass_mm(section_height)} ММ",
        dim_font,
        RED,
    )
    return _png(canvas)


def render_lift_kinematic(section: object, calc: object) -> bytes:
    canvas = Image.new("RGB", (1050, 980), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)
    number_font = load_font(25, bold=True)
    label_font = load_font(19, bold=True)
    _center_text(draw, (525, 35), "КИНЕМАТИЧЕСКАЯ СХЕМА", title_font)

    x_axis = 170
    top, bottom = 100, 870
    draw.line((x_axis, top, x_axis, bottom), fill=INK, width=8)
    draw.ellipse(
        (x_axis - 22, top - 22, x_axis + 22, top + 22),
        fill=BACKGROUND,
        outline=INK,
        width=6,
    )
    draw.ellipse(
        (x_axis - 22, bottom - 22, x_axis + 22, bottom + 22),
        fill=BACKGROUND,
        outline=INK,
        width=6,
    )

    panels = list(getattr(calc, "panels", None) or [])
    count = max(len(panels), 1)
    y_step = min(195, 560 / max(count - 1, 1))
    start_y = 205
    for index, panel in enumerate(panels):
        cx = 410 + index * 115
        cy = start_y + index * y_step
        glass_top = cy - 65
        glass_bottom = cy + 65
        draw.line((x_axis + 10, top + 20, cx - 25, glass_bottom), fill=GRID, width=3)
        draw.rectangle((cx - 12, glass_top, cx + 12, glass_bottom), fill="#8AB6BD")
        draw.rounded_rectangle(
            (cx - 42, glass_top - 22, cx + 42, glass_top + 22),
            radius=5,
            fill="#F5F7F7",
            outline=INK,
            width=4,
        )
        draw.rounded_rectangle(
            (cx - 42, glass_bottom - 22, cx + 42, glass_bottom + 22),
            radius=5,
            fill="#F5F7F7",
            outline=INK,
            width=4,
        )
        _center_text(draw, (cx + 67, cy), str(panel.panel), number_font)

    label = "НАПРАВЛЕНИЕ ДВИЖЕНИЯ"
    rotated = Image.new("RGBA", (400, 50), (255, 255, 255, 0))
    rotated_draw = ImageDraw.Draw(rotated)
    rotated_draw.text((0, 5), label, font=label_font, fill=MUTED)
    rotated = rotated.rotate(90, expand=True)
    canvas.paste(rotated, (55, 310), rotated)
    return _png(canvas)


def render_lift_assembly(section: object, calc: object) -> bytes:
    panels = list(getattr(calc, "panels", None) or [])
    count = max(len(panels), 1)
    canvas = Image.new("RGB", (1600, 520), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(28, bold=True)
    number_font = load_font(30, bold=True)
    label_font = load_font(18, bold=True)
    _center_text(draw, (800, 30), "ПАНЕЛИ ПРИ СКЛЕЙКЕ", title_font)
    gap = 20
    card_width = (1500 - gap * (count - 1)) / count
    fill_color = glass_fill(getattr(calc, "filling_text", ""))
    for index, panel in enumerate(panels):
        left = 50 + index * (card_width + gap)
        right = left + card_width
        top, bottom = 75, 475
        draw.rectangle((left, top, right, bottom), outline=GRID, width=2)
        fill_box = (left + 50, top + 65, right - 50, bottom - 95)
        draw.rectangle(fill_box, fill=fill_color, outline=INK, width=3)
        _center_text(
            draw,
            ((fill_box[0] + fill_box[2]) / 2, (fill_box[1] + fill_box[3]) / 2),
            str(panel.panel),
            number_font,
        )
        _center_text(
            draw,
            ((left + right) / 2, bottom - 60),
            f"ЗАПОЛНЕНИЕ {glass_mm(panel.width_mm)} × {glass_mm(panel.height_mm)}",
            label_font,
        )
        _center_text(
            draw,
            ((left + right) / 2, bottom - 28),
            f"СКЛЕЙКА {glass_mm(panel.glued_width_mm)} × {glass_mm(panel.glued_height_mm)}",
            label_font,
            "#006FA8",
        )
    return _png(canvas)


def render_book_room(section: object, calc: object) -> bytes:
    canvas = Image.new("RGB", (1600, 760), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)
    number_font = load_font(23, bold=True)
    role_font = load_font(15, bold=True)
    dim_font = load_font(19, bold=True)
    _center_text(draw, (800, 34), "ВИД ИЗ ПОМЕЩЕНИЯ", title_font)

    section_width = max(float(getattr(section, "width", 0) or 0), 1)
    section_height = max(float(getattr(section, "height", 0) or 0), 1)
    drawing_width, drawing_height = _fit_rect(
        section_width,
        section_height,
        1320,
        500,
    )
    left = (1600 - drawing_width) // 2
    top = 82 + max(0, (500 - drawing_height) // 2)
    right = left + drawing_width
    bottom = top + drawing_height
    draw.line((left - 8, top - 9, right + 8, top - 9), fill=INK, width=8)
    draw.line((left - 8, bottom + 9, right + 8, bottom + 9), fill=INK, width=8)

    panels = list(getattr(calc, "panels", []) or [])
    total_panel_width = (
        sum(max(float(getattr(panel, "panel_width_mm", 0) or 0), 1) for panel in panels)
        or 1
    )
    x = left
    config = getattr(calc, "normalized_config", {}) or {}
    handle_height = float(config.get("handle_height_mm") or 1000)
    handle_y = bottom - min(1.0, max(0.0, handle_height / section_height)) * drawing_height
    for panel in panels:
        panel_width = max(float(getattr(panel, "panel_width_mm", 0) or 0), 1)
        panel_px = drawing_width * panel_width / total_panel_width
        panel_left = round(x)
        panel_right = round(x + panel_px)
        role = str(getattr(panel, "role", "standard") or "standard")
        filling = str(getattr(panel, "glass_type", "") or "")
        fill = glass_fill(filling)
        outline = "#D97706" if role == "fixed" else INK
        draw.rectangle(
            (panel_left + 2, top, panel_right - 2, bottom),
            fill=fill,
            outline=outline,
            width=4 if role in {"door", "moving_door", "fixed"} else 2,
        )
        if glass_is_matte(filling):
            _matte_pattern(
                draw,
                (panel_left + 4, top + 4, panel_right - 4, bottom - 4),
            )
        center_x = (panel_left + panel_right) / 2
        _center_text(
            draw,
            (center_x, top + 48),
            str(getattr(panel, "number", "")),
            number_font,
        )
        if role == "fixed":
            draw.line(
                (panel_left + 12, top + 12, panel_right - 12, bottom - 12),
                fill="#B7791F",
                width=2,
            )
            draw.line(
                (panel_right - 12, top + 12, panel_left + 12, bottom - 12),
                fill="#B7791F",
                width=2,
            )
            _center_text(draw, (center_x, top + 80), "ГЛУХАЯ", role_font, "#9A620F")
        direction = str(getattr(panel, "movement_direction", "none") or "none")
        if direction != "none":
            span = min(70, max(24, panel_px * 0.22))
            if direction == "left":
                _arrow(
                    draw, (center_x + span, bottom - 60), (center_x - span, bottom - 60)
                )
            else:
                _arrow(
                    draw, (center_x - span, bottom - 60), (center_x + span, bottom - 60)
                )
        if role in {"door", "moving_door"}:
            side = str(getattr(panel, "door_side", "") or "")
            converges_right = side == "left" or (not side and direction == "left")
            outer_x = panel_left + 12 if converges_right else panel_right - 12
            convergence_x = panel_right - 12 if converges_right else panel_left + 12
            draw.line(
                (outer_x, top + drawing_height * 0.30, convergence_x, top + drawing_height * 0.50),
                fill=INK,
                width=4,
            )
            draw.line(
                (convergence_x, top + drawing_height * 0.50, outer_x, top + drawing_height * 0.70),
                fill=INK,
                width=4,
            )
            hardware_x = panel_left + panel_px * (0.72 if converges_right else 0.28)
            radius = 9 if str(getattr(panel, "door_hardware", "")) == "lock" else 6
            draw.ellipse(
                (hardware_x - radius, handle_y - radius, hardware_x + radius, handle_y + radius),
                outline=INK,
                width=3,
            )
        _center_text(
            draw,
            (center_x, bottom + 38),
            _format_book_dimension(getattr(panel, "glass_width_mm", 0)),
            _fitted_font(
                draw,
                _format_book_dimension(getattr(panel, "glass_width_mm", 0)),
                panel_px - 8,
                21,
            ),
            RED,
        )
        x += panel_px

    draw.line((left, bottom + 73, right, bottom + 73), fill=INK, width=2)
    draw.line((left, bottom + 62, left, bottom + 84), fill=INK, width=2)
    draw.line((right, bottom + 62, right, bottom + 84), fill=INK, width=2)
    _center_text(
        draw,
        (800, bottom + 104),
        f"{_format_book_dimension(section_width)} ММ",
        dim_font,
        RED,
    )
    height_label = Image.new("RGBA", (240, 54), (255, 255, 255, 0))
    height_draw = ImageDraw.Draw(height_label)
    _center_text(
        height_draw,
        (120, 27),
        f"{_format_book_dimension(section_height)} ММ",
        dim_font,
        RED,
    )
    height_label = height_label.rotate(90, expand=True)
    canvas.paste(height_label, (right + 25, int((top + bottom - height_label.height) / 2)), height_label)
    return _cropped_png(canvas)


def _format_book_dimension(value: object) -> str:
    number = round(float(value or 0), 1)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}".replace(".", ",")


def render_book_top(section: object, calc: object) -> bytes:
    canvas = Image.new("RGB", (1600, 660), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    number_font = load_font(19, bold=True)
    dim_font = load_font(20, bold=True)
    label_font = load_font(17, bold=True)
    left, right = 120, 1480
    guide_y = 300
    _center_text(draw, (800, 32), "УЛИЦА", label_font, MUTED)
    _center_text(draw, (800, 490), "ПОМЕЩЕНИЕ", label_font, MUTED)
    draw.line((left, guide_y - 12, right, guide_y - 12), fill=GRID, width=2)
    draw.line((left, guide_y, right, guide_y), fill=INK, width=8)
    draw.line((left, guide_y + 12, right, guide_y + 12), fill=GRID, width=2)

    panels = list(getattr(calc, "panels", []) or [])
    total_width = (
        sum(max(float(getattr(panel, "panel_width_mm", 0) or 0), 1) for panel in panels)
        or 1
    )
    x = left
    for panel in panels:
        logical_width = max(float(getattr(panel, "panel_width_mm", 0) or 0), 1)
        panel_px = (right - left) * logical_width / total_width
        panel_left = round(x)
        panel_right = round(x + panel_px)
        center_x = (panel_left + panel_right) / 2
        role = str(getattr(panel, "role", "standard") or "standard")
        if role == "fixed":
            draw.rectangle(
                (panel_left + 3, guide_y - 14, panel_right - 3, guide_y + 14),
                fill="#F6D89B",
                outline="#B7791F",
                width=3,
            )
            _center_text(draw, (center_x, guide_y), "Г", number_font, "#8B5A14")
        x += panel_px

    config = getattr(calc, "normalized_config", {}) or {}
    legacy_left_angle = float(config.get("angle_left_deg") or 0)
    legacy_right_angle = float(config.get("angle_right_deg") or 0)
    if legacy_left_angle > 0:
        radians = math.radians(180 - legacy_left_angle)
        draw.line(
            (
                left,
                guide_y,
                left + math.cos(radians) * 170,
                guide_y - math.sin(radians) * 170,
            ),
            fill="#B7791F",
            width=8,
        )
    if legacy_right_angle > 0:
        radians = math.radians(180 - legacy_right_angle)
        draw.line(
            (
                right,
                guide_y,
                right - math.cos(radians) * 170,
                guide_y - math.sin(radians) * 170,
            ),
            fill="#B7791F",
            width=8,
        )
    for direction in ("left", "right"):
        stack = [
            panel
            for panel in panels
            if str(getattr(panel, "role", "")) != "fixed"
            and str(getattr(panel, "movement_direction", "")) == direction
        ]
        if not stack:
            continue
        door = next(
            (
                panel
                for panel in stack
                if str(getattr(panel, "role", "")) in {"door", "moving_door"}
            ),
            None,
        )
        opening = str(getattr(door, "door_opening", "inside_in") or "inside_in")
        room_side = opening in {"inside_in", "outside_in"}
        y_end = guide_y + (155 if room_side else -155)
        base_x = left + 22 if direction == "left" else right - 22
        x_step = 18 if direction == "left" else -18
        for index, panel in enumerate(stack):
            leaf_x = base_x + x_step * index
            role = str(getattr(panel, "role", "standard") or "standard")
            color = "#C05621" if role == "moving_door" else INK
            width_px = 6 if role == "door" else 4
            draw.line((leaf_x, guide_y, leaf_x, y_end), fill=color, width=width_px)
            _center_text(
                draw,
                (leaf_x, y_end + (18 if room_side else -18)),
                str(getattr(panel, "number", "")),
                number_font,
            )
        if direction == "left":
            _arrow(draw, (left + 300, guide_y), (left + 70, guide_y))
        else:
            _arrow(draw, (right - 300, guide_y), (right - 70, guide_y))

    obstacle = float(config.get("obstacle_distance_mm") or 0)
    if obstacle > 0:
        active_sides: set[str] = set()
        for panel in panels:
            if str(getattr(panel, "role", "")) not in {"door", "moving_door"}:
                continue
            opening = str(getattr(panel, "door_opening", "inside_in") or "inside_in")
            active_sides.add("room" if opening in {"inside_in", "outside_in"} else "street")
        for active_side in active_sides or {"room"}:
            obstacle_y = 525 if active_side == "room" else 72
            draw.line((left, obstacle_y, right, obstacle_y), fill=RED, width=3)
            _center_text(
                draw,
                (800, obstacle_y + (24 if active_side == "room" else 22)),
                f"ДО ПРЕПЯТСТВИЯ {_format_book_dimension(obstacle)} ММ",
                label_font,
                RED,
            )
    draw.line((left, 595, right, 595), fill=INK, width=2)
    draw.line((left, 583, left, 607), fill=INK, width=2)
    draw.line((right, 583, right, 607), fill=INK, width=2)
    _center_text(
        draw,
        (800, 630),
        f"{_format_book_dimension(getattr(section, 'width', 0))} ММ",
        dim_font,
        RED,
    )
    return _png(canvas)


def section_diagrams(
    section: object,
    calc: object,
) -> list[tuple[str, bytes]]:
    system = str(getattr(section, "system", "") or "").strip().upper()
    if system == "КНИЖКА":
        return [
            ("Вид из помещения", render_book_room(section, calc)),
            ("Схема · вид сверху", render_book_top(section, calc)),
        ]
    reference = _reference_diagrams(section, calc)
    if system == "ЛИФТ":
        if len(reference) >= 2:
            return [
                *reference[:2],
                ("Панели при склейке", render_lift_assembly(section, calc)),
            ]
        return [
            ("Вид из помещения", render_lift_front(section, calc)),
            ("Кинематическая схема", render_lift_kinematic(section, calc)),
            ("Панели при склейке", render_lift_assembly(section, calc)),
        ]
    if len(reference) >= 2:
        return reference[:2]
    return [
        ("Вид из помещения", render_slide_room(section, calc)),
        ("Схема · вид сверху", render_slide_top(section, calc)),
    ]
