"""Money and frozen-edition regressions; isolated in-memory DB, no live data."""

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from database import Base
from engine.quote_pricing import (
    _allocate_money,
    _apply_quote_discount_rules,
    _prepare_money_presentation,
    _public_line,
    calculate_quote,
    decimal_value,
    freeze_quote,
    get_or_create_quote_state,
    internal_quote_state,
    public_quote,
    quote_revision_list,
    quote_revision_snapshot,
    refresh_quote_revision,
    safe_public_payload,
    _section_requirements,
    calculate_standalone_sale,
)
from schemas import (
    QuoteConfigUpdate,
    QuoteDiscountRule,
    QuoteManualService,
    StandaloneSaleItem,
)
from api.quotes import update_quote_config


TERMS = {
    name: Decimal("0")
    for name in (
        "dealer_markup_percent",
        "profile_discount_percent",
        "construction_discount_percent",
        "component_discount_percent",
        "service_discount_percent",
    )
}


def make_line(amount, quantity="1", category="component", line_id="test"):
    return _public_line(
        line_id=line_id,
        name="Позиция",
        category=category,
        quantity=Decimal(quantity),
        unit="м",
        internal_total=Decimal(amount),
        terms=TERMS,
    )


def test_cents_survive_sanitizer_and_rounding_is_separate():
    lines = [
        make_line(amount, line_id=str(i))[0]
        for i, amount in enumerate(("10.40", "20.40", "30.40"))
    ]
    totals = _prepare_money_presentation(lines)
    payload = {
        "money_presentation_version": 2,
        "lines": lines,
        "totals": totals,
        "export_allowed": True,
    }
    safe = safe_public_payload(payload)
    assert [row["document_line_total"] for row in safe["lines"]] == [
        "10.40",
        "20.40",
        "30.40",
    ]
    assert safe["totals"]["subtotal"] == "61.20"
    assert safe["totals"]["rounding_adjustment"] == "-0.20"
    assert safe["totals"]["grand_total"] == "61.00"
    assert safe_public_payload(safe) == safe


def test_fractional_quantity_uses_real_divisor():
    lines = [make_line("100", "0.5")[0]]
    totals = _prepare_money_presentation(lines)
    safe = safe_public_payload(
        {"money_presentation_version": 2, "lines": lines, "totals": totals}
    )
    assert safe["lines"][0]["document_unit_final_price"] == "200.00"


def test_tiny_fixed_discount_has_exact_bounded_cent_allocation():
    pairs = [make_line("0.01", line_id=str(i)) for i in range(4)]
    lines, exact = [p[0] for p in pairs], [p[1] for p in pairs]
    _apply_quote_discount_rules(
        lines, exact, [{"scope": "order", "mode": "fixed", "value": "0.02"}]
    )
    assert sum((row["total"] for row in exact), Decimal(0)) == Decimal("0.02")
    assert all(Decimal(0) <= row["total"] <= Decimal("0.01") for row in exact)
    assert _allocate_money([Decimal("0.01")] * 4, Decimal("0.02")) == [
        Decimal("0.01"),
        Decimal("0.01"),
        Decimal(0),
        Decimal(0),
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_discount_stages_ignore_entry_order_and_keep_additional_rules(reverse):
    line, exact = make_line("10000", category="construction")
    rules = [
        {"id": "rub", "scope": "order", "mode": "fixed", "value": "1000"},
        {"id": "pct", "scope": "order", "mode": "percent", "value": "10"},
        {"id": "category", "scope": "construction", "mode": "percent", "value": "10"},
        {"id": "extra", "scope": "construction", "mode": "percent", "value": "10"},
    ]
    _apply_quote_discount_rules(
        [line], [exact], list(reversed(rules)) if reverse else rules
    )
    assert line["line_total"] == "6290.00"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_financial_inputs_rejected(value):
    with pytest.raises(ValidationError):
        QuoteDiscountRule(scope="order", mode="fixed", value=value)
    with pytest.raises(ValidationError):
        StandaloneSaleItem(catalog_item_id=1, quantity=value)
    with pytest.raises(ValidationError):
        QuoteManualService(
            id="s", name="Услуга", quantity="1", unit="шт.", sale_price=value
        )
    assert decimal_value(value) == Decimal(0)


@pytest.fixture
def quote_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = models.User(
            username="review",
            password_hash="test",
            display_name="Менеджер",
            role="admin",
            is_active=True,
        )
        db.add(actor)
        db.flush()
        project = models.Project(
            number="Money",
            customer="Клиент",
            created_by=actor.id,
            extra_components=json.dumps(
                [
                    {
                        "id": "m",
                        "name": "Ручная позиция",
                        "qty": "1",
                        "unit": "шт",
                        "unit_price": "150",
                        "actual_cost": "80",
                    }
                ]
            ),
        )
        db.add(project)
        db.flush()
        yield db, project, actor
    engine.dispose()


def test_frozen_revision_history_is_immutable(quote_db):
    db, project, actor = quote_db
    first = freeze_quote(db, project, actor)
    assert first["totals"]["grand_total"] == "150.00"
    state = get_or_create_quote_state(db, project)
    original = state.public_payload
    project.extra_components = json.dumps(
        [
            {
                "name": "Ручная позиция",
                "qty": "2",
                "unit": "шт",
                "unit_price": "150",
                "actual_cost": "80",
            }
        ]
    )
    project.updated_at = datetime.utcnow()
    assert public_quote(db, project)["totals"]["grand_total"] == "150.00"
    assert state.public_payload == original
    refreshed = refresh_quote_revision(db, project, actor)
    assert refreshed["revision"] == 2
    assert refreshed["totals"]["grand_total"] == "300.00"
    assert (
        quote_revision_snapshot(db, project, 1)[0]["totals"]["grand_total"] == "150.00"
    )
    assert [row["revision"] for row in quote_revision_list(db, project)] == [2, 1]
    assert (
        db.query(models.ProjectQuoteRevision)
        .filter_by(project_id=project.id, revision=1)
        .one()
        .public_payload
        == original
    )


def test_missing_private_snapshot_does_not_unfreeze_quote(quote_db):
    db, project, actor = quote_db
    freeze_quote(db, project, actor)
    state = get_or_create_quote_state(db, project)
    original = state.public_payload
    state.internal_payload = "{}"
    result = internal_quote_state(db, project)
    assert result["status"] == "fixed"
    assert state.status == "fixed" and state.revision == 1
    assert state.public_payload == original


def test_legacy_frozen_money_keeps_historical_rendering(quote_db):
    db, project, actor = quote_db
    state = get_or_create_quote_state(db, project)
    legacy = {
        "lines": [
            {
                "id": str(i),
                "quantity": "1",
                "line_total_before_discount": value,
                "line_total": value,
            }
            for i, value in enumerate(("10.40", "20.40", "30.40"))
        ],
        "totals": {"subtotal": "61.20", "grand_total": "61.20"},
        "export_allowed": True,
    }
    state.status, state.revision, state.fixed_at, state.fixed_by = (
        "fixed",
        4,
        datetime.utcnow(),
        actor.id,
    )
    state.public_payload = json.dumps(legacy)
    expected = safe_public_payload(legacy)
    actual = public_quote(db, project)
    assert actual["totals"] == expected["totals"]
    assert actual["lines"] == expected["lines"]
    assert json.loads(state.public_payload) == legacy


@pytest.mark.parametrize("quantity", ["", "0", "-1", "NaN", "Infinity"])
def test_incomplete_extra_quantity_blocks_quote(quote_db, quantity):
    db, project, _ = quote_db
    project.extra_components = json.dumps(
        [{"name": "Копия", "qty": quantity, "unit_price": "150", "unit": "шт"}]
    )
    state = get_or_create_quote_state(db, project)
    public, _, _ = calculate_quote(db, project, state)
    assert not public["export_allowed"]
    assert any(
        issue["code"] == "invalid_extra_quantity" for issue in public["pricing_issues"]
    )


def test_service_sale_price_is_not_assumed_actual_cost(quote_db):
    db, project, _ = quote_db
    state = get_or_create_quote_state(db, project)
    state.services_payload = json.dumps(
        [
            {
                "id": "service",
                "name": "Монтаж",
                "quantity": "2",
                "unit": "шт.",
                "base_cost": "100",
            }
        ]
    )
    state.discounts_payload = json.dumps(
        [{"scope": "service", "mode": "percent", "value": "10"}]
    )
    public, internal, _ = calculate_quote(db, project, state)
    service = internal["services"][0]
    assert service["actual_cost"] is None and not service["cost_known"]
    assert service["final_price"] == "180.00"
    assert service["after_dealer_terms"] == "200.00"
    assert service["order_discount_amount"] == "20.00"
    assert internal["cost_warnings"]
    assert public["export_allowed"]


def catalog_price(
    db,
    actor,
    *,
    sku="PROFILE",
    unit="п.м.",
    category="profile",
    cost="200",
    minimum="0",
):
    item = models.CatalogItem(
        sku=sku,
        name=sku,
        group="Профили" if category == "profile" else "Фурнитура",
        unit=unit,
        is_active=True,
    )
    db.add(item)
    db.flush()
    version = models.CatalogPriceVersion(
        catalog_item_id=item.id,
        cost=Decimal(cost),
        profile_markup_percent=35,
        construction_markup_percent=0,
        category=category,
        unit=unit,
        min_margin_percent=Decimal(minimum),
        effective_from=datetime.utcnow() - timedelta(days=1),
        created_by=actor.id,
        reason="regression",
    )
    db.add(version)
    db.flush()
    return item


@pytest.mark.parametrize(
    "unit,category,total,billed",
    [("п.м.", "profile", "1620.00", "6"), ("шт", "component", "540.00", "2")],
)
def test_extra_length_conversion_uses_price_unit_and_preserves_piece_count(
    quote_db, unit, category, total, billed
):
    db, project, actor = quote_db
    item = catalog_price(db, actor, unit=unit, category=category)
    project.extra_components = json.dumps(
        [
            {
                "catalog_item_id": item.id,
                "qty": "2",
                "size": "3000",
                "unit": "шт",
                "unit_price": "1",
            }
        ]
    )
    public, internal, _ = calculate_quote(
        db, project, get_or_create_quote_state(db, project)
    )
    row = public["lines"][0]
    assert row["line_total"] == total and row["quantity"] == "2"
    assert row["unit"] == "шт"
    detail = internal["project_extras"][0]
    assert detail["pricing_quantity"] == billed
    assert Decimal(detail["cost"]) * Decimal(detail["quantity"]) == Decimal(
        detail["base_cost_total"]
    )
    assert detail["final_price"] == total
    sale = calculate_standalone_sale(
        db, [StandaloneSaleItem(catalog_item_id=item.id, quantity=billed)]
    )
    assert sale["totals"]["grand_total"] == total


def test_future_catalog_version_not_used_until_effective(quote_db):
    db, project, actor = quote_db
    item = catalog_price(db, actor)
    db.add(
        models.CatalogPriceVersion(
            catalog_item_id=item.id,
            cost=900,
            profile_markup_percent=35,
            category="profile",
            unit="п.м.",
            min_margin_percent=0,
            effective_from=datetime.utcnow() + timedelta(days=1),
            created_by=actor.id,
            reason="future",
        )
    )
    db.flush()
    project.extra_components = json.dumps(
        [{"catalog_item_id": item.id, "qty": "2", "size": "3000", "unit": "шт"}]
    )
    state = get_or_create_quote_state(db, project)
    current = calculate_quote(db, project, state)[0]
    future = calculate_quote(
        db, project, state, at=datetime.utcnow() + timedelta(days=2)
    )[0]
    assert current["lines"][0]["line_total"] == "1620.00"
    assert future["lines"][0]["line_total"] == "7290.00"


def test_dealer_markup_is_included_in_bom_floor_and_final_trace(quote_db):
    db, project, actor = quote_db
    actor.role = "dealer"
    db.add(
        models.DealerPricingTerms(
            user_id=actor.id, dealer_markup_percent=100, updated_by=actor.id
        )
    )
    project.extra_components = "[]"
    section = models.Section(
        project_id=project.id,
        name="Секция",
        system="СЛАЙД",
        width=2000,
        height=2400,
        panels=3,
        quantity=1,
        rails=3,
    )
    db.add(section)
    db.flush()
    for requirement in {
        row["sku"]: row for row in _section_requirements(section)[1]
    }.values():
        catalog_price(
            db,
            actor,
            sku=requirement["sku"],
            unit=requirement["unit"],
            category=requirement["category"],
            cost="10",
            minimum="50",
        )
    db.add(models.SystemPricingScope(code="SLIDE_1", revision=1))
    for item in db.query(models.CatalogItem).all():
        db.add(
            models.SystemComponentPriceVersion(
                system_code="SLIDE_1",
                catalog_item_id=item.id,
                waste_percent=0,
                markup_percent=0,
                discount_percent=0,
                effective_from=datetime.utcnow(),
                created_by=actor.id,
                reason="Quote test setup",
            )
        )
    db.flush()
    state = get_or_create_quote_state(db, project)
    public, internal, _ = calculate_quote(db, project, state)
    assert public["export_allowed"], internal["issues"]
    assert not any(
        issue["code"] == "below_minimum_margin" for issue in internal["issues"]
    )
    state.discounts_payload = json.dumps(
        [{"scope": "order", "mode": "percent", "value": "60"}]
    )
    public, internal, _ = calculate_quote(db, project, state)
    assert not public["export_allowed"]
    row = internal["sections"][0]
    assert row["final_price"] == public["lines"][0]["line_total"]
    assert sum(
        (Decimal(item["client_total"]) for item in row["bom"]), Decimal(0)
    ) == Decimal(row["final_price"])


def test_service_known_cost_preserved_for_legacy_client_and_private_for_regular_user(
    quote_db,
):
    db, project, actor = quote_db
    state = get_or_create_quote_state(db, project)
    state.services_payload = json.dumps(
        [
            {
                "id": "service",
                "name": "Монтаж",
                "quantity": "1",
                "unit": "шт.",
                "sale_price": "100",
                "actual_cost": "30",
            }
        ]
    )
    payload = QuoteConfigUpdate(
        services=[
            {
                "id": "service",
                "name": "Монтаж",
                "quantity": "1",
                "unit": "шт.",
                "base_cost": "120",
            }
        ]
    )
    update_quote_config(project.id, payload, db, actor)
    assert json.loads(state.services_payload)[0]["actual_cost"] == "30"
    actor.role, actor.can_manage_prices = "user", False
    payload.services[0].sale_price = Decimal("140")
    update_quote_config(project.id, payload, db, actor)
    assert json.loads(state.services_payload)[0]["actual_cost"] == "30"


def test_duplicate_or_blank_service_ids_rejected():
    service = {
        "id": "same",
        "name": "Монтаж",
        "quantity": "1",
        "unit": "шт.",
        "sale_price": "100",
    }
    with pytest.raises(ValidationError):
        QuoteConfigUpdate(services=[service, service])
    with pytest.raises(ValidationError):
        QuoteManualService(**{**service, "id": " "})
