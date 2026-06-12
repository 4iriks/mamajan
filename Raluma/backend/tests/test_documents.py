"""
Тесты API производственных документов (preview, overrides).
PDF-генерацию не тестируем (требует WeasyPrint + системные библиотеки).
"""

import json
from types import SimpleNamespace

from engine.pdf import (
    _img_b64,
    expand_glass_widths,
    get_profile_asset_path,
    profile_dimension,
)
from engine.project_documents import CalculatedSection, _build_glass_rows


class TestProfileAssetSafety:
    def test_img_b64_accepts_known_profile_image(self):
        assert get_profile_asset_path("RS112.jpg") is not None
        assert _img_b64("RS112.jpg").startswith("data:image/jpeg;base64,")

    def test_img_b64_accepts_known_svg_profile_image(self):
        assert get_profile_asset_path("RS23231.svg") is not None
        assert _img_b64("RS23231.svg").startswith("data:image/svg+xml;base64,")

    def test_img_b64_rejects_path_traversal(self):
        assert get_profile_asset_path("../models.py") is None
        assert get_profile_asset_path("..\\models.py") is None
        assert _img_b64("../models.py") == ""
        assert _img_b64("..\\models.py") == ""

    def test_img_b64_rejects_non_image_extension(self):
        assert get_profile_asset_path("models.py") is None
        assert _img_b64("models.py") == ""


class TestDiagramGlassWidths:
    def test_expands_edge_and_middle_glass_widths(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(position="Крайние", width_mm=520, qty=2),
                SimpleNamespace(position="Промежуточные", width_mm=470, qty=2),
            ]
        )

        assert expand_glass_widths(calc, 4, 2000) == [520, 470, 470, 520]

    def test_expands_asymmetric_glass_widths(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(position="Левое", width_mm=540, qty=1),
                SimpleNamespace(position="Промежуточные", width_mm=470, qty=1),
                SimpleNamespace(position="Правое", width_mm=500, qty=1),
            ]
        )

        assert expand_glass_widths(calc, 3, 1510) == [540, 470, 500]

    def test_expands_two_row_central_glass_widths(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(position="Левое", width_mm=520, qty=1),
                SimpleNamespace(position="Промежуточные", width_mm=470, qty=2),
                SimpleNamespace(position="Центральные", width_mm=500, qty=2),
                SimpleNamespace(position="Правое", width_mm=530, qty=1),
            ]
        )

        assert expand_glass_widths(calc, 6, 3000) == [520, 470, 500, 500, 470, 530]

    def test_profile_dimension_reads_calculation_metadata(self):
        calc = SimpleNamespace(
            profiles=[
                SimpleNamespace(article="RS2333", section_height_mm=16),
            ]
        )

        assert profile_dimension(calc, ["RS2333"], "section_height_mm", 10) == 16


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
        assert 'data-profile="RS2333-left"' in r.text
        assert 'data-profile="RS2333-right"' in r.text

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

    def test_local_preview_two_rows_renders_central_glass(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-2R", "customer": "Тест"},
                "section": {
                    "name": "Секция 2",
                    "system": "СЛАЙД",
                    "width": 2000,
                    "height": 2400,
                    "panels": 4,
                    "quantity": 1,
                    "rails": 3,
                    "slide_rows": 2,
                    "unused_track": "Внешний",
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "center_handle": "Ручка-кноб RS3014",
                    "center_lock": "Замок стекло-стекло RS30301",
                },
            },
        )
        assert r.status_code == 200
        assert "SLIDE-стандарт 2 ряда" in r.text
        assert "Центральные" in r.text
        assert "RS30301" in r.text

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

    def test_local_preview_unused_track_and_side_profile(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-TRACK", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 3000,
                    "panels": 2,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Накладной окраш",
                    "painting_type": "RAL нестандарт",
                    "ral_color": "9016 МАТОВЫЙ",
                    "unused_track": "Внутренний",
                    "inter_glass_profile": "— Без межстекольного профиля —",
                    "profile_left_lock_bar": True,
                    "profile_left_handle_bar": True,
                },
            },
        )

        assert r.status_code == 200
        assert "RAL 9016 МАТОВЫЙ" in r.text
        assert "НЕСТАНДАРТ" not in r.text
        assert "Не используется внутренняя полоса" in r.text
        assert "Порог 3-рельсовый накладной" in r.text
        assert "RS23231.svg" not in r.text  # картинка встраивается data-uri
        assert "Межстекольный профиль" not in r.text
        assert 'data-profile="left-side-stack"' in r.text

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
        assert r.text.index("ОБРАЩАЮ ВНИМАНИЕ") < r.text.index("КРОМКИ ПОЛИРОВАННЫЕ")

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


class TestProjectGlassOrder:
    def test_left_edge_drawing_does_not_mark_whole_section(self):
        project = SimpleNamespace(number="P-001")
        section = SimpleNamespace(
            panels=3,
            quantity=1,
            slide_rows=1,
            lock_left="ЗАМОК-ЗАЩЕЛКА 1стор",
            lock_right="Без",
            handle_left="Без ручки (глухая)",
            handle_right="Без ручки (глухая)",
            floor_latches_left=False,
            floor_latches_right=False,
        )
        calc = SimpleNamespace(
            glass_type="10ММ",
            glass=[
                SimpleNamespace(
                    position="Крайние", width_mm=500, height_mm=2200, qty=2
                ),
                SimpleNamespace(
                    position="Промежуточные", width_mm=450, height_mm=2200, qty=1
                ),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=1, section=section, calc=calc)]
        )

        drawing_rows = [row for row in rows if row["note"] == "(чертеж)"]
        assert len(drawing_rows) == 1
        assert drawing_rows[0]["width"] == 500
        assert drawing_rows[0]["qty"] == 1
        assert drawing_rows[0]["marking"] == "P-001 1,1"

        plain_qty = sum(row["qty"] for row in rows if row["note"] == "")
        assert plain_qty == 2

    def test_two_row_center_drawing_marks_only_central_glass(self):
        project = SimpleNamespace(number="P-002")
        section = SimpleNamespace(
            panels=4,
            quantity=1,
            slide_rows=2,
            lock_left="Без",
            lock_right="Без",
            handle_left="Без ручки (глухая)",
            handle_right="Без ручки (глухая)",
            floor_latches_left=False,
            floor_latches_right=False,
            center_lock="Замок стекло-стекло RS30301",
            center_handle="Без ручки (подвижные)",
            center_floor_latches_left=False,
            center_floor_latches_right=False,
        )
        calc = SimpleNamespace(
            glass_type="10ММ",
            glass=[
                SimpleNamespace(position="Левое", width_mm=500, height_mm=2200, qty=1),
                SimpleNamespace(
                    position="Центральные", width_mm=500, height_mm=2200, qty=2
                ),
                SimpleNamespace(position="Правое", width_mm=500, height_mm=2200, qty=1),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=2, section=section, calc=calc)]
        )

        drawing_row = [row for row in rows if row["note"] == "(чертеж)"][0]
        plain_row = [row for row in rows if row["note"] == ""][0]
        assert drawing_row["qty"] == 2
        assert drawing_row["marking"] == "P-002 2,2, P-002 2,3"
        assert plain_row["qty"] == 2
        assert plain_row["marking"] == "P-002 2,1, P-002 2,4"

    def test_two_row_left_center_floor_latch_marks_one_central_glass(self):
        project = SimpleNamespace(number="P-003")
        section = SimpleNamespace(
            panels=4,
            quantity=1,
            slide_rows=2,
            lock_left="Без замка",
            lock_right="Без замка",
            handle_left="Без ручки (глухая)",
            handle_right="Без ручки (глухая)",
            floor_latches_left=False,
            floor_latches_right=False,
            center_lock="Без замка",
            center_handle="Без ручки (подвижные)",
            center_floor_latches_left=True,
            center_floor_latches_right=False,
        )
        calc = SimpleNamespace(
            glass_type="10ММ",
            glass=[
                SimpleNamespace(position="Левое", width_mm=500, height_mm=2200, qty=1),
                SimpleNamespace(
                    position="Центральные", width_mm=500, height_mm=2200, qty=2
                ),
                SimpleNamespace(position="Правое", width_mm=500, height_mm=2200, qty=1),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=3, section=section, calc=calc)]
        )

        drawing_row = [row for row in rows if row["note"] == "(чертеж)"][0]
        plain_row = [row for row in rows if row["note"] == ""][0]
        assert drawing_row["qty"] == 1
        assert drawing_row["marking"] == "P-003 3,2"
        assert plain_row["qty"] == 3
        assert plain_row["marking"] == "P-003 3,1, P-003 3,3, P-003 3,4"

    def test_no_hardware_labels_do_not_create_drawing_note(self):
        project = SimpleNamespace(number="P-004")
        section = SimpleNamespace(
            panels=3,
            quantity=1,
            slide_rows=1,
            lock="Без замка",
            handle="Без ручки",
            lock_left="Без замка",
            lock_right="Без замка",
            handle_left="Без ручки (глухая)",
            handle_right="Без ручки (глухая)",
            floor_latches_left=False,
            floor_latches_right=False,
        )
        calc = SimpleNamespace(
            glass_type="10ММ",
            glass=[
                SimpleNamespace(
                    position="Крайние", width_mm=500, height_mm=2200, qty=2
                ),
                SimpleNamespace(
                    position="Промежуточные", width_mm=450, height_mm=2200, qty=1
                ),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=4, section=section, calc=calc)]
        )

        assert [row for row in rows if row["note"] == "(чертеж)"] == []
        assert sum(row["qty"] for row in rows if row["note"] == "") == 3


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
