"""
Ручные SQLite-миграции.

SQLite не поддерживает IF NOT EXISTS для ALTER TABLE,
поэтому каждый ALTER оборачиваем в try/except.

Вызывается из main.py при старте приложения.
"""

from sqlalchemy import text
from database import engine


# ── Новые колонки ──────────────────────────────────────────────────────────────

_ADD_COLUMNS = [
    # projects
    "ALTER TABLE projects ADD COLUMN subtype VARCHAR",
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
    # sections
    "ALTER TABLE sections ADD COLUMN system VARCHAR",
    "ALTER TABLE sections ADD COLUMN door_system VARCHAR",
    "ALTER TABLE sections ADD COLUMN cs_shape VARCHAR",
    "ALTER TABLE sections ADD COLUMN cs_width2 FLOAT",
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
    "ALTER TABLE sections ADD COLUMN extra_parts VARCHAR",
    "ALTER TABLE sections ADD COLUMN comments VARCHAR",
    "ALTER TABLE sections ADD COLUMN handle_offset_left INTEGER",
    "ALTER TABLE sections ADD COLUMN handle_offset_right INTEGER",
    "ALTER TABLE sections ADD COLUMN document_overrides TEXT DEFAULT '{}'",
    # СЛАЙД 2 ряда
    "ALTER TABLE sections ADD COLUMN slide_rows INTEGER DEFAULT 1",
    "ALTER TABLE sections ADD COLUMN center_handle VARCHAR",
    "ALTER TABLE sections ADD COLUMN center_lock VARCHAR",
    "ALTER TABLE sections ADD COLUMN center_handle_offset INTEGER",
    "ALTER TABLE sections ADD COLUMN center_floor_latches_left BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN center_floor_latches_right BOOLEAN DEFAULT 0",
]


# ── Миграции данных ────────────────────────────────────────────────────────────

_DATA_MIGRATIONS = [
    # Перенос system из project в sections для старых данных
    (
        "UPDATE sections SET system = "
        "(SELECT system FROM projects WHERE projects.id = sections.project_id) "
        "WHERE system IS NULL"
    ),
    # Переименование замков (ТЗ6)
    "UPDATE sections SET lock_left = 'ЗАМОК-ЗАЩЕЛКА 1стор' WHERE lock_left = '1-сторонний RS3018'",
    "UPDATE sections SET lock_left = 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом' WHERE lock_left = '2-сторонний с ключом RS3019'",
    "UPDATE sections SET lock_right = 'ЗАМОК-ЗАЩЕЛКА 1стор' WHERE lock_right = '1-сторонний RS3018'",
    "UPDATE sections SET lock_right = 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом' WHERE lock_right = '2-сторонний с ключом RS3019'",
]


def run_migrations():
    """Выполнить все миграции. Безопасно вызывать при каждом старте."""
    with engine.connect() as conn:
        for col_sql in _ADD_COLUMNS:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass  # колонка уже существует

    with engine.connect() as conn:
        for sql in _DATA_MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
