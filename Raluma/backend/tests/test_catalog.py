import sqlite3
import json
import io
import zipfile
from decimal import Decimal

from database import SessionLocal
import models


def test_rs1005_insert_migration_preserves_admin_changes():
    from migrations import _CREATE_TABLES, _DATA_MIGRATIONS

    connection = sqlite3.connect(":memory:")
    catalog_table_sql = next(
        sql
        for sql in _CREATE_TABLES
        if "CREATE TABLE IF NOT EXISTS catalog_items" in sql
    )
    rs1005_insert = next(
        sql
        for sql in _DATA_MIGRATIONS
        if "INSERT OR IGNORE INTO catalog_items" in sql and "('RS1005'" in sql
    )
    connection.execute(catalog_table_sql)
    connection.execute(rs1005_insert)
    connection.execute(
        'UPDATE catalog_items SET name = ?, "group" = ?, unit = ?, '
        "image_file = ?, waste_percent = ? WHERE sku = 'RS1005'",
        ("Название администратора", "Своя группа", "компл.", "custom.png", 17),
    )

    connection.execute(rs1005_insert)
    row = connection.execute(
        'SELECT name, "group", unit, image_file, waste_percent '
        "FROM catalog_items WHERE sku = 'RS1005'"
    ).fetchone()

    assert row == (
        "Название администратора",
        "Своя группа",
        "компл.",
        "custom.png",
        17,
    )


def test_hardware_catalog_requires_admin(client):
    r = client.get("/api/catalog/hardware")

    assert r.status_code in (401, 403)


def test_hardware_catalog_options_are_public(client):
    r = client.get("/api/catalog/hardware/options")

    assert r.status_code == 200
    data = r.json()
    skus = {item["sku"] for item in data}
    assert "RS30301" in skus
    assert "RS2323" in skus
    assert "RS1313" in skus
    assert "RS3110" in skus
    assert "RS1005" in skus
    assert "RS123" in skus
    assert "RL101" in skus
    assert "RL2085" in skus
    assert all(item["unit"] for item in data)
    assert "purchasePrice" not in data[0]


def test_no_color_catalog_item_auto_selects_hidden_execution_snapshot(
    client, admin_headers
):
    options = client.get("/api/catalog/hardware/options").json()
    item = next(
        row for row in options if not row["finishVariants"] and not row["requiresPaint"]
    )
    response = client.post(
        "/api/projects",
        headers=admin_headers,
        json={
            "order_number": "NO-COLOR",
            "customer": "Тест",
            "extra_components": json.dumps(
                [{"catalog_item_id": item["id"], "qty": 1}],
                ensure_ascii=False,
            ),
        },
    )
    assert response.status_code == 201, response.text
    try:
        snapshot = json.loads(response.json()["extra_components"])[0]
        assert snapshot["finish_variant_id"] == item["finishVariants"][0]["id"]
        assert snapshot["finish_name"] == ""
        assert snapshot["requires_paint"] is False
    finally:
        client.delete(f"/api/projects/{response.json()['id']}", headers=admin_headers)


def test_hardware_catalog_options_use_natural_sku_order(client, admin_headers):
    created_ids = []
    for sku in ("ZZ10-NATURAL", "ZZ2-NATURAL", "ZZ-NATURAL"):
        response = client.post(
            "/api/catalog/hardware",
            headers=admin_headers,
            json={
                "sku": sku,
                "name": f"Позиция {sku}",
                "group": "Фурнитура",
                "system": "Все",
                "unit": "шт",
                "purchasePrice": 0,
                "markupPercent": 0,
                "weight": 0,
                "wastePercent": 0,
                "sectionWidthMm": 0,
                "sectionHeightMm": 0,
                "imageFile": "",
                "paintMode": "Не красится",
                "colorVariants": ["Без цвета"],
                "supplier": "Тест",
                "isActive": True,
                "note": "natural sort",
            },
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    options = client.get("/api/catalog/hardware/options").json()
    ordered = [row["sku"] for row in options if "-NATURAL" in row["sku"]]
    assert ordered == ["ZZ-NATURAL", "ZZ2-NATURAL", "ZZ10-NATURAL"]

    for item_id in created_ids:
        client.delete(f"/api/catalog/hardware/{item_id}", headers=admin_headers)


def test_hardware_catalog_returns_calculation_seed(client, admin_headers):
    r = client.get("/api/catalog/hardware", headers=admin_headers)

    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10

    by_sku = {item["sku"]: item for item in data}
    assert by_sku["RS112"]["imageFile"] == "RS112.png"
    assert by_sku["RS112"]["sectionWidthMm"] == 52
    assert by_sku["RS112"]["colorVariants"] == [
        "Анод",
        "RAL стандарт",
        "RAL нестандарт",
    ]
    assert by_sku["RS2323"]["paintMode"] == "Частично"
    assert (
        by_sku["RS2323"]["note"]
        == "В заявке на покраску отмечать область, которую не красить"
    )
    assert by_sku["RL101"]["system"] == "ЛИФТ"
    assert by_sku["RL101"]["imageFile"] == "RL101.png"
    assert by_sku["RL101"]["paintMode"] == "Красится"
    assert by_sku["RL104"]["paintMode"] == "Частично"
    assert by_sku["RL104"]["note"] == (
        "W - 155 красится; W - 62 не красится по исходным Excel ЛИФТ"
    )
    assert by_sku["RL2085"]["group"] == "Фурнитура"
    assert by_sku["RL2085"]["paintMode"] == "Не красится"


def test_hardware_catalog_updates_item(client, admin_headers):
    items = client.get("/api/catalog/hardware", headers=admin_headers).json()
    item = next(row for row in items if row["sku"] == "RS112")
    payload = {
        **item,
        "finishVariants": [
            {
                **variant,
                "cost": 777,
                "profileMarkupPercent": 41,
            }
            if variant["code"] == "ANOD"
            else variant
            for variant in item["finishVariants"]
        ],
    }

    r = client.put(
        f"/api/catalog/hardware/{item['id']}",
        headers=admin_headers,
        json=payload,
    )

    assert r.status_code == 200
    data = r.json()
    assert data["purchasePrice"] == 777
    assert data["markupPercent"] == 41
    anod = next(row for row in data["finishVariants"] if row["code"] == "ANOD")
    assert anod["cost"] == "777.00"
    assert anod["profileMarkupPercent"] == 41

    listed = client.get("/api/catalog/hardware", headers=admin_headers).json()
    updated = next(row for row in listed if row["sku"] == "RS112")
    assert updated["purchasePrice"] == 777


def test_hardware_catalog_create_duplicate_and_archive(client, admin_headers):
    payload = {
        "sku": "TEST-CAT-001",
        "name": "Тестовая позиция",
        "group": "Расходники",
        "system": "Все",
        "unit": "шт",
        "purchasePrice": 12.5,
        "markupPercent": 20,
        "profileDiscountPercent": 7,
        "weight": 0.1,
        "wastePercent": 30,
        "constructionMarkupPercent": 200,
        "constructionDiscountPercent": 35,
        "sectionWidthMm": 72,
        "sectionHeightMm": 53,
        "imageFile": "",
        "paintMode": "Не красится",
        "colorVariants": ["Без цвета"],
        "supplier": "Тест",
        "isActive": True,
        "note": "pytest",
    }

    created = client.post("/api/catalog/hardware", headers=admin_headers, json=payload)
    assert created.status_code == 201
    item = created.json()
    assert item["sku"] == payload["sku"]
    for field in (
        "unit",
        "purchasePrice",
        "markupPercent",
        "profileDiscountPercent",
        "weight",
        "wastePercent",
        "constructionMarkupPercent",
        "constructionDiscountPercent",
        "sectionWidthMm",
        "sectionHeightMm",
    ):
        assert item[field] == payload[field]

    db = SessionLocal()
    try:
        version = (
            db.query(models.CatalogPriceVersion)
            .filter_by(catalog_item_id=item["id"])
            .order_by(models.CatalogPriceVersion.id.desc())
            .first()
        )
        assert Decimal(version.cost) == Decimal("12.5")
        assert Decimal(version.profile_markup_percent) == Decimal("20")
        assert Decimal(version.profile_discount_percent) == Decimal("7")
        assert Decimal(version.waste_markup_percent) == Decimal("30")
        assert Decimal(version.construction_markup_percent) == Decimal("200")
        assert Decimal(version.construction_discount_percent) == Decimal("35")
        assert version.unit == "шт"
    finally:
        db.close()

    duplicate = client.post(
        "/api/catalog/hardware", headers=admin_headers, json=payload
    )
    assert duplicate.status_code == 400

    archived = client.delete(
        f"/api/catalog/hardware/{item['id']}",
        headers=admin_headers,
    )
    assert archived.status_code == 200
    assert archived.json()["isActive"] is False


def test_finish_variants_have_public_prices_and_project_snapshots(
    client, admin_headers
):
    payload = {
        "sku": "TEST-FINISH-001",
        "name": "Профиль с исполнениями",
        "group": "Профили",
        "system": "СЛАЙД",
        "unit": "п.м.",
        "purchasePrice": 50,
        "markupPercent": 99,
        "weight": 1.2,
        "wastePercent": 15,
        "sectionWidthMm": 10,
        "sectionHeightMm": 20,
        "imageFile": "",
        "paintMode": "Красится",
        "colorVariants": ["Анод", "RAL стандарт", "RAL нестандарт"],
        "finishVariants": [
            {
                "code": "ANOD",
                "name": "Анод",
                "cost": 120,
                "profileMarkupPercent": 99,
                "requiresPaint": False,
            },
            {
                "code": "RAL_STANDARD",
                "name": "RAL стандарт",
                "cost": 175.5,
                "profileMarkupPercent": 99,
                "requiresPaint": True,
            },
            {
                "code": "RAL_NONSTANDARD",
                "name": "RAL нестандарт",
                "cost": 190,
                "profileMarkupPercent": 99,
                "requiresPaint": True,
            },
        ],
        "supplier": "Скрытый поставщик",
        "isActive": True,
        "note": "pytest variants",
    }
    created = client.post("/api/catalog/hardware", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    project_id = None
    try:
        variants = {row["name"]: row for row in item["finishVariants"]}
        assert variants["Анод"]["cost"] == "120.00"
        assert variants["Анод"]["requiresPaint"] is False
        assert variants["RAL стандарт"]["cost"] == "175.50"
        assert variants["RAL стандарт"]["requiresPaint"] is True

        options = client.get("/api/catalog/hardware/options")
        assert options.status_code == 200
        public = next(row for row in options.json() if row["id"] == item["id"])
        assert public["paintMode"] == "Красится"
        assert public["requiresPaint"] is True
        assert public["finishVariants"] == [
            {
                key: variant[key]
                for key in ("id", "code", "name", "requiresPaint", "isActive")
            }
            for variant in item["finishVariants"]
        ]
        assert all(
            not {
                "cost",
                "profileMarkupPercent",
                "profileDiscountPercent",
                "constructionMarkupPercent",
                "constructionDiscountPercent",
            }
            & variant.keys()
            for variant in public["finishVariants"]
        )
        for internal_key in (
            "purchasePrice",
            "markupPercent",
            "wastePercent",
            "weight",
            "supplier",
        ):
            assert internal_key not in public

        selected = variants["RAL стандарт"]
        project_response = client.post(
            "/api/projects",
            headers=admin_headers,
            json={
                "order_number": "FINISH-SNAPSHOT",
                "customer": "Тест",
                "extra_components": json.dumps(
                    [
                        {
                            "catalog_item_id": item["id"],
                            "finish_variant_id": selected["id"],
                            "qty": 2,
                            "size": "1200 мм",
                            "unit": "п.м.",
                            "delivery_stage": "2",
                            "color": "RAL 9016",
                        }
                    ],
                    ensure_ascii=False,
                ),
            },
        )
        assert project_response.status_code == 201, project_response.text
        project_id = project_response.json()["id"]
        snapshot = json.loads(project_response.json()["extra_components"])[0]
        assert snapshot == {
            "catalog_item_id": item["id"],
            "finish_variant_id": selected["id"],
            "sku": "TEST-FINISH-001",
            "name": "Профиль с исполнениями",
            "category": "profile",
            "finish_name": "RAL стандарт",
            "color": "RAL 9016",
            "requires_paint": True,
            "size": "1200 мм",
            "qty": "2",
            "unit": "п.м.",
            "unit_price": "349.25",
            "image_file": "",
            "delivery_stage": "2",
        }

        quote = client.get(f"/api/projects/{project_id}/quote", headers=admin_headers)
        assert quote.status_code == 200
        component_line = next(
            row for row in quote.json()["lines"] if row["category"] == "profile"
        )
        assert component_line["line_total"] == "698.50"
        assert component_line["component_details"]["finish"] == "RAL стандарт"
        assert component_line["component_details"]["color"] == "RAL 9016"
        token = admin_headers["Authorization"].replace("Bearer ", "")
        commercial = client.get(
            f"/api/projects/{project_id}/documents/commercial/preview",
            params={"token": token},
        )
        assert commercial.status_code == 200
        assert "TEST-FINISH-001" in commercial.text
        assert "Профиль с исполнениями" in commercial.text
        assert "RAL стандарт" in commercial.text
        assert "RAL 9016" in commercial.text
        assert "699" in commercial.text
        assert "Профили" in commercial.text
        assert 'class="quote-brand-name"' in commercial.text
        assert "Счет №" in commercial.text
        assert project_response.json()["invoice_number"] in commercial.text

        commercial_docx = client.get(
            f"/api/projects/{project_id}/documents/commercial/docx",
            headers=admin_headers,
        )
        assert commercial_docx.status_code == 200
        with zipfile.ZipFile(io.BytesIO(commercial_docx.content)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "Менеджер" in document_xml
        assert "Дата" in document_xml
        assert "Тест" in document_xml

        missing_variant = client.put(
            f"/api/projects/{project_id}",
            headers=admin_headers,
            json={
                "extra_components": json.dumps(
                    [{"catalog_item_id": item["id"], "qty": 1}]
                )
            },
        )
        assert missing_variant.status_code == 400
        assert "исполнение" in missing_variant.json()["detail"].lower()
    finally:
        if project_id is not None:
            client.delete(f"/api/projects/{project_id}", headers=admin_headers)
        client.delete(f"/api/catalog/hardware/{item['id']}", headers=admin_headers)


def test_catalog_service_is_priced_in_quote_but_not_shipped_as_hardware(
    client, admin_headers
):
    payload = {
        "sku": "TEST-SERVICE-001",
        "name": "Доставка для теста",
        "group": "Услуги",
        "system": "Все",
        "unit": "шт",
        "purchasePrice": 100,
        "markupPercent": 20,
        "profileDiscountPercent": 0,
        "weight": 0,
        "wastePercent": 0,
        "constructionMarkupPercent": 0,
        "constructionDiscountPercent": 0,
        "sectionWidthMm": 0,
        "sectionHeightMm": 0,
        "imageFile": "",
        "paintMode": "Не красится",
        "colorVariants": [],
        "finishVariants": [],
        "supplier": "",
        "isActive": True,
        "note": "pytest service",
    }
    created = client.post("/api/catalog/hardware", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    project_id = None
    try:
        project = client.post(
            "/api/projects",
            headers=admin_headers,
            json={
                "customer": "Тестовый заказчик",
                "extra_components": json.dumps(
                    [{"catalog_item_id": item["id"], "qty": 2}],
                    ensure_ascii=False,
                ),
            },
        )
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]

        quote = client.get(f"/api/projects/{project_id}/quote", headers=admin_headers)
        assert quote.status_code == 200, quote.text
        service_line = next(
            row for row in quote.json()["lines"] if row["category"] == "service"
        )
        assert service_line["component_details"]["sku"] == "TEST-SERVICE-001"
        assert service_line["line_total"] == "240.00"

        token = admin_headers["Authorization"].replace("Bearer ", "")
        commercial = client.get(
            f"/api/projects/{project_id}/documents/commercial/preview",
            params={"token": token},
        )
        assert commercial.status_code == 200
        assert "Доставка для теста" in commercial.text
        assert 'class="quote-brand-name"' in commercial.text

        for document_type in ("delivery", "hardware_order", "sketch"):
            document = client.get(
                f"/api/projects/{project_id}/documents/{document_type}/preview",
                params={"token": token},
            )
            assert document.status_code == 200, document.text
            assert "TEST-SERVICE-001" not in document.text
    finally:
        if project_id is not None:
            client.delete(f"/api/projects/{project_id}", headers=admin_headers)
        client.delete(f"/api/catalog/hardware/{item['id']}", headers=admin_headers)


def test_profile_asset_returns_existing_image(client):
    r = client.get("/api/catalog/profile-assets/RS112.png")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 0


def test_profile_asset_returns_existing_threshold_png(client):
    r = client.get("/api/catalog/profile-assets/RS23231.png")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 0


def test_profile_asset_returns_lift_images(client):
    for filename in ("RL101.png", "RL2085.png", "RL210.png"):
        r = client.get(f"/api/catalog/profile-assets/{filename}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0


def test_profile_asset_returns_new_rs123_rs3110_and_rs1005_images(client):
    for filename, media_type in (
        ("RS123.jpg", "image/jpeg"),
        ("RS3110.jpg", "image/jpeg"),
        ("RS1005.png", "image/png"),
    ):
        r = client.get(f"/api/catalog/profile-assets/{filename}")
        assert r.status_code == 200
        assert r.headers["content-type"] == media_type
        assert len(r.content) > 0


def test_profile_asset_returns_side_assembly_images(client):
    for filename in (
        "SIDE_RS1002.png",
        "SIDE_RS1082_RS1002.png",
        "SIDE_RS1082_RS112.png",
        "SIDE_RS2081_RS112.png",
    ):
        r = client.get(f"/api/catalog/profile-assets/{filename}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0


def test_profile_asset_rejects_path_traversal(client):
    r = client.get("/api/catalog/profile-assets/..%2Fmodels.py")

    assert r.status_code == 404


def test_profile_asset_rejects_non_image_extension(client):
    r = client.get("/api/catalog/profile-assets/models.py")

    assert r.status_code == 404
