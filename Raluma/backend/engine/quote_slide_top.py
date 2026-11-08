"""Portable SVG counterpart of the editor's SlideSchemeSVG, using frozen inputs."""

import base64
import io
import re
from xml.etree import ElementTree as ET

from PIL import Image

INK = "#123f47"
OPTION_FIELDS = {
    *(
        f"profile_{side}_{kind}"
        for side in ("left", "right")
        for kind in ("wall", "lock_bar", "p_bar", "handle_bar", "bubble")
    ),
    "center_handle",
    "inter_glass_profile",
    "inter_glass_width_mm",
}
# Source image bounds and display sizes match SlideDiagrams.tsx.
ASSEMBLIES = {
    "lock-handle": ("SIDE_RS2081_RS112.png", 584, 383, (33, 0, 583, 364), 60, 1.16, 30),
    "p-handle": ("SIDE_RS1082_RS112.png", 389, 401, (36, 14, 357, 379), 60, 1.16, 28),
    "p-bubble": ("SIDE_RS1082_RS1002.png", 249, 245, (42, 38, 220, 215), 44, 1, 32),
    "bubble": ("SIDE_RS1002.png", 177, 133, (17, 21, 149, 108), 32, 1, 28),
}


def snapshot_top_options(section, calc):
    from engine.pdf import profile_dimension

    options = {
        key: getattr(section, key, None)
        for key in OPTION_FIELDS
        if key != "inter_glass_width_mm"
    }
    inter = str(options.get("inter_glass_profile") or "").lower()
    article = (
        "RS1006"
        if "rs1006" in inter
        else (
            "RS3061"
            if any(value in inter for value in ("rs3061", "rs1004", "зацеп"))
            else "RS2061"
        )
    )
    options["inter_glass_width_mm"] = profile_dimension(
        calc, [article], "section_width_mm", 20
    )
    return options


def _options(details):
    """Old fixed quotes already contain the selected articles; never read the live section."""
    options = {}
    for side in ("left", "right"):
        articles = {
            row.get("article") for row in details.get(f"technical_{side}") or []
        }
        for kind, codes in {
            "wall": {"RS2333", "RS2335"},
            "lock_bar": {"RS2081"},
            "p_bar": {"RS1082"},
            "handle_bar": {"RS112"},
            "bubble": {"RS1002"},
        }.items():
            options[f"profile_{side}_{kind}"] = bool(articles & codes)
    common = details.get("technical_common") or []
    options["inter_glass_profile"] = next(
        (
            row["article"]
            for row in common
            if row.get("article") in {"RS2061", "RS3061", "RS1004", "RS1006"}
        ),
        "",
    )
    options["center_handle"] = next(
        (
            row["article"]
            for row in common
            if row.get("article") in {"RS112", "RS3014", "RS3017", "RS30201"}
        ),
        "",
    )
    options["inter_glass_width_mm"] = 20
    saved = details.get("top_view_options")
    if isinstance(saved, dict):
        options.update(
            {key: value for key, value in saved.items() if key in OPTION_FIELDS}
        )
    return options


def _assembly(options, side):
    def selected(kind):
        return options.get(f"profile_{side}_{kind}")

    if selected("lock_bar") and selected("handle_bar"):
        return "lock-handle"
    if selected("p_bar") and selected("handle_bar"):
        return "p-handle"
    if selected("p_bar") and selected("bubble"):
        return "p-bubble"
    return "bubble" if selected("bubble") else None


def _image_uri(filename, opacity):
    # Pre-tint PNGs: SVG filters are not rendered consistently by PDF and Word.
    from engine.pdf import get_profile_asset_path

    path = get_profile_asset_path(filename)
    if path is None:
        raise FileNotFoundError(f"Missing diagram profile asset: {filename}")
    with Image.open(path) as original:
        alpha = (
            original.convert("RGBA")
            .getchannel("A")
            .point(lambda value: round(value * opacity))
        )
        tinted = Image.new("RGBA", original.size, INK)
        tinted.putalpha(alpha)
    output = io.BytesIO()
    tinted.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(
        "ascii"
    )


def render_quote_top_svg(details, key="top"):
    from engine.pdf import glass_fill, glass_is_matte, glass_mm

    options = _options(details)
    rows = details.get("panel_geometry") or []
    if not rows:
        return ""
    rails = max(int(details.get("rails") or 3), 1)
    two_rows = int(details.get("slide_rows") or 1) == 2
    first_right = details.get("first_panel_inside", "Справа") == "Справа"
    widths = [max(glass_mm(row.get("width_mm")), 1) for row in rows]
    width_total = sum(widths)
    panel_rails = [max(0, min(rails - 1, int(row.get("rail") or 0))) for row in rows]
    count = len(rows)
    row_height, top, left, span = 34, 28, 130, 500
    bottom = top + rails * row_height
    height = bottom + 42
    scale = span / max(float(details.get("width_mm") or width_total), 1)
    center_gap = max(1, 3 * scale) if two_rows else 0
    variants = {side: _assembly(options, side) for side in ("left", "right")}
    images = {}
    for side, variant in variants.items():
        if variant:
            filename, w, h, bounds, display_h, stretch, depth = ASSEMBLIES[variant]
            x0, y0, x1, y1 = bounds
            sy = display_h / (y1 - y0 + 1)
            sx = sy * stretch
            images[side] = dict(
                filename=filename,
                width=w * sx,
                height=h * sy,
                x=-x1 * sx,
                y=-(y0 + y1) / 2 * sy,
                visible=(x1 - x0 + 1) * sx,
                depth=depth,
            )
    scheme_left = left - images["left"]["visible"] + 12 if "left" in images else left
    scheme_right = (
        left + span + images["right"]["visible"] - 12
        if "right" in images
        else left + span
    )
    wall_overlap = 11 if rails == 5 else 8
    outer_left = (
        scheme_left - 34 + wall_overlap
        if options.get("profile_left_wall")
        else scheme_left
    )
    outer_right = (
        scheme_right + 34 - wall_overlap
        if options.get("profile_right_wall")
        else scheme_right
    )
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "role": "img",
            "aria-label": "Вид сверху",
            "data-quote-top-view": "detailed",
            "viewBox": f"{outer_left - 12} 0 {outer_right - outer_left + 24} {height}",
        },
    )

    def add(tag, parent=None, **attrs):
        return ET.SubElement(
            parent if parent is not None else root,
            tag,
            {k.replace("_", "-"): str(v) for k, v in attrs.items() if v is not None},
        )

    def line(x1, y1, x2, y2, **attrs):
        return add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=INK, **attrs)

    def text(x, y, value, size=8, **attrs):
        node = add(
            "text",
            x=x,
            y=y,
            font_size=size,
            font_family="Arial",
            fill=INK,
            font_weight="bold",
            text_anchor=attrs.pop("text_anchor", "middle"),
            **attrs,
        )
        node.text = str(value)

    glass_type = str(details.get("glass_type") or "")
    supplied = (
        details.get("glass_supplied") is not False
        and "БЕЗ СТЕКЛА" not in glass_type.upper()
    )
    fill = glass_fill(glass_type) if supplied else "#ffffff"
    matte = supplied and glass_is_matte(glass_type)
    pattern_id = "quote-top-matte-" + re.sub(r"[^a-zA-Z0-9_-]", "", str(key))
    if matte:
        defs = add("defs")
        pattern = add(
            "pattern",
            defs,
            id=pattern_id,
            width=5,
            height=5,
            patternUnits="userSpaceOnUse",
            data_glass_pattern="matte",
        )
        add("rect", pattern, width=5, height=5, fill=fill)
        add("circle", pattern, cx=1.25, cy=1.25, r=0.65, fill=INK, fill_opacity=0.48)
    text(380, 12, "УЛИЦА", fill_opacity=0.45, letter_spacing=1.5)
    text(380, bottom + 14, "ПОМЕЩЕНИЕ", fill_opacity=0.45, letter_spacing=1.5)
    for y in (top - 2, bottom + 2):
        line(scheme_left, y, scheme_right, y, stroke_width=1.5, stroke_opacity=0.5)
    for x in (scheme_left, scheme_right):
        line(x, top - 4, x, bottom + 4, stroke_width=2, stroke_opacity=0.5)
    for side in ("left", "right"):
        if not options.get(f"profile_{side}_wall"):
            continue
        article = "RS2335" if rails == 5 else "RS2333"
        wall_x = (
            scheme_left - 34 + wall_overlap
            if side == "left"
            else scheme_right - wall_overlap
        )
        wall_y, wall_h = top - 8, rails * row_height + 16
        transform = (
            f"translate({wall_x} {wall_y + wall_h}) rotate(-90)"
            if side == "left"
            else f"translate({wall_x + 34} {wall_y}) rotate(90)"
        )
        group = add("g", data_profile_image=f"{article}-{side}", transform=transform)
        add(
            "image",
            group,
            href=_image_uri(article + ".png", 0.72),
            x=0,
            y=0,
            width=wall_h,
            height=34,
            preserveAspectRatio="none",
        )
    for rail in range(rails):
        unused = rail not in panel_rails
        cy = top + (rail + 0.5) * row_height
        line(
            scheme_left,
            cy,
            scheme_right,
            cy,
            stroke_width=1 if unused else 1.5,
            stroke_opacity=0.22 if unused else 0.55,
            stroke_dasharray="5 5" if unused else None,
        )
    layout = []
    cursor = left
    for index, (row, width) in enumerate(zip(rows, widths, strict=True)):
        panel_width = width / width_total * span
        x1 = cursor + (5 if index == 0 else -6)
        x2 = cursor + panel_width + (-5 if index == count - 1 else 6)
        if index == 0 and "left" in images:
            x1 = left + 16 - images["left"]["depth"]
        if index == count - 1 and "right" in images:
            x2 = left + span - 16 + images["right"]["depth"]
        if two_rows and index == count // 2 - 1:
            x2 = cursor + panel_width - center_gap / 2
        elif two_rows and index == count // 2:
            x1 = cursor + center_gap / 2
        cy = top + (panel_rails[index] + 0.5) * row_height
        layout.append((cursor, panel_width, x1, x2, cy))
        number = row.get("number") or row.get("index") or index + 1
        add(
            "rect",
            x=x1,
            y=cy - 6,
            width=max(1, x2 - x1),
            height=12,
            rx=2,
            data_quote_top_panel=number,
            data_rail=panel_rails[index],
            data_scheme_panel=index + 1,
            data_glass_fill=fill,
            data_glass_pattern="matte" if matte else None,
            fill=f"url(#{pattern_id})" if matte else fill,
            fill_opacity=0.52,
            stroke=INK,
            stroke_width=1.4,
            stroke_opacity=0.9,
        )
        label = f"{width} · №{number}"
        text(
            cursor + panel_width / 2,
            cy + 5,
            label,
            size=max(6, min(11, panel_width / max(2.5, len(label) * 0.62))),
        )
        cursor += panel_width
    if two_rows and "rs112" in str(options.get("center_handle") or "").lower():
        for side, index in (("left", count // 2 - 1), ("right", count // 2)):
            px, pw, _, _, cy = layout[index]
            x = (
                px + pw - center_gap / 2 - 4
                if side == "left"
                else px + center_gap / 2 + 4
            )
            end = x - 9 if side == "left" else x + 9
            group = add("g", data_center_rs112_top=side, data_profile_width_mm=40)
            for a, b, c, d, w in [
                (x, cy - 14, x, cy + 14, 2),
                (x - 5, cy - 14, x + 5, cy - 14, 2),
                (x - 5, cy + 14, x + 5, cy + 14, 2),
                (x, cy - 3, end, cy - 3, 1.4),
                (x, cy + 3, end, cy + 3, 1.4),
            ]:
                add(
                    "line",
                    group,
                    x1=a,
                    y1=b,
                    x2=c,
                    y2=d,
                    stroke=INK,
                    stroke_width=w,
                    stroke_opacity=0.82,
                )
    inter = str(options.get("inter_glass_profile") or "").lower()
    if inter and "без" not in inter:
        iw = max(6, float(options.get("inter_glass_width_mm") or 20) * scale)
        for index in range(count - 1):
            if two_rows and index == count // 2 - 1:
                continue
            next_panel = index < count / 2 if two_rows else first_right
            owner = index + 1 if next_panel else index
            _, _, x1, x2, cy = layout[owner]
            x = x1 if next_panel else x2
            direction = 1 if next_panel else -1
            inner = x + direction * iw
            add(
                "path",
                data_profile="inter-glass",
                data_dir=direction,
                d=f"M {inner} {cy - 10} L {x} {cy - 10} L {x} {cy + 10} L {inner} {cy + 10}",
                fill="none",
                stroke=INK,
                stroke_width=1.6,
                stroke_opacity=0.72,
                stroke_linecap="round",
                stroke_linejoin="round",
            )
            line(x, cy - 6, inner, cy - 6, stroke_width=0.9, stroke_opacity=0.45)
    for side, data in images.items():
        index = 0 if side == "left" else count - 1
        x = left + 16 if side == "left" else left + span - 16
        group = add(
            "g",
            data_side_assembly=variants[side],
            transform=f"translate({x} {layout[index][4]})"
            + (" scale(-1 1)" if side == "right" else ""),
        )
        add(
            "image",
            group,
            data_side_assembly_image=data["filename"],
            href=_image_uri(data["filename"], 0.82),
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
            preserveAspectRatio="none",
        )
    ay, ax = bottom + 22, 380
    line(ax - 65, ay, ax + 65, ay, stroke_width=2, stroke_opacity=0.6)
    for direction in (-1, 1) if two_rows else (-1,) if first_right else (1,):
        x = ax + direction * 65
        add(
            "polyline",
            points=f"{x - direction * 10},{ay - 10 / 1.5} {x},{ay} {x - direction * 10},{ay + 10 / 1.5}",
            stroke=INK,
            stroke_width=2,
            fill="none",
            stroke_opacity=0.6,
        )
    text(
        ax if two_rows else ax - 71 if first_right else ax + 71,
        ay + 14 if two_rows else ay + 4,
        "сдвиг",
        fill_opacity=0.5,
        text_anchor="middle" if two_rows else "end" if first_right else "start",
    )
    return ET.tostring(root, encoding="unicode")
