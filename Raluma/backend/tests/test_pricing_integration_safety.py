"""Cross-boundary pricing regressions using an isolated, disposable database."""
import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError

import models
from api.documents import _document_quote
from api.projects import _normalize_project_extras, _project_response, list_projects
from database import Base
from engine.cost_report import _allocate, _metrics, build_cost_report_context, build_cost_report_xlsx
from engine.office_docx import _rubles
from engine.project_documents import _document_money, render_project_document_html
from engine.quote_pricing import freeze_quote, get_or_create_quote_state, refresh_quote_revision
from engine.quote_pricing import public_quote
from schemas import QuoteManualService, QuoteDiscountRule, StandaloneSaleItem


@pytest.fixture
def isolated_pricing():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = models.User(username="safety", display_name="Test", password_hash="x", role="superadmin")
        db.add(actor)
        db.flush()
        project = models.Project(number="Safety", customer="Test", created_by=actor.id,
                                 extra_components=json.dumps([{"id": "stable", "name": "Деталь",
                                                              "qty": "2", "unit_price": "10.40", "actual_cost": "0"}]))
        db.add(project)
        db.flush()
        yield db, project, actor
    engine.dispose()


def test_private_extra_cost_is_hidden_and_preserved_on_ordinary_edit(isolated_pricing):
    db, project, actor = isolated_pricing
    ordinary = models.User(role="user", can_manage_prices=False)
    visible = json.loads(_project_response(project, ordinary)["extra_components"])
    assert "actual_cost" not in visible[0]
    assert "actual_cost" not in json.loads(list_projects(db, ordinary)[0]["extra_components"])[0]
    assert json.loads(_project_response(project, actor)["extra_components"])[0]["actual_cost"] == "0"
    visible[0]["qty"] = "3"
    updated = json.loads(_normalize_project_extras(json.dumps(visible), db, actor=ordinary, previous=project.extra_components))
    assert updated[0]["actual_cost"] == "0"
    assert updated[0]["qty"] == "3"
    assert updated[0]["id"] == "stable"
    for supplied in ("1", None, ""):
        visible[0]["actual_cost"] = supplied
        with pytest.raises(HTTPException) as failure:
            _normalize_project_extras(json.dumps(visible), db, actor=ordinary)
        assert failure.value.status_code == 403


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1e1000000", "1e999"])
def test_invalid_manual_sale_and_cost_rejected(isolated_pricing, value):
    db, _, actor = isolated_pricing
    for key in ("unit_price", "actual_cost"):
        with pytest.raises(HTTPException) as failure:
            _normalize_project_extras(json.dumps([{"name": "Деталь", "qty": "1", key: value}]), db, actor=actor)
        assert failure.value.status_code == 400


@pytest.mark.parametrize("value", ["1e999", "1e1000000"])
def test_large_financial_input_is_validation_error(value):
    with pytest.raises(ValidationError):
        QuoteManualService(id="service", name="Service", quantity="1", unit="шт.", sale_price=value)
    with pytest.raises(ValidationError):
        QuoteDiscountRule(scope="order", mode="fixed", value=value)
    with pytest.raises(ValidationError):
        StandaloneSaleItem(catalog_item_id=1, quantity=value)


def test_empty_copy_quantity_is_preserved_and_duplicate_ids_rejected(isolated_pricing):
    db, _, actor = isolated_pricing
    rows = [{"id": "copy", "name": "Копия", "qty": "", "unit_price": "10"}]
    assert json.loads(_normalize_project_extras(json.dumps(rows), db, actor=actor))[0]["qty"] == ""
    with pytest.raises(HTTPException):
        _normalize_project_extras(json.dumps(rows * 2), db, actor=actor)
    for quantity in (0, "0", "NaN"):
        rows[0]["qty"] = quantity
        with pytest.raises(HTTPException):
            _normalize_project_extras(json.dumps(rows), db, actor=actor)


def test_manual_article_collision_keeps_entered_price_and_category(isolated_pricing):
    db, project, actor = isolated_pricing
    item = models.CatalogItem(sku="COLLISION", name="Каталог", group="Профили", unit="шт")
    db.add(item)
    db.flush()
    from datetime import datetime
    db.add(models.CatalogPriceVersion(catalog_item_id=item.id, cost=10, category="profile", unit="шт",
                                     effective_from=datetime(2020, 1, 1), created_by=actor.id, reason="Fixture"))
    db.flush()
    project.extra_components = json.dumps([{"sku": "COLLISION", "name": "Ручная", "category": "profile", "qty": "2", "unit_price": "100"}])
    quote = public_quote(db, project)
    assert quote["lines"][0]["line_total"] == "200.00"
    assert quote["lines"][0]["category"] == "profile"


def test_document_export_never_implicitly_fixes_or_reprices(isolated_pricing):
    db, project, actor = isolated_pricing
    with pytest.raises(HTTPException) as failure:
        _document_quote(db, project, require_fixed=True)
    assert failure.value.status_code == 409
    state = get_or_create_quote_state(db, project)
    assert state.status == "draft"
    freeze_quote(db, project, actor)
    original = state.public_payload
    project.extra_components = json.dumps([{"name": "Новая деталь", "qty": "3", "unit_price": "100"}])
    payload = _document_quote(db, project, require_fixed=True)
    assert payload["totals"]["grand_total"] == "21.00"
    assert state.public_payload == original
    refresh_quote_revision(db, project, actor)
    assert _document_quote(db, project, 1, require_fixed=True)["totals"]["grand_total"] == "21.00"
    assert _document_quote(db, project, 2, require_fixed=True)["totals"]["grand_total"] == "300.00"
    with pytest.raises(HTTPException) as missing:
        _document_quote(db, project, 100)
    assert missing.value.status_code == 404


def test_missing_frozen_cost_report_does_not_rebuild_saved_quote(isolated_pricing):
    db, project, actor = isolated_pricing
    freeze_quote(db, project, actor)
    state = get_or_create_quote_state(db, project)
    state.internal_payload = "{}"
    original = state.public_payload
    context = build_cost_report_context(db, project, freeze_for_export=True, actor=actor)
    assert context["incomplete"] is True
    assert context["summary"]["profit"] is None
    assert context["summary"]["client_total"] == Decimal("21")
    assert state.status == "fixed" and state.revision == 1
    assert state.public_payload == original and state.internal_payload == "{}"


def test_cost_report_unknown_is_not_zero_and_zero_cost_is_valid(isolated_pricing):
    db, project, actor = isolated_pricing
    state = get_or_create_quote_state(db, project)
    state.services_payload = json.dumps([{"id": "service", "name": "Монтаж", "quantity": "1",
                                          "unit": "услуга", "sale_price": "100", "actual_cost": "0"}])
    known = build_cost_report_context(db, project, freeze_for_export=True, actor=actor)
    assert state.status == "draft"
    assert known["summary"]["profit"] == Decimal("121")
    assert known["summary"]["markup_percent"] is None
    assert known["summary"]["margin_percent"] == Decimal("100")
    assert build_cost_report_xlsx(known).startswith(b"PK")
    state.services_payload = json.dumps([{"id": "service", "name": "Монтаж", "quantity": "1",
                                          "unit": "услуга", "sale_price": "100", "actual_cost": None}])
    unknown = build_cost_report_context(db, project)
    assert unknown["incomplete"] is True
    assert unknown["summary"]["profit"] is None
    assert unknown["services"][0]["complete"] is False
    assert unknown["services"][0]["cost_text"] == "—"


def test_loss_and_zero_revenue_do_not_hide_profit():
    assert _metrics(Decimal("100"), Decimal("0"), complete=True) == {
        "profit": Decimal("-100"), "markup_percent": Decimal("-100"), "margin_percent": None,
    }
    assert _allocate(Decimal("0.02"), [Decimal("0.01")] * 4) == [Decimal("0.01"), Decimal("0.01"), Decimal("0"), Decimal("0")]


def test_new_document_money_preserves_cents_and_old_money_keeps_whole_rubles(isolated_pricing):
    db, project, actor = isolated_pricing
    payload = freeze_quote(db, project, actor)
    html = render_project_document_html(project, [], "commercial", quote=payload)
    assert "10,40" in html and "20,80" in html and "Округление до рубля" in html
    assert "0,20" in html
    assert _document_money("1525.11") == _rubles("1525.11") == "1 525,11"
    assert _document_money(1525) == _rubles(1525) == "1 525"
