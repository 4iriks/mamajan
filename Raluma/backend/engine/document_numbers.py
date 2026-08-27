"""Shared numbering rules for generated documents."""

from __future__ import annotations

import re
from typing import Iterable


def production_project_number(project: object, fallback: str = "") -> str:
    """Return the manually entered project number, never the invoice number."""
    value = getattr(project, "order_number", None) or getattr(project, "number", None)
    return str(value or fallback).strip()


def commercial_document_number(project: object, fallback: str = "") -> str:
    """Return the invoice number used by commercial documents."""
    value = (
        getattr(project, "invoice_number", None)
        or getattr(project, "order_number", None)
        or getattr(project, "number", None)
    )
    return str(value or fallback).strip()


def section_name_number(section: object) -> int | None:
    """Read only an explicit ``Секция/Изделие N`` prefix from a section name."""

    match = re.match(
        r"\s*(?:секция|изделие)\s*(?:№\s*)?(\d+)\b",
        str(getattr(section, "name", "") or ""),
        re.IGNORECASE,
    )
    if not match:
        return None
    number = int(match.group(1))
    return number if number > 0 else None


def _section_order(section: object) -> int | None:
    try:
        order = int(getattr(section, "order", 0) or 0)
    except (TypeError, ValueError):
        return None
    return order if order > 0 else None


def resolve_section_numbers(
    sections: Iterable[object],
) -> list[tuple[int, object]]:
    """Return sections in stable production order with unique positive numbers.

    Explicit names remain authoritative when they form an increasing sequence.
    Corrupt zero/duplicate/backward values are replaced by the next free number,
    so all project documents share the same collision-safe markings.
    """

    indexed = list(enumerate(sections, start=1))
    ordered = sorted(
        indexed,
        key=lambda item: (
            section_name_number(item[1])
            or _section_order(item[1])
            or item[0],
            item[0],
        ),
    )

    resolved: list[tuple[int, object]] = []
    used: set[int] = set()
    previous = 0
    for fallback, section in ordered:
        preferred = (
            section_name_number(section) or _section_order(section) or fallback
        )
        number = preferred
        if number <= previous or number in used:
            number = previous + 1
        while number in used:
            number += 1
        used.add(number)
        previous = number
        resolved.append((number, section))
    return resolved


def resolved_section_number(
    sections: Iterable[object], section: object, fallback: int = 1
) -> int:
    """Resolve one section through the same project-wide numbering sequence."""

    section_id = getattr(section, "id", None)
    for number, candidate in resolve_section_numbers(sections):
        if candidate is section:
            return number
        if section_id is not None and getattr(candidate, "id", None) == section_id:
            return number
    return section_name_number(section) or _section_order(section) or fallback


def production_section_label(section: object, fallback: str = "Секция") -> str:
    """Return the collision-safe label attached by the document API when present."""

    number = getattr(section, "document_section_number", None)
    if number:
        return f"Секция {number}"
    return str(getattr(section, "name", "") or fallback)
