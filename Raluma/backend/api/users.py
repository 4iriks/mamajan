from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import require_admin, hash_password, generate_password

router = APIRouter(prefix="/api/users", tags=["users"])

MANAGED_ROLES = ("user", "dealer")
ALL_ROLES = (*MANAGED_ROLES, "admin", "superadmin")
TEXT_FIELDS = (
    "customer",
    "employee_number",
    "position",
    "dealer_company",
    "dealer_contact_name",
    "dealer_phone",
    "dealer_email",
    "dealer_city",
    "dealer_address",
    "dealer_inn",
    "dealer_notes",
)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_dealer_discount(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0 or value > 100:
        raise HTTPException(
            status_code=400, detail="Скидка дилера должна быть от 0 до 100"
        )
    return value


def _ensure_admin_can_manage_user(
    target_user: models.User, current_user: models.User
) -> None:
    if current_user.role == "admin" and target_user.role not in MANAGED_ROLES:
        raise HTTPException(status_code=403, detail="Недостаточно прав")


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    # admin видит сотрудников/дилеров; superadmin видит всех
    if current_user.role == "superadmin":
        return db.query(models.User).order_by(models.User.id).all()
    return (
        db.query(models.User)
        .filter(models.User.role.in_(MANAGED_ROLES))
        .order_by(models.User.id)
        .all()
    )


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if data.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail="Неизвестная роль")
    # admin может создавать сотрудников и дилеров; superadmin может создавать admin
    if current_user.role == "admin" and data.role not in MANAGED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Администратор может создавать только сотрудников и дилеров",
        )
    username = data.username.strip()
    display_name = data.display_name.strip() or username
    if not username:
        raise HTTPException(status_code=400, detail="Введите логин")
    if not data.password.strip():
        raise HTTPException(status_code=400, detail="Введите пароль")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Логин уже занят")
    user = models.User(
        username=username,
        password_hash=hash_password(data.password),
        display_name=display_name,
        role=data.role,
        customer=_blank_to_none(data.customer),
        employee_number=_blank_to_none(data.employee_number),
        position=_blank_to_none(data.position),
        dealer_company=_blank_to_none(data.dealer_company),
        dealer_contact_name=_blank_to_none(data.dealer_contact_name),
        dealer_phone=_blank_to_none(data.dealer_phone),
        dealer_email=_blank_to_none(data.dealer_email),
        dealer_city=_blank_to_none(data.dealer_city),
        dealer_address=_blank_to_none(data.dealer_address),
        dealer_inn=_blank_to_none(data.dealer_inn),
        dealer_discount_percent=_validate_dealer_discount(data.dealer_discount_percent),
        dealer_notes=_blank_to_none(data.dealer_notes),
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
    _ensure_admin_can_manage_user(user, current_user)
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
    _ensure_admin_can_manage_user(user, current_user)
    updates = data.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    next_role = updates.get("role")
    if next_role is not None:
        if next_role not in ALL_ROLES:
            raise HTTPException(status_code=400, detail="Неизвестная роль")
        if current_user.role == "admin" and next_role not in MANAGED_ROLES:
            raise HTTPException(status_code=403, detail="Нельзя повысить до admin")
    if "display_name" in updates:
        display_name = (updates["display_name"] or "").strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="Введите имя")
        updates["display_name"] = display_name
    for field in TEXT_FIELDS:
        if field in updates:
            updates[field] = _blank_to_none(updates[field])
    if "dealer_discount_percent" in updates:
        updates["dealer_discount_percent"] = _validate_dealer_discount(
            updates["dealer_discount_percent"]
        )
    for field, value in updates.items():
        setattr(user, field, value)
    if password is not None:
        if not password.strip():
            raise HTTPException(status_code=400, detail="Введите пароль")
        user.password_hash = hash_password(password)
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
    _ensure_admin_can_manage_user(user, current_user)
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
    _ensure_admin_can_manage_user(user, current_user)
    new_password = generate_password()
    user.password_hash = hash_password(new_password)
    db.commit()
    return {"new_password": new_password}
