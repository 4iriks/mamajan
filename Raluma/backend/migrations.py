"""
Ручные SQLite-миграции.

SQLite не поддерживает IF NOT EXISTS для ALTER TABLE,
поэтому каждый ALTER оборачиваем в try/except.

Вызывается из main.py при старте приложения.
"""

from sqlalchemy import text
from database import engine


# ── Новые таблицы ─────────────────────────────────────────────────────────────

_CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS catalog_items (
        id INTEGER PRIMARY KEY,
        sku VARCHAR NOT NULL UNIQUE,
        name VARCHAR NOT NULL,
        "group" VARCHAR NOT NULL DEFAULT 'Профили',
        system VARCHAR NOT NULL DEFAULT 'СЛАЙД',
        unit VARCHAR NOT NULL DEFAULT 'шт',
        purchase_price FLOAT NOT NULL DEFAULT 0,
        markup_percent FLOAT NOT NULL DEFAULT 0,
        weight FLOAT NOT NULL DEFAULT 0,
        waste_percent FLOAT NOT NULL DEFAULT 0,
        section_width_mm FLOAT NOT NULL DEFAULT 0,
        section_height_mm FLOAT NOT NULL DEFAULT 0,
        image_file VARCHAR,
        paint_mode VARCHAR NOT NULL DEFAULT 'Не красится',
        color_variants TEXT NOT NULL DEFAULT '[]',
        supplier VARCHAR,
        is_active BOOLEAN DEFAULT 1,
        note TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS section_templates (
        id INTEGER PRIMARY KEY,
        name VARCHAR NOT NULL,
        system VARCHAR NOT NULL,
        template_data TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(created_by) REFERENCES users(id)
    )
    """,
]


# ── Новые колонки ──────────────────────────────────────────────────────────────

_ADD_COLUMNS = [
    # users
    "ALTER TABLE users ADD COLUMN employee_number VARCHAR",
    "ALTER TABLE users ADD COLUMN position VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_company VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_contact_name VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_phone VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_email VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_city VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_address VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_inn VARCHAR",
    "ALTER TABLE users ADD COLUMN dealer_discount_percent FLOAT",
    "ALTER TABLE users ADD COLUMN dealer_notes TEXT",
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
    "ALTER TABLE sections ADD COLUMN extra_components TEXT DEFAULT '[]'",
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
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'В заявке на покраску отмечать область, которую не красить' WHERE sku IN ('RS2323', 'RS2325')",
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'Накладной порог, верхние бобышки не красить' WHERE sku IN ('RS23231', 'RS23251')",
]


def run_migrations():
    """Выполнить все миграции. Безопасно вызывать при каждом старте."""
    with engine.connect() as conn:
        for table_sql in _CREATE_TABLES:
            try:
                conn.execute(text(table_sql))
                conn.commit()
            except Exception:
                pass

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
