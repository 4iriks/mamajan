"""Verify migration on a SQLite backup; never writes to the source database.

Usage: python scripts/verify-construction-pricing-migration.py SOURCE.db NEW_COPY.db
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime

source, target = (Path(value).resolve() for value in sys.argv[1:3])
if source == target or target.exists():
    raise SystemExit("Destination must be a new, separate file")
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(target) as backup:
    original.backup(backup)
os.environ["DATABASE_URL"] = "sqlite:///" + target.as_posix()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import models
from database import Base, engine, SessionLocal
from migrations import run_migrations
from main import seed_superadmin
from api.catalog import _ensure_catalog_seed
from engine.pricing_rules import resolve_effective_price, PERCENT_FIELDS
from engine.construction_pricing import migrate_construction_pricing, current_components, component_key

Base.metadata.create_all(engine)
run_migrations()
seed_superadmin()
now = datetime.utcnow()
with SessionLocal() as db:
    _ensure_catalog_seed(db)
    db.commit()
    dates = [now] + sorted({row.effective_from for cls in (models.CatalogPriceVersion,
        models.CatalogPricingRuleVersion, models.CatalogPricingBindingVersion)
        for row in db.query(cls).all() if row.effective_from > now})
    snapshots = {row.id: (row.public_payload, row.internal_payload) for row in db.query(models.ProjectQuoteState).all()}
    before = {}
    for item in db.query(models.CatalogItem).all():
        variants = list(item.finish_variants) or [None]
        for finish in variants:
            for at in dates:
                price = resolve_effective_price(db, item, finish, at, use_legacy_rules=True)
                if price:
                    before[item.id, finish.id if finish else None, at] = (price.cost, *(getattr(price, f) for f in PERCENT_FIELDS))
    assert migrate_construction_pricing(db, at=now), "Copy has already been migrated"
    db.commit()
    construction_count = 0
    for (item_id, finish_id, at), expected in before.items():
        item = db.get(models.CatalogItem, item_id)
        finish = db.get(models.CatalogFinishVariant, finish_id) if finish_id else None
        actual = resolve_effective_price(db, item, finish, at)
        assert (actual.cost, *(getattr(actual, f) for f in PERCENT_FIELDS)) == expected, (item.sku, finish_id, at)
        for code in ("SLIDE_1", "SLIDE_2", "CS"):
            setting = current_components(db, code, at).get(component_key(item_id, finish_id))
            if setting:
                assert (setting.waste_percent, setting.markup_percent, setting.discount_percent) == expected[3:]
                construction_count += 1
    assert snapshots == {row.id: (row.public_payload, row.internal_payload) for row in db.query(models.ProjectQuoteState).all()}
    counts = [db.query(cls).count() for cls in (models.CatalogPriceVersion, models.SystemComponentPriceVersion)]
    assert not migrate_construction_pricing(db)
    assert counts == [db.query(cls).count() for cls in (models.CatalogPriceVersion, models.SystemComponentPriceVersion)]
    report = {"source_untouched": str(source), "verified_copy": str(target), "catalog_prices": len(before),
              "system_prices": construction_count, "effective_dates": len(dates), "fixed_snapshots": len(snapshots),
              "idempotent": True}
    target.with_suffix('.verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
