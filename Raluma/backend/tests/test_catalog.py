def test_profile_asset_returns_existing_image(client):
    r = client.get("/api/catalog/profile-assets/RS112.jpg")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert len(r.content) > 0


def test_profile_asset_rejects_path_traversal(client):
    r = client.get("/api/catalog/profile-assets/..%2Fmodels.py")

    assert r.status_code == 404
