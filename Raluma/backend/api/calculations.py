"""Отдельные API расчётных контуров."""

from dataclasses import asdict
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException

import models
import schemas
from auth import get_current_user
from engine.book_calc import BookCalculationError, calculate_book
from engine.legacy_values import normalize_section_data_values


router = APIRouter(prefix="/api/calculate", tags=["calculations"])


def _book_payload(data: schemas.SectionCreate) -> dict:
    values = normalize_section_data_values(data.model_dump())
    section = SimpleNamespace(**values)
    try:
        return asdict(calculate_book(section))
    except BookCalculationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/book")
def calculate_book_section(
    data: schemas.SectionCreate,
    _current_user: models.User = Depends(get_current_user),
):
    """Рассчитать сохранённую или ещё не сохранённую секцию КНИЖКИ."""
    return _book_payload(data)


@router.post("/local/book")
def calculate_local_book_section(data: schemas.SectionCreate):
    """Гостевой расчёт КНИЖКИ без авторизации."""
    return _book_payload(data)
