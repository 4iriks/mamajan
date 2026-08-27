"""
PDF/HTML движок для производственного листа.
Jinja2 → HTML → WeasyPrint → bytes
"""

import base64
import io
import json
import os
import re
from math import ceil
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from engine.document_numbers import production_project_number, production_section_label

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")

GLASS_FILL_COLORS = {
    "clear": "#dceff3",
    "bronze": "#e4c39f",
    "gray": "#c9d0d3",
    "matte": "#e5e8e7",
    "clarified": "#eefaf8",
    "triplex": "#d3eadb",
}
ASSETS_DIR = os.path.join(BACKEND_DIR, "assets", "profiles")
ASSETS_PATH = Path(ASSETS_DIR).resolve()
DRAWINGS_DIR = os.path.join(BACKEND_DIR, "assets", "drawings")
DRAWINGS_PATH = Path(DRAWINGS_DIR).resolve()
IMAGE_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "svg": "image/svg+xml",
}


def get_profile_asset_path(filename: str | None) -> Path | None:
    """Return a safe profile asset path inside ASSETS_DIR, or None."""
    if not filename:
        return None
    if "/" in filename or "\\" in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in IMAGE_MIME_TYPES:
        return None
    path = (ASSETS_PATH / filename).resolve()
    if path.parent != ASSETS_PATH or not path.is_file():
        return None
    return path


def get_drawing_asset_path(filename: str | None) -> Path | None:
    """Return a safe drawing PDF path inside assets/drawings, or None."""
    if not filename:
        return None
    if "/" in filename or "\\" in filename:
        return None
    if filename.rsplit(".", 1)[-1].lower() != "pdf":
        return None
    path = (DRAWINGS_PATH / filename).resolve()
    if path.parent != DRAWINGS_PATH or not path.is_file():
        return None
    return path


def append_pdf_drawings(pdf_bytes: bytes, drawing_files: list[str]) -> bytes:
    files = []
    for filename in drawing_files:
        path = get_drawing_asset_path(filename)
        if path and path not in files:
            files.append(path)
    if not files:
        return pdf_bytes

    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:
        return pdf_bytes

    writer = PdfWriter()
    source = PdfReader(io.BytesIO(pdf_bytes))
    for page in source.pages:
        writer.add_page(page)
    for path in files:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def expand_glass_widths(calc, panels: int, fallback_width: float) -> list[float]:
    safe_panels = max(int(panels or 0), 1)
    panel_rows = getattr(calc, "panel_glass", None) or []
    if len(panel_rows) >= safe_panels:
        return [
            round(float(getattr(panel, "width_mm", 0) or 0), 1)
            for panel in panel_rows[:safe_panels]
        ]

    fallback_panel = float(fallback_width or 0) / safe_panels
    glass_rows = getattr(calc, "glass", None) or []
    if not glass_rows:
        return [round(fallback_panel, 1) for _ in range(safe_panels)]

    def find_width(needle: str) -> float | None:
        for glass in glass_rows:
            qty = float(getattr(glass, "qty", 0) or 0)
            position = str(getattr(glass, "position", "") or "").lower()
            if qty > 0 and needle in position:
                width = float(getattr(glass, "width_mm", 0) or 0)
                if width > 0:
                    return width
        return None

    edge = find_width("крайн")
    left = find_width("лев")
    right = find_width("прав")
    center = find_width("централь")
    middle = find_width("промеж") or edge or left or right or fallback_panel

    if safe_panels == 1:
        return [round(middle, 1)]
    if center and safe_panels >= 4:
        side_middle_count = max(safe_panels - 4, 0) // 2
        widths = [left or middle]
        widths.extend([middle] * side_middle_count)
        widths.extend([center, center])
        widths.extend([middle] * side_middle_count)
        widths.append(right or middle)
        if len(widths) < safe_panels:
            widths.extend([middle] * (safe_panels - len(widths)))
        return [round(width, 1) for width in widths[:safe_panels]]

    widths = []
    for index in range(safe_panels):
        if index == 0:
            widths.append(left or edge or middle)
        elif index == safe_panels - 1:
            widths.append(right or edge or middle)
        else:
            widths.append(middle)
    return [round(width, 1) for width in widths]


def expand_glass_profile_lengths(
    calc, panels: int, fallback_width: float
) -> list[float]:
    safe_panels = max(int(panels or 0), 1)
    panel_rows = getattr(calc, "panel_glass", None) or []
    if len(panel_rows) >= safe_panels:
        return [
            round(float(getattr(panel, "glass_profile_length", 0) or 0), 1)
            for panel in panel_rows[:safe_panels]
        ]

    fallback_panel = float(fallback_width or 0) / safe_panels
    glass_rows = getattr(calc, "glass", None) or []
    if not glass_rows:
        return [round(fallback_panel, 1) for _ in range(safe_panels)]

    def find_length(needle: str) -> float | None:
        for glass in glass_rows:
            qty = float(getattr(glass, "qty", 0) or 0)
            position = str(getattr(glass, "position", "") or "").lower()
            if qty > 0 and needle in position:
                length = float(getattr(glass, "glass_profile_length", 0) or 0)
                if length > 0:
                    return length
        return None

    edge = find_length("крайн")
    left = find_length("лев")
    right = find_length("прав")
    center = find_length("централь")
    middle = find_length("промеж") or edge or left or right or fallback_panel

    if safe_panels == 1:
        return [round(middle, 1)]
    if center and safe_panels >= 4:
        side_middle_count = max(safe_panels - 4, 0) // 2
        lengths = [left or middle]
        lengths.extend([middle] * side_middle_count)
        lengths.extend([center, center])
        lengths.extend([middle] * side_middle_count)
        lengths.append(right or middle)
        if len(lengths) < safe_panels:
            lengths.extend([middle] * (safe_panels - len(lengths)))
        return [round(length, 1) for length in lengths[:safe_panels]]

    lengths = []
    for index in range(safe_panels):
        if index == 0:
            lengths.append(left or edge or middle)
        elif index == safe_panels - 1:
            lengths.append(right or edge or middle)
        else:
            lengths.append(middle)
    return [round(length, 1) for length in lengths]


def profile_dimension(
    calc,
    articles: list[str],
    key: str,
    fallback: float,
) -> float:
    profiles = getattr(calc, "profiles", None) or []
    for profile in profiles:
        if getattr(profile, "article", None) not in articles:
            continue
        value = float(getattr(profile, key, 0) or 0)
        if value > 0:
            return value
    return fallback


def _format_length_for_display(value: float) -> str:
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded).replace(".", ",")


def glass_mm(value: float) -> int:
    """Round a positive glass dimension to the nearest whole millimeter."""
    return int(float(value or 0) + 0.5)


def glass_fill(value: str | None) -> str:
    """Return the shared diagram fill for a selected glass description."""
    normalized = str(value or "").upper()
    if "БРОНЗ" in normalized:
        return GLASS_FILL_COLORS["bronze"]
    if "СЕРО" in normalized:
        return GLASS_FILL_COLORS["gray"]
    if "МАТ" in normalized:
        return GLASS_FILL_COLORS["matte"]
    if "ПРОСВЕТ" in normalized:
        return GLASS_FILL_COLORS["clarified"]
    if "ТРИПЛЕКС" in normalized:
        return GLASS_FILL_COLORS["triplex"]
    return GLASS_FILL_COLORS["clear"]


def glass_is_matte(value: str | None) -> bool:
    """Return whether glass diagrams should use the matte dot pattern."""
    return "МАТ" in str(value or "").upper()


def brush_meters(value: float | str) -> str:
    """Round brush length upward to 0.1 m and keep the unit visible."""
    normalized = str(value or 0).strip().lower().replace("м", "").replace(",", ".")
    try:
        rounded = ceil(float(normalized) * 10) / 10
    except (TypeError, ValueError):
        return str(value)
    return f"{rounded:.1f}".replace(".", ",") + " м"


def _strip_split_note(note: str) -> str:
    return re.sub(r"^часть \d+/\d+;?\s*", "", note or "").strip()


def display_profiles(profiles: list) -> list:
    rows = []
    grouped: dict[tuple, SimpleNamespace] = {}

    for profile in profiles:
        field_key = getattr(profile, "field_key", "") or ""
        note = getattr(profile, "note", "") or ""
        is_split = "_part_" in field_key or note.startswith("часть ")
        if not is_split:
            rows.append(profile)
            continue

        base_field_key = field_key.split("_part_", 1)[0]
        clean_note = _strip_split_note(note)
        key = (
            getattr(profile, "article", ""),
            getattr(profile, "name", ""),
            getattr(profile, "image", ""),
            base_field_key,
            clean_note,
        )
        row = grouped.get(key)
        if row is None:
            row = SimpleNamespace(
                article=getattr(profile, "article", ""),
                name=getattr(profile, "name", ""),
                length_mm=0,
                qty=0,
                painted=getattr(profile, "painted", False),
                image=getattr(profile, "image", None),
                field_key=base_field_key,
                note=clean_note,
                section_width_mm=getattr(profile, "section_width_mm", 0),
                section_height_mm=getattr(profile, "section_height_mm", 0),
                paint_mode=getattr(profile, "paint_mode", ""),
                color_variants=getattr(profile, "color_variants", []),
                paint_note=getattr(profile, "paint_note", ""),
                glass_positions=getattr(profile, "glass_positions", ""),
                display_cuts=[],
            )
            grouped[key] = row
            rows.append(row)

        length = _format_length_for_display(getattr(profile, "length_mm", 0))
        length_field = field_key or f"{base_field_key}_cut_{len(row.display_cuts) + 1}"
        qty_field = f"{length_field}_qty"
        qty = int(getattr(profile, "qty", 0) or 0)
        for cut in row.display_cuts:
            if cut["length"] == length:
                cut["qty"] += qty
                break
        else:
            row.display_cuts.append(
                {
                    "length": length,
                    "qty": qty,
                    "length_field": length_field,
                    "qty_field": qty_field,
                }
            )

    return rows


def display_hardware(hardware: list) -> list:
    """Attach stable source indexes used by editable production-sheet fields."""
    rows = []

    for source_index, item in enumerate(hardware, start=1):
        article = getattr(item, "article", "")
        rows.append(
            SimpleNamespace(
                article=article,
                name=getattr(item, "name", ""),
                value=getattr(item, "value", 0),
                unit=getattr(item, "unit", "шт"),
                image=getattr(item, "image", None),
                field_key=getattr(item, "field_key", ""),
                display_group="",
                source_index=source_index,
                sub_items=getattr(item, "sub_items", None),
            )
        )

    return rows


def _parse_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _normalize_extra_component(row) -> dict | None:
    if not isinstance(row, dict):
        return None
    art = str(row.get("art") or row.get("sku") or "").strip()
    name = str(row.get("name") or "").strip()
    size = str(row.get("size") or "").strip()
    qty = str(row.get("qty") or row.get("quantity") or "").strip()
    color = str(row.get("color") or "").strip()
    if not any((art, name, size, qty, color)):
        return None
    return {"art": art, "name": name, "size": size, "qty": qty, "color": color}


def section_extra_components(section, overrides: dict | None = None) -> list[dict]:
    section_rows = _parse_json_list(getattr(section, "extra_components", None))
    override_rows = _parse_json_list((overrides or {}).get("extra_components"))
    source = section_rows if section_rows else override_rows
    rows: list[dict] = []
    for row in source:
        normalized = _normalize_extra_component(row)
        if normalized is not None:
            rows.append(normalized)
    return rows


def _img_b64(filename: str) -> str:
    """Jinja2-фильтр: имя файла → data URI base64 или пустая строка."""
    path = get_profile_asset_path(filename)
    if not path:
        return ""
    with path.open("rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = filename.rsplit(".", 1)[-1].lower()
    mime = IMAGE_MIME_TYPES[ext]
    return f"data:{mime};base64,{data}"


def _get_env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["img_b64"] = _img_b64
    env.filters["enumerate"] = enumerate
    env.filters["glass_mm"] = glass_mm
    env.filters["glass_fill"] = glass_fill
    env.filters["glass_is_matte"] = glass_is_matte
    env.filters["brush_meters"] = brush_meters
    env.globals["glass_widths"] = expand_glass_widths
    env.globals["glass_profile_lengths"] = expand_glass_profile_lengths
    env.globals["profile_dimension"] = profile_dimension
    env.globals["display_profiles"] = display_profiles
    env.globals["display_hardware"] = display_hardware
    env.globals["section_extra_components"] = section_extra_components
    return env


def _section_sheet_template(section) -> str:
    if str(getattr(section, "system", "") or "").strip().upper() == "ЛИФТ":
        return "lift_section_sheet.html"
    return "section_sheet.html"


def render_preview(project, section, calc) -> str:
    """
    Рендерит HTML-строку с contenteditable для предпросмотра в iframe.
    calc — SlideCalcResult из engine.slide_calc.
    """
    overrides = {}
    try:
        overrides = json.loads(section.document_overrides or "{}")
    except Exception:
        pass

    env = _get_env()
    template = env.get_template(_section_sheet_template(section))
    return template.render(
        project=project,
        project_number=production_project_number(project),
        section_label=production_section_label(section),
        section=section,
        calc=calc,
        overrides=overrides,
        is_pdf=False,
    )


def render_pdf_html(project, section, calc) -> str:
    """
    Рендерит HTML для WeasyPrint (без contenteditable JS, без интерактивности).
    """
    overrides = {}
    try:
        overrides = json.loads(section.document_overrides or "{}")
    except Exception:
        pass

    env = _get_env()
    template = env.get_template(_section_sheet_template(section))
    return template.render(
        project=project,
        project_number=production_project_number(project),
        section_label=production_section_label(section),
        section=section,
        calc=calc,
        overrides=overrides,
        is_pdf=True,
    )


def generate_pdf(html: str) -> bytes:
    """HTML строка → PDF байты через WeasyPrint."""
    from weasyprint import HTML as WH

    return WH(string=html, base_url=ASSETS_DIR).write_pdf()
