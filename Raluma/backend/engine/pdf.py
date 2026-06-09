"""
PDF/HTML движок для производственного листа.
Jinja2 → HTML → WeasyPrint → bytes
"""

import base64
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
ASSETS_DIR = os.path.join(BACKEND_DIR, "assets", "profiles")
ASSETS_PATH = Path(ASSETS_DIR).resolve()
IMAGE_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
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


def expand_glass_widths(calc, panels: int, fallback_width: float) -> list[float]:
    safe_panels = max(int(panels or 0), 1)
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
    middle = find_width("промеж") or edge or left or right or fallback_panel

    if safe_panels == 1:
        return [round(middle, 1)]

    widths = []
    for index in range(safe_panels):
        if index == 0:
            widths.append(left or edge or middle)
        elif index == safe_panels - 1:
            widths.append(right or edge or middle)
        else:
            widths.append(middle)
    return [round(width, 1) for width in widths]


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
    env.globals["glass_widths"] = expand_glass_widths
    env.globals["profile_dimension"] = profile_dimension
    return env


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
    template = env.get_template("section_sheet.html")
    return template.render(
        project=project,
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
    template = env.get_template("section_sheet.html")
    return template.render(
        project=project,
        section=section,
        calc=calc,
        overrides=overrides,
        is_pdf=True,
    )


def generate_pdf(html: str) -> bytes:
    """HTML строка → PDF байты через WeasyPrint."""
    from weasyprint import HTML as WH

    return WH(string=html, base_url=ASSETS_DIR).write_pdf()
