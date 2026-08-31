"""
Ручные SQLite-миграции.

SQLite не поддерживает IF NOT EXISTS для ALTER TABLE,
поэтому каждый ALTER оборачиваем в try/except.

Вызывается из main.py при старте приложения.
"""

import json

from sqlalchemy import text
from database import engine
from engine.glass_types import normalize_slide_glass_type
from engine.legacy_values import (
    normalize_center_handle_offset,
)


# ── Новые таблицы ─────────────────────────────────────────────────────────────

_CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS migration_markers (
        name VARCHAR PRIMARY KEY,
        applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS catalog_items (
        id INTEGER PRIMARY KEY,
        sku VARCHAR NOT NULL UNIQUE,
        name VARCHAR NOT NULL,
        "group" VARCHAR NOT NULL DEFAULT 'Профили',
        system VARCHAR NOT NULL DEFAULT 'СЛАЙД',
        system_groups TEXT NOT NULL DEFAULT '["SLIDE_1", "SLIDE_2"]',
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
        finish_variant_id INTEGER,
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
        FOREIGN KEY(finish_variant_id) REFERENCES catalog_finish_variants(id),
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
        discounts_payload TEXT NOT NULL DEFAULT '[]',
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
    """
    CREATE TABLE IF NOT EXISTS catalog_finish_variants (
        id INTEGER PRIMARY KEY,
        catalog_item_id INTEGER NOT NULL,
        code VARCHAR NOT NULL DEFAULT 'BASE',
        name VARCHAR NOT NULL,
        price NUMERIC(14, 2) NOT NULL DEFAULT 0,
        cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
        profile_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        profile_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        construction_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        construction_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        requires_paint BOOLEAN NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(catalog_item_id) REFERENCES catalog_items(id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_catalog_finish_variants_item
    ON catalog_finish_variants (catalog_item_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS construction_price_groups (
        id INTEGER PRIMARY KEY,
        code VARCHAR NOT NULL UNIQUE,
        name VARCHAR NOT NULL,
        markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_by INTEGER,
        FOREIGN KEY(updated_by) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invoice_counters (
        name VARCHAR PRIMARY KEY,
        value INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_projects_invoice_number
    ON projects (invoice_number) WHERE invoice_number IS NOT NULL
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
    "ALTER TABLE project_quote_states ADD COLUMN discounts_payload TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE catalog_finish_variants ADD COLUMN cost NUMERIC(14, 2) NOT NULL DEFAULT 0",
    'ALTER TABLE catalog_items ADD COLUMN system_groups TEXT NOT NULL DEFAULT \'["SLIDE_1", "SLIDE_2"]\'',
    "ALTER TABLE catalog_finish_variants ADD COLUMN code VARCHAR NOT NULL DEFAULT 'BASE'",
    "ALTER TABLE catalog_finish_variants ADD COLUMN profile_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0",
    "ALTER TABLE catalog_finish_variants ADD COLUMN profile_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0",
    "ALTER TABLE catalog_finish_variants ADD COLUMN construction_markup_percent NUMERIC(8, 4) NOT NULL DEFAULT 0",
    "ALTER TABLE catalog_finish_variants ADD COLUMN construction_discount_percent NUMERIC(8, 4) NOT NULL DEFAULT 0",
    "ALTER TABLE catalog_price_versions ADD COLUMN finish_variant_id INTEGER",
    # projects
    "ALTER TABLE projects ADD COLUMN invoice_number VARCHAR",
    "ALTER TABLE projects ADD COLUMN order_number VARCHAR",
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
    "ALTER TABLE sections ADD COLUMN glass_supplied BOOLEAN NOT NULL DEFAULT 1",
    "ALTER TABLE sections ADD COLUMN price_group_id INTEGER",
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
    "ALTER TABLE sections ADD COLUMN book_left_door_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_right_door_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_left_fixed_left_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_left_fixed_left_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_left_fixed_right_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_left_fixed_right_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_right_fixed_left_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_right_fixed_left_width FLOAT",
    "ALTER TABLE sections ADD COLUMN book_right_fixed_right_enabled BOOLEAN DEFAULT 0",
    "ALTER TABLE sections ADD COLUMN book_right_fixed_right_width FLOAT",
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
    "INSERT OR IGNORE INTO pricing_settings (id, include_waste_markup, default_vat_rate, updated_at) VALUES (1, 1, 20, CURRENT_TIMESTAMP)",
    "UPDATE pricing_settings SET include_waste_markup = 1 WHERE id = 1",
    # Старые проекты без корректно сохранённой этапности считаются одноэтапными.
    "UPDATE projects SET production_stages = 1 WHERE production_stages IS NULL OR production_stages NOT IN (1, 2)",
    "UPDATE projects SET current_stage = 1 WHERE current_stage IS NULL OR current_stage NOT IN (1, 2)",
    "UPDATE projects SET extra_components = '[]' WHERE extra_components IS NULL OR TRIM(extra_components) = ''",
    # Historical ``number`` is the manually entered order reference.  Invoice
    # numbers intentionally remain NULL for every pre-migration project.
    "UPDATE projects SET order_number = number WHERE order_number IS NULL",
    "UPDATE projects SET hardware_installation = 'not_installed' WHERE hardware_installation IS NULL OR hardware_installation NOT IN ('installed', 'not_installed')",
    "UPDATE sections SET glass_supplied = 1 WHERE glass_supplied IS NULL",
    "INSERT OR IGNORE INTO construction_price_groups (code, name, markup_percent, is_active, created_at, updated_at) VALUES ('SLIDE', 'СЛАЙД', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO construction_price_groups (code, name, markup_percent, is_active, created_at, updated_at) VALUES ('BOOK', 'КНИЖКА', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO construction_price_groups (code, name, markup_percent, is_active, created_at, updated_at) VALUES ('LIFT', 'ЛИФТ', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO construction_price_groups (code, name, markup_percent, is_active, created_at, updated_at) VALUES ('SLIDE_1', 'СЛАЙД 1 ряд', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "INSERT OR IGNORE INTO construction_price_groups (code, name, markup_percent, is_active, created_at, updated_at) VALUES ('SLIDE_2', 'СЛАЙД 2 ряда', 0, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
    "UPDATE construction_price_groups SET is_active = 0 WHERE code IN ('SLIDE', 'BOOK', 'LIFT')",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = CASE WHEN COALESCE(slide_rows, 1) = 2 THEN 'SLIDE_2' ELSE 'SLIDE_1' END) WHERE UPPER(TRIM(system)) = 'СЛАЙД'",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'SLIDE') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'СЛАЙД'",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'BOOK') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'КНИЖКА'",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'LIFT') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'ЛИФТ'",
    # Перенос system из project в sections для старых данных
    (
        "UPDATE sections SET system = "
        "(SELECT system FROM projects WHERE projects.id = sections.project_id) "
        "WHERE system IS NULL"
    ),
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'SLIDE') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'СЛАЙД'",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'BOOK') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'КНИЖКА'",
    "UPDATE sections SET price_group_id = (SELECT id FROM construction_price_groups WHERE code = 'LIFT') WHERE price_group_id IS NULL AND UPPER(TRIM(system)) = 'ЛИФТ'",
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
    # Insert-only migration: once RS1005 exists, administrator edits must win.
    "INSERT OR IGNORE INTO catalog_items (sku, name, \"group\", system, unit, purchase_price, markup_percent, weight, waste_percent, section_width_mm, section_height_mm, image_file, paint_mode, color_variants, supplier, is_active, note, created_at, updated_at) VALUES ('RS1005', 'h-уплотнитель 10 мм', 'Уплотнители', 'СЛАЙД', 'м.п.', 0, 35, 0, 4, 0, 0, 'RS1005.png', 'Не красится', '[\"Без цвета\"]', 'Склад', 1, 'Центральный стык СЛАЙД 2 ряда; складская заготовка 3000 мм', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
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
                "SELECT id, sku FROM catalog_items WHERE sku LIKE 'GLASS|%' ORDER BY id"
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


def _json_list(value: object) -> list[dict]:
    try:
        parsed = json.loads(value or "[]") if not isinstance(value, list) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [dict(row) for row in parsed if isinstance(row, dict)]


def _extra_quantity(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return max(0.0, float(str(value).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _quantity_text(value: float) -> str:
    rounded = round(value, 6)
    return str(int(rounded)) if rounded.is_integer() else f"{rounded:g}"


def _extra_key(row: dict) -> tuple[str, ...]:
    def clean(*names: str) -> str:
        for name in names:
            value = row.get(name)
            if value not in (None, ""):
                return " ".join(str(value).strip().casefold().split())
        return ""

    return (
        clean("catalog_item_id", "catalogItemId"),
        clean("finish_variant_id", "finishVariantId"),
        clean("sku", "art", "article"),
        clean("name"),
        clean("finish_name", "finishName", "color"),
        clean("size"),
        clean("unit"),
        clean("deliveryStage", "delivery_stage", "stage"),
    )


def _merge_extra_rows(target: list[dict], row: dict) -> None:
    key = _extra_key(row)
    existing = next((item for item in target if _extra_key(item) == key), None)
    if existing is None:
        target.append(row)
        return
    old_qty = _extra_quantity(existing.get("qty", existing.get("quantity")))
    new_qty = _extra_quantity(row.get("qty", row.get("quantity")))
    if old_qty is not None and new_qty is not None:
        existing["qty"] = _quantity_text(old_qty + new_qty)
        existing.pop("quantity", None)


def _migrate_section_extras_to_project(conn) -> None:
    """Move legacy section extras once and clear their legacy source rows.

    Quantities in a section were specified per product, so migration multiplies
    them by ``Section.quantity``.  Matching snapshots are merged, preventing
    duplicate shipment/paint/document rows.
    """

    try:
        projects = conn.execute(
            text("SELECT id, extra_components FROM projects ORDER BY id")
        ).fetchall()
    except Exception:
        return
    for project_id, project_raw in projects:
        section_rows = conn.execute(
            text(
                "SELECT id, quantity, extra_components FROM sections "
                "WHERE project_id = :project_id ORDER BY id"
            ),
            {"project_id": project_id},
        ).fetchall()
        migrated = False
        merged: list[dict] = []
        for existing in _json_list(project_raw):
            _merge_extra_rows(merged, existing)
        for section_id, section_quantity, raw in section_rows:
            legacy = _json_list(raw)
            if not legacy:
                continue
            multiplier = _extra_quantity(section_quantity) or 1.0
            for source in legacy:
                row = dict(source)
                qty = _extra_quantity(row.get("qty", row.get("quantity")))
                if qty is not None:
                    row["qty"] = _quantity_text(qty * multiplier)
                    row.pop("quantity", None)
                _merge_extra_rows(merged, row)
            conn.execute(
                text("UPDATE sections SET extra_components = '[]' WHERE id = :id"),
                {"id": section_id},
            )
            migrated = True
        if migrated:
            conn.execute(
                text(
                    "UPDATE projects SET extra_components = :payload "
                    "WHERE id = :project_id"
                ),
                {
                    "payload": json.dumps(merged, ensure_ascii=False),
                    "project_id": project_id,
                },
            )


def _backfill_finish_variants(conn) -> None:
    """Convert legacy color-name arrays into first-class finish variants."""

    try:
        items = conn.execute(
            text(
                "SELECT id, color_variants, purchase_price, markup_percent, "
                "paint_mode FROM catalog_items ORDER BY id"
            )
        ).fetchall()
    except Exception:
        return
    for item_id, raw, purchase_price, markup_percent, paint_mode in items:
        existing = conn.execute(
            text(
                "SELECT COUNT(*) FROM catalog_finish_variants "
                "WHERE catalog_item_id = :item_id"
            ),
            {"item_id": item_id},
        ).scalar_one()
        if existing:
            continue
        try:
            names = json.loads(raw or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            names = []
        if not isinstance(names, list):
            continue
        base_price = max(0.0, float(purchase_price or 0)) * (
            1 + max(0.0, float(markup_percent or 0)) / 100
        )
        mode = str(paint_mode or "").casefold()
        for value in names:
            name = " ".join(str(value or "").split())
            if not name:
                continue
            normalized = name.casefold()
            requires_paint = ("ral" in normalized or "окрас" in normalized) or (
                ("красится" in mode or "частично" in mode)
                and "не красится" not in mode
                and "анод" not in normalized
                and "без цвета" not in normalized
            )
            conn.execute(
                text(
                    "INSERT INTO catalog_finish_variants "
                    "(catalog_item_id, name, price, cost, requires_paint, is_active, "
                    "created_at, updated_at) VALUES "
                    "(:item_id, :name, :price, :cost, :requires_paint, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "item_id": item_id,
                    "name": name,
                    "price": round(base_price, 2),
                    "cost": max(0.0, float(purchase_price or 0)),
                    "requires_paint": bool(requires_paint),
                },
            )


def _backfill_finish_variant_costs_once(conn) -> None:
    marker = "catalog-finish-variant-cost-v1"
    applied = conn.execute(
        text("SELECT 1 FROM migration_markers WHERE name = :name"),
        {"name": marker},
    ).first()
    if applied:
        return
    conn.execute(
        text(
            "UPDATE catalog_finish_variants SET cost = CASE "
            "WHEN ABS(price - (SELECT COALESCE(purchase_price, 0) * "
            "(1 + COALESCE(markup_percent, 0) / 100.0) FROM catalog_items "
            "WHERE catalog_items.id = catalog_finish_variants.catalog_item_id)) < 0.01 "
            "THEN (SELECT COALESCE(purchase_price, 0) FROM catalog_items "
            "WHERE catalog_items.id = catalog_finish_variants.catalog_item_id) "
            "ELSE price END WHERE cost = 0"
        )
    )
    conn.execute(
        text("INSERT INTO migration_markers (name) VALUES (:name)"),
        {"name": marker},
    )


def _catalog_finish_code(name: object) -> str:
    normalized = " ".join(str(name or "").strip().casefold().split())
    if "нестандарт" in normalized:
        return "RAL_NONSTANDARD"
    if "ral" in normalized:
        return "RAL_STANDARD"
    if "анод" in normalized:
        return "ANOD"
    return "BASE"


def _migrate_unified_catalog_pricing_once(conn) -> None:
    """Move the active catalog price into fixed execution rows exactly once."""

    marker = "unified-catalog-finish-pricing-v1"
    if conn.execute(
        text("SELECT 1 FROM migration_markers WHERE name = :name"),
        {"name": marker},
    ).first():
        return

    two_row_only = {"RS1005", "RS108", "RS1083", "RS3110"}
    items = conn.execute(
        text(
            "SELECT id, sku, system, paint_mode, purchase_price, markup_percent, "
            'waste_percent, "group", unit FROM catalog_items ORDER BY id'
        )
    ).fetchall()
    actor_id = conn.execute(
        text(
            "SELECT id FROM users WHERE role IN ('admin', 'superadmin') "
            "ORDER BY CASE WHEN role = 'superadmin' THEN 0 ELSE 1 END, id LIMIT 1"
        )
    ).scalar()
    finish_names = {
        "BASE": ("Без окраски", False),
        "ANOD": ("Анод", False),
        "RAL_STANDARD": ("RAL стандарт", True),
        "RAL_NONSTANDARD": ("RAL нестандарт", True),
    }

    for (
        item_id,
        sku,
        system,
        paint_mode,
        purchase_price,
        markup_percent,
        waste_percent,
        group_name,
        unit,
    ) in items:
        if "СЛАЙД" in str(system or "").upper():
            groups = (
                ["SLIDE_2"]
                if str(sku or "").upper() in two_row_only
                else ["SLIDE_1", "SLIDE_2"]
            )
        else:
            groups = []
        conn.execute(
            text("UPDATE catalog_items SET system_groups = :groups WHERE id = :id"),
            {"groups": json.dumps(groups, ensure_ascii=False), "id": item_id},
        )

        mode = " ".join(str(paint_mode or "").strip().casefold().split())
        paintable = (
            "красится" in mode and "не красится" not in mode
        ) or "частично" in mode
        expected_codes = (
            ["ANOD", "RAL_STANDARD", "RAL_NONSTANDARD"] if paintable else ["BASE"]
        )
        variants = conn.execute(
            text(
                "SELECT id, name, cost FROM catalog_finish_variants "
                "WHERE catalog_item_id = :item_id ORDER BY id"
            ),
            {"item_id": item_id},
        ).fetchall()
        variants_by_code = {
            _catalog_finish_code(name): (variant_id, cost)
            for variant_id, name, cost in variants
        }
        active_price = conn.execute(
            text(
                "SELECT cost, profile_markup_percent, profile_discount_percent, "
                "construction_markup_percent, construction_discount_percent, "
                "category, unit, min_margin_percent FROM catalog_price_versions "
                "WHERE catalog_item_id = :item_id AND finish_variant_id IS NULL "
                "AND effective_from <= CURRENT_TIMESTAMP "
                "ORDER BY effective_from DESC, id DESC LIMIT 1"
            ),
            {"item_id": item_id},
        ).first()
        if active_price:
            (
                base_cost,
                profile_markup,
                profile_discount,
                construction_markup,
                construction_discount,
                category,
                price_unit,
                min_margin,
            ) = active_price
        else:
            base_cost = purchase_price or 0
            profile_markup = markup_percent or 0
            profile_discount = 0
            construction_markup = 0
            construction_discount = 0
            category = (
                "profile" if "проф" in str(group_name or "").casefold() else "component"
            )
            price_unit = unit or "шт"
            min_margin = 0

        retained_ids = []
        for code in expected_codes:
            fixed_name, requires_paint = finish_names[code]
            existing = variants_by_code.get(code)
            if existing:
                variant_id, variant_cost = existing
                selected_cost = (
                    variant_cost if variant_cost not in (None, 0) else base_cost
                )
                conn.execute(
                    text(
                        "UPDATE catalog_finish_variants SET code = :code, name = :name, "
                        "cost = :cost, price = :cost, profile_markup_percent = :profile_markup, "
                        "profile_discount_percent = :profile_discount, "
                        "construction_markup_percent = :construction_markup, "
                        "construction_discount_percent = :construction_discount, "
                        "requires_paint = :requires_paint, is_active = 1, "
                        "updated_at = CURRENT_TIMESTAMP WHERE id = :variant_id"
                    ),
                    {
                        "code": code,
                        "name": fixed_name,
                        "cost": selected_cost,
                        "profile_markup": profile_markup,
                        "profile_discount": profile_discount,
                        "construction_markup": construction_markup,
                        "construction_discount": construction_discount,
                        "requires_paint": requires_paint,
                        "variant_id": variant_id,
                    },
                )
            else:
                result = conn.execute(
                    text(
                        "INSERT INTO catalog_finish_variants "
                        "(catalog_item_id, code, name, price, cost, "
                        "profile_markup_percent, profile_discount_percent, "
                        "construction_markup_percent, construction_discount_percent, "
                        "requires_paint, is_active, created_at, updated_at) VALUES "
                        "(:item_id, :code, :name, :cost, :cost, :profile_markup, "
                        ":profile_discount, :construction_markup, :construction_discount, "
                        ":requires_paint, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "item_id": item_id,
                        "code": code,
                        "name": fixed_name,
                        "cost": base_cost,
                        "profile_markup": profile_markup,
                        "profile_discount": profile_discount,
                        "construction_markup": construction_markup,
                        "construction_discount": construction_discount,
                        "requires_paint": requires_paint,
                    },
                )
                variant_id = result.lastrowid
                selected_cost = base_cost
            retained_ids.append(int(variant_id))
            if (
                actor_id
                and not conn.execute(
                    text(
                        "SELECT 1 FROM catalog_price_versions WHERE "
                        "catalog_item_id = :item_id AND finish_variant_id = :variant_id LIMIT 1"
                    ),
                    {"item_id": item_id, "variant_id": variant_id},
                ).first()
            ):
                conn.execute(
                    text(
                        "INSERT INTO catalog_price_versions "
                        "(catalog_item_id, finish_variant_id, cost, profile_markup_percent, "
                        "profile_discount_percent, waste_markup_percent, "
                        "construction_markup_percent, construction_discount_percent, "
                        "category, unit, min_margin_percent, effective_from, created_at, "
                        "created_by, reason) VALUES (:item_id, :variant_id, :cost, "
                        ":profile_markup, :profile_discount, :waste, :construction_markup, "
                        ":construction_discount, :category, :unit, :min_margin, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :actor_id, :reason)"
                    ),
                    {
                        "item_id": item_id,
                        "variant_id": variant_id,
                        "cost": selected_cost,
                        "profile_markup": profile_markup,
                        "profile_discount": profile_discount,
                        "waste": waste_percent or 0,
                        "construction_markup": construction_markup,
                        "construction_discount": construction_discount,
                        "category": category,
                        "unit": price_unit,
                        "min_margin": min_margin,
                        "actor_id": actor_id,
                        "reason": f"Миграция исполнения {fixed_name}",
                    },
                )
        if retained_ids:
            placeholders = ", ".join(str(value) for value in retained_ids)
            conn.execute(
                text(
                    "UPDATE catalog_finish_variants SET is_active = 0 "
                    f"WHERE catalog_item_id = :item_id AND id NOT IN ({placeholders})"
                ),
                {"item_id": item_id},
            )
        conn.execute(
            text(
                "UPDATE catalog_items SET color_variants = :variants WHERE id = :item_id"
            ),
            {
                "variants": json.dumps(
                    [finish_names[code][0] for code in expected_codes],
                    ensure_ascii=False,
                ),
                "item_id": item_id,
            },
        )

    conn.execute(
        text("UPDATE project_quote_states SET vat_mode = 'none', vat_rate = 0")
    )
    conn.execute(
        text("INSERT INTO migration_markers (name) VALUES (:name)"),
        {"name": marker},
    )


def _sync_invoice_counter(conn) -> None:
    """Never let the atomic allocator move behind an already issued invoice."""

    try:
        maximum = conn.execute(
            text(
                "SELECT COALESCE(MAX(CAST(invoice_number AS INTEGER)), 0) "
                "FROM projects WHERE invoice_number IS NOT NULL "
                "AND invoice_number <> ''"
            )
        ).scalar_one()
    except Exception:
        maximum = 0
    conn.execute(
        text(
            "INSERT OR IGNORE INTO invoice_counters (name, value) "
            "VALUES ('project_invoice', :value)"
        ),
        {"value": int(maximum or 0)},
    )
    conn.execute(
        text(
            "UPDATE invoice_counters SET value = :value "
            "WHERE name = 'project_invoice' AND value < :value"
        ),
        {"value": int(maximum or 0)},
    )


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

        # The partial unique index cannot be created before the legacy table
        # receives ``invoice_number``; retry it after all ALTER statements.
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_projects_invoice_number "
                    "ON projects (invoice_number) WHERE invoice_number IS NOT NULL"
                )
            )
            conn.commit()
        except Exception:
            pass

    with engine.connect() as conn:
        for sql in _DATA_MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

        migrations = (
            _normalize_section_center_offsets,
            _normalize_glass_catalog_items,
            _backfill_finish_variant_costs_once,
            _backfill_finish_variants,
            _migrate_unified_catalog_pricing_once,
            _migrate_section_extras_to_project,
            _sync_invoice_counter,
        )
        for migration in migrations:
            try:
                migration(conn)
                conn.commit()
            except Exception:
                conn.rollback()
