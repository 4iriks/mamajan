"""Mass-edit previews disclose the same inheritance change that apply performs."""
from datetime import datetime, timedelta
from decimal import Decimal

from api.catalog import apply_catalog_pricing_bulk, preview_catalog_pricing_bulk
from api.pricing_rules import _rule_dict
from engine.pricing_rules import append_binding, binding_mode, resolve_effective_price
import models
from schemas import CatalogPricingBulkRequest
from tests.test_pricing_rules import add_rule, item_with_price, rule_db as rule_db


def test_bulk_preview_discloses_detaching_rule_and_preserves_other_coefficients(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    add_rule(db, actor, markup=40)
    append_binding(db, variant, "auto", actor.id, "Use ready rule", datetime.utcnow())
    db.commit()
    request = CatalogPricingBulkRequest(
        item_ids=[item.id], finish_codes=["COLORLESS"], profile_markup_percent=45,
        reason="Individual exception",
    )
    preview = preview_catalog_pricing_bulk(request, db, actor)
    row = preview["rows"][0]
    assert row["sourceBefore"]["mode"] == "auto"
    assert row["sourceBefore"]["label"].startswith("Общее правило")
    assert row["sourceAfter"]["mode"] == "individual"
    assert row["before"]["profile"]["final"] == "140.00"
    assert row["after"]["profile"]["final"] == "145.00"
    assert binding_mode(db, variant, datetime.utcnow()) == "auto", "preview is read-only"
    applied = apply_catalog_pricing_bulk(request, db, actor)
    assert applied["rows"] == preview["rows"]
    price = resolve_effective_price(db, item, variant)
    assert price.source["mode"] == "individual"
    assert price.profile_markup_percent == Decimal("45")
    assert price.construction_markup_percent == Decimal("50"), "untouched coefficients keep their effective values"


def test_bulk_individual_preview_does_not_claim_a_rule_source(rule_db):
    db, actor = rule_db
    item, _ = item_with_price(db, actor)
    preview = preview_catalog_pricing_bulk(CatalogPricingBulkRequest(
        item_ids=[item.id], finish_codes=["COLORLESS"], waste_markup_percent=4,
        reason="Waste correction",
    ), db, actor)
    assert preview["rows"][0]["sourceBefore"]["mode"] == "individual"
    assert preview["rows"][0]["sourceAfter"]["mode"] == "individual"


def test_next_rule_version_shows_the_winner_for_the_same_future_timestamp(rule_db):
    db, actor = rule_db
    item, variant = item_with_price(db, actor)
    rule = add_rule(db, actor, markup=40)
    now = datetime.utcnow()
    future = now + timedelta(days=1)
    append_binding(db, variant, "auto", actor.id, "Use ready rule", now)
    for markup in (50, 60):
        rule.versions.append(models.CatalogPricingRuleVersion(
            name=f"Scheduled {markup}", profile_markup_percent=markup,
            effective_from=future, created_by=actor.id, reason="Future correction",
        ))
    db.commit()
    listed = _rule_dict(rule, now)
    assert listed["active_version"]["profile_markup_percent"] == "40"
    assert listed["next_version"]["profile_markup_percent"] == "60"
    assert listed["next_version"]["id"] == resolve_effective_price(db, item, variant, future).source["rule_version_id"]
