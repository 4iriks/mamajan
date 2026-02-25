from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_project_or_404(project_id: int, db: Session, current_user: models.User) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    # user видит только свои проекты; admin/superadmin видят все
    if current_user.role == "user" and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    return project


@router.get("", response_model=list[schemas.ProjectList])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Project)
    if current_user.role == "user":
        query = query.filter(models.Project.created_by == current_user.id)
    return query.order_by(models.Project.created_at.desc()).all()


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    data: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = models.Project(
        number=data.number,
        customer=data.customer,
        system=data.system,
        subtype=data.subtype,
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_project_or_404(project_id, db, current_user)


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    data: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db, current_user)
    if data.number is not None:
        project.number = data.number
    if data.customer is not None:
        project.customer = data.customer
    if data.system is not None:
        project.system = data.system
    if data.subtype is not None:
        project.subtype = data.subtype
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db, current_user)
    db.delete(project)
    db.commit()


@router.post("/{project_id}/copy", response_model=schemas.ProjectOut, status_code=201)
def copy_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    source = _get_project_or_404(project_id, db, current_user)
    new_project = models.Project(
        number=source.number + "-копия",
        customer=source.customer,
        system=source.system,
        subtype=source.subtype,
        created_by=current_user.id,
    )
    db.add(new_project)
    db.flush()
    for s in source.sections:
        new_section = models.Section(
            project_id=new_project.id,
            order=s.order, name=s.name,
            width=s.width, height=s.height, panels=s.panels, quantity=s.quantity,
            glass_type=s.glass_type, painting_type=s.painting_type, ral_color=s.ral_color,
            corner_left=s.corner_left, corner_right=s.corner_right, external_width=s.external_width,
            rails=s.rails, threshold=s.threshold, first_panel_inside=s.first_panel_inside,
            unused_track=s.unused_track, inter_glass_profile=s.inter_glass_profile,
            profile_left=s.profile_left, profile_right=s.profile_right,
            lock=s.lock, handle=s.handle,
            floor_latches_left=s.floor_latches_left, floor_latches_right=s.floor_latches_right,
            handle_offset=s.handle_offset,
            doors=s.doors, door_side=s.door_side, door_type=s.door_type,
            door_opening=s.door_opening, compensator=s.compensator,
            angle_left=s.angle_left, angle_right=s.angle_right, book_system=s.book_system,
            door_system=s.door_system, cs_shape=s.cs_shape, cs_width2=s.cs_width2,
        )
        db.add(new_section)
    db.commit()
    db.refresh(new_project)
    return new_project
