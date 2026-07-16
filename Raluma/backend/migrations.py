"""
Ручные SQLite-миграции.

SQLite не поддерживает IF NOT EXISTS для ALTER TABLE,
поэтому каждый ALTER оборачиваем в try/except.

Вызывается из main.py при старте приложения.
"""

import json

from sqlalchemy import text
from database import engine
from engine.legacy_values import normalize_section_data_values


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
    "ALTER TABLE projects ADD COLUMN paint_manual_rows TEXT DEFAULT '[]'",
    "ALTER TABLE projects ADD COLUMN delivery_note_data TEXT DEFAULT '{}'",
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
    "UPDATE sections SET lock_left = 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018' WHERE lock_left IN ('1-сторонний RS3018', 'ЗАМОК-ЗАЩЕЛКА 1стор')",
    "UPDATE sections SET lock_left = 'ЗАМОК двухсторонний с ключом RS3020' WHERE lock_left IN ('2-сторонний с ключом RS3019', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом')",
    "UPDATE sections SET lock_right = 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018' WHERE lock_right IN ('1-сторонний RS3018', 'ЗАМОК-ЗАЩЕЛКА 1стор')",
    "UPDATE sections SET lock_right = 'ЗАМОК двухсторонний с ключом RS3020' WHERE lock_right IN ('2-сторонний с ключом RS3019', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом')",
    "UPDATE sections SET handle_left = 'Ручка-скоба 600мм RS30201' WHERE handle_left = 'Ручка-скоба'",
    "UPDATE sections SET handle_right = 'Ручка-скоба 600мм RS30201' WHERE handle_right = 'Ручка-скоба'",
    "UPDATE sections SET center_handle = 'Ручка-скоба 600мм RS30201' WHERE center_handle = 'Ручка-скоба'",
    "UPDATE sections SET lock = 'ЗАМОК двухсторонний с ключом RS3020' WHERE lock IN ('RS3019 С ключом', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом')",
    "UPDATE sections SET handle = 'Ручка-скоба 600мм RS30201' WHERE handle = 'Ручка-скоба'",
    "UPDATE sections SET inter_glass_profile = 'Профиль с зацепом RS3061' WHERE inter_glass_profile = 'h-профиль RS1004'",
    "UPDATE sections SET inter_glass_profile = 'Алюминиевый RS2061' WHERE system = 'СЛАЙД' AND inter_glass_profile IS NULL",
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'В заявке на покраску отмечать область, которую не красить' WHERE sku IN ('RS2323', 'RS2325')",
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'Накладной порог, верхние бобышки не красить' WHERE sku IN ('RS23231', 'RS23251')",
    "UPDATE catalog_items SET image_file = 'RS1313.png' WHERE sku = 'RS1313'",
    "UPDATE catalog_items SET image_file = 'RS1315.png' WHERE sku = 'RS1315'",
    "UPDATE catalog_items SET image_file = 'RS2323.png' WHERE sku = 'RS2323'",
    "UPDATE catalog_items SET image_file = 'RS2325.png' WHERE sku = 'RS2325'",
    "UPDATE catalog_items SET image_file = 'RS23231.png' WHERE sku = 'RS23231'",
    "UPDATE catalog_items SET image_file = 'RS23251.png' WHERE sku = 'RS23251'",
    "UPDATE catalog_items SET name = 'Порог накладной 3-рельсовый' WHERE sku = 'RS23231'",
    "UPDATE catalog_items SET name = 'Порог накладной 5-рельсовый' WHERE sku = 'RS23251'",
    "UPDATE catalog_items SET image_file = 'RS2333.png' WHERE sku = 'RS2333'",
    "UPDATE catalog_items SET image_file = 'RS2335.png' WHERE sku = 'RS2335'",
    "UPDATE catalog_items SET image_file = 'RS2081.png' WHERE sku = 'RS2081'",
    "UPDATE catalog_items SET image_file = 'RS1082.png' WHERE sku = 'RS1082'",
    "UPDATE catalog_items SET image_file = 'RS112.png' WHERE sku = 'RS112'",
    "UPDATE catalog_items SET image_file = 'RS2061.png' WHERE sku = 'RS2061'",
    "UPDATE catalog_items SET image_file = 'RS1006.png' WHERE sku = 'RS1006'",
    "UPDATE catalog_items SET image_file = 'RS2021.png' WHERE sku = 'RS2021'",
    "UPDATE catalog_items SET image_file = 'RS1002.png' WHERE sku = 'RS1002'",
    "UPDATE catalog_items SET image_file = 'RS205.png' WHERE sku = 'RS205'",
    "UPDATE catalog_items SET image_file = 'RS1083.png' WHERE sku = 'RS1083'",
    "UPDATE catalog_items SET image_file = 'RS108.png' WHERE sku = 'RS108'",
    "UPDATE catalog_items SET image_file = 'RS206.png' WHERE sku = 'RS206'",
    "UPDATE catalog_items SET image_file = 'RS30301.png' WHERE sku = 'RS30301'",
    "UPDATE catalog_items SET image_file = 'RS3014.png' WHERE sku = 'RS3014'",
    "UPDATE catalog_items SET image_file = 'RS3017.png' WHERE sku = 'RS3017'",
    "UPDATE catalog_items SET image_file = 'RU003.png' WHERE sku = 'RU003'",
    "UPDATE catalog_items SET image_file = 'RU005.png' WHERE sku = 'RU005'",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS1006', 'Прозрачный профиль', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 20, 12, 'RS1006.png', 'Не красится', '[\"Без цвета\"]', 'Raluma', 1, 'Прозрачный межстекольный профиль, перехлест между стеклами 9,5 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS108', 'Заглушка стекольного центральная', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS108.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Центральные створки СЛАЙД 2 ряда', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RU003', 'Ролик 2-колесный', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RU003.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Для панелей шириной до 500 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RU005', 'Ролик 4-колесный', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RU005.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Для панелей шириной больше 500 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS3061', 'Профиль с зацепом', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 18.8, 18.8, 'RS3061.png', 'Не красится', '[\"Без цвета\"]', 'Raluma', 1, 'Заменяет старый h-профиль RS1004, перехлест между стеклами 11,5 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS30201', 'Ручка-скоба 600мм', 'Ручки', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS30201.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Боковые и центральные панели СЛАЙД', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE catalog_items SET image_file = 'RS3061.png', name = 'Профиль с зацепом' WHERE sku = 'RS3061'",
    "UPDATE catalog_items SET image_file = 'RS30201.png', name = 'Ручка-скоба 600мм' WHERE sku = 'RS30201'",
    "UPDATE catalog_items SET image_file = 'RS1006.png', name = 'Прозрачный профиль' WHERE sku = 'RS1006'",
    "UPDATE catalog_items SET image_file = 'RS108.png', name = 'Заглушка стекольного центральная' WHERE sku = 'RS108'",
    "UPDATE catalog_items SET image_file = 'RU003.png', name = 'Ролик 2-колесный' WHERE sku = 'RU003'",
    "UPDATE catalog_items SET image_file = 'RU005.png', name = 'Ролик 4-колесный' WHERE sku = 'RU005'",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS3110', 'h-уплотнитель центрального стыка', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 0, 0, 'RS3110.jpg', 'Не красится', '[\"Без цвета\"]', 'Склад', 1, 'Для центрального стыка СЛАЙД 2 ряда, кроме варианта с центральными RS112', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS123', 'Ответная планка замка RS3020', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS123.jpg', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Ставится по одной планке на каждый замок RS3020', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE catalog_items SET name = 'Соединительный профиль 30×20×30', image_file = 'RS1083.png' WHERE sku = 'RS1083'",
    "UPDATE catalog_items SET name = 'h-уплотнитель центрального стыка', \"group\" = 'Профили', unit = 'м.п.', image_file = 'RS3110.jpg', waste_percent = 4 WHERE sku = 'RS3110'",
    "UPDATE catalog_items SET name = 'Ответная планка замка RS3020', \"group\" = 'Фурнитура', unit = 'шт', image_file = 'RS123.jpg' WHERE sku = 'RS123'",
]


def _normalize_section_templates(conn):
    """Обновить legacy-значения внутри JSON шаблонов секций."""
    try:
        templates = conn.execute(
            text("SELECT id, template_data FROM section_templates")
        ).fetchall()
    except Exception:
        return

    for template_id, raw_data in templates:
        try:
            data = json.loads(raw_data or "{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        normalized = normalize_section_data_values(data)
        if normalized == data:
            continue
        conn.execute(
            text(
                "UPDATE section_templates "
                "SET template_data = :template_data "
                "WHERE id = :template_id"
            ),
            {
                "template_data": json.dumps(normalized, ensure_ascii=False),
                "template_id": template_id,
            },
        )


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

        try:
            _normalize_section_templates(conn)
            conn.commit()
        except Exception:
            pass
