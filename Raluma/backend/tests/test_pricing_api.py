import io
import json
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from openpyxl import Workbook
from pypdf import PdfReader

import models
from database import SessionLocal
from engine.quote_pricing import _section_requirements


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _login_headers(client, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_user(client, admin_headers, role="user", **overrides):
    password = overrides.pop("password", "secret123")
    username = overrides.pop("username", _unique(role))
    payload = {
        "username": username,
        "display_name": overrides.pop("display_name", username),
        "password": password,
        "role": role,
        "is_active": True,
        **overrides,
    }
    response = client.post("/api/users", headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json(), password


def _new_catalog_item():
    db = SessionLocal()
    try:
        item = models.CatalogItem(
            sku=_unique("PRICE"),
            name="Тестовая позиция цены",
            group="Профили",
            system="СЛАЙД",
            unit="п.м.",
            is_active=True,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id, item.sku
    finally:
        db.close()


def _delete_catalog_item(item_id: int):
    db = SessionLocal()
    try:
        item = db.get(models.CatalogItem, item_id)
        if item is not None:
            db.delete(item)
            db.commit()
    finally:
        db.close()


def _price_payload(cost: str, effective_from: datetime, reason="Тест цены"):
    return {
        "cost": cost,
        "profile_markup_percent": "100",
        "profile_discount_percent": "25",
        "waste_markup_percent": "30",
        "construction_markup_percent": "200",
        "construction_discount_percent": "35",
        "category": "profile",
        "unit": "п.м.",
        "min_margin_percent": "10",
        "effective_from": effective_from.isoformat(),
        "reason": reason,
    }


def test_price_versions_future_history_bulk_and_rollback(client, admin_headers):
    item_id, sku = _new_catalog_item()
    try:
        active = client.post(
            f"/api/pricing/catalog/{item_id}/versions",
            headers=admin_headers,
            json=_price_payload("100", datetime.utcnow() - timedelta(minutes=1)),
        )
        assert active.status_code == 201, active.text
        active_id = active.json()["id"]

        future = client.post(
            f"/api/pricing/catalog/{item_id}/versions",
            headers=admin_headers,
            json=_price_payload("200", datetime.utcnow() + timedelta(days=1)),
        )
        assert future.status_code == 201, future.text

        catalog = client.get("/api/pricing/catalog", headers=admin_headers)
        assert catalog.status_code == 200
        row = next(item for item in catalog.json()["items"] if item["id"] == item_id)
        assert row["active_price"]["cost"] == "100.00"
        assert row["next_price"]["cost"] == "200.00"
        assert row["history_count"] == 2

        bulk_data = {
            "item_ids": [item_id],
            "percent": "10",
            "effective_from": datetime.utcnow().isoformat(),
            "reason": "Индексация",
        }
        preview = client.post(
            "/api/pricing/catalog/bulk/preview",
            headers=admin_headers,
            json=bulk_data,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["rows"][0] == {
            "item_id": item_id,
            "sku": sku,
            "name": "Тестовая позиция цены",
            "old_cost": "100.00",
            "new_cost": "110.00",
            "source_version_id": active_id,
        }
        applied = client.post(
            "/api/pricing/catalog/bulk/apply",
            headers=admin_headers,
            json=bulk_data,
        )
        assert applied.status_code == 201, applied.text
        assert applied.json()["versions"][0]["cost"] == "110.00"

        rolled_back = client.post(
            f"/api/pricing/catalog/{item_id}/rollback/{active_id}",
            headers=admin_headers,
            json={
                "effective_from": datetime.utcnow().isoformat(),
                "reason": "Возврат проверенной цены",
            },
        )
        assert rolled_back.status_code == 201, rolled_back.text
        assert rolled_back.json()["cost"] == "100.00"
        assert rolled_back.json()["rollback_of_id"] == active_id

        history = client.get(
            f"/api/pricing/catalog/{item_id}/versions",
            headers=admin_headers,
        )
        assert history.status_code == 200
        assert len(history.json()["versions"]) == 4
    finally:
        _delete_catalog_item(item_id)


def test_excel_import_reads_formatted_percentages_and_applies_atomically(
    client,
    admin_headers,
):
    item_id, sku = _new_catalog_item()
    try:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Цены"
        sheet.append(
            [
                "Артикул",
                "Себестоимость",
                "Наценка на профиль",
                "Скидка на профиль",
                "Наценка на отходы",
                "Наценка на конструкции",
                "Скидка на конструкции",
                "Категория",
                "Единица",
                "Минимальная маржа",
            ]
        )
        sheet.append([sku, 123.45, 1, 0.25, 0.3, 2, 0.35, "profile", "п.м.", 0.1])
        for cell in sheet[2][2:7]:
            cell.number_format = "0%"
        sheet["J2"].number_format = "0%"
        output = io.BytesIO()
        workbook.save(output)

        preview = client.post(
            "/api/pricing/catalog/import/preview",
            headers=admin_headers,
            files={
                "file": (
                    "prices.xlsx",
                    output.getvalue(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert preview.status_code == 200, preview.text
        data = preview.json()
        assert data["valid"] is True
        assert data["rows"][0]["profile_markup_percent"] == "100"
        assert data["rows"][0]["profile_discount_percent"] == "25"
        assert data["rows"][0]["construction_markup_percent"] == "200"
        assert data["rows"][0]["min_margin_percent"] == "10"

        invalid_atomic = client.post(
            "/api/pricing/catalog/import/apply",
            headers=admin_headers,
            json={
                "rows": [*data["rows"], {**data["rows"][0], "sku": "NOT-FOUND"}],
                "reason": "Проверка атомарности",
            },
        )
        assert invalid_atomic.status_code == 400
        history = client.get(
            f"/api/pricing/catalog/{item_id}/versions",
            headers=admin_headers,
        ).json()
        assert history["versions"] == []

        applied = client.post(
            "/api/pricing/catalog/import/apply",
            headers=admin_headers,
            json={"rows": data["rows"], "reason": "Импорт прайс-листа"},
        )
        assert applied.status_code == 201, applied.text
        assert applied.json()["versions"][0]["cost"] == "123.45"
    finally:
        _delete_catalog_item(item_id)


def test_pricing_permission_and_dealer_quote_access(client, admin_headers):
    manager, manager_password = _create_user(client, admin_headers, role="user")
    price_manager, price_password = _create_user(
        client,
        admin_headers,
        role="user",
        can_manage_prices=True,
    )
    dealer, dealer_password = _create_user(client, admin_headers, role="dealer")
    dealer_headers = _login_headers(client, dealer["username"], dealer_password)
    manager_headers = _login_headers(client, manager["username"], manager_password)
    price_headers = _login_headers(client, price_manager["username"], price_password)
    project_id = None
    price_manager_project_id = None
    try:
        dealer_me = client.get("/api/auth/me", headers=dealer_headers)
        assert dealer_me.status_code == 200
        assert "dealer_discount_percent" not in dealer_me.json()
        assert client.get("/api/pricing/catalog", headers=manager_headers).status_code == 403
        assert client.get("/api/pricing/catalog", headers=dealer_headers).status_code == 403
        assert client.get("/api/pricing/catalog", headers=price_headers).status_code == 200
        terms = client.put(
            f"/api/pricing/dealers/{dealer['id']}",
            headers=price_headers,
            json={
                "dealer_markup_percent": "20",
                "profile_discount_percent": "5",
                "construction_discount_percent": "10",
                "component_discount_percent": "7",
                "service_discount_percent": "3",
            },
        )
        assert terms.status_code == 200, terms.text
        assert terms.json()["construction_discount_percent"] == "10"
        assert (
            client.get(
                f"/api/pricing/dealers/{dealer['id']}", headers=dealer_headers
            ).status_code
            == 403
        )
        price_manager_project = client.post(
            "/api/projects",
            headers=price_headers,
            json={"number": _unique("PRICE-Q"), "customer": "Клиент"},
        )
        assert price_manager_project.status_code == 201
        price_manager_project_id = price_manager_project.json()["id"]
        one_time_price = client.put(
            f"/api/projects/{price_manager_project_id}/quote/overrides",
            headers=price_headers,
            json={
                "overrides": [
                    {
                        "sku": "SPECIAL-PRICE",
                        "cost": "100",
                        "comment": "Согласовано для конкретного КП",
                    }
                ]
            },
        )
        assert one_time_price.status_code == 200, one_time_price.text
        margin_override = client.put(
            f"/api/projects/{price_manager_project_id}/quote/overrides",
            headers=price_headers,
            json={
                "overrides": [],
                "margin_override_comment": "Попытка разрешить исключение",
            },
        )
        assert margin_override.status_code == 403

        project = client.post(
            "/api/projects",
            headers=dealer_headers,
            json={"number": _unique("DEALER-Q"), "customer": "Дилер"},
        )
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]
        assert client.get(f"/api/projects/{project_id}/quote").status_code == 403
        assert (
            client.get(
                f"/api/pricing/projects/{project_id}", headers=dealer_headers
            ).status_code
            == 403
        )
        config = {
            "vat_mode": "none",
            "vat_rate": "20",
            "validity_days": 14,
            "manufacturing_term": "",
            "payment_terms": "",
            "services": [],
        }
        assert (
            client.put(
                f"/api/projects/{project_id}/quote/config",
                headers=dealer_headers,
                json=config,
            ).status_code
            == 403
        )
    finally:
        if project_id is not None:
            client.delete(f"/api/projects/{project_id}", headers=dealer_headers)
        if price_manager_project_id is not None:
            client.delete(
                f"/api/projects/{price_manager_project_id}", headers=price_headers
            )
        db = SessionLocal()
        try:
            db.query(models.DealerPricingTerms).filter_by(
                user_id=dealer["id"]
            ).delete()
            db.commit()
        finally:
            db.close()
        for user in (manager, price_manager, dealer):
            client.delete(f"/api/users/{user['id']}", headers=admin_headers)


def _seed_quote_prices(project_id: int, actor_id: int):
    db = SessionLocal()
    created_versions = []
    created_items = []
    try:
        project = db.get(models.Project, project_id)
        requirements = []
        for section in project.sections:
            _, section_requirements = _section_requirements(section)
            requirements.extend(section_requirements)
        by_sku = {}
        for required in requirements:
            by_sku.setdefault(required["sku"], required)
        skipped_sku = next(iter(by_sku))
        margin_sku = next(sku for sku in by_sku if sku != skipped_sku)
        for sku, required in by_sku.items():
            if sku == skipped_sku:
                continue
            item = db.query(models.CatalogItem).filter_by(sku=sku).first()
            if item is None:
                item = models.CatalogItem(
                    sku=sku,
                    name=required["name"],
                    group="Тест расчёта",
                    system="СЛАЙД",
                    unit=required["unit"],
                    is_active=True,
                )
                db.add(item)
                db.flush()
                created_items.append(item.id)
            version = models.CatalogPriceVersion(
                catalog_item_id=item.id,
                cost=Decimal("10.00"),
                profile_markup_percent=Decimal("0"),
                profile_discount_percent=Decimal("0"),
                waste_markup_percent=Decimal("30"),
                construction_markup_percent=Decimal("0"),
                construction_discount_percent=Decimal("0"),
                category=required["category"],
                unit=required["unit"],
                min_margin_percent=(
                    Decimal("1000") if sku == margin_sku else Decimal("0")
                ),
                effective_from=datetime.utcnow() - timedelta(minutes=1),
                created_at=datetime.utcnow(),
                created_by=actor_id,
                reason="Интеграционный тест КП",
            )
            db.add(version)
            db.flush()
            created_versions.append(version.id)
        db.commit()
        return {
            "skipped_sku": skipped_sku,
            "margin_sku": margin_sku,
            "versions": created_versions,
            "items": created_items,
            "requirements": by_sku,
        }
    finally:
        db.close()


def _cleanup_quote_prices(seed):
    db = SessionLocal()
    try:
        if seed["versions"]:
            db.query(models.CatalogPriceVersion).filter(
                models.CatalogPriceVersion.id.in_(seed["versions"])
            ).delete(synchronize_session=False)
        if seed["items"]:
            db.query(models.CatalogItem).filter(
                models.CatalogItem.id.in_(seed["items"])
            ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _assert_no_internal_pricing(payload):
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "base_cost",
        "internal_total",
        "dealer_markup",
        "minimum_total",
        "min_margin",
        "price_version",
        '"bom"',
        "override_comment",
    ):
        assert forbidden not in serialized


def test_quote_missing_override_margin_vat_snapshot_and_safe_exports(
    client,
    admin_headers,
    project,
    section,
):
    admin_id = client.get("/api/auth/me", headers=admin_headers).json()["id"]
    initial = client.get(
        f"/api/projects/{project['id']}/quote", headers=admin_headers
    )
    assert initial.status_code == 200
    assert initial.json()["export_allowed"] is False
    assert initial.json()["missing_price_count"] > 0
    assert "missing_prices" not in initial.json()
    blocked_pdf = client.get(
        f"/api/projects/{project['id']}/documents/commercial/pdf",
        headers=admin_headers,
    )
    assert blocked_pdf.status_code == 409
    blocked_quote = blocked_pdf.json()["detail"]["quote"]
    assert "missing_prices" not in blocked_quote
    _assert_no_internal_pricing(blocked_quote)

    seed = _seed_quote_prices(project["id"], admin_id)
    try:
        missing = client.get(
            f"/api/projects/{project['id']}/quote", headers=admin_headers
        ).json()
        assert missing["missing_price_count"] == 1
        internal_missing = client.get(
            f"/api/pricing/projects/{project['id']}", headers=admin_headers
        ).json()
        assert {row["sku"] for row in internal_missing["missing_prices"]} == {
            seed["skipped_sku"]
        }
        token = admin_headers["Authorization"].replace("Bearer ", "")
        incomplete_preview = client.get(
            f"/api/projects/{project['id']}/documents/commercial/preview",
            params={"token": token},
        )
        assert incomplete_preview.status_code == 200
        assert seed["skipped_sku"] not in incomplete_preview.text

        invalid_override = client.put(
            f"/api/projects/{project['id']}/quote/overrides",
            headers=admin_headers,
            json={
                "overrides": [
                    {"sku": seed["skipped_sku"], "cost": "12", "comment": ""}
                ],
                "margin_override_comment": "",
            },
        )
        assert invalid_override.status_code == 422

        overridden = client.put(
            f"/api/projects/{project['id']}/quote/overrides",
            headers=admin_headers,
            json={
                "overrides": [
                    {
                        "sku": seed["skipped_sku"],
                        "cost": "12",
                        "comment": "Разовая согласованная цена",
                    }
                ],
                "margin_override_comment": "",
            },
        )
        assert overridden.status_code == 200, overridden.text
        assert overridden.json()["missing_price_count"] == 0
        assert overridden.json()["export_allowed"] is False
        assert overridden.json()["warnings"] == ["Расчёт требует проверки менеджером."]
        assert "минималь" not in json.dumps(
            overridden.json(), ensure_ascii=False
        ).lower()
        internal_margin = client.get(
            f"/api/pricing/projects/{project['id']}", headers=admin_headers
        ).json()
        assert any(
            "минималь" in warning.lower()
            for warning in internal_margin["pending_warnings"]
        )

        unsupported_unit = client.put(
            f"/api/projects/{project['id']}/quote/config",
            headers=admin_headers,
            json={
                "vat_mode": "none",
                "vat_rate": "20",
                "validity_days": 14,
                "manufacturing_term": "",
                "payment_terms": "",
                "services": [
                    {
                        "id": "bad-unit",
                        "name": "Доставка",
                        "quantity": "1",
                        "unit": "рейс",
                        "base_cost": "100",
                    }
                ],
            },
        )
        assert unsupported_unit.status_code == 400

        configured = client.put(
            f"/api/projects/{project['id']}/quote/config",
            headers=admin_headers,
            json={
                "vat_mode": "on_top",
                "vat_rate": "20",
                "validity_days": 21,
                "manufacturing_term": "20 рабочих дней",
                "payment_terms": "70% аванс, 30% перед отгрузкой",
                "services": [
                    {
                        "id": "delivery",
                        "name": "Доставка",
                        "quantity": "2",
                        "unit": "шт.",
                        "base_cost": "100",
                    }
                ],
            },
        )
        assert configured.status_code == 200, configured.text

        allowed = client.put(
            f"/api/projects/{project['id']}/quote/overrides",
            headers=admin_headers,
            json={
                "overrides": [
                    {
                        "sku": seed["skipped_sku"],
                        "cost": "12",
                        "comment": "Разовая согласованная цена",
                    }
                ],
                "margin_override_comment": "Разрешено руководителем для тендера",
            },
        )
        assert allowed.status_code == 200, allowed.text
        quote = allowed.json()
        assert quote["export_allowed"] is True
        assert quote["vat"]["mode"] == "on_top"
        assert Decimal(quote["totals"]["vat"]) == (
            Decimal(quote["totals"]["subtotal"]) * Decimal("0.20")
        ).quantize(Decimal("0.01"))
        assert quote["totals"]["document_grand_total"] == sum(
            row["document_line_total"] for row in quote["lines"]
        )
        construction_line = next(
            row for row in quote["lines"] if row.get("section_details")
        )
        assert construction_line["section_details"]["glass_type"] == (
            "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
        )
        assert len(construction_line["section_details"]["panel_geometry"]) == 3
        assert construction_line["breakdown"][-1]["name"] == (
            "Стекло, покраска и изготовление"
        )
        assert sum(
            row["line_total"] for row in construction_line["breakdown"]
        ) == construction_line["document_line_total"]
        _assert_no_internal_pricing(quote)

        preview = client.get(
            f"/api/projects/{project['id']}/documents/commercial/preview",
            params={"token": token},
        )
        assert preview.status_code == 200, preview.text
        assert "Себестоимость" not in preview.text
        assert "Разовая согласованная цена" not in preview.text
        assert "70% аванс" in preview.text
        assert "Технические характеристики" in preview.text
        assert "Масштабный вид из помещения" in preview.text
        assert "Вид сверху" in preview.text
        assert "Профили и фурнитура" in preview.text
        assert "Стекло, покраска и изготовление" in preview.text

        word_draft = client.get(
            f"/api/projects/{project['id']}/documents/commercial/docx",
            headers=admin_headers,
        )
        assert word_draft.status_code == 200, word_draft.text
        assert client.get(
            f"/api/projects/{project['id']}/quote", headers=admin_headers
        ).json()["status"] == "draft"
        with zipfile.ZipFile(io.BytesIO(word_draft.content)) as archive:
            word_xml = archive.read("word/document.xml").decode("utf-8")
            quote_images = [
                name for name in archive.namelist() if name.startswith("word/media/")
            ]
        assert "Себестоимость" not in word_xml
        assert "Разовая согласованная цена" not in word_xml
        assert "Тип стекла" in word_xml
        assert "ПРОФИЛИ И ФУРНИТУРА" in word_xml
        assert "Стекло, покраска и изготовление" in word_xml
        assert len(quote_images) >= 2

        pdf = client.get(
            f"/api/projects/{project['id']}/documents/commercial/pdf",
            headers=admin_headers,
        )
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b"%PDF")
        pdf_text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf.content)).pages
        )
        assert "ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ" in pdf_text.upper()
        assert "СТЕКЛО, ПОКРАСКА И ИЗГОТОВЛЕНИЕ" in pdf_text.upper()
        fixed = client.get(
            f"/api/projects/{project['id']}/quote", headers=admin_headers
        ).json()
        assert fixed["status"] == "fixed"
        assert fixed["revision"] == 1
        original_total = fixed["totals"]["grand_total"]
        fixed_details = next(
            row["section_details"]
            for row in fixed["lines"]
            if row.get("section_details")
        )
        assert fixed_details["width_mm"] == "2000"

        db = SessionLocal()
        try:
            changed = db.get(models.CatalogPriceVersion, seed["versions"][0])
            replacement = models.CatalogPriceVersion(
                catalog_item_id=changed.catalog_item_id,
                cost=Decimal("999.00"),
                profile_markup_percent=changed.profile_markup_percent,
                profile_discount_percent=changed.profile_discount_percent,
                waste_markup_percent=changed.waste_markup_percent,
                construction_markup_percent=changed.construction_markup_percent,
                construction_discount_percent=changed.construction_discount_percent,
                category=changed.category,
                unit=changed.unit,
                min_margin_percent=Decimal("0"),
                effective_from=datetime.utcnow(),
                created_at=datetime.utcnow(),
                created_by=admin_id,
                reason="Новая цена после фиксации",
            )
            db.add(replacement)
            changed_section = db.get(models.Section, section["id"])
            changed_section.width = 2100
            db.get(models.Project, project["id"]).updated_at = datetime.utcnow()
            db.commit()
            db.refresh(replacement)
            seed["versions"].append(replacement.id)
        finally:
            db.close()

        stale = client.get(
            f"/api/projects/{project['id']}/quote", headers=admin_headers
        ).json()
        assert stale["stale"] is True
        assert stale["totals"]["grand_total"] == original_total

        stale_word = client.get(
            f"/api/projects/{project['id']}/documents/commercial/docx",
            headers=admin_headers,
        )
        assert stale_word.status_code == 200
        with zipfile.ZipFile(io.BytesIO(stale_word.content)) as archive:
            stale_word_xml = archive.read("word/document.xml").decode("utf-8")
        assert "Расчёт устарел" in stale_word_xml
        assert "2000 × 2400" in stale_word_xml
        assert "2100 × 2400" not in stale_word_xml

        refreshed = client.post(
            f"/api/projects/{project['id']}/quote/refresh",
            headers=admin_headers,
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["revision"] == 2
        assert refreshed.json()["status"] == "fixed"
        assert refreshed.json()["totals"]["grand_total"] != original_total
        refreshed_details = next(
            row["section_details"]
            for row in refreshed.json()["lines"]
            if row.get("section_details")
        )
        assert refreshed_details["width_mm"] == "2100"
        refreshed_word = client.get(
            f"/api/projects/{project['id']}/documents/commercial/docx",
            headers=admin_headers,
        )
        assert refreshed_word.status_code == 200
        with zipfile.ZipFile(io.BytesIO(refreshed_word.content)) as archive:
            refreshed_word_xml = archive.read("word/document.xml").decode("utf-8")
        assert "2100 × 2400" in refreshed_word_xml
    finally:
        _cleanup_quote_prices(seed)
