from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user
from engine.legacy_values import normalize_section_data_values

from project_access import (
    get_project,
    require_content_write,
    validate_dealer_content,
    sanitize_project_payload,
)

router = APIRouter(prefix="/api/projects", tags=["sections"])


def _section_response(section, actor):
    value = schemas.SectionOut.model_validate(section).model_dump()
    return sanitize_project_payload({"sections": [value]}, actor)["sections"][0]


def _assign_price_group(section_data: dict, db: Session) -> None:
    if str(section_data.get("system") or "").strip().upper() not in {
        "СЛАЙД",
        "КНИЖКА",
    }:
        section_data["glass_supplied"] = True
    group_id = section_data.get("price_group_id")
    if group_id is not None:
        if db.get(models.ConstructionPriceGroup, group_id) is None:
            raise HTTPException(status_code=400, detail="Ценовая группа не найдена")
        return
    system_code = {
        "СЛАЙД": "SLIDE",
        "КНИЖКА": "BOOK",
        "ЛИФТ": "LIFT",
    }.get(str(section_data.get("system") or "").strip().upper())
    if not system_code:
        return
    group = (
        db.query(models.ConstructionPriceGroup)
        .filter_by(code=system_code, is_active=True)
        .first()
    )
    if group is not None:
        section_data["price_group_id"] = group.id


def _get_project_or_403(
    project_id: int, db: Session, current_user: models.User
) -> models.Project:
    return get_project(db, project_id, current_user)


@router.get("/{project_id}/sections", response_model=list[schemas.SectionOut])
def list_sections(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_project_or_403(project_id, db, current_user)
    rows = (
        db.query(models.Section)
        .filter(models.Section.project_id == project_id)
        .order_by(models.Section.order)
        .all()
    )
    return [_section_response(row, current_user) for row in rows]


@router.post(
    "/{project_id}/sections", response_model=schemas.SectionOut, status_code=201
)
def create_section(
    project_id: int,
    response: Response,
    data: schemas.SectionCreate,
    version: int | None = Header(default=None, alias="X-Project-Version"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_403(project_id, db, current_user)
    require_content_write(db, project, current_user, version)
    response.headers["X-Project-Version"] = str(project.review_version)
    # auto order: use max to avoid collisions after deletions
    max_order = (
        db.query(func.max(models.Section.order))
        .filter(models.Section.project_id == project_id)
        .scalar()
    )
    section_data = normalize_section_data_values(data.model_dump())
    validate_dealer_content(
        current_user,
        system=section_data.get("system"),
        extras=section_data.get("extra_components"),
    )
    _assign_price_group(section_data, db)
    section_data["order"] = (max_order or 0) + 1
    section = models.Section(project_id=project_id, **section_data)
    db.add(section)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(section)
    return _section_response(section, current_user)


@router.put("/{project_id}/sections/{section_id}", response_model=schemas.SectionOut)
def update_section(
    project_id: int,
    response: Response,
    section_id: int,
    data: schemas.SectionUpdate,
    version: int | None = Header(default=None, alias="X-Project-Version"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_403(project_id, db, current_user)
    require_content_write(db, project, current_user, version)
    response.headers["X-Project-Version"] = str(project.review_version)
    section = (
        db.query(models.Section)
        .filter(
            models.Section.id == section_id,
            models.Section.project_id == project_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    section_data = normalize_section_data_values(data.model_dump())
    if not section_data.get("first_panels_placement"):
        section_data["first_panels_placement"] = section.first_panels_placement
        if (section.slide_rows or 1) == 2 and section_data.get(
            "unused_track"
        ) != section.unused_track:
            section_data["first_panels_placement"] = section.first_panels_placement or (
                "center"
                if (section.unused_track or "Внешний") == "Внешний"
                else "outside"
            )
    validate_dealer_content(
        current_user,
        system=section_data.get("system"),
        extras=section_data.get("extra_components"),
    )
    _assign_price_group(section_data, db)
    # ``order`` is server-owned after creation. Older editors sent a zero-based
    # array index here and could silently turn the first section into order=0.
    section_data.pop("order", None)
    for field, value in section_data.items():
        setattr(section, field, value)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(section)
    return _section_response(section, current_user)


@router.delete("/{project_id}/sections/{section_id}", status_code=204)
def delete_section(
    project_id: int,
    response: Response,
    section_id: int,
    version: int | None = Header(default=None, alias="X-Project-Version"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_403(project_id, db, current_user)
    require_content_write(db, project, current_user, version)
    response.headers["X-Project-Version"] = str(project.review_version)
    section = (
        db.query(models.Section)
        .filter(
            models.Section.id == section_id,
            models.Section.project_id == project_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    db.delete(section)
    project.updated_at = datetime.utcnow()
    db.commit()
