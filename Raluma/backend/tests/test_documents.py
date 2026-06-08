"""
Тесты API производственных документов (preview, overrides).
PDF-генерацию не тестируем (требует WeasyPrint + системные библиотеки).
"""

import json


def _create_slide_section(client, admin_headers, project_id):
    r = client.post(
        f"/api/projects/{project_id}/sections",
        headers=admin_headers,
        json={
            "name": "Секция 1",
            "system": "СЛАЙД",
            "width": 2000,
            "height": 2400,
            "panels": 3,
            "quantity": 1,
            "rails": 3,
            "threshold": "Стандартный анод",
            "first_panel_inside": "Справа",
            "inter_glass_profile": "Алюминиевый RS2061",
            "profile_left_wall": True,
            "profile_right_wall": True,
        },
    )
    assert r.status_code == 201
    return r.json()


class TestPreview:
    def test_preview_returns_html(self, client, admin_headers, project):
        section = _create_slide_section(client, admin_headers, project["id"])
        token = admin_headers["Authorization"].replace("Bearer ", "")
        r = client.get(
            f"/api/projects/{project['id']}/sections/{section['id']}/preview",
            params={"token": token},
        )
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "contenteditable" in r.text

    def test_preview_no_token(self, client, project, admin_headers):
        section = _create_slide_section(client, admin_headers, project["id"])
        r = client.get(
            f"/api/projects/{project['id']}/sections/{section['id']}/preview",
        )
        assert r.status_code == 401

    def test_preview_invalid_token(self, client, admin_headers, project):
        section = _create_slide_section(client, admin_headers, project["id"])
        r = client.get(
            f"/api/projects/{project['id']}/sections/{section['id']}/preview",
            params={"token": "invalid_token"},
        )
        assert r.status_code == 401

    def test_preview_not_found(self, client, admin_headers, project):
        token = admin_headers["Authorization"].replace("Bearer ", "")
        r = client.get(
            f"/api/projects/{project['id']}/sections/999999/preview",
            params={"token": token},
        )
        assert r.status_code == 404

    def test_preview_non_slide(self, client, admin_headers, project):
        """Не-СЛАЙД секция возвращает HTML с сообщением."""
        s = client.post(
            f"/api/projects/{project['id']}/sections",
            headers=admin_headers,
            json={"name": "ЦС1", "system": "ЦС"},
        ).json()
        token = admin_headers["Authorization"].replace("Bearer ", "")
        r = client.get(
            f"/api/projects/{project['id']}/sections/{s['id']}/preview",
            params={"token": token},
        )
        assert r.status_code == 200
        assert "только для системы СЛАЙД" in r.text


class TestLocalPreview:
    def test_local_preview_returns_html_without_auth(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-001", "customer": "Гость"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 2000,
                    "height": 2400,
                    "panels": 3,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "first_panel_inside": "Справа",
                },
            },
        )
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "LOCAL-001" in r.text
        assert "contenteditable" in r.text

    def test_local_preview_non_slide(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-002"},
                "section": {"name": "Комплект", "system": "КОМПЛЕКТАЦИЯ"},
            },
        )
        assert r.status_code == 200
        assert "только для системы СЛАЙД" in r.text

    def test_local_calc_returns_glass_and_catalog_profiles(self, client):
        r = client.post(
            "/api/projects/local/sections/calc",
            json={
                "project": {"number": "LOCAL-CALC"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 2000,
                    "height": 2400,
                    "panels": 3,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "first_panel_inside": "Справа",
                },
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["glass"]
        threshold = [p for p in data["profiles"] if p["article"] == "RS2323"][0]
        assert threshold["section_width_mm"] == 76
        assert threshold["paint_note"] == "НЕ КРАСИТЬ!!!"


class TestProjectDocuments:
    def test_project_commercial_preview_returns_readonly_html(
        self, client, admin_headers, project
    ):
        _create_slide_section(client, admin_headers, project["id"])
        token = admin_headers["Authorization"].replace("Bearer ", "")

        r = client.get(
            f"/api/projects/{project['id']}/documents/commercial/preview",
            params={"token": token},
        )

        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Коммерческое предложение" in r.text
        assert "TEST-001" in r.text
        assert "contenteditable" not in r.text

    def test_project_paint_preview_returns_html(self, client, admin_headers, project):
        _create_slide_section(client, admin_headers, project["id"])
        token = admin_headers["Authorization"].replace("Bearer ", "")

        r = client.get(
            f"/api/projects/{project['id']}/documents/paint/preview",
            params={"token": token},
        )

        assert r.status_code == 200
        assert "Заявка на покраску" in r.text
        assert "RS1313" in r.text

    def test_project_glass_preview_returns_html(self, client, admin_headers, project):
        _create_slide_section(client, admin_headers, project["id"])
        token = admin_headers["Authorization"].replace("Bearer ", "")

        r = client.get(
            f"/api/projects/{project['id']}/documents/glass/preview",
            params={"token": token},
        )

        assert r.status_code == 200
        assert "Заказ стекла" in r.text
        assert "КРОМКИ ПОЛИРОВАННЫЕ" in r.text
        assert "ОБРАЩАЮ ВНИМАНИЕ" in r.text
        assert r.text.index("ОБРАЩАЮ ВНИМАНИЕ") < r.text.index(
            "КРОМКИ ПОЛИРОВАННЫЕ"
        )

    def test_project_document_preview_requires_token(
        self, client, admin_headers, project
    ):
        _create_slide_section(client, admin_headers, project["id"])

        r = client.get(
            f"/api/projects/{project['id']}/documents/commercial/preview",
        )

        assert r.status_code == 401

    def test_local_project_document_preview_without_auth(self, client):
        r = client.post(
            "/api/projects/local/documents/glass/preview",
            json={
                "project": {"number": "LOCAL-DOC", "customer": "Гость"},
                "sections": [
                    {
                        "name": "Секция 1",
                        "system": "СЛАЙД",
                        "width": 2000,
                        "height": 2400,
                        "panels": 3,
                        "quantity": 1,
                        "rails": 3,
                        "threshold": "Стандартный анод",
                        "first_panel_inside": "Справа",
                    }
                ],
            },
        )

        assert r.status_code == 200
        assert "LOCAL-DOC" in r.text
        assert "Заказ стекла" in r.text


class TestOverrides:
    def test_save_overrides(self, client, admin_headers, project):
        section = _create_slide_section(client, admin_headers, project["id"])
        r = client.patch(
            f"/api/projects/{project['id']}/sections/{section['id']}/overrides",
            headers=admin_headers,
            json={"overrides": {"threshold_length": "1999"}},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_overrides_merge(self, client, admin_headers, project):
        """Повторный PATCH мёрджит, не перезаписывает."""
        section = _create_slide_section(client, admin_headers, project["id"])
        sid = section["id"]
        pid = project["id"]

        client.patch(
            f"/api/projects/{pid}/sections/{sid}/overrides",
            headers=admin_headers,
            json={"overrides": {"field_a": "111"}},
        )
        client.patch(
            f"/api/projects/{pid}/sections/{sid}/overrides",
            headers=admin_headers,
            json={"overrides": {"field_b": "222"}},
        )

        # Читаем секцию, проверяем что оба поля на месте
        s = client.get(f"/api/projects/{pid}/sections", headers=admin_headers).json()
        sec = [x for x in s if x["id"] == sid][0]
        overrides = json.loads(sec.get("document_overrides", "{}"))
        assert overrides["field_a"] == "111"
        assert overrides["field_b"] == "222"

    def test_clear_overrides(self, client, admin_headers, project):
        section = _create_slide_section(client, admin_headers, project["id"])
        sid = section["id"]
        pid = project["id"]

        client.patch(
            f"/api/projects/{pid}/sections/{sid}/overrides",
            headers=admin_headers,
            json={"overrides": {"x": "1"}},
        )
        r = client.delete(
            f"/api/projects/{pid}/sections/{sid}/overrides",
            headers=admin_headers,
        )
        assert r.status_code == 200

        s = client.get(f"/api/projects/{pid}/sections", headers=admin_headers).json()
        sec = [x for x in s if x["id"] == sid][0]
        overrides = json.loads(sec.get("document_overrides", "{}"))
        assert overrides == {}

    def test_overrides_require_auth(self, client, project, admin_headers):
        section = _create_slide_section(client, admin_headers, project["id"])
        r = client.patch(
            f"/api/projects/{project['id']}/sections/{section['id']}/overrides",
            json={"overrides": {"x": "1"}},
        )
        assert r.status_code == 403

    def test_overrides_not_found(self, client, admin_headers, project):
        r = client.patch(
            f"/api/projects/{project['id']}/sections/999999/overrides",
            headers=admin_headers,
            json={"overrides": {"x": "1"}},
        )
        assert r.status_code == 404
