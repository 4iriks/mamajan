"""Isolated rule tests: no production database or shared test fixture writes."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from database import Base, get_db
from engine.pricing_rules import (
    append_binding,
    capture_individual_price,
    resolve_effective_price as current_price,
    price_preview,
)


def resolve_effective_price(*args, **kwargs):
    return current_price(*args, use_legacy_rules=True, **kwargs)


@pytest.fixture
def rule_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = models.User(
            username="rules", display_name="Rules", password_hash="x", role="superadmin"
        )
        db.add(actor)
        db.flush()
        yield db, actor
    engine.dispose()


def item_with_price(db, actor, sku="R1", group="Профили", cost=100, markup=20):
    item = models.CatalogItem(sku=sku, name=sku, group=group, unit="п.м.")
    variant = models.CatalogFinishVariant(
        code="COLORLESS",
        name="Без цвета",
        cost=cost,
        price=cost,
        profile_markup_percent=markup,
    )
    item.finish_variants.append(variant)
    db.add(item)
    db.flush()
    item.price_versions.append(
        models.CatalogPriceVersion(
            finish_variant_id=variant.id,
            cost=cost,
            profile_markup_percent=markup,
            category="profile",
            unit="п.м.",
            effective_from=datetime.utcnow() - timedelta(days=10),
            created_by=actor.id,
            reason="Initial",
        )
    )
    db.commit()
    return item, variant


def add_rule(db, actor, scope="default", group="", markup=40, at=None):
    rule = models.CatalogPricingRule(
        scope=scope,
        group_name=group,
        scope_key="default" if scope == "default" else "group:" + group.casefold(),
    )
    rule.versions.append(
        models.CatalogPricingRuleVersion(
            name="Rule",
            profile_markup_percent=markup,
            construction_markup_percent=50,
            effective_from=at or datetime.utcnow() - timedelta(days=1),
            created_by=actor.id,
            reason="Test",
        )
    )
    db.add(rule)
    db.commit()
    return rule


def test_existing_variants_opt_in_and_group_wins(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    default = add_rule(db, actor, markup=40)
    group = add_rule(db, actor, scope="group", group="Профили", markup=60)
    assert resolve_effective_price(db, item, variant).profile_markup_percent == 20
    now = datetime.utcnow()
    append_binding(db, variant, "auto", actor.id, "Explicit opt-in", now)
    db.commit()
    price = resolve_effective_price(db, item, variant)
    assert price.profile_markup_percent == 60
    assert price.source["rule_id"] == group.id
    assert price.cost == 100
    group.versions.append(
        models.CatalogPricingRuleVersion(
            name="Disabled",
            is_active=False,
            effective_from=now,
            created_by=actor.id,
            reason="Disable",
        )
    )
    db.commit()
    price = resolve_effective_price(db, item, variant)
    assert price.profile_markup_percent == 40
    assert price.source["rule_id"] == default.id


def test_effective_dates_and_individual_snapshot(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    now = datetime.utcnow()
    rule = add_rule(db, actor, markup=40)
    append_binding(db, variant, "auto", actor.id, "Enable", now - timedelta(hours=1))
    rule.versions.append(
        models.CatalogPricingRuleVersion(
            name="Future",
            profile_markup_percent=80,
            effective_from=now + timedelta(days=1),
            created_by=actor.id,
            reason="Future",
        )
    )
    item.price_versions.append(
        models.CatalogPriceVersion(
            finish_variant_id=variant.id,
            cost=200,
            profile_markup_percent=99,
            category="profile",
            unit="п.м.",
            effective_from=now + timedelta(days=1),
            created_by=actor.id,
            reason="Future cost",
        )
    )
    db.commit()
    current = resolve_effective_price(db, item, variant, now)
    assert (current.cost, current.profile_markup_percent) == (100, 40)
    future = resolve_effective_price(db, item, variant, now + timedelta(days=2))
    assert (future.cost, future.profile_markup_percent) == (200, 80)
    # A preview of the scheduled future never contaminates the current result.
    current_again = resolve_effective_price(db, item, variant, now)
    assert (current_again.cost, current_again.profile_markup_percent) == (100, 40)
    assert variant.cost == 100
    capture_individual_price(db, item, variant, current, actor.id, "Individual", now)
    append_binding(db, variant, "individual", actor.id, "Individual", now)
    db.commit()
    assert (
        resolve_effective_price(
            db, item, variant, now + timedelta(seconds=1)
        ).profile_markup_percent
        == 40
    )
    assert (
        resolve_effective_price(db, item, variant, now - timedelta(minutes=1)).source[
            "mode"
        ]
        == "auto"
    )


def test_finish_prices_are_not_taken_from_other_finish_or_mutable_cache(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    second = models.CatalogFinishVariant(
        code="RAL_STANDARD", name="RAL стандарт", cost=999, price=999
    )
    item.finish_variants.append(second)
    db.flush()
    item.price_versions.append(
        models.CatalogPriceVersion(
            finish_variant_id=second.id,
            cost=250,
            category="profile",
            unit="п.м.",
            min_margin_percent=70,
            effective_from=datetime.utcnow() - timedelta(hours=1),
            created_by=actor.id,
            reason="Second finish",
        )
    )
    variant.cost = 777
    db.commit()
    first_price = resolve_effective_price(db, item, variant)
    second_price = resolve_effective_price(db, item, second)
    assert (first_price.cost, first_price.min_margin_percent) == (100, 0)
    assert (second_price.cost, second_price.min_margin_percent) == (250, 70)


def test_baseline_preserves_current_values_and_is_idempotent(rule_db):
    from migrations import _preserve_effective_pricing_baseline_once

    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    item.price_versions.append(
        models.CatalogPriceVersion(
            cost=90,
            profile_markup_percent=90,
            category="profile",
            unit="п.м.",
            min_margin_percent=17,
            effective_from=datetime.utcnow() - timedelta(days=11),
            created_by=actor.id,
            reason="Old generic version",
        )
    )
    scheduled = datetime.utcnow() + timedelta(days=1)
    item.price_versions.append(
        models.CatalogPriceVersion(
            finish_variant_id=variant.id,
            cost=200,
            profile_markup_percent=70,
            category="profile",
            unit="п.м.",
            effective_from=scheduled,
            created_by=actor.id,
            reason="Scheduled exact version",
        )
    )
    variant.cost = 123
    variant.profile_markup_percent = 45
    db.commit()
    conn = db.connection()
    conn.execute(text("CREATE TABLE migration_markers (name TEXT PRIMARY KEY)"))
    _preserve_effective_pricing_baseline_once(conn)
    db.commit()
    db.expire_all()
    price = resolve_effective_price(db, item, variant)
    assert (price.cost, price.profile_markup_percent) == (123, 45)
    assert price.min_margin_percent == 17  # old engine's generic floor is preserved
    future = resolve_effective_price(
        db, item, variant, scheduled + timedelta(seconds=1)
    )
    assert (future.cost, future.profile_markup_percent) == (200, 70)
    count = db.query(models.CatalogPriceVersion).count()
    _preserve_effective_pricing_baseline_once(db.connection())
    assert db.query(models.CatalogPriceVersion).count() == count


def test_timezone_normalization_and_fractional_percent(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor, markup=Decimal("12.3456"))
    price = resolve_effective_price(db, item, variant, datetime.now(timezone.utc))
    assert price_preview(price)["profile"]["final"] == "112.35"


def test_catalog_roundtrip_preserves_materialized_prices_and_independent_edits(rule_db):
    from api.catalog import _item_to_dict, update_hardware_item
    from schemas import CatalogItemUpdate

    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    add_rule(db, actor, markup=45)
    append_binding(db, variant, "auto", actor.id, "Use rule", datetime.utcnow())
    db.commit()
    from engine.construction_pricing import migrate_construction_pricing

    migrate_construction_pricing(db)
    db.commit()
    payload = _item_to_dict(item)
    payload["note"] = "Metadata only"
    assert payload["finishVariants"][0]["profileMarkupPercent"] == 45
    saved = update_hardware_item(item.id, CatalogItemUpdate(**payload), db, actor)
    assert saved["finishVariants"][0]["pricingMode"] == "individual"
    assert current_price(db, item, variant).profile_markup_percent == 45
    saved["finishVariants"][0]["profileMarkupPercent"] = 55
    edited = update_hardware_item(item.id, CatalogItemUpdate(**saved), db, actor)
    assert edited["finishVariants"][0]["pricingMode"] == "individual"
    assert current_price(db, item, variant).profile_markup_percent == 55
    edited["finishVariants"][0]["minimumMarkupPercent"] = "12.5"
    minimum_edited = update_hardware_item(
        item.id, CatalogItemUpdate(**edited), db, actor
    )
    assert minimum_edited["finishVariants"][0]["minimumMarkupPercent"] == 12.5
    assert current_price(db, item, variant).min_margin_percent == Decimal("12.5")


def test_new_price_version_and_rollback_target_finish_and_honor_date(rule_db):
    from api.pricing import (
        FinishPriceVersionCreate,
        create_price_version,
        rollback_price_version,
    )
    from schemas import CatalogPriceRollback

    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    initial = item.price_versions[0]
    future = datetime.utcnow() + timedelta(days=1)
    result = create_price_version(
        item.id,
        FinishPriceVersionCreate(
            finish_variant_id=variant.id,
            cost=200,
            profile_markup_percent=30,
            category="profile",
            unit="п.м.",
            effective_from=future,
            reason="Scheduled price",
        ),
        db,
        actor,
    )
    assert result["finish_variant_id"] == variant.id
    assert resolve_effective_price(db, item, variant).cost == 100
    assert (
        resolve_effective_price(db, item, variant, future + timedelta(seconds=1)).cost
        == 200
    )
    rollback_price_version(
        item.id,
        initial.id,
        CatalogPriceRollback(
            effective_from=future + timedelta(days=1), reason="Rollback"
        ),
        db,
        actor,
    )
    assert (
        resolve_effective_price(db, item, variant, future + timedelta(days=2)).cost
        == 100
    )
    assert resolve_effective_price(db, item, variant).cost == 100


def test_cost_change_preserves_other_finish_cost(rule_db):
    from api.pricing import create_price_version, FinishPriceVersionCreate

    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    second = models.CatalogFinishVariant(
        code="RAL_STANDARD", name="RAL стандарт", cost=250, price=250
    )
    item.finish_variants.append(second)
    db.flush()
    item.price_versions.append(
        models.CatalogPriceVersion(
            finish_variant_id=second.id,
            cost=250,
            category="profile",
            unit="п.м.",
            effective_from=datetime.utcnow() - timedelta(hours=1),
            created_by=actor.id,
            reason="Second finish",
        )
    )
    db.commit()
    create_price_version(
        item.id,
        FinishPriceVersionCreate(
            finish_variant_id=variant.id,
            cost=110,
            category="profile",
            unit="п.м.",
            effective_from=datetime.utcnow(),
            reason="Cost edit",
        ),
        db,
        actor,
    )
    assert current_price(db, item, variant).cost == 110
    assert current_price(db, item, second).cost == 250


def test_system_pricing_api_denies_non_price_manager(rule_db):
    from api.construction_pricing import router
    from auth import get_current_user

    db, actor = rule_db
    actor.role = "user"
    actor.can_manage_prices = False
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app) as client:
        assert client.get("/api/construction-pricing/systems").status_code == 403
        assert client.get("/api/construction-pricing/systems/CS").status_code == 403


def test_fresh_install_baseline_does_not_run_late_after_prices_are_entered():
    from migrations import _preserve_effective_pricing_baseline_once

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE migration_markers (name TEXT PRIMARY KEY)"))
        _preserve_effective_pricing_baseline_once(conn)
        assert (
            conn.execute(text("SELECT COUNT(*) FROM migration_markers")).scalar() == 1
        )
        assert (
            conn.execute(text("SELECT COUNT(*) FROM catalog_price_versions")).scalar()
            == 0
        )
    engine.dispose()


def test_cost_only_import_preserves_coefficients_and_inheritance(rule_db):
    from api.pricing import _import_version_payload

    db, actor = rule_db
    item, variant = item_with_price(db, actor, markup=35)
    payload = _import_version_payload(
        item,
        {
            "profile_markup_percent": "",
            "profile_discount_percent": "",
            "construction_markup_percent": "",
            "min_margin_percent": "",
        },
        Decimal("125"),
        variant,
        "Cost only",
    )
    assert payload.cost == 125
    assert payload.profile_markup_percent == 35
    assert payload.profile_discount_percent == 0
