from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import verify_password, create_access_token, get_current_user, hash_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )
    user.last_login = datetime.utcnow()
    db.commit()
    token = create_access_token(user.id, user.username, user.role)
    return {"access_token": token}


@router.post("/register", response_model=schemas.TokenResponse, status_code=201)
def register(data: schemas.RegisterRequest, db: Session = Depends(get_db)):
    username = data.username.strip()
    password = data.password
    display_name = (data.display_name or username).strip()

    if not username:
        raise HTTPException(status_code=400, detail="Введите логин")
    if not password:
        raise HTTPException(status_code=400, detail="Введите пароль")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status_code=400, detail="Логин уже занят")

    user = models.User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name or username,
        role="user",
        is_active=True,
        last_login=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username, user.role)
    return {"access_token": token}


@router.get("/me", response_model=schemas.UserMe)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
