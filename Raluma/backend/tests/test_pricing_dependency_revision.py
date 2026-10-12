"""Pricing dependency / override regressions, using isolated in-memory data."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from database import Base
from engine.pricing_rules import append_binding
from engine.quote_pricing import (
    _price_requirement,
    approve_margin_override,
    calculate_quote,
    current_quote_preview_token,
    freeze_quote,
    get_or_create_quote_state,
    public_quote,
    quote_is_stale,
    refresh_quote_revision,
)


NOW = datetime(2026, 10, 13, 10)


@pytest.fixture
def dependency_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = models.User(
            username="dependency", password_hash="x", display_name="Admin", role="admin"
        )
        db.add(actor)
        db.flush()
        yield db, actor
    engine.dispose()


def add_item(db, actor, *, sku="TEST", generic=True, cost=100, minimum=0):
    item = models.CatalogItem(
        sku=sku, name=sku, group="Профили", unit="шт", system_groups='["SLIDE_1"]'
    )
    variant = models.CatalogFinishVariant(
        code="COLORLESS",
        name="Без цвета",
        cost=cost,
        price=cost,
        profile_markup_percent=50,
        construction_markup_percent=30,
    )
    item.finish_variants.append(variant)
    db.add(item)
    db.flush()
    for finish_id in [None, variant.id] if generic else [variant.id]:
        add_price(
            item,
            actor,
            finish_id,
            cost=cost,
            minimum=minimum,
            at=NOW - timedelta(days=2),
        )
    db.flush()
    return item, variant


def add_price(item, actor, finish_id, *, cost=100, minimum=0, at=NOW):
    row = models.CatalogPriceVersion(
        finish_variant_id=finish_id,
        cost=cost,
        profile_markup_percent=50,
        construction_markup_percent=30,
        category="component",
        unit="шт",
        min_margin_percent=minimum,
        effective_from=at,
        created_by=actor.id,
        reason="Test",
    )
    item.price_versions.append(row)
    return row


def add_project(db, actor, item=None, variant=None):
    extra = {
        "name": "Manual",
        "qty": "1",
        "unit": "шт",
        "unit_price": "150",
        "actual_cost": "80",
    }
    if item is not None:
        extra = {
            "catalog_item_id": item.id,
            "finish_variant_id": variant.id,
            "qty": "1",
            "unit": "шт",
        }
    project = models.Project(
        number="Test",
        customer="Demo",
        created_by=actor.id,
        extra_components=json.dumps([extra]),
    )
    db.add(project)
    db.flush()
    return project


def add_rule(db, actor, *, group="Unused", markup=70, at=NOW - timedelta(days=1)):
    rule = models.CatalogPricingRule(
        scope="group", group_name=group, scope_key="group:" + group.casefold()
    )
    rule.versions.append(
        models.CatalogPricingRuleVersion(
            name="Rule",
            profile_markup_percent=markup,
            construction_markup_percent=30,
            effective_from=at,
            created_by=actor.id,
            reason="Test",
        )
    )
    db.add(rule)
    db.flush()
    return rule


def required():
    return {
        "sku": "TEST",
        "name": "Test",
        "category": "component",
        "unit": "шт",
        "quantity": Decimal(2),
        "source": "component",
    }


def test_sale_override_preserves_known_purchase_cost_and_minimum():
    version = SimpleNamespace(
        id=1,
        cost=Decimal(1000),
        unit="шт",
        category="component",
        profile_markup_percent=50,
        profile_discount_percent=0,
        waste_markup_percent=4,
        construction_markup_percent=30,
        construction_discount_percent=0,
        min_margin_percent=20,
    )
    item = SimpleNamespace(finish_variants=[], weight=0)
    row, issue = _price_requirement(
        required(),
        {"TEST": (item, version)},
        {"TEST": {"cost": "100", "comment": "Agreed sale"}},
        mode="construction",
    )
    assert issue is None
    assert row["cost"] == "1000.00" and row["cost_known"] is True
    assert row["base_cost_total"] == "2000.00"
    assert row["minimum_total"] == "2400.00" and row["min_margin_percent"] == "20"
    assert row["internal_total"] == "200.00" and row["sale_price_override"] == "100.00"
    assert row["price_stages"]["construction"]["after_markup"] == "2704.00"


def test_sale_override_with_no_catalog_cost_stays_unknown():
    row, issue = _price_requirement(
        required(), {}, {"TEST": {"cost": "100"}}, mode="construction"
    )
    assert issue is None
    assert row["cost_known"] is False and row["cost"] == "0.00"
    assert row["minimum_total"] == "0.00" and row["internal_total"] == "200.00"


def test_sale_override_cannot_compare_floor_in_a_different_unit():
    item = SimpleNamespace(finish_variants=[])
    version = SimpleNamespace(cost=Decimal(100), unit="п.м.")
    row, issue = _price_requirement(
        required(),
        {"TEST": (item, version)},
        {"TEST": {"cost": "100"}},
        mode="construction",
    )
    assert row is None and issue["code"] == "unit_mismatch"


def test_override_missing_finish_does_not_use_another_finish_cost(dependency_db):
    db, actor = dependency_db
    item, variant = add_item(db, actor)
    variant.name = "RAL стандарт"
    db.flush()
    request = {**required(), "finish": "Сублимация"}
    row, issue = _price_requirement(
        request,
        {"TEST": (item, item.price_versions[0])},
        {"TEST": {"cost": "100"}},
        mode="construction",
        db=db,
        at=NOW,
    )
    assert issue is None and row["cost_known"] is False
    assert row["cost"] == "0.00" and row["price_version_id"] is None


@pytest.mark.parametrize("generic", [False, True])
def test_scheduled_finish_price_invalidates_quote_without_mutating_snapshot(
    dependency_db, generic
):
    db, actor = dependency_db
    item, variant = add_item(db, actor, generic=generic)
    add_price(item, actor, variant.id, cost=200, at=NOW + timedelta(days=1))
    project = add_project(db, actor, item, variant)
    first = freeze_quote(db, project, actor, at=NOW)
    state = get_or_create_quote_state(db, project)
    original = state.public_payload
    after = NOW + timedelta(days=2)
    assert first["totals"]["grand_total"] == "150.00"
    assert quote_is_stale(db, project, state, at=after)
    assert public_quote(db, project, at=after)["totals"]["grand_total"] == "150.00"
    assert state.public_payload == original
    result = refresh_quote_revision(db, project, actor, at=after)
    assert result["totals"]["grand_total"] == "300.00" and result["revision"] == 2
    saved = (
        db.query(models.ProjectQuoteRevision)
        .filter_by(project_id=project.id, revision=1)
        .one()
    )
    assert saved.public_payload == original


@pytest.mark.parametrize("linked", [False, True])
def test_unrelated_catalog_rule_binding_and_cache_do_not_stale_quote(
    dependency_db, linked
):
    db, actor = dependency_db
    item, variant = add_item(db, actor)
    project = add_project(
        db, actor, item if linked else None, variant if linked else None
    )
    freeze_quote(db, project, actor, at=NOW)
    state = get_or_create_quote_state(db, project)
    token = current_quote_preview_token(db, project, at=NOW)
    unrelated, unrelated_finish = add_item(db, actor, sku="OTHER")
    add_rule(db, actor)
    append_binding(db, unrelated_finish, "auto", actor.id, "Test", NOW)
    add_price(unrelated, actor, unrelated_finish.id, cost=300, at=NOW)
    # Cache refresh and metadata changes are not changes to effective prices.
    variant.price = variant.cost = 999
    item.updated_at = NOW + timedelta(seconds=1)
    db.flush()
    assert not quote_is_stale(db, project, state, at=NOW)
    assert current_quote_preview_token(db, project, at=NOW) == token


def test_unselected_finish_activation_does_not_stale_quote(dependency_db):
    db, actor = dependency_db
    item, variant = add_item(db, actor, generic=False)
    second = models.CatalogFinishVariant(
        code="OTHER", name="Other", cost=300, price=300
    )
    item.finish_variants.append(second)
    db.flush()
    add_price(item, actor, second.id, cost=300, at=NOW + timedelta(days=1))
    project = add_project(db, actor, item, variant)
    freeze_quote(db, project, actor, at=NOW)
    assert not quote_is_stale(
        db, project, get_or_create_quote_state(db, project), at=NOW + timedelta(days=2)
    )


def test_used_rule_scheduled_activation_changes_quote(dependency_db):
    db, actor = dependency_db
    item, variant = add_item(db, actor)
    rule = add_rule(db, actor, group=item.group, markup=50)
    append_binding(db, variant, "auto", actor.id, "Test", NOW - timedelta(days=1))
    rule.versions.append(
        models.CatalogPricingRuleVersion(
            name="Tomorrow",
            profile_markup_percent=80,
            effective_from=NOW + timedelta(days=1),
            created_by=actor.id,
            reason="Test",
        )
    )
    project = add_project(db, actor, item, variant)
    freeze_quote(db, project, actor, at=NOW)
    state = get_or_create_quote_state(db, project)
    assert not quote_is_stale(db, project, state, at=NOW + timedelta(hours=1))
    assert quote_is_stale(db, project, state, at=NOW + timedelta(days=2))


def section_project(db, actor, monkeypatch):
    project = models.Project(
        number="Test", customer="Demo", created_by=actor.id, extra_components="[]"
    )
    project.sections.append(
        models.Section(
            name="Section",
            system="СЛАЙД",
            width=2000,
            height=2400,
            panels=3,
            quantity=1,
            order=1,
        )
    )
    db.add(project)
    db.flush()
    monkeypatch.setattr(
        "engine.quote_pricing._section_requirements",
        lambda section: (SimpleNamespace(), [required()]),
    )
    monkeypatch.setattr(
        "engine.quote_pricing._section_snapshot",
        lambda section, calc: {"glass_supplied": False},
    )
    return project


def test_override_floor_requires_approval_and_unrelated_changes_preserve_it(
    dependency_db, monkeypatch
):
    db, actor = dependency_db
    item, variant = add_item(db, actor, cost=1000, minimum=20)
    project = section_project(db, actor, monkeypatch)
    state = get_or_create_quote_state(db, project)
    state.overrides_payload = json.dumps(
        [{"sku": "TEST", "cost": "100", "comment": "Low sale"}]
    )
    public, internal, _ = calculate_quote(db, project, state, at=NOW)
    assert not public["export_allowed"]
    assert internal["sections"][0]["bom"][0]["cost"] == "1000.00"
    assert (
        internal["margin_approval"]["required"]
        and not internal["margin_approval"]["valid"]
    )
    assert approve_margin_override(db, project, state, actor, "Approved", at=NOW)[
        "valid"
    ]
    freeze_quote(db, project, actor, at=NOW)
    add_rule(db, actor)
    assert not quote_is_stale(db, project, state, at=NOW)
    assert calculate_quote(db, project, state, at=NOW)[1]["margin_approval"]["valid"]
    add_price(
        item, actor, variant.id, cost=1100, minimum=20, at=NOW + timedelta(days=1)
    )
    public, internal, _ = calculate_quote(
        db, project, state, at=NOW + timedelta(days=2)
    )
    assert not public["export_allowed"] and not internal["margin_approval"]["valid"]


def test_unknown_override_cost_report_does_not_invent_profit(
    dependency_db, monkeypatch
):
    from engine.cost_report import build_cost_report_context

    db, actor = dependency_db
    project = section_project(db, actor, monkeypatch)
    state = get_or_create_quote_state(db, project)
    state.overrides_payload = json.dumps(
        [{"sku": "TEST", "cost": "100", "comment": "Missing catalog"}]
    )
    public, internal, _ = calculate_quote(db, project, state, at=NOW)
    assert public["export_allowed"]
    assert internal["cost_warnings"][0]["code"] == "unknown_actual_cost"
    freeze_quote(db, project, actor, at=NOW)
    report = build_cost_report_context(db, project)
    assert report["summary"]["profit"] is None
    assert not report["summary"]["complete"]


def test_preview_token_covers_private_floor_date_and_revision(dependency_db):
    db, actor = dependency_db
    item, variant = add_item(db, actor)
    project = add_project(db, actor, item, variant)
    before = current_quote_preview_token(db, project, at=NOW)
    add_price(item, actor, variant.id, minimum=10, at=NOW)
    db.flush()
    floor_changed = current_quote_preview_token(db, project, at=NOW)
    assert before != floor_changed
    freeze_quote(db, project, actor, at=NOW)
    fixed = current_quote_preview_token(db, project, at=NOW)
    assert fixed != floor_changed
    assert fixed != current_quote_preview_token(db, project, at=NOW + timedelta(days=1))


def test_preview_token_keeps_precision_of_sale_override(dependency_db, monkeypatch):
    db, actor = dependency_db
    project = section_project(db, actor, monkeypatch)
    state = get_or_create_quote_state(db, project)
    state.overrides_payload = json.dumps(
        [{"sku": "TEST", "cost": "1.231", "comment": "Test"}]
    )
    before = current_quote_preview_token(db, project, at=NOW)
    state.overrides_payload = json.dumps(
        [{"sku": "TEST", "cost": "1.234", "comment": "Test"}]
    )
    assert before != current_quote_preview_token(db, project, at=NOW)


def test_system_bulk_markup_affects_only_used_item_versions(dependency_db, monkeypatch):
    from api.pricing import _apply_group_markup_to_catalog

    monkeypatch.setattr("api.pricing.datetime", SimpleNamespace(utcnow=lambda: NOW))
    db, actor = dependency_db
    item, variant = add_item(db, actor)
    project = add_project(db, actor, item, variant)
    group = models.ConstructionPriceGroup(
        code="SLIDE_1", name="Slide", markup_percent=30
    )
    db.add(group)
    db.flush()
    freeze_quote(db, project, actor, at=NOW)
    state = get_or_create_quote_state(db, project)
    group.name = "Label only"
    group.updated_at = NOW
    db.flush()
    assert not quote_is_stale(db, project, state, at=NOW)
    group.markup_percent = 40
    _apply_group_markup_to_catalog(db, group, actor)
    db.flush()
    # System bulk writes a new actual price version, not a hidden multiplier.
    assert quote_is_stale(db, project, state, at=NOW)


def test_old_fixed_signature_keeps_payload_immutable(dependency_db):
    db, actor = dependency_db
    project = add_project(db, actor)
    freeze_quote(db, project, actor, at=NOW)
    state = get_or_create_quote_state(db, project)
    original = state.public_payload
    state.source_signature = "old-algorithm-signature"
    result = public_quote(db, project, at=NOW)
    assert result["stale"] and result["totals"]["grand_total"] == "150.00"
    assert state.public_payload == original and state.revision == 1
