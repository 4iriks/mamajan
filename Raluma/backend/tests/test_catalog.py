def test_hardware_catalog_requires_admin(client):
    r = client.get("/api/catalog/hardware")

    assert r.status_code in (401, 403)


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


def test_profile_asset_returns_existing_image(client):
    r = client.get("/api/catalog/profile-assets/RS112.jpg")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert len(r.content) > 0


def test_profile_asset_rejects_path_traversal(client):
    r = client.get("/api/catalog/profile-assets/..%2Fmodels.py")

    assert r.status_code == 404
