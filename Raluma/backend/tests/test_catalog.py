def test_hardware_catalog_requires_admin(client):
    r = client.get("/api/catalog/hardware")

    assert r.status_code in (401, 403)


def test_hardware_catalog_options_are_public(client):
    r = client.get("/api/catalog/hardware/options")

    assert r.status_code == 200
    data = r.json()
    skus = {item["sku"] for item in data}
    assert "RS30301" in skus
    assert "RS2323" not in skus
    assert "RS1313" not in skus
    assert "purchasePrice" not in data[0]


def test_hardware_catalog_returns_calculation_seed(client, admin_headers):
    r = client.get("/api/catalog/hardware", headers=admin_headers)

    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 10

    by_sku = {item["sku"]: item for item in data}
    assert by_sku["RS112"]["imageFile"] == "RS112.jpg"
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


def test_hardware_catalog_updates_item(client, admin_headers):
    items = client.get("/api/catalog/hardware", headers=admin_headers).json()
    item = next(row for row in items if row["sku"] == "RS112")
    payload = {**item, "purchasePrice": 777, "markupPercent": 41}

    r = client.put(
        f"/api/catalog/hardware/{item['id']}",
        headers=admin_headers,
        json=payload,
    )

    assert r.status_code == 200
    data = r.json()
    assert data["purchasePrice"] == 777
    assert data["markupPercent"] == 41

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
        "weight": 0.1,
        "wastePercent": 0,
        "sectionWidthMm": 0,
        "sectionHeightMm": 0,
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


def test_profile_asset_returns_existing_image(client):
    r = client.get("/api/catalog/profile-assets/RS112.jpg")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert len(r.content) > 0


def test_profile_asset_returns_existing_svg(client):
    r = client.get("/api/catalog/profile-assets/RS23231.svg")

    assert r.status_code == 200
    assert r.headers["content-type"] in (
        "image/svg+xml",
        "image/svg+xml; charset=utf-8",
    )
    assert len(r.content) > 0


def test_profile_asset_rejects_path_traversal(client):
    r = client.get("/api/catalog/profile-assets/..%2Fmodels.py")

    assert r.status_code == 404


def test_profile_asset_rejects_non_image_extension(client):
    r = client.get("/api/catalog/profile-assets/models.py")

    assert r.status_code == 404
