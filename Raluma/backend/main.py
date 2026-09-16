import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text
from database import engine, Base
import models  # noqa: F401 — нужен для создания таблиц
from auth import hash_password
from database import SessionLocal
from api import auth, users, projects, sections, documents
from migrations import run_migrations


def seed_superadmin():
    """Создаёт superadmin при первом запуске если его нет."""
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == "admin").first()
        if not existing:
            initial_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
            if len(initial_password) < 12 or initial_password.lower().startswith(
                "replace"
            ):
                raise RuntimeError(
                    "Set INITIAL_ADMIN_PASSWORD to at least 12 characters"
                )
            superadmin = models.User(
                username="admin",
                password_hash=hash_password(initial_password),
                display_name="Администратор",
                role="superadmin",
                is_active=True,
            )
            db.add(superadmin)
            db.commit()
            print("Initial admin account created")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_superadmin()
    yield


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
app.include_router(documents.router)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "service": "Ралюма API", "detail": str(e)},
        )
    return {"status": "ok", "service": "Ралюма API"}
