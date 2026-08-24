"""Shared numbering rules for generated documents."""

from __future__ import annotations


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
