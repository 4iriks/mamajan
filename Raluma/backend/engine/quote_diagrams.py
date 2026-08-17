"""Stable quote sketches rendered from the public, frozen section snapshot."""

from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from typing import Any

from PIL import Image, ImageDraw

from engine.office_common import load_font


INK = "#123F47"
MUTED = "#667B80"
GRID = "#A8BBC0"
BACKGROUND = "#FFFFFF"
GLASS_COLORS = {
    "clear": "#DCEFF3",
    "bronze": "#E4C39F",
    "gray": "#C9D0D3",
    "matte": "#E5E8E7",
    "clarified": "#EEFAF8",
    "triplex": "#D3EADB",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(Decimal(str(value).replace(",", ".")))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _glass_fill(value: Any) -> str:
    text = str(value or "").upper()
    if "БЕЗ СТЕКЛА" in text:
        return BACKGROUND
    if "БРОНЗ" in text:
        return GLASS_COLORS["bronze"]
    if "СЕРО" in text:
        return GLASS_COLORS["gray"]
    if "МАТ" in text:
        return GLASS_COLORS["matte"]
    if "ПРОСВЕТ" in text:
        return GLASS_COLORS["clarified"]
    if "ТРИПЛЕКС" in text:
        return GLASS_COLORS["triplex"]
    return GLASS_COLORS["clear"]


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font,
    fill: str = INK,
) -> None:
    width, height = _text_size(draw, text, font)
    draw.text((xy[0] - width / 2, xy[1] - height / 2), text, font=font, fill=fill)


def _fitted_font(draw: ImageDraw.ImageDraw, text: str, max_width: float, *, preferred: int = 24):
    """Return the largest readable dimension font which fits its panel."""
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
    start_head: bool = False,
    end_head: bool = True,
    width: int = 4,
) -> None:
    draw.line((start, end), fill=INK, width=width)

    def head(tip: tuple[float, float], tail: tuple[float, float]) -> None:
        dx = tip[0] - tail[0]
        dy = tip[1] - tail[1]
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        size = 13
        draw.polygon(
            (
                tip,
                (tip[0] - ux * size + px * size * 0.55, tip[1] - uy * size + py * size * 0.55),
                (tip[0] - ux * size - px * size * 0.55, tip[1] - uy * size - py * size * 0.55),
            ),
            fill=INK,
        )

    if end_head:
        head(end, start)
    if start_head:
        head(start, end)


def _matte_pattern(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    for y in range(box[1] + 9, box[3] - 3, 14):
        for x in range(box[0] + 9, box[2] - 3, 14):
            draw.ellipse((x, y, x + 2, y + 2), fill="#8E9A9C")


def _geometry(details: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in details.get("panel_geometry") or [] if isinstance(row, dict)]
    return rows or [
        {
            "index": 1,
            "number": 1,
            "width_mm": details.get("width_mm") or 1,
            "rail": 0,
            "direction": "right",
            "deaf": False,
        }
    ]


def render_quote_room_png(details: dict[str, Any]) -> bytes:
    canvas = Image.new("RGB", (1800, 720), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(31, bold=True)
    number_font = load_font(31, bold=True)
    dimension_font = load_font(22, bold=True)
    small_font = load_font(18)
    _center_text(draw, (900, 34), "ВИД ИЗ ПОМЕЩЕНИЯ", title_font)

    section_width = max(_number(details.get("width_mm"), 1), 1)
    section_height = max(_number(details.get("height_mm"), 1), 1)
    scale = min(1500 / section_width, 470 / section_height)
    drawing_width = max(1, round(section_width * scale))
    drawing_height = max(1, round(section_height * scale))
    left = (1800 - drawing_width) // 2
    top = 85 + max(0, (470 - drawing_height) // 2)
    right = left + drawing_width
    bottom = top + drawing_height
    draw.rectangle((left, top, right, bottom), outline=INK, width=7)
    draw.rectangle((left + 10, top + 10, right - 10, bottom - 10), outline=GRID, width=2)

    rows = _geometry(details)
    widths = [max(_number(row.get("width_mm"), 1), 1) for row in rows]
    width_total = sum(widths) or len(widths)
    fill = _glass_fill(details.get("glass_type"))
    matte = "МАТ" in str(details.get("glass_type") or "").upper()
    x = left + 12
    inner_width = drawing_width - 24
    for row, width_mm in zip(rows, widths):
        panel_px = inner_width * width_mm / width_total
        panel_left = round(x)
        panel_right = round(x + panel_px)
        box = (panel_left, top + 12, panel_right, bottom - 12)
        draw.rectangle(box, fill=fill, outline=GRID, width=2)
        if matte:
            _matte_pattern(draw, box)
        cx = (panel_left + panel_right) / 2
        cy = (top + bottom) / 2
        _center_text(draw, (cx, cy - 28), str(row.get("number") or row.get("index") or ""), number_font)
        if bool(row.get("deaf")) or row.get("direction") == "none":
            draw.line((panel_left + 12, top + 22, panel_right - 12, bottom - 22), fill=GRID, width=3)
            draw.line((panel_right - 12, top + 22, panel_left + 12, bottom - 22), fill=GRID, width=3)
        else:
            direction = str(row.get("direction") or "right")
            start = (cx - 34, cy + 24)
            end = (cx + 34, cy + 24)
            _arrow(
                draw,
                start,
                end,
                start_head=direction in {"left", "both"},
                end_head=direction in {"right", "both"},
            )
        width_label = str(round(width_mm))
        panel_dimension_font = _fitted_font(draw, width_label, panel_px - 8)
        _center_text(draw, (cx, bottom + 34), width_label, panel_dimension_font)
        x += panel_px

    draw.line((left, bottom + 61, right, bottom + 61), fill=GRID, width=2)
    _center_text(draw, ((left + right) / 2, bottom + 92), str(round(section_width)), dimension_font)
    draw.line((right + 36, top, right + 36, bottom), fill=GRID, width=2)
    _center_text(draw, (right + 76, (top + bottom) / 2), str(round(section_height)), dimension_font)
    _center_text(draw, ((left + right) / 2, top - 24), "УЛИЦА", small_font, MUTED)
    _center_text(draw, ((left + right) / 2, bottom + 126), "ПОМЕЩЕНИЕ", small_font, MUTED)
    return _png(canvas)


def render_quote_top_png(details: dict[str, Any]) -> bytes:
    canvas = Image.new("RGB", (1800, 720), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(31, bold=True)
    label_font = load_font(20, bold=True)
    small_font = load_font(18)
    _center_text(draw, (900, 34), "ВИД СВЕРХУ", title_font)

    left, top, right, bottom = 130, 95, 1670, 510
    rails = max(int(_number(details.get("rails"), 1)), 1)
    row_height = (bottom - top) / rails
    draw.rectangle((left, top, right, bottom), outline=INK, width=4)
    for rail in range(1, rails):
        y = top + rail * row_height
        draw.line((left, y, right, y), fill=GRID, width=2)

    rows = _geometry(details)
    widths = [max(_number(row.get("width_mm"), 1), 1) for row in rows]
    width_total = sum(widths) or len(widths)
    fill = _glass_fill(details.get("glass_type"))
    matte = "МАТ" in str(details.get("glass_type") or "").upper()
    x = left
    for row, width_mm in zip(rows, widths):
        panel_px = (right - left) * width_mm / width_total
        rail = max(0, min(rails - 1, int(_number(row.get("rail"), 0))))
        cy = top + (rail + 0.5) * row_height
        x1 = round(x + 4)
        x2 = round(x + panel_px - 4)
        y1 = round(cy - min(21, row_height * 0.28))
        y2 = round(cy + min(21, row_height * 0.28))
        box = (x1, y1, x2, y2)
        draw.rectangle(box, fill=fill, outline=INK, width=3)
        if matte:
            _matte_pattern(draw, box)
        _center_text(
            draw,
            ((x1 + x2) / 2, (y1 + y2) / 2),
            f"{round(width_mm)} · №{row.get('number') or row.get('index')}",
            label_font,
        )
        x += panel_px

    _center_text(draw, (900, 72), "УЛИЦА", small_font, MUTED)
    _center_text(draw, (900, 548), "ПОМЕЩЕНИЕ", small_font, MUTED)
    direction = str(details.get("slide_direction") or "right")
    _arrow(
        draw,
        (820, 596),
        (980, 596),
        start_head=direction in {"left", "both"},
        end_head=direction in {"right", "both"},
        width=3,
    )
    _center_text(draw, (900, 630), "НАПРАВЛЕНИЕ СДВИГА", small_font, MUTED)
    return _png(canvas)
