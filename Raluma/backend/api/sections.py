from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["sections"])


def _get_project_or_403(project_id: int, db: Session, current_user: models.User) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role == "user" and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return project


@router.get("/{project_id}/sections", response_model=list[schemas.SectionOut])
def list_sections(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_project_or_403(project_id, db, current_user)
    return db.query(models.Section).filter(
        models.Section.project_id == project_id
    ).order_by(models.Section.order).all()


@router.post("/{project_id}/sections", response_model=schemas.SectionOut, status_code=201)
def create_section(
    project_id: int,
    data: schemas.SectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_project_or_403(project_id, db, current_user)
    # auto order: use max to avoid collisions after deletions
    max_order = db.query(func.max(models.Section.order)).filter(
        models.Section.project_id == project_id
    ).scalar()
    section_data = data.model_dump()
    section_data['order'] = (max_order or 0) + 1
    section = models.Section(project_id=project_id, **section_data)
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.put("/{project_id}/sections/{section_id}", response_model=schemas.SectionOut)
def update_section(
    project_id: int,
    section_id: int,
    data: schemas.SectionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_project_or_403(project_id, db, current_user)
    section = db.query(models.Section).filter(
        models.Section.id == section_id,
        models.Section.project_id == project_id,
    ).first()
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    for field, value in data.model_dump().items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    return section


@router.delete("/{project_id}/sections/{section_id}", status_code=204)
def delete_section(
    project_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_project_or_403(project_id, db, current_user)
    section = db.query(models.Section).filter(
        models.Section.id == section_id,
        models.Section.project_id == project_id,
    ).first()
    if not section:
        raise HTTPException(status_code=404, detail="Секция не найдена")
    db.delete(section)
    db.commit()
