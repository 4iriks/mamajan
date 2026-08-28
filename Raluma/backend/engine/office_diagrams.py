"""Raster diagrams used by editable Office exports.

The PDF/HTML documents keep their native SVG diagrams. Office files receive
high-resolution PNG equivalents so tables remain editable while schemes stay
stable in Word and Excel.
"""

from __future__ import annotations

import io
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
            14,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
        panel_font_size = _print_font_pixels(
            17,
            print_crop_width,
            print_crop_height,
            max_width_mm=print_max_width_mm,
            max_height_mm=82,
        )
        dimension_font_size = _print_font_pixels(
            19,
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
    for index, panel_width in enumerate(widths):
        panel_px = inner_width * panel_width / width_sum
        panel_left = round(x)
        panel_right = round(x + panel_px)
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
    number_font = load_font(28, bold=True)
    role_font = load_font(17, bold=True)
    dim_font = load_font(21, bold=True)
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
    role_names = {
        "standard": "ПАНЕЛЬ",
        "door": "ДВЕРЬ",
        "fixed": "ГЛУХАЯ",
        "moving_door": "ДОП. ДВЕРЬ",
    }
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
        _center_text(
            draw,
            (center_x, top + 78),
            role_names.get(role, role.upper()),
            role_font,
            MUTED,
        )
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
        f"{_format_book_dimension(section_width)} × {_format_book_dimension(section_height)} ММ",
        dim_font,
        RED,
    )
    return _png(canvas)


def _format_book_dimension(value: object) -> str:
    number = round(float(value or 0), 1)
    if number == int(number):
        return str(int(number))
    return f"{number:.1f}".replace(".", ",")


def render_book_top(section: object, calc: object) -> bytes:
    canvas = Image.new("RGB", (1600, 560), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, bold=True)
    number_font = load_font(24, bold=True)
    dim_font = load_font(20, bold=True)
    label_font = load_font(17, bold=True)
    _center_text(draw, (800, 34), "СХЕМА · ВИД СВЕРХУ", title_font)
    left, right = 100, 1500
    guide_y = 108
    draw.rounded_rectangle(
        (left, guide_y - 10, right, guide_y + 10),
        radius=4,
        fill="#DDE7E9",
        outline=GRID,
        width=2,
    )
    _center_text(draw, (800, 80), "ПРОЁМ / НАПРАВЛЯЮЩАЯ", label_font, MUTED)

    panels = list(getattr(calc, "panels", []) or [])
    total_width = (
        sum(max(float(getattr(panel, "panel_width_mm", 0) or 0), 1) for panel in panels)
        or 1
    )
    x = left
    panel_y = 180
    for panel in panels:
        logical_width = max(float(getattr(panel, "panel_width_mm", 0) or 0), 1)
        panel_px = (right - left) * logical_width / total_width
        panel_left = round(x)
        panel_right = round(x + panel_px)
        center_x = (panel_left + panel_right) / 2
        role = str(getattr(panel, "role", "standard") or "standard")
        color = "#F59E0B" if role == "fixed" else "#B8D7DC"
        draw.rounded_rectangle(
            (panel_left + 3, panel_y - 16, panel_right - 3, panel_y + 16),
            radius=4,
            fill=color,
            outline="#F97316" if role == "moving_door" else INK,
            width=4 if role in {"door", "moving_door"} else 2,
        )
        _center_text(
            draw,
            (center_x, panel_y - 43),
            str(getattr(panel, "number", "")),
            number_font,
        )
        direction = str(getattr(panel, "movement_direction", "none") or "none")
        if direction != "none":
            span = min(72, max(25, panel_px * 0.23))
            if direction == "left":
                _arrow(
                    draw,
                    (center_x + span, panel_y + 70),
                    (center_x - span, panel_y + 70),
                )
            else:
                _arrow(
                    draw,
                    (center_x - span, panel_y + 70),
                    (center_x + span, panel_y + 70),
                )
        if role in {"door", "moving_door"}:
            radius = min(95, max(42, panel_px * 0.45))
            hinge_x = (
                panel_right - 5
                if getattr(panel, "door_side", "") == "right"
                else panel_left + 5
            )
            box = (
                hinge_x - radius,
                panel_y - radius,
                hinge_x + radius,
                panel_y + radius,
            )
            draw.arc(box, start=15, end=90, fill=INK, width=3)
        x += panel_px

    config = getattr(calc, "normalized_config", {}) or {}
    obstacle = float(config.get("obstacle_distance_mm") or 0)
    if obstacle > 0:
        obstacle_y = 350
        draw.line((left, obstacle_y, right, obstacle_y), fill=RED, width=3)
        _center_text(
            draw,
            (800, obstacle_y + 30),
            f"ПРЕПЯТСТВИЕ · {_format_book_dimension(obstacle)} ММ",
            label_font,
            RED,
        )
    draw.line((left, 460, right, 460), fill=INK, width=2)
    draw.line((left, 448, left, 472), fill=INK, width=2)
    draw.line((right, 448, right, 472), fill=INK, width=2)
    _center_text(
        draw,
        (800, 500),
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
