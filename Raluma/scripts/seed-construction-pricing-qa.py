"""Create a NEW isolated database for real browser/API regression checks."""
import json
import os
from pathlib import Path
import sys
from datetime import datetime

target = Path(sys.argv[1]).resolve()
if target.exists():
    raise SystemExit('Refusing to overwrite an existing database')
target.parent.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + target.as_posix()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import models
import schemas
from database import Base, engine, SessionLocal
from migrations import run_migrations
from main import seed_superadmin
from api.catalog import _ensure_catalog_seed
from engine.construction_pricing import migrate_construction_pricing
from engine.quote_pricing import construction_requirements

Base.metadata.create_all(engine)
run_migrations()
seed_superadmin()
with SessionLocal() as db:
    _ensure_catalog_seed(db)
    actor = db.query(models.User).filter_by(username='admin').one()
    db.add(models.Customer(name='Проверка цен', name_key='проверка цен'))
    sections = []
    for index, (system, rows, width, height, config) in enumerate([
        ('СЛАЙД', 1, 3000, 2200, None), ('СЛАЙД', 1, 5000, 2600, None),
        ('СЛАЙД', 1, 2400, 2100, None), ('СЛАЙД', 1, 3600, 2400, None),
        ('СЛАЙД', 2, 4000, 2400, None), ('СЛАЙД', 2, 5000, 2200, None),
        ('ЦС', 1, 2240, 1600, {'vertical': {'count': 1}, 'horizontal': {'count': 1}}),
        ('ЦС', 1, 3000, 1800, None),
    ], 1):
        project = models.Project(number=f'QA-{index}', customer='Проверка цен', created_by=actor.id)
        db.add(project); db.flush()
        values = schemas.SectionCreate(name=f'Образец {index}', system=system, width=width, height=height,
            panels=4 if rows == 2 else 3, slide_rows=rows, quantity=2 if index == 7 else 1,
            cs_config=config).model_dump()
        section = models.Section(project_id=project.id, **values)
        db.add(section); db.flush(); sections.append(section)
    seen = set()
    for section in sections:
        _, requirements = construction_requirements(db, section)
        for row in requirements:
            finish_name = row.get('finish') or 'Без цвета'
            if (row['sku'], finish_name) in seen:
                continue
            seen.add((row['sku'], finish_name))
            item = db.query(models.CatalogItem).filter_by(sku=row['sku']).first()
            if item is None:
                item = models.CatalogItem(sku=row['sku'], name=row['name'], group='Расходники',
                    unit=row['unit'], system_groups='["SLIDE_1", "SLIDE_2", "CS"]', is_active=True)
                db.add(item); db.flush()
            variant = next((v for v in item.finish_variants if v.name == finish_name), None)
            if variant is None:
                variant = models.CatalogFinishVariant(name=finish_name,
                    code={'Без цвета':'COLORLESS', 'Анод/неокрас':'ANOD_UNPAINTED'}.get(finish_name, 'RAL_STANDARD'),
                    cost=125, price=125, cost_is_set=True, is_active=True)
                item.finish_variants.append(variant); db.flush()
            variant.cost = variant.price = 125
            variant.cost_is_set = True
            item.price_versions.append(models.CatalogPriceVersion(finish_variant_id=variant.id,
                cost=125, cost_is_set=True, profile_markup_percent=35, waste_markup_percent=4,
                construction_markup_percent=30, construction_discount_percent=0,
                category=row['category'], unit=row['unit'], min_margin_percent=0,
                effective_from=datetime.utcnow(), created_by=actor.id, reason='QA fixture'))
    db.flush()
    migrate_construction_pricing(db); db.commit()
    print(json.dumps({'database': str(target), 'sections': [s.id for s in sections]}))
