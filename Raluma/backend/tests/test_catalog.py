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
