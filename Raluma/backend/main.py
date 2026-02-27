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
            "ALTER TABLE sections ADD COLUMN system VARCHAR",
            "ALTER TABLE sections ADD COLUMN profile_left_wall BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_left_lock_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_left_p_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_left_handle_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_left_bubble BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_right_wall BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_right_lock_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_right_p_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_right_handle_bar BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN profile_right_bubble BOOLEAN DEFAULT 0",
            "ALTER TABLE sections ADD COLUMN lock_left VARCHAR",
            "ALTER TABLE sections ADD COLUMN lock_right VARCHAR",
            "ALTER TABLE sections ADD COLUMN book_subtype VARCHAR",
            "ALTER TABLE sections ADD COLUMN handle_left VARCHAR",
            "ALTER TABLE sections ADD COLUMN handle_right VARCHAR",
            "ALTER TABLE projects ADD COLUMN extra_parts VARCHAR",
            "ALTER TABLE projects ADD COLUMN comments VARCHAR",
            "ALTER TABLE projects ADD COLUMN production_stages INTEGER DEFAULT 1",
            "ALTER TABLE projects ADD COLUMN current_stage INTEGER DEFAULT 1",
            "ALTER TABLE projects ADD COLUMN status VARCHAR",
            "ALTER TABLE projects ADD COLUMN glass_status VARCHAR",
            "ALTER TABLE projects ADD COLUMN glass_invoice VARCHAR",
            "ALTER TABLE projects ADD COLUMN glass_ready_date VARCHAR",
            "ALTER TABLE projects ADD COLUMN paint_status VARCHAR",
            "ALTER TABLE projects ADD COLUMN paint_ship_date VARCHAR",
            "ALTER TABLE projects ADD COLUMN paint_received_date VARCHAR",
            "ALTER TABLE projects ADD COLUMN order_items VARCHAR",
        ]:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass  # колонка уже существует
    # Переносим system из project в sections для старых данных
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "UPDATE sections SET system = (SELECT system FROM projects WHERE projects.id = sections.project_id) "
                "WHERE system IS NULL"
            ))
            conn.commit()
        except Exception:
            pass
    # Переименование замков (ТЗ6)
    with engine.connect() as conn:
        for sql in [
            "UPDATE sections SET lock_left = 'ЗАМОК-ЗАЩЕЛКА 1стор' WHERE lock_left = '1-сторонний RS3018'",
            "UPDATE sections SET lock_left = 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом' WHERE lock_left = '2-сторонний с ключом RS3019'",
            "UPDATE sections SET lock_right = 'ЗАМОК-ЗАЩЕЛКА 1стор' WHERE lock_right = '1-сторонний RS3018'",
            "UPDATE sections SET lock_right = 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом' WHERE lock_right = '2-сторонний с ключом RS3019'",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
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
        return JSONResponse(
            status_code=503,
            content={"status": "error", "service": "Ралюма API", "detail": str(e)},
        )
    return {"status": "ok", "service": "Ралюма API"}
