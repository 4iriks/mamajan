"""
Тесты API производственных документов (preview, overrides).
PDF-генерацию проверяем только если установлен WeasyPrint.
"""

import json
from types import SimpleNamespace

import pytest

from engine.pdf import (
    _img_b64,
    display_profiles,
    expand_glass_widths,
    get_profile_asset_path,
    glass_mm,
    profile_dimension,
    section_extra_components,
)
from engine.project_documents import (
    CalculatedSection,
    _build_glass_rows,
    _build_paint_pages,
    _iter_slide_sections,
)


class TestProfileAssetSafety:
    def test_img_b64_accepts_known_profile_image(self):
        assert get_profile_asset_path("RS112.jpg") is not None
        assert _img_b64("RS112.jpg").startswith("data:image/jpeg;base64,")

    def test_img_b64_accepts_known_svg_profile_image(self):
        assert get_profile_asset_path("RS23231.svg") is not None
        assert _img_b64("RS23231.svg").startswith("data:image/svg+xml;base64,")
        assert get_profile_asset_path("RS2021.svg") is not None
        assert _img_b64("RS2021.svg").startswith("data:image/svg+xml;base64,")

    def test_img_b64_rejects_path_traversal(self):
        assert get_profile_asset_path("../models.py") is None
        assert get_profile_asset_path("..\\models.py") is None
        assert _img_b64("../models.py") == ""
        assert _img_b64("..\\models.py") == ""

    def test_img_b64_rejects_non_image_extension(self):
        assert get_profile_asset_path("models.py") is None
        assert _img_b64("models.py") == ""


class TestProfileDisplayRows:
    def test_split_profile_parts_are_grouped_for_sheet_display(self):
        rows = display_profiles(
            [
                SimpleNamespace(
                    article="RS2323",
                    name="Порог",
                    length_mm=2975,
                    qty=2,
                    painted=True,
                    image="RS2323.jpg",
                    field_key="threshold_length_part_1",
                    note="часть 1/2; рассверлить",
                    section_width_mm=76,
                    section_height_mm=23,
                    paint_mode="Частично",
                    color_variants=[],
                    paint_note="НЕ КРАСИТЬ!!!",
                    glass_positions="",
                ),
                SimpleNamespace(
                    article="RS2323",
                    name="Порог",
                    length_mm=2976,
                    qty=2,
                    painted=True,
                    image="RS2323.jpg",
                    field_key="threshold_length_part_2",
                    note="часть 2/2; рассверлить",
                    section_width_mm=76,
                    section_height_mm=23,
                    paint_mode="Частично",
                    color_variants=[],
                    paint_note="НЕ КРАСИТЬ!!!",
                    glass_positions="",
                ),
            ]
        )

        assert len(rows) == 1
        assert rows[0].note == "рассверлить"
        assert rows[0].display_cuts == [
            {
                "length": "2975",
                "qty": 2,
                "length_field": "threshold_length_part_1",
                "qty_field": "threshold_length_part_1_qty",
            },
            {
                "length": "2976",
                "qty": 2,
                "length_field": "threshold_length_part_2",
                "qty_field": "threshold_length_part_2_qty",
            },
        ]


class TestDiagramGlassWidths:
    def test_glass_mm_rounds_up(self):
        assert glass_mm(995.0) == 995
        assert glass_mm(995.1) == 996
        assert glass_mm(995.9) == 996

    def test_expands_edge_and_middle_glass_widths(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(position="Крайние", width_mm=520.1, qty=2),
                SimpleNamespace(position="Промежуточные", width_mm=470.1, qty=2),
            ]
        )

        assert [glass_mm(width) for width in expand_glass_widths(calc, 4, 2000)] == [
            521,
            471,
            471,
            521,
        ]

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


def _create_slide_section(client, admin_headers, project_id, **overrides):
    payload = {
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
    }
    payload.update(overrides)
    r = client.post(
        f"/api/projects/{project_id}/sections",
        headers=admin_headers,
        json=payload,
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
        assert 'data-profile="inter-glass" data-panel="1" data-dir="1"' in r.text
        assert 'data-profile="inter-glass" data-panel="3" data-dir="-1"' in r.text

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
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "profile_left_lock_bar": True,
                    "profile_left_handle_bar": True,
                },
            },
        )

        assert r.status_code == 200
        assert "RAL 9016 МАТОВЫЙ" in r.text
        assert "НЕСТАНДАРТ" not in r.text
        assert "Не используется внутренняя полоса" in r.text
        assert "Порог 3-рельсовый накладной окраш" in r.text
        assert ">Накладной окраш<" not in r.text
        assert "RS23231.svg" not in r.text  # картинка встраивается data-uri
        assert "Межстекольный профиль" not in r.text
        assert 'data-profile="left-side-stack"' not in r.text
        assert 'data-profile-image="RS2081-left"' not in r.text
        assert 'data-profile-image="RS112-left"' not in r.text
        assert 'data-profile="RS2333-left" data-profile-image="RS2333-left"' in r.text
        assert 'data-profile="RS2333-right" data-profile-image="RS2333-right"' in r.text

    def test_local_preview_inter_glass_mirrors_for_first_panel_right(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-IG", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 3000,
                    "panels": 3,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Накладной окраш",
                    "first_panel_inside": "Справа",
                    "inter_glass_profile": "Алюминиевый RS2061",
                },
            },
        )

        assert r.status_code == 200
        assert 'data-profile="inter-glass" data-panel="2" data-dir="1"' in r.text
        assert 'data-profile="inter-glass" data-panel="1" data-dir="1"' in r.text
        assert 'data-profile="inter-glass" data-panel="3"' not in r.text
        assert 'class="prof-img mirror-x" alt="RS2061"' in r.text

    def test_local_preview_rs2021_skips_zero_intermediate_label(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-RS2021", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 3000,
                    "panels": 2,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "— Без межстекольного профиля —",
                },
            },
        )

        assert r.status_code == 200
        assert "Стекольный профиль" in r.text
        assert "Крайние" in r.text
        assert "Промежуточные" not in r.text

    def test_local_preview_extra_components_from_section(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-EC", "customer": "Тест"},
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
                    "extra_components": json.dumps(
                        [
                            {
                                "sku": "BOX-1",
                                "name": "Бокс",
                                "color": "RAL 9016",
                                "size": "1200",
                                "qty": "2",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                },
            },
        )

        assert r.status_code == 200
        assert "ДОПОЛНИТЕЛЬНЫЕ КОМПЛЕКТУЮЩИЕ" in r.text
        assert "BOX-1" in r.text
        assert "RAL 9016" in r.text
        assert "contenteditable=\"true\" data-field=\"ec_" not in r.text

    def test_section_extra_components_prefer_section_over_legacy_override(self):
        section = SimpleNamespace(
            extra_components=json.dumps(
                [{"sku": "BOX-NEW", "name": "Новый бокс", "qty": "2"}],
                ensure_ascii=False,
            )
        )
        overrides = {
            "extra_components": [
                {"art": "BOX-OLD", "name": "Старый бокс", "qty": "1"}
            ]
        }

        rows = section_extra_components(section, overrides)

        assert rows == [
            {
                "art": "BOX-NEW",
                "name": "Новый бокс",
                "size": "",
                "qty": "2",
                "color": "",
            }
        ]

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
        _create_slide_section(
            client,
            admin_headers,
            project["id"],
            threshold="Стандартный окраш",
            painting_type="RAL стандарт",
        )
        token = admin_headers["Authorization"].replace("Bearer ", "")

        r = client.get(
            f"/api/projects/{project['id']}/documents/paint/preview",
            params={"token": token},
        )

        assert r.status_code == 200
        assert "Заявка на покраску" in r.text
        assert "RS1313" in r.text
        assert 'class="doc-head"' in r.text
        assert 'class="meta paint-meta"' in r.text
        assert "paint-bosses-marker" in r.text
        assert "paint-marker-standard-threshold" in r.text

    def test_project_paint_preview_skips_anod_threshold(
        self, client, admin_headers, project
    ):
        _create_slide_section(
            client,
            admin_headers,
            project["id"],
            threshold="Стандартный анод",
            painting_type="RAL стандарт",
        )
        token = admin_headers["Authorization"].replace("Bearer ", "")

        r = client.get(
            f"/api/projects/{project['id']}/documents/paint/preview",
            params={"token": token},
        )

        assert r.status_code == 200
        assert "RS1313" in r.text
        assert "RS2323" not in r.text

    def test_local_project_paint_overlay_threshold_marks_bosses(self, client):
        r = client.post(
            "/api/projects/local/documents/paint/preview",
            json={
                "project": {"number": "LOCAL-PAINT", "customer": "Тест"},
                "sections": [
                    {
                        "name": "Секция 1",
                        "system": "СЛАЙД",
                        "width": 2000,
                        "height": 2400,
                        "panels": 3,
                        "quantity": 1,
                        "rails": 3,
                        "threshold": "Накладной окраш",
                        "painting_type": "RAL стандарт",
                        "ral_color": "9016 МАТОВЫЙ",
                        "first_panel_inside": "Справа",
                    }
                ],
            },
        )

        assert r.status_code == 200
        assert "RS23231" in r.text
        assert "НЕ КРАСИТЬ!!!" in r.text
        assert "paint-marker-overlay-threshold" in r.text

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
        assert 'data-field="project_number"' in r.text
        assert 'data-field="project_customer"' in r.text
        assert "postMessage({ type: 'dirty'" in r.text
        assert f"Проект {project['number']}" not in r.text
        assert 'class="doc-head"' in r.text
        assert 'class="meta glass-meta"' in r.text
        assert r.text.index("КРОМКИ ПОЛИРОВАННЫЕ") < r.text.index("ОБРАЩАЮ ВНИМАНИЕ")

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
        assert "Проект LOCAL-DOC" not in r.text

    def test_local_project_glass_pdf_download_returns_pdf(self, client):
        pytest.importorskip("weasyprint")

        r = client.post(
            "/api/projects/local/documents/glass/pdf",
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
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")


class TestProjectPaintOrder:
    def test_clean_size_rounds_up_to_50_mm_step(self):
        section = SimpleNamespace()
        calc = SimpleNamespace(
            color_text="RAL 9016",
            profiles=[
                SimpleNamespace(
                    article="RS2021",
                    name="Стекольный профиль",
                    length_mm=1445.2,
                    qty=2,
                    painted=True,
                    image="RS2021.svg",
                    paint_note="",
                    paint_mode="Красится",
                ),
                SimpleNamespace(
                    article="RS2333",
                    name="Пристеночный профиль",
                    length_mm=3000,
                    qty=1,
                    painted=True,
                    image="RS2333.jpg",
                    paint_note="",
                    paint_mode="Красится",
                ),
            ],
        )

        pages = _build_paint_pages(
            [CalculatedSection(order=1, section=section, calc=calc)]
        )

        rows = {row["article"]: row for row in pages[0]["rows"]}
        assert rows["RS2021"]["clean"] == 1450
        assert rows["RS2021"]["allowance"] == 1500
        assert rows["RS2333"]["clean"] == 3000

    def test_same_article_rows_are_grouped_for_template_rowspan(self):
        section = SimpleNamespace()
        calc = SimpleNamespace(
            color_text="RAL 9016",
            profiles=[
                SimpleNamespace(
                    article="RS2021",
                    name="Стекольный профиль",
                    length_mm=1445,
                    qty=2,
                    painted=True,
                    image="RS2021.svg",
                    paint_note="",
                    paint_mode="Красится",
                ),
                SimpleNamespace(
                    article="RS2021",
                    name="Стекольный профиль",
                    length_mm=2838,
                    qty=1,
                    painted=True,
                    image="RS2021.svg",
                    paint_note="",
                    paint_mode="Красится",
                ),
            ],
        )

        pages = _build_paint_pages(
            [CalculatedSection(order=1, section=section, calc=calc)]
        )

        group = pages[0]["groups"][0]
        assert group["article"] == "RS2021"
        assert [row["clean"] for row in group["rows"]] == [1450, 2850]
        assert [row["qty"] for row in group["rows"]] == [2, 1]

    def test_threshold_marker_classes_are_article_specific(self):
        section = SimpleNamespace()
        calc = SimpleNamespace(
            color_text="RAL 9016",
            profiles=[
                SimpleNamespace(
                    article="RS2323",
                    name="Порог 3-рельсовый",
                    length_mm=2968,
                    qty=1,
                    painted=True,
                    image="RS2323.jpg",
                    paint_note="НЕ КРАСИТЬ!!!",
                    paint_mode="Частично",
                ),
                SimpleNamespace(
                    article="RS23231",
                    name="Порог 3-рельсовый накладной",
                    length_mm=2968,
                    qty=1,
                    painted=True,
                    image="RS23231.svg",
                    paint_note="НЕ КРАСИТЬ!!!",
                    paint_mode="Частично",
                ),
            ],
        )

        pages = _build_paint_pages(
            [CalculatedSection(order=1, section=section, calc=calc)]
        )
        rows = {row["article"]: row for row in pages[0]["rows"]}

        assert rows["RS2323"]["paint_marker_class"] == "paint-marker-standard-threshold"
        assert rows["RS23231"]["paint_marker_class"] == "paint-marker-overlay-threshold"


class TestProjectGlassOrder:
    def test_slide_sections_sort_by_visible_section_number(self):
        def section(name: str, order: int):
            return SimpleNamespace(
                name=name,
                order=order,
                system="СЛАЙД",
                width=2000,
                height=2400,
                panels=3,
                quantity=1,
                rails=3,
                threshold="Стандартный анод",
                painting_type="RAL стандарт",
                ral_color="9016",
                glass_type="10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ",
                first_panel_inside="Справа",
                unused_track="",
                inter_glass_profile="Алюминиевый RS2061",
                profile_left_wall=True,
                profile_right_wall=True,
                profile_left_lock_bar=False,
                profile_right_lock_bar=False,
                profile_left_p_bar=False,
                profile_right_p_bar=False,
                profile_left_handle_bar=False,
                profile_right_handle_bar=False,
                profile_left_bubble=False,
                profile_right_bubble=False,
                lock_left="Без",
                lock_right="Без",
                handle_left="Без",
                handle_right="Без",
                handle_offset_left=0,
                handle_offset_right=0,
                floor_latches_left=False,
                floor_latches_right=False,
                slide_rows=1,
            )

        rows = _iter_slide_sections(
            [section("Секция 2", 1), section("Секция 1", 99)]
        )

        assert [row.section.name for row in rows] == ["Секция 1", "Секция 2"]
        assert [row.order for row in rows] == [1, 2]

    def test_left_edge_knob_drawing_does_not_mark_whole_section(self):
        project = SimpleNamespace(number="P-001")
        section = SimpleNamespace(
            panels=3,
            quantity=1,
            slide_rows=1,
            lock_left="Без",
            lock_right="Без",
            handle_left="Ручка-кноб RS3014",
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
        assert drawing_rows[0]["marking"] == "1,1"

        plain_qty = sum(row["qty"] for row in rows if row["note"] == "")
        assert plain_qty == 2

    def test_glass_rows_sort_by_first_physical_marking(self):
        project = SimpleNamespace(number="P-ORDER")
        section = SimpleNamespace(
            panels=3,
            quantity=1,
            slide_rows=1,
            lock_left="Без",
            lock_right="Без",
            handle_left="Без ручки (глухая)",
            handle_right="Без ручки (глухая)",
            floor_latches_left=False,
            floor_latches_right=False,
        )
        calc = SimpleNamespace(
            glass_type="10ММ",
            glass=[
                SimpleNamespace(position="Левое", width_mm=1003.1, height_mm=2200.1, qty=1),
                SimpleNamespace(
                    position="Промежуточные", width_mm=995.1, height_mm=2200.1, qty=1
                ),
                SimpleNamespace(position="Правое", width_mm=1003.1, height_mm=2200.1, qty=1),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=1, section=section, calc=calc)]
        )

        assert rows[0]["marking"] == "1,1"
        assert rows[0]["markings"] == ["1,1", "1,3"]
        assert rows[0]["width"] == 1004
        assert rows[0]["height"] == 2201
        assert rows[1]["marking"] == "1,2"

    def test_two_row_center_bracket_drawing_marks_only_central_glass(self):
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
            center_lock="Без замка",
            center_handle="Ручка-скоба",
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
        assert drawing_row["marking"] == "2,2"
        assert plain_row["qty"] == 2
        assert plain_row["marking"] == "2,1"

    def test_two_row_left_center_floor_latch_does_not_create_drawing_note(self):
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

        plain_row = [row for row in rows if row["note"] == ""][0]
        assert [row for row in rows if row["note"] == "(чертеж)"] == []
        assert plain_row["qty"] == 4
        assert plain_row["marking"] == "3,1"

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

    def test_overrides_drop_legacy_extra_components(
        self, client, admin_headers, project
    ):
        section = _create_slide_section(client, admin_headers, project["id"])
        sid = section["id"]
        pid = project["id"]

        r = client.patch(
            f"/api/projects/{pid}/sections/{sid}/overrides",
            headers=admin_headers,
            json={
                "overrides": {
                    "extra_components": [{"art": "OLD"}],
                    "field_a": "111",
                }
            },
        )

        assert r.status_code == 200
        s = client.get(f"/api/projects/{pid}/sections", headers=admin_headers).json()
        sec = [x for x in s if x["id"] == sid][0]
        overrides = json.loads(sec.get("document_overrides", "{}"))
        assert "extra_components" not in overrides
        assert overrides["field_a"] == "111"

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
