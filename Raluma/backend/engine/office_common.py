"""Shared helpers for editable DOCX/XLSX production documents."""

from __future__ import annotations

import base64
import binascii
import io
import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFont

from engine.pdf import get_profile_asset_path, glass_mm


BRAND_DARK = "102833"
BRAND_TEAL = "117985"
BRAND_LIGHT = "EAF5F7"
GRID_GRAY = "D8DEE1"
HEADER_GRAY = "E8ECEE"
RED = "D00000"
WHITE = "FFFFFF"
BLACK = "000000"


def format_number(value: Any, decimals: int = 1) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return str(value or "")
    rounded = round(number, decimals)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".").replace(".", ",")


def format_dimension(value: Any) -> str:
    """Format dimensions exactly as the PDF production sheets do."""
    try:
        return str(glass_mm(float(value or 0)))
    except (TypeError, ValueError):
        return str(value or "")


def drawing_files_for_sections(sections: Any) -> list[str]:
    """Return drawing appendices required by the selected section handles."""
    files: list[str] = []
    for section in sections:
        values = [
            getattr(section, "handle", ""),
            getattr(section, "handle_left", ""),
            getattr(section, "handle_right", ""),
            getattr(section, "center_handle", ""),
        ]
        text = " ".join(str(value or "").lower() for value in values)
        if ("rs3014" in text or "кноб" in text) and "knob.pdf" not in files:
            files.append("knob.pdf")
        if ("rs30201" in text or "скоб" in text) and "brace600.pdf" not in files:
            files.append("brace600.pdf")
    return files


def drawing_image_streams_for_sections(
    sections: Any,
) -> list[tuple[str, io.BytesIO]]:
    """Load printable PNG previews for the PDF drawing appendices."""
    drawings_dir = Path(__file__).resolve().parent.parent / "assets" / "drawings"
    result: list[tuple[str, io.BytesIO]] = []
    for filename in drawing_files_for_sections(sections):
        image_path = drawings_dir / f"{Path(filename).stem}.png"
        if image_path.is_file():
            result.append((image_path.stem, io.BytesIO(image_path.read_bytes())))
    return result


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def load_overrides(section: object) -> dict[str, Any]:
    raw = getattr(section, "document_overrides", None)
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def override_value(
    overrides: dict[str, Any],
    key: str,
    default: Any,
) -> Any:
    value = overrides.get(key, default)
    return default if value is None else value


def _decode_data_uri(data_uri: str) -> bytes | None:
    if not data_uri or "," not in data_uri:
        return None
    header, encoded = data_uri.split(",", 1)
    if ";base64" not in header:
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None


def _trim_image(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_box = alpha.getbbox()
    if alpha_box:
        return rgba.crop(alpha_box)

    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    diff = ImageChops.difference(rgba, white).convert("L")
    box = diff.getbbox()
    return rgba.crop(box) if box else rgba


def image_png_bytes(
    filename: str | None = None,
    image_data: str | None = None,
    *,
    max_size: tuple[int, int] = (900, 500),
    trim: bool = True,
) -> bytes | None:
    """Load a catalog/manual image and normalize it to an Office-safe PNG."""
    raw: bytes | None = _decode_data_uri(str(image_data or ""))
    if raw is None:
        path = get_profile_asset_path(filename)
        if not path:
            return None
        raw = path.read_bytes()

    try:
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGBA")
    except Exception:
        return None

    if trim:
        image = _trim_image(image)
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def image_stream(
    filename: str | None = None,
    image_data: str | None = None,
    *,
    max_size: tuple[int, int] = (900, 500),
    trim: bool = True,
) -> io.BytesIO | None:
    data = image_png_bytes(
        filename,
        image_data,
        max_size=max_size,
        trim=trim,
    )
    return io.BytesIO(data) if data else None


def _font_candidates(bold: bool) -> list[Path]:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        windows / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/liberation2")
        / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu")
        / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    return candidates


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for candidate in _font_candidates(bold):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def normalize_filename(value: str) -> str:
    text = "".join(
        char if char not in '<>:"/\\|?*' else "_" for char in str(value or "")
    ).strip(" .")
    return text or "document"
