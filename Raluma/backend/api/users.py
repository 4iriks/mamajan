from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user, require_admin, hash_password, generate_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    # admin видит всех user; superadmin видит всех
    if current_user.role == "superadmin":
        return db.query(models.User).order_by(models.User.id).all()
    return db.query(models.User).filter(models.User.role == "user").order_by(models.User.id).all()


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    # admin может создавать только user
    if current_user.role == "admin" and data.role != "user":
        raise HTTPException(status_code=403, detail="Администратор может создавать только пользователей")
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Логин уже занят")
    user = models.User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        customer=data.customer,
        is_active=data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # admin не может менять других admin/superadmin
    if current_user.role == "admin" and user.role != "user":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        if current_user.role == "admin" and data.role != "user":
            raise HTTPException(status_code=403, detail="Нельзя повысить до admin")
        user.role = data.role
    if data.customer is not None:
        user.customer = data.customer
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password:
        user.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    if current_user.role == "admin" and user.role != "user":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    db.delete(user)
    db.commit()


@router.post("/{user_id}/reset-password", response_model=schemas.ResetPasswordResponse)
def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if current_user.role == "admin" and user.role != "user":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    new_password = generate_password()
    user.password_hash = hash_password(new_password)
    db.commit()
    return {"new_password": new_password}
