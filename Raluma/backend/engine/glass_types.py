"""Canonical glass descriptions shared by SLIDE calculations and documents."""

from __future__ import annotations

import re
from typing import Any


SLIDE_GLASS_TYPES = (
    "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
    "10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ",
    "10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ",
    "10ММ ЗАКАЛЕННОЕ МАТОВОЕ",
    "10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ",
    "ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ",
)
SLIDE_DEFAULT_GLASS_TYPE = SLIDE_GLASS_TYPES[0]
NON_SLIDE_DEFAULT_GLASS_TYPE = "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"

_SLIDE_GLASS_ALIASES = {
    "10ММ ПРОЗРАЧНОЕ": SLIDE_GLASS_TYPES[0],
    "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ": SLIDE_GLASS_TYPES[0],
    "10ММ БРОНЗА В МАССЕ": SLIDE_GLASS_TYPES[1],
    "10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ": SLIDE_GLASS_TYPES[1],
    "10ММ СЕРОЕ В МАССЕ": SLIDE_GLASS_TYPES[2],
    "10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ": SLIDE_GLASS_TYPES[2],
    "10ММ МАТОВОЕ": SLIDE_GLASS_TYPES[3],
    "10ММ ЗАКАЛЕННОЕ МАТОВОЕ": SLIDE_GLASS_TYPES[3],
    "10ММ ПРОСВЕТЛЕННОЕ": SLIDE_GLASS_TYPES[4],
    "10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ": SLIDE_GLASS_TYPES[4],
    "ТРИПЛЕКС 4.1.4": SLIDE_GLASS_TYPES[5],
    "ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ": SLIDE_GLASS_TYPES[5],
}
_TEMPERED_WORD_RE = re.compile(r"\bЗАКАЛ[ЕЁ]НН[А-ЯA-Z]*\b", re.IGNORECASE)
_THICKNESS_RE = re.compile(r"^(.*?\b\d+(?:[.,]\d+)?\s*ММ)\b(.*)$", re.IGNORECASE)


def _clean_glass_text(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().replace("Ё", "Е").split())


def normalize_slide_glass_type(value: Any) -> str:
    """Return one unambiguous tempered-glass description for SLIDE.

    Known historical options are mapped exactly. A custom value receives the
    full word ``ЗАКАЛЕННОЕ`` once; values that already contain any grammatical
    form of ``ЗАКАЛЕННЫЙ`` are left intact.
    """

    text = _clean_glass_text(value)
    if not text:
        return SLIDE_DEFAULT_GLASS_TYPE
    alias = _SLIDE_GLASS_ALIASES.get(text)
    if alias:
        return alias
    if _TEMPERED_WORD_RE.search(text):
        return text
    if text.startswith("ТРИПЛЕКС"):
        return f"{text} ЗАКАЛЕННЫЙ"
    thickness = _THICKNESS_RE.match(text)
    if thickness:
        prefix, suffix = thickness.groups()
        return " ".join(f"{prefix} ЗАКАЛЕННОЕ{suffix}".split())
    return f"ЗАКАЛЕННОЕ {text}"


def normalize_glass_type(value: Any, system: str | None) -> str:
    if (system or "").strip().upper() in {"СЛАЙД", "КНИЖКА"}:
        return normalize_slide_glass_type(value)
    text = " ".join(str(value or "").strip().split())
    return text or NON_SLIDE_DEFAULT_GLASS_TYPE


def default_glass_type(system: str | None) -> str:
    return (
        SLIDE_DEFAULT_GLASS_TYPE
        if (system or "").strip().upper() == "СЛАЙД"
        else NON_SLIDE_DEFAULT_GLASS_TYPE
    )
