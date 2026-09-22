"""Отдельные API расчётных контуров."""

from dataclasses import asdict
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user
from database import get_db
from engine.book_calc import BookCalculationError, calculate_book
from engine.cs_calc import CsCalculationError, calculate_cs
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


def _cs_payload(data: schemas.SectionCreate, db: Session) -> dict:
    values = normalize_section_data_values(data.model_dump())
    section = SimpleNamespace(**values)
    system = None
    if data.cs_system_id is not None:
        system = (
            db.query(models.CsSystem)
            .filter(models.CsSystem.id == data.cs_system_id, models.CsSystem.is_active == True)  # noqa: E712
            .first()
        )
        if system is None:
            raise HTTPException(status_code=422, detail="Выбранная система ЦС недоступна")
    if system is None:
        system = (
            db.query(models.CsSystem)
            .filter(models.CsSystem.is_active == True)  # noqa: E712
            .order_by(models.CsSystem.id)
            .first()
        )
    outer_profile = db.get(models.CatalogItem, system.outer_profile_item_id) if system and system.outer_profile_item_id else None
    joint_profile = db.get(models.CatalogItem, system.joint_profile_item_id) if system and system.joint_profile_item_id else None
    try:
        return calculate_cs(
            section,
            system=system,
            outer_profile=outer_profile,
            joint_profile=joint_profile,
        )
    except CsCalculationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/cs")
def calculate_cs_section(
    data: schemas.SectionCreate,
    db: Session = Depends(get_db),
    _current_user: models.User = Depends(get_current_user),
):
    return _cs_payload(data, db)


@router.post("/local/cs")
def calculate_local_cs_section(
    data: schemas.SectionCreate,
    db: Session = Depends(get_db),
):
    return _cs_payload(data, db)
