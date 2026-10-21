"""Explicit customer directory; historical project strings never seed this list."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user, require_superadmin
from database import get_db
from models import Customer, User

router = APIRouter(prefix="/api/customers", tags=["customers"])


class CustomerWrite(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    is_active: bool = True


class CustomerOut(CustomerWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int


def active_customer(db: Session, value: str | None) -> str:
    key = " ".join(str(value or "").split()).casefold()
    aliases = {"ооо пр": "ооо прозрачные решения", "ооо ки": "ооо крокна инжиниринг"}
    row = (
        db.query(Customer)
        .filter_by(name_key=aliases.get(key, key), is_active=True)
        .first()
    )
    if row is None:
        raise HTTPException(422, "Выберите активного заказчика из справочника")
    return row.name


@router.get("", response_model=list[CustomerOut])
def list_customers(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Customer)
    if not include_inactive or user.role != "superadmin":
        query = query.filter_by(is_active=True)
    return query.order_by(Customer.name).all()


def save_customer(db: Session, row: Customer, data: CustomerWrite):
    row.name = " ".join(data.name.split())
    if not row.name:
        raise HTTPException(422, "Укажите название заказчика")
    row.name_key = row.name.casefold()
    row.is_active = data.is_active
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Такой заказчик уже есть в справочнике") from None
    db.refresh(row)
    return row


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    data: CustomerWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    return save_customer(db, Customer(), data)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    data: CustomerWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    row = db.get(Customer, customer_id)
    if row is None:
        raise HTTPException(404, "Заказчик не найден")
    return save_customer(db, row, data)
