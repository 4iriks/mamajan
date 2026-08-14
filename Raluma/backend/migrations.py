"""
Ручные SQLite-миграции.

SQLite не поддерживает IF NOT EXISTS для ALTER TABLE,
поэтому каждый ALTER оборачиваем в try/except.

Вызывается из main.py при старте приложения.
"""

from sqlalchemy import text
from database import engine
from engine.glass_types import normalize_slide_glass_type
from engine.legacy_values import (
    normalize_center_handle_offset,
)


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
    CREATE TABLE IF NOT EXISTS catalog_price_versions (
        id INTEGER PRIMARY KEY,
        catalog_item_id INTEGER NOT NULL,
        cost NUMERIC(14, 2) NOT NULL,
        profile_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        profile_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        waste_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        construction_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        construction_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        category VARCHAR NOT NULL,
        unit VARCHAR NOT NULL,
        min_margin_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        effective_from DATETIME NOT NULL,
        created_at DATETIME NOT NULL,
        created_by INTEGER NOT NULL,
        reason TEXT NOT NULL,
        rollback_of_id INTEGER,
        FOREIGN KEY(catalog_item_id) REFERENCES catalog_items(id),
        FOREIGN KEY(created_by) REFERENCES users(id),
        FOREIGN KEY(rollback_of_id) REFERENCES catalog_price_versions(id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_catalog_price_versions_item_date
    ON catalog_price_versions (catalog_item_id, effective_from)
    """,
    """
    CREATE TABLE IF NOT EXISTS dealer_pricing_terms (
        user_id INTEGER PRIMARY KEY,
        dealer_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        profile_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        construction_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        component_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        service_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL,
        updated_by INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(updated_by) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pricing_settings (
        id INTEGER PRIMARY KEY,
        include_waste_markup BOOLEAN NOT NULL DEFAULT 0,
        default_vat_rate NUMERIC(6, 3) NOT NULL DEFAULT 20,
        updated_at DATETIME NOT NULL,
        updated_by INTEGER,
        FOREIGN KEY(updated_by) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_quote_states (
        id INTEGER PRIMARY KEY,
        project_id INTEGER NOT NULL UNIQUE,
        revision INTEGER NOT NULL DEFAULT 1,
        status VARCHAR NOT NULL DEFAULT 'draft',
        public_payload TEXT NOT NULL DEFAULT '{}',
        internal_payload TEXT NOT NULL DEFAULT '{}',
        services_payload TEXT NOT NULL DEFAULT '[]',
        overrides_payload TEXT NOT NULL DEFAULT '[]',
        vat_mode VARCHAR NOT NULL DEFAULT 'none',
        vat_rate NUMERIC(6, 3) NOT NULL DEFAULT 20,
        validity_days INTEGER NOT NULL DEFAULT 14,
        manufacturing_term VARCHAR NOT NULL DEFAULT '',
        payment_terms VARCHAR NOT NULL DEFAULT '',
        margin_override_comment TEXT,
        margin_override_context_signature VARCHAR,
        margin_override_target_revision INTEGER,
        margin_override_approved_by INTEGER,
        margin_override_approved_at DATETIME,
        source_signature VARCHAR NOT NULL DEFAULT '',
        source_project_updated_at DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        fixed_at DATETIME,
        fixed_by INTEGER,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(fixed_by) REFERENCES users(id),
        FOREIGN KEY(margin_override_approved_by) REFERENCES users(id)
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
    "ALTER TABLE users ADD COLUMN can_manage_prices BOOLEAN NOT NULL DEFAULT 0",
    # project_quote_states: context-bound minimum-margin approvals. Existing
    # comments intentionally keep NULL approval metadata and are therefore invalid.
    "ALTER TABLE project_quote_states ADD COLUMN margin_override_context_signature VARCHAR",
    "ALTER TABLE project_quote_states ADD COLUMN margin_override_target_revision INTEGER",
    "ALTER TABLE project_quote_states ADD COLUMN margin_override_approved_by INTEGER",
    "ALTER TABLE project_quote_states ADD COLUMN margin_override_approved_at DATETIME",
    # projects
    "ALTER TABLE projects ADD COLUMN subtype VARCHAR",
    "ALTER TABLE projects ADD COLUMN extra_parts VARCHAR",
    "ALTER TABLE projects ADD COLUMN extra_components TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE projects ADD COLUMN hardware_installation VARCHAR NOT NULL DEFAULT 'not_installed'",
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
    # КНИЖКА — отдельные параметры дверей и предварительных конфигураций
    "ALTER TABLE sections ADD COLUMN book_left_door_hardware VARCHAR",
    "ALTER TABLE sections ADD COLUMN book_right_door_hardware VARCHAR",
    "ALTER TABLE sections ADD COLUMN book_left_door_opening VARCHAR",
    "ALTER TABLE sections ADD COLUMN book_right_door_opening VARCHAR",
    "ALTER TABLE sections ADD COLUMN book_obstacle_distance FLOAT",
    "ALTER TABLE sections ADD COLUMN book_left_stack_panels INTEGER",
    "ALTER TABLE sections ADD COLUMN book_handle_height FLOAT",
    "ALTER TABLE sections ADD COLUMN book_extra_fixed_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_extra_fixed_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_extra_fixed_side VARCHAR",
    "ALTER TABLE sections ADD COLUMN book_extra_door_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_extra_door_panel INTEGER",
    "ALTER TABLE sections ADD COLUMN book_extra_door_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_extra_door_opening VARCHAR",
    # ЛИФТ
    "ALTER TABLE sections ADD COLUMN lift_filling_type VARCHAR DEFAULT 'СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ'",
    "ALTER TABLE sections ADD COLUMN lift_filling_custom VARCHAR",
    "ALTER TABLE sections ADD COLUMN lift_control_type VARCHAR DEFAULT 'Пульт ДУ'",
    "ALTER TABLE sections ADD COLUMN lift_remote_channels INTEGER DEFAULT 1",
    "ALTER TABLE sections ADD COLUMN lift_remote_1ch_qty INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN lift_remote_6ch_qty INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN lift_cable_side VARCHAR DEFAULT 'Справа'",
    "ALTER TABLE sections ADD COLUMN lift_opening_type VARCHAR DEFAULT 'Сдвиг вниз'",
]


# ── Миграции данных ────────────────────────────────────────────────────────────

_DATA_MIGRATIONS = [
    "INSERT OR IGNORE INTO pricing_settings (id, include_waste_markup, default_vat_rate, updated_at) VALUES (1, 0, 20, CURRENT_TIMESTAMP)",
    # Старые проекты без корректно сохранённой этапности считаются одноэтапными.
    "UPDATE projects SET production_stages = 1 WHERE production_stages IS NULL OR production_stages NOT IN (1, 2)",
    "UPDATE projects SET current_stage = 1 WHERE current_stage IS NULL OR current_stage NOT IN (1, 2)",
    "UPDATE projects SET extra_components = '[]' WHERE extra_components IS NULL OR TRIM(extra_components) = ''",
    "UPDATE projects SET hardware_installation = 'not_installed' WHERE hardware_installation IS NULL OR hardware_installation NOT IN ('installed', 'not_installed')",
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
    "UPDATE sections SET glass_type = '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ' WHERE system = 'СЛАЙД' AND glass_type IN ('10ММ ПРОЗРАЧНОЕ', '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ')",
    "UPDATE sections SET glass_type = '10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ' WHERE system = 'СЛАЙД' AND glass_type IN ('10ММ БРОНЗА В МАССЕ', '10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ')",
    "UPDATE sections SET glass_type = '10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ' WHERE system = 'СЛАЙД' AND glass_type IN ('10ММ СЕРОЕ В МАССЕ', '10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ')",
    "UPDATE sections SET glass_type = '10ММ ЗАКАЛЕННОЕ МАТОВОЕ' WHERE system = 'СЛАЙД' AND glass_type IN ('10ММ МАТОВОЕ', '10ММ ЗАКАЛЕННОЕ МАТОВОЕ')",
    "UPDATE sections SET glass_type = '10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ' WHERE system = 'СЛАЙД' AND glass_type IN ('10ММ ПРОСВЕТЛЕННОЕ', '10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ')",
    "UPDATE sections SET glass_type = 'ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ' WHERE system = 'СЛАЙД' AND glass_type IN ('ТРИПЛЕКС 4.1.4', 'ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ')",
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'В заявке на покраску отмечать область, которую не красить' WHERE sku IN ('RS2323', 'RS2325')",
    "UPDATE catalog_items SET paint_mode = 'Частично', note = 'Накладной порог, верхние бобышки не красить' WHERE sku IN ('RS23231', 'RS23251')",
    "UPDATE catalog_items SET paint_mode = 'Частично', color_variants = '[\"Анод\", \"RAL стандарт\", \"RAL нестандарт\"]', note = 'W - 155 красится; W - 62 не красится по исходным Excel ЛИФТ' WHERE sku = 'RL104' AND system = 'ЛИФТ'",
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
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS1005', 'h-уплотнитель 10 мм', 'Уплотнители', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 0, 0, 'RS1005.png', 'Не красится', '[\"Без цвета\"]', 'Склад', 1, 'Центральный стык СЛАЙД 2 ряда; складская заготовка 3000 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE catalog_items SET name = 'h-уплотнитель 10 мм', \"group\" = 'Уплотнители', unit = 'м.п.', image_file = 'RS1005.png', waste_percent = 4 WHERE sku = 'RS1005'",
    "UPDATE catalog_items SET image_file = 'RS205.png' WHERE sku = 'RS205'",
    "UPDATE catalog_items SET image_file = 'RS1083.png' WHERE sku = 'RS1083'",
    "UPDATE catalog_items SET image_file = 'RS108.png' WHERE sku = 'RS108'",
    "UPDATE catalog_items SET image_file = 'RS206.png' WHERE sku = 'RS206'",
    "UPDATE catalog_items SET image_file = 'RS30301.png' WHERE sku = 'RS30301'",
    "UPDATE catalog_items SET image_file = 'RS3014.png' WHERE sku = 'RS3014'",
    "UPDATE catalog_items SET image_file = 'RS3017.png' WHERE sku = 'RS3017'",
    "UPDATE catalog_items SET image_file = 'RU003.png' WHERE sku = 'RU003'",
    "UPDATE catalog_items SET image_file = 'RU005.png' WHERE sku = 'RU005'",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS1006', 'Прозрачный межстекольный', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 20, 12, 'RS1006.png', 'Не красится', '[\"Без цвета\"]', 'Raluma', 1, 'Прозрачный межстекольный профиль, перехлест между стеклами 9,5 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS108', 'Заглушка стекольного центральная', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS108.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Центральные створки СЛАЙД 2 ряда', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RU003', 'Ролик 2-колесный', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RU003.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Для панелей шириной до 500 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RU005', 'Ролик 4-колесный', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RU005.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Для панелей шириной больше 500 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS3061', 'Профиль с зацепом', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 18.8, 18.8, 'RS3061.png', 'Не красится', '[\"Без цвета\"]', 'Raluma', 1, 'Заменяет старый h-профиль RS1004, перехлест между стеклами 11,5 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS30201', 'Ручка-скоба 600мм', 'Ручки', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS30201.png', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Боковые и центральные панели СЛАЙД', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE catalog_items SET image_file = 'RS3061.png', name = 'Профиль с зацепом' WHERE sku = 'RS3061'",
    "UPDATE catalog_items SET image_file = 'RS30201.png', name = 'Ручка-скоба 600мм' WHERE sku = 'RS30201'",
    "UPDATE catalog_items SET image_file = 'RS1006.png', name = 'Прозрачный межстекольный' WHERE sku = 'RS1006'",
    "UPDATE catalog_items SET image_file = 'RS108.png', name = 'Заглушка стекольного центральная' WHERE sku = 'RS108'",
    "UPDATE catalog_items SET image_file = 'RU003.png', name = 'Ролик 2-колесный' WHERE sku = 'RU003'",
    "UPDATE catalog_items SET image_file = 'RU005.png', name = 'Ролик 4-колесный' WHERE sku = 'RU005'",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS3110', 'h-уплотнитель центрального стыка', 'Профили', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 0, 0, 'RS3110.jpg', 'Не красится', '[\"Без цвета\"]', 'Склад', 1, 'Для центрального стыка СЛАЙД 2 ряда, кроме варианта с центральными RS112', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS123', 'Ответная планка замка RS3020', 'Фурнитура', 'СЛАЙД', 'шт', 0, 40, 0, 0, 0, 0, 'RS123.jpg', 'Не красится', '[\"Без цвета\"]', 'Фурнитура СПБ', 1, 'Ставится по одной планке на каждый замок RS3020', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE catalog_items SET name = 'Соединительный профиль 30×20×30', image_file = 'RS1083.png' WHERE sku = 'RS1083'",
    "UPDATE catalog_items SET name = 'h-уплотнитель центрального стыка', \"group\" = 'Профили', unit = 'м.п.', image_file = 'RS3110.jpg', waste_percent = 4 WHERE sku = 'RS3110'",
    "UPDATE catalog_items SET name = 'Ответная планка замка RS3020', \"group\" = 'Фурнитура', unit = 'шт', image_file = 'RS123.jpg' WHERE sku = 'RS123'",
]


def _normalize_section_center_offsets(conn):
    """Удалить старые скрытые отступы C у неподдерживаемых ручек."""
    try:
        sections = conn.execute(
            text(
                "SELECT id, center_handle, center_handle_offset "
                "FROM sections WHERE center_handle_offset IS NOT NULL"
            )
        ).fetchall()
    except Exception:
        return

    for section_id, center_handle, offset in sections:
        normalized = normalize_center_handle_offset(center_handle, offset)
        if normalized == offset:
            continue
        conn.execute(
            text(
                "UPDATE sections SET center_handle_offset = :offset "
                "WHERE id = :section_id"
            ),
            {"offset": normalized, "section_id": section_id},
        )


def _normalize_glass_catalog_items(conn):
    """Keep historical GLASS SKUs usable after the public naming migration."""
    try:
        rows = conn.execute(
            text(
                "SELECT id, sku FROM catalog_items "
                "WHERE sku LIKE 'GLASS|%' ORDER BY id"
            )
        ).fetchall()
    except Exception:
        return

    by_sku = {str(sku): int(item_id) for item_id, sku in rows}
    for item_id, sku in rows:
        sku = str(sku)
        glass_type = sku.split("|", 1)[1] if "|" in sku else ""
        normalized_type = normalize_slide_glass_type(glass_type)
        normalized_sku = f"GLASS|{normalized_type}"
        if normalized_sku == sku:
            conn.execute(
                text("UPDATE catalog_items SET name = :name WHERE id = :item_id"),
                {"name": normalized_type, "item_id": item_id},
            )
            continue

        target_id = by_sku.get(normalized_sku)
        if target_id is None:
            conn.execute(
                text(
                    "UPDATE catalog_items SET sku = :sku, name = :name "
                    "WHERE id = :item_id"
                ),
                {"sku": normalized_sku, "name": normalized_type, "item_id": item_id},
            )
            by_sku.pop(sku, None)
            by_sku[normalized_sku] = int(item_id)
            continue

        if int(target_id) == int(item_id):
            continue
        conn.execute(
            text(
                "UPDATE catalog_price_versions SET catalog_item_id = :target_id "
                "WHERE catalog_item_id = :source_id"
            ),
            {"target_id": target_id, "source_id": item_id},
        )
        conn.execute(
            text("DELETE FROM catalog_items WHERE id = :item_id"),
            {"item_id": item_id},
        )
        conn.execute(
            text("UPDATE catalog_items SET name = :name WHERE id = :target_id"),
            {"name": normalized_type, "target_id": target_id},
        )
        by_sku.pop(sku, None)


def run_migrations():
    """Выполнить все миграции. Безопасно вызывать при каждом старте."""
    # Прежние пользовательские шаблоны заменены фиксированным каталогом СЛАЙД.
    # Удаление идемпотентно и очищает все сохранённые старые шаблоны.
    with engine.connect() as conn:
        try:
            conn.execute(text("DROP TABLE IF EXISTS section_templates"))
            conn.commit()
        except Exception:
            pass

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
            _normalize_section_center_offsets(conn)
            _normalize_glass_catalog_items(conn)
            conn.commit()
        except Exception:
            pass
