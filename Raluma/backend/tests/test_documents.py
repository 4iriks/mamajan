"""
Тесты API производственных документов (preview, overrides).
PDF-генерацию проверяем только если установлен WeasyPrint.
"""

import io
import json
import re
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from engine.pdf import (
    _img_b64,
    brush_meters,
    display_hardware,
    display_profiles,
    expand_glass_profile_lengths,
    expand_glass_widths,
    get_profile_asset_path,
    glass_mm,
    profile_dimension,
    section_extra_components,
)
from engine.project_documents import (
    CalculatedSection,
    _build_delivery_context,
    _build_glass_rows,
    _build_paint_pages,
    _iter_slide_sections,
    render_project_document_html,
)
from schemas import SectionCreate


class TestProfileAssetSafety:
    def test_img_b64_accepts_known_profile_image(self):
        assert get_profile_asset_path("RS112.png") is not None
        assert _img_b64("RS112.png").startswith("data:image/png;base64,")

    def test_img_b64_accepts_known_png_profile_images(self):
        assert get_profile_asset_path("RS23231.png") is not None
        assert _img_b64("RS23231.png").startswith("data:image/png;base64,")
        assert get_profile_asset_path("RS2021.png") is not None
        assert _img_b64("RS2021.png").startswith("data:image/png;base64,")

    def test_img_b64_rejects_path_traversal(self):
        assert get_profile_asset_path("../models.py") is None
        assert get_profile_asset_path("..\\models.py") is None
        assert _img_b64("../models.py") == ""
        assert _img_b64("..\\models.py") == ""

    def test_img_b64_rejects_non_image_extension(self):
        assert get_profile_asset_path("models.py") is None
        assert _img_b64("models.py") == ""


class TestProfileDisplayRows:
    def test_brush_meters_rounds_up_to_one_decimal(self):
        assert brush_meters(14.11) == "14,2 м"
        assert brush_meters("3,31") == "3,4 м"

    def test_display_hardware_keeps_lock_and_strike_in_separate_rows(self):
        hardware = [
            SimpleNamespace(
                article="BEFORE",
                name="До замка",
                value=1,
                unit="шт",
                image=None,
                field_key="before",
                sub_items=None,
            ),
            SimpleNamespace(
                article="RS3020",
                name="Замок",
                value=2,
                unit="шт",
                image="RS3020.png",
                field_key="rs3020_lock",
                sub_items=None,
            ),
            SimpleNamespace(
                article="RS123",
                name="Ответная планка",
                value=2,
                unit="шт",
                image="RS123.jpg",
                field_key="rs123",
                sub_items=None,
            ),
            SimpleNamespace(
                article="AFTER",
                name="После замка",
                value=1,
                unit="шт",
                image=None,
                field_key="after",
                sub_items=None,
            ),
        ]

        rows = display_hardware(hardware)

        assert [row.article for row in rows] == ["BEFORE", "RS3020", "RS123", "AFTER"]
        assert [row.source_index for row in rows] == [1, 2, 3, 4]
        assert all(row.sub_items is None for row in rows)

    def test_expand_glass_profile_lengths_matches_physical_panels(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(
                    position="Левое",
                    qty=1,
                    glass_profile_length=980,
                ),
                SimpleNamespace(
                    position="Промежуточные",
                    qty=2,
                    glass_profile_length=972,
                ),
                SimpleNamespace(
                    position="Правое",
                    qty=1,
                    glass_profile_length=981,
                ),
            ]
        )

        assert expand_glass_profile_lengths(calc, panels=4, fallback_width=4000) == [
            980,
            972,
            972,
            981,
        ]

    def test_split_profile_parts_are_grouped_for_sheet_display(self):
        rows = display_profiles(
            [
                SimpleNamespace(
                    article="RS2323",
                    name="Порог",
                    length_mm=2975,
                    qty=2,
                    painted=True,
                    image="RS2323.png",
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
                    image="RS2323.png",
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
    def test_glass_mm_rounds_to_nearest_millimeter(self):
        assert glass_mm(995.0) == 995
        assert glass_mm(995.1) == 995
        assert glass_mm(995.5) == 996
        assert glass_mm(995.9) == 996

    def test_expands_edge_and_middle_glass_widths(self):
        calc = SimpleNamespace(
            glass=[
                SimpleNamespace(position="Крайние", width_mm=520.1, qty=2),
                SimpleNamespace(position="Промежуточные", width_mm=470.1, qty=2),
            ]
        )

        assert [glass_mm(width) for width in expand_glass_widths(calc, 4, 2000)] == [
            520,
            470,
            470,
            520,
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


def _delivery_section(**overrides):
    payload = {
        "name": "Секция 1",
        "order": 1,
        "system": "СЛАЙД",
        "width": 2000,
        "height": 2400,
        "panels": 3,
        "quantity": 1,
        "rails": 3,
        "slide_rows": 1,
        "threshold": "Стандартный анод",
        "painting_type": "RAL стандарт",
        "ral_color": "9016 МАТОВЫЙ",
        "first_panel_inside": "Справа",
        "inter_glass_profile": "Алюминиевый RS2061",
    }
    payload.update(overrides)
    return SimpleNamespace(**SectionCreate(**payload).model_dump())


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
        assert 'data-profile-image="RS2333-left"' in r.text
        assert 'data-profile-image="RS2333-right"' in r.text
        assert 'width="66" height="30"' in r.text
        assert 'data-profile-image="RS2333-left" transform="translate(48 ' in r.text
        assert 'data-profile-image="RS2333-right" transform="translate(392 ' in r.text
        assert re.search(r"RU008</td>\s*<td[^>]*>\d+,\d м</td>", r.text)
        assert re.search(r"RU007</td>\s*<td[^>]*>\d+,\d м</td>", r.text)

    def test_five_rail_wall_profiles_touch_top_view(
        self, client, admin_headers, project
    ):
        section = _create_slide_section(
            client,
            admin_headers,
            project["id"],
            rails=5,
            panels=4,
        )
        token = admin_headers["Authorization"].replace("Bearer ", "")
        r = client.get(
            f"/api/projects/{project['id']}/sections/{section['id']}/preview",
            params={"token": token},
        )
        assert r.status_code == 200
        assert 'width="102" height="30"' in r.text
        assert 'data-profile-image="RS2335-left" transform="translate(51 ' in r.text
        assert 'data-profile-image="RS2335-right" transform="translate(389 ' in r.text

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
        assert 'data-profile="inter-glass" data-panel="2" data-dir="1"' in r.text
        assert 'data-profile="inter-glass" data-panel="3" data-dir="-1"' in r.text
        assert r.text.count('data-profile="inter-glass"') == 2

    def test_two_row_six_panel_inter_glass_profiles_start_from_center(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-2R-6"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 2400,
                    "panels": 6,
                    "quantity": 1,
                    "rails": 3,
                    "slide_rows": 2,
                    "unused_track": "Внешний",
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                },
            },
        )

        assert r.status_code == 200
        assert r.text.count('data-profile="inter-glass"') == 4
        for panel, direction in ((2, 1), (3, 1), (4, -1), (5, -1)):
            assert (
                f'data-profile="inter-glass" data-panel="{panel}" '
                f'data-dir="{direction}"'
            ) in r.text

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
                    "profile_right_p_bar": True,
                    "profile_right_bubble": True,
                },
            },
        )

        assert r.status_code == 200
        assert "RAL 9016 МАТОВЫЙ" in r.text
        assert "НЕСТАНДАРТ" not in r.text
        assert "Не используется внутренняя полоса" in r.text
        assert "Порог накладной 3-рельсовый окраш" in r.text
        assert ">Накладной окраш<" not in r.text
        assert "RS23231.png" not in r.text  # картинка встраивается data-uri
        assert "Межстекольный профиль" not in r.text
        assert 'data-profile="left-side-stack"' not in r.text
        assert 'data-profile-image="RS2081-left"' not in r.text
        assert 'data-profile-image="RS112-left"' not in r.text
        assert 'data-profile-image="RS2333-left"' in r.text
        assert 'data-profile-image="RS2333-right"' in r.text
        assert 'data-side-assembly="lock-handle"' in r.text
        assert 'data-side-assembly="p-bubble"' in r.text

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
        assert (
            'class="prof-img pl-art-rs2061 pl-focus-img mirror-x" alt="RS2061"'
            in r.text
        )

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
        assert 'class="gp-pos"' in r.text
        assert 'class="gp-len"' in r.text
        assert 'class="gp-qty"' in r.text
        assert "text-overflow" not in r.text
        assert "</span> шт</td>" in r.text
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
        assert 'contenteditable="true" data-field="ec_' not in r.text
        assert '<div class="ec-section">' in r.text
        ec_index = r.text.index("ДОПОЛНИТЕЛЬНЫЕ КОМПЛЕКТУЮЩИЕ")
        assert 'class="page-break"' not in r.text[:ec_index]

    def test_local_pdf_keeps_ten_extra_components_on_first_page(self, client):
        pytest.importorskip("weasyprint")

        extra_components = [
            {
                "sku": f"EXTRA-{index:02d}",
                "name": f"Дополнительная деталь {index}",
                "color": "RAL 9016",
                "size": "1200",
                "qty": "1",
            }
            for index in range(1, 11)
        ]
        r = client.post(
            "/api/projects/local/sections/pdf",
            json={
                "project": {"number": "LOCAL-EC-10", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 3000,
                    "panels": 3,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "first_panel_inside": "Справа",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "profile_left_lock_bar": True,
                    "profile_right_handle_bar": True,
                    "lock_left": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                    "extra_components": json.dumps(
                        extra_components, ensure_ascii=False
                    ),
                },
            },
        )

        assert r.status_code == 200
        pages = PdfReader(io.BytesIO(r.content)).pages
        assert len(pages) == 2
        first_page_text = pages[0].extract_text()
        assert "EXTRA-01" in first_page_text
        assert "EXTRA-10" in first_page_text
        second_page_text = pages[1].extract_text()
        assert "EXTRA-10" not in second_page_text
        assert "Нарезка профиля по ТЗ" in second_page_text
        assert "Ответственные за заказ на производстве" in second_page_text

    def test_local_preview_slide_sheet_uses_three_hardware_columns_without_checklist(
        self, client
    ):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-HW", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 3000,
                    "height": 3000,
                    "panels": 3,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "profile_left_lock_bar": True,
                    "profile_right_handle_bar": True,
                    "comments": "Комментарий для производства",
                },
            },
        )

        assert r.status_code == 200
        assert "ФУРНИТУРА" in r.text
        assert "Саморез" in r.text
        assert "<b>ЧЕК-ЛИСТ</b>" not in r.text
        assert "Вставить фетровое уплотнение" not in r.text
        assert '<div class="check-page">' in r.text
        assert "ПРОЕКТ № LOCAL-HW — Секция 1" in r.text
        assert "Нарезка профиля по ТЗ" in r.text
        assert "Примечания и особые отметки при производстве или проверке ОТК" in r.text
        assert r.text.count('style="display:block; width:72%; margin:0 0 0 7%;"') >= 2
        production_end = r.text.index("</div><!-- production-page-end -->")
        checklist_start = r.text.index('<div class="check-page">')
        assert production_end < checklist_start
        assert 'data-field="check_note_1"' in r.text
        assert 'data-field="check_note_14"' not in r.text
        assert "font-size: 12.5pt; font-weight: 700;" in r.text
        assert "КОММЕНТАРИИ К СЕКЦИИ" not in r.text
        assert "Комментарий для производства" in r.text
        assert 'class="params-notes"' in r.text
        assert '<div class="params-notes-title">ПРИМЕЧАНИЕ</div>' in r.text
        assert r.text.count("Комментарий для производства") >= 2
        assert r.text.count('style="width:33%;"') >= 2

    def test_local_preview_renders_rs3020_and_rs123_in_separate_hardware_cells(
        self, client
    ):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-LOCK", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 2000,
                    "height": 2400,
                    "panels": 2,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "lock_left": "ЗАМОК двухсторонний с ключом RS3020",
                },
            },
        )

        assert r.status_code == 200
        assert 'data-hardware-group="RS3020-RS123"' not in r.text
        assert 'data-hardware-subitem="RS3020"' not in r.text
        assert 'data-hardware-subitem="RS123"' not in r.text
        assert '<div class="hw-art">RS3020</div>' in r.text
        assert '<div class="hw-art">RS123</div>' in r.text

    def test_local_preview_hides_rs3110_length_but_keeps_piece_quantity(self, client):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-RS3110", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 2000,
                    "height": 2400,
                    "panels": 4,
                    "quantity": 1,
                    "rails": 3,
                    "slide_rows": 2,
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "center_handle": "Без ручки (глухие)",
                },
            },
        )

        assert r.status_code == 200
        assert 'data-profile-article="RS3110"' in r.text
        assert 'data-profile-article="RS3110" data-length-visible="false"' in r.text

    def test_local_preview_section_4_room_scheme_keeps_physical_glass_order(
        self, client
    ):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-S4", "customer": "Тест"},
                "section": {
                    "name": "Секция 4",
                    "system": "СЛАЙД",
                    "width": 1900,
                    "height": 2720,
                    "panels": 2,
                    "quantity": 1,
                    "rails": 3,
                    "threshold": "Стандартный анод",
                    "first_panel_inside": "Слева",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                    "profile_left_lock_bar": True,
                    "profile_left_handle_bar": True,
                    "profile_right_p_bar": True,
                    "profile_right_bubble": True,
                    "handle_left": "Без",
                    "lock_left": "ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
                    "handle_right": "Без",
                    "lock_right": "Без",
                },
            },
        )

        assert r.status_code == 200
        assert "901 (917)" in r.text
        assert "909 (909)" in r.text
        assert r.text.index("901 (917)") < r.text.index("909 (909)")

    def test_local_preview_two_row_sheet_uses_three_hardware_columns_without_checklist(
        self, client
    ):
        r = client.post(
            "/api/projects/local/sections/preview",
            json={
                "project": {"number": "LOCAL-HW2", "customer": "Тест"},
                "section": {
                    "name": "Секция 1",
                    "system": "СЛАЙД",
                    "width": 4000,
                    "height": 3000,
                    "panels": 6,
                    "quantity": 1,
                    "rails": 3,
                    "slide_rows": 2,
                    "threshold": "Стандартный анод",
                    "inter_glass_profile": "Алюминиевый RS2061",
                    "profile_left_wall": True,
                    "profile_right_wall": True,
                },
            },
        )

        assert r.status_code == 200
        assert "SLIDE-стандарт 2 ряда" in r.text
        assert "ФУРНИТУРА" in r.text
        assert "<b>ЧЕК-ЛИСТ</b>" not in r.text
        assert "Установить ролики" not in r.text
        assert '<div class="check-page">' in r.text
        assert "ПРОЕКТ № LOCAL-HW2 — Секция 1" in r.text
        assert "Фрезеровка профиля-замка под защелку" in r.text

    def test_section_extra_components_prefer_section_over_legacy_override(self):
        section = SimpleNamespace(
            extra_components=json.dumps(
                [{"sku": "BOX-NEW", "name": "Новый бокс", "qty": "2"}],
                ensure_ascii=False,
            )
        )
        overrides = {
            "extra_components": [{"art": "BOX-OLD", "name": "Старый бокс", "qty": "1"}]
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
        assert 'class="paint-meta-value"' in r.text
        assert 'class="paint-meta-value paint-color-value"' in r.text
        assert "paint-bosses-marker" in r.text
        assert "paint-marker-standard-threshold" in r.text
        assert "top: 1.3mm;" in r.text
        assert "width: 80%;" in r.text

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
        assert "top: 1.5mm;" in r.text
        assert "width: 84%;" in r.text

    def test_local_project_paint_preview_includes_manual_rows(self, client):
        r = client.post(
            "/api/projects/local/documents/paint/preview",
            json={
                "project": {
                    "number": "LOCAL-PAINT",
                    "customer": "Гость",
                    "paint_manual_rows": json.dumps(
                        [
                            {
                                "color": "RAL 7016",
                                "article": "MAN-GUEST",
                                "name": "Ручная гостевая деталь",
                                "qty": "2",
                                "clean": "1450",
                                "allowance": "1500",
                                "totalM": "3.0",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                },
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
                        "painting_type": "Анодированный",
                        "first_panel_inside": "Справа",
                    }
                ],
            },
        )

        assert r.status_code == 200
        assert "MAN-GUEST" in r.text
        assert "Ручная гостевая деталь" in r.text
        assert "RAL 7016" in r.text

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
                    image="RS2021.png",
                    paint_note="",
                    paint_mode="Красится",
                ),
                SimpleNamespace(
                    article="RS2333",
                    name="Пристеночный профиль",
                    length_mm=3000,
                    qty=1,
                    painted=True,
                    image="RS2333.png",
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
                    image="RS2021.png",
                    paint_note="",
                    paint_mode="Красится",
                ),
                SimpleNamespace(
                    article="RS2021",
                    name="Стекольный профиль",
                    length_mm=2838,
                    qty=1,
                    painted=True,
                    image="RS2021.png",
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

    def test_manual_paint_rows_are_added_to_color_page(self):
        section = SimpleNamespace()
        calc = SimpleNamespace(color_text="RAL 9016", profiles=[])
        pages = _build_paint_pages(
            [CalculatedSection(order=1, section=section, calc=calc)],
            [
                {
                    "color": "RAL 7016",
                    "article": "MAN-1",
                    "name": "Ручная деталь",
                    "imageData": "data:image/png;base64,abc",
                    "qty": "2",
                    "clean": "1445",
                    "allowance": "1500",
                    "note": "срочно",
                }
            ],
        )

        page = pages[0]
        row = page["rows"][0]
        group = page["groups"][0]
        assert page["color"] == "RAL 7016"
        assert row["article"] == "MAN-1"
        assert row["total_m"] == 3.0
        assert group["image_data"] == "data:image/png;base64,abc"

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
                    image="RS2323.png",
                    paint_note="НЕ КРАСИТЬ!!!",
                    paint_mode="Частично",
                ),
                SimpleNamespace(
                    article="RS23231",
                    name="Порог накладной 3-рельсовый",
                    length_mm=2968,
                    qty=1,
                    painted=True,
                    image="RS23231.png",
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

        rows = _iter_slide_sections([section("Секция 2", 1), section("Секция 1", 99)])

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
                SimpleNamespace(
                    position="Левое", width_mm=1003.1, height_mm=2200.1, qty=1
                ),
                SimpleNamespace(
                    position="Промежуточные", width_mm=995.1, height_mm=2200.1, qty=1
                ),
                SimpleNamespace(
                    position="Правое", width_mm=1003.1, height_mm=2200.1, qty=1
                ),
            ],
        )

        rows = _build_glass_rows(
            project, [CalculatedSection(order=1, section=section, calc=calc)]
        )

        assert rows[0]["marking"] == "1,1"
        assert rows[0]["markings"] == ["1,1", "1,3"]
        assert rows[0]["width"] == 1003
        assert rows[0]["height"] == 2200
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


class TestDeliveryNote:
    @staticmethod
    def project(**overrides):
        values = {
            "number": "Н-001",
            "customer": "ООО ТЕСТ",
            "glass_status": "Заказано",
            "delivery_note_data": json.dumps(
                {"includeGlass": False, "places": {}}, ensure_ascii=False
            ),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_constructions_include_all_systems_and_threshold_does_not_split_group(self):
        sections = [
            _delivery_section(
                name="Секция 1",
                order=1,
                quantity=2,
                threshold="Стандартный анод",
            ),
            _delivery_section(
                name="Секция 2",
                order=2,
                quantity=1,
                threshold="Накладной окраш",
            ),
            _delivery_section(
                name="Секция 3",
                order=3,
                system="КНИЖКА",
                book_system="B25",
            ),
            _delivery_section(
                name="Секция 4",
                order=4,
                system="ЛИФТ",
                door_system="одностворчатая",
            ),
            _delivery_section(
                name="Секция 5",
                order=5,
                system="ЦС",
                cs_shape="Прямоугольник",
            ),
        ]

        context = _build_delivery_context(self.project(), sections)
        rows = [
            row
            for row in context["delivery_item1_rows"]
            if row["kind"] == "construction"
        ]
        slide = [row for row in rows if "SLIDE" in row["name"]][0]

        assert len(rows) == 4
        assert slide["qty"] == 3
        assert slide["threshold"] == "Пороги согласно ТЗ"
        assert {
            (dimension["size"], dimension["threshold"])
            for dimension in slide["dimensions"]
        } == {
            ("2000×2400 мм", "Стандартный анод"),
            ("2000×2400 мм", "Накладной окраш"),
        }
        assert any("КНИЖКА B25" in row["name"] for row in rows)
        assert any("ЛИФТ" in row["name"] for row in rows)
        assert any("Raluma ЦС" in row["name"] for row in rows)

    def test_anodized_construction_ignores_stale_ral_color(self):
        section = _delivery_section(
            painting_type="Анодированный",
            ral_color="7024 МАТОВЫЙ",
            threshold="Стандартный анод",
        )
        context = _build_delivery_context(
            self.project(
                delivery_note_data=json.dumps(
                    {"includeGlass": True, "places": {}}, ensure_ascii=False
                )
            ),
            [section],
        )

        construction = next(
            row
            for row in context["delivery_item1_rows"]
            if row["kind"] == "construction"
        )
        glass = next(
            row for row in context["delivery_item1_rows"] if row["kind"] == "glass"
        )

        assert construction["color"] == "Анодированный"
        assert glass["color"] == "Анодированный"

    def test_glass_is_grouped_inside_section_and_marked_in_project_order(self):
        project = self.project(
            delivery_note_data=json.dumps(
                {"includeGlass": True, "places": {}}, ensure_ascii=False
            )
        )
        section = _delivery_section(
            name="Секция 4",
            order=4,
            panels=3,
            quantity=2,
        )

        context = _build_delivery_context(project, [section])
        glass_groups = [
            row for row in context["delivery_item1_rows"] if row["kind"] == "glass"
        ]

        assert len(glass_groups) == 1
        assert glass_groups[0]["qty"] == 6
        assert sum(row["qty"] for row in glass_groups[0]["rows"]) == 6
        assert [row["marking"] for row in glass_groups[0]["rows"]] == ["Н-001 4,1"]

    def test_hardware_rows_exclude_rs3018_rs3020_and_keep_special_groups(self):
        section = _delivery_section(
            panels=2,
            quantity=2,
            handle_left="Ручка-кноб RS3014",
            handle_right="Стеклянная ручка RS3017",
            lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
            lock_right="ЗАМОК двухсторонний с ключом RS3020",
            floor_latches_left=True,
            extra_components=json.dumps(
                [
                    {
                        "sku": "BOX-1",
                        "name": "Монтажный бокс",
                        "color": "RAL 9016",
                        "size": "1200 мм",
                        "qty": "3",
                    }
                ],
                ensure_ascii=False,
            ),
        )

        context = _build_delivery_context(self.project(), [section])
        rows = {row["article"]: row for row in context["delivery_item2_rows"]}

        assert (
            context["delivery_item2_rows"][0]["name"]
            == "Комплект фурнитуры согласно ТЗ"
        )
        assert rows["RS3014"]["qty"] == 2
        assert rows["RS3017"]["qty"] == 2
        assert rows["RS205"]["qty"] == 2
        assert rows["BOX-1"]["qty"] == 6
        assert "RS3018" not in rows
        assert "RS3020" not in rows

    def test_reference_4108_total_includes_rs3110_and_six_rs2081(self):
        sections = [
            _delivery_section(
                name="Секция 1",
                order=1,
                height=2545,
                panels=4,
                slide_rows=2,
                threshold="Накладной окраш",
                ral_color="9005 МАТОВЫЙ",
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
                handle_left="Ручка-кноб RS3014",
                handle_right="Ручка-кноб RS3014",
                center_lock="Замок стекло-стекло RS30301",
                center_handle="Без ручки",
            ),
            _delivery_section(
                name="Секция 2",
                order=2,
                height=2545,
                panels=3,
                threshold="Накладной окраш",
                ral_color="9005 МАТОВЫЙ",
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
            ),
            _delivery_section(
                name="Секция 3",
                order=3,
                height=2545,
                panels=3,
                threshold="Накладной окраш",
                ral_color="9005 МАТОВЫЙ",
                profile_left_lock_bar=True,
                profile_right_lock_bar=True,
            ),
            _delivery_section(name="Секция 4", order=4, panels=3),
        ]

        context = _build_delivery_context(self.project(), sections)
        hardware = {row["article"]: row for row in context["delivery_item2_rows"]}

        assert hardware["RS3110"]["qty"] == 1
        assert hardware["RS2081"]["qty"] == 6
        assert hardware["RS2081"]["color"] == "RAL 9005 МАТОВЫЙ"
        assert hardware["RS2081"]["size"] == "2490 мм"
        assert hardware["RS2081"]["note"] == "БЕЗ ФРЕЗЕРОВКИ ПОД ЗАЩЕЛКИ"
        assert context["delivery_total_qty"] == "15"

        html = render_project_document_html(self.project(), sections, "delivery")
        assert "БЕЗ ФРЕЗЕРОВКИ ПОД ЗАЩЕЛКИ" in html

    def test_rs2081_processing_note_is_split_by_physical_side(self):
        section = _delivery_section(
            height=2545,
            panels=2,
            threshold="Накладной окраш",
            profile_left_lock_bar=True,
            profile_right_lock_bar=True,
            lock_left="ЗАМОК-ЗАЩЕЛКА 1стор RS3018",
            lock_right="Без замка",
        )

        context = _build_delivery_context(self.project(), [section])
        rows = [
            row for row in context["delivery_item2_rows"] if row["article"] == "RS2081"
        ]

        assert len(rows) == 2
        assert {row["qty"] for row in rows} == {1.0}
        assert {row["note"] for row in rows} == {
            "",
            "БЕЗ ФРЕЗЕРОВКИ ПОД ЗАЩЕЛКИ",
        }

    def test_reference_4027_total_is_33(self):
        project = self.project(
            number="В26-5-4027",
            delivery_note_data=json.dumps(
                {"includeGlass": True, "places": {}}, ensure_ascii=False
            ),
        )
        sections = [
            _delivery_section(
                name="Секция 1",
                order=1,
                width=4945,
                height=2890,
                panels=4,
                rails=3,
                slide_rows=2,
                threshold="Накладной анод",
                ral_color="7024 МАТОВЫЙ",
                center_handle="Без ручки",
            ),
            _delivery_section(
                name="Секция 2",
                order=2,
                width=2350,
                height=2300,
                panels=4,
                rails=3,
                threshold="Накладной анод",
                ral_color="7024 МАТОВЫЙ",
                handle_left="Ручка-кноб RS3014",
                handle_right="Ручка-кноб RS3014",
                floor_latches_left=True,
                floor_latches_right=True,
            ),
            _delivery_section(
                name="Секция 3",
                order=3,
                width=3680,
                height=2890,
                panels=6,
                rails=5,
                threshold="Накладной анод",
                ral_color="7024 МАТОВЫЙ",
            ),
            _delivery_section(
                name="Секция 4",
                order=4,
                width=3310,
                height=2890,
                panels=3,
                rails=5,
                threshold="Накладной анод",
                ral_color="7024 МАТОВЫЙ",
            ),
            _delivery_section(
                name="Секция 5",
                order=5,
                width=3890,
                height=2300,
                panels=5,
                rails=5,
                threshold="Накладной анод",
                ral_color="7024 МАТОВЫЙ",
            ),
        ]

        context = _build_delivery_context(project, sections)
        glass_qty = sum(
            row["qty"]
            for row in context["delivery_item1_rows"]
            if row["kind"] == "glass"
        )
        hardware = {row["article"]: row for row in context["delivery_item2_rows"]}
        glass_by_section: dict[int, int] = {}
        for group in context["delivery_item1_rows"]:
            if group["kind"] != "glass":
                continue
            for row in group["rows"]:
                match = re.search(r"(\d+),\d+$", row["marking"])
                assert match is not None
                section_number = int(match.group(1))
                glass_by_section[section_number] = (
                    glass_by_section.get(section_number, 0) + row["qty"]
                )
        construction_sizes = {
            dimension["size"]
            for row in context["delivery_item1_rows"]
            if row["kind"] == "construction"
            for dimension in row["dimensions"]
        }

        assert glass_qty == 22
        assert glass_by_section == {1: 4, 2: 4, 3: 6, 4: 3, 5: 5}
        assert construction_sizes == {
            "4945×2890 мм",
            "2350×2300 мм",
            "3680×2890 мм",
            "3310×2890 мм",
            "3890×2300 мм",
        }
        assert hardware["RS3014"]["qty"] == 2
        assert hardware["RS205"]["qty"] == 2
        assert hardware["RS3110"]["qty"] == 1
        assert context["delivery_total_qty"] == "33"

    def test_non_slide_glass_is_listed_without_invented_dimensions(self):
        project = self.project(
            delivery_note_data=json.dumps(
                {"includeGlass": True, "places": {}}, ensure_ascii=False
            )
        )
        sections = [
            _delivery_section(
                name="Секция 1",
                order=1,
                system="КНИЖКА",
                panels=3,
                quantity=2,
            ),
            _delivery_section(
                name="Секция 2",
                order=2,
                system="ЛИФТ",
                panels=2,
                quantity=1,
            ),
            _delivery_section(
                name="Секция 3",
                order=3,
                system="ЦС",
                panels=1,
                quantity=1,
            ),
        ]

        context = _build_delivery_context(project, sections)
        glass_rows = [
            row for row in context["delivery_item1_rows"] if row["kind"] == "glass"
        ]
        detail_rows = [detail for row in glass_rows for detail in row["rows"]]

        assert sum(row["qty"] for row in glass_rows) == 9
        assert {detail["marking"] for detail in detail_rows} == {
            "Н-001 1,1",
            "Н-001 2,1",
            "Н-001 3,1",
        }
        assert all(detail["width"] is None for detail in detail_rows)
        assert all(detail["height"] is None for detail in detail_rows)
        assert all(detail["note"] == "Размеры согласно ТЗ" for detail in detail_rows)

    def test_places_are_stable_and_restored_per_group(self):
        section = _delivery_section(quantity=2)
        first = _build_delivery_context(self.project(), [section])
        construction = first["delivery_item1_rows"][0]
        hardware = first["delivery_item2_rows"][0]
        project = self.project(
            delivery_note_data=json.dumps(
                {
                    "includeGlass": False,
                    "places": {
                        construction["place_key"]: "4",
                        hardware["place_key"]: "2",
                    },
                },
                ensure_ascii=False,
            )
        )

        restored = _build_delivery_context(project, [section])

        assert restored["delivery_item1_rows"][0]["places"] == "4"
        assert restored["delivery_item2_rows"][0]["places"] == "2"
        assert (
            restored["delivery_item1_rows"][0]["place_key"]
            != restored["delivery_item2_rows"][0]["place_key"]
        )

    def test_authenticated_preview_renders_saved_delivery_requisites(
        self, client, admin_headers, project
    ):
        _create_slide_section(client, admin_headers, project["id"])
        saved = {
            "dateMode": "custom",
            "date": "2026-07-15",
            "note": "Отгрузка по звонку",
            "contact": "Иван Иванов",
            "delivery": "Самовывоз",
            "includeGlass": False,
            "places": {},
        }
        update = client.put(
            f"/api/projects/{project['id']}",
            headers=admin_headers,
            json={"delivery_note_data": json.dumps(saved, ensure_ascii=False)},
        )
        assert update.status_code == 200
        token = admin_headers["Authorization"].replace("Bearer ", "")

        response = client.get(
            f"/api/projects/{project['id']}/documents/delivery/preview",
            params={"token": token},
        )

        assert response.status_code == 200
        assert "Накладная № TEST-001" in response.text
        assert "15.07.2026" in response.text
        assert "Отгрузка по звонку" in response.text
        assert "Иван Иванов" in response.text
        assert "Самовывоз" in response.text
        assert 'data-delivery-place-key="' in response.text
        assert "Стекло 10ММ" not in response.text
        assert "Доставка, разгрузка и монтаж" in response.text
        assert "Изделия и комплектацию принял" in response.text
        assert "<th>Примечание</th>" not in response.text
        assert response.text.count('class="signature-role">Исполнитель</span>') == 1
        assert response.text.count('class="signature-role">Заказчик</span>') == 1

    def test_guest_preview_includes_non_slide_systems(self, client):
        response = client.post(
            "/api/projects/local/documents/delivery/preview",
            json={
                "project": {
                    "number": "LOCAL-N-1",
                    "customer": "Гость",
                    "delivery_note_data": json.dumps(
                        {"includeGlass": False, "places": {}},
                        ensure_ascii=False,
                    ),
                },
                "sections": [
                    {
                        "name": "Секция 1",
                        "order": 1,
                        "system": "КНИЖКА",
                        "book_system": "B25",
                        "width": 2100,
                        "height": 2500,
                        "quantity": 2,
                    },
                    {
                        "name": "Секция 2",
                        "order": 2,
                        "system": "ЛИФТ",
                        "width": 1800,
                        "height": 2300,
                        "quantity": 1,
                    },
                    {
                        "name": "Секция 3",
                        "order": 3,
                        "system": "ЦС",
                        "cs_shape": "Прямоугольник",
                        "width": 1200,
                        "height": 1800,
                        "quantity": 1,
                    },
                ],
            },
        )

        assert response.status_code == 200
        assert "Raluma КНИЖКА B25" in response.text
        assert "Raluma ЛИФТ" in response.text
        assert "Raluma ЦС" in response.text
        assert 'contenteditable="true"' in response.text


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
