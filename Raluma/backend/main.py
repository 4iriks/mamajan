import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from database import engine, Base
import models  # noqa: F401 — нужен для создания таблиц
from auth import hash_password
from database import SessionLocal
from api import auth, users, projects, sections


def seed_superadmin():
    """Создаёт superadmin при первом запуске если его нет."""
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == "admin").first()
        if not existing:
            superadmin = models.User(
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="Администратор",
                role="superadmin",
                is_active=True,
            )
            db.add(superadmin)
            db.commit()
            print("✅ Создан superadmin: admin / admin123")
            print("⚠️  Смените пароль после первого входа!")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    # Миграции для новых колонок (SQLite не поддерживает ALTER IF NOT EXISTS)
    with engine.connect() as conn:
        for col_sql in [
            "ALTER TABLE projects ADD COLUMN subtype VARCHAR",
            "ALTER TABLE sections ADD COLUMN door_system VARCHAR",
            "ALTER TABLE sections ADD COLUMN cs_shape VARCHAR",
            "ALTER TABLE sections ADD COLUMN cs_width2 FLOAT",
        ]:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass  # колонка уже существует
    seed_superadmin()
    yield
    # Shutdown (ничего не нужно)


app = FastAPI(
    title="Ралюма API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — разрешаем фронтенд
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", "http://localhost:3000"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(sections.router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        return {"status": "error", "service": "Ралюма API", "detail": str(e)}
    return {"status": "ok", "service": "Ралюма API"}
