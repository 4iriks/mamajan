"""System price isolation, migration, pure previews and CS quote parity."""
import json
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
import schemas
from api.construction_pricing import router
from auth import require_price_manager
from database import Base, get_db
from engine.construction_pricing import (
    component_key, configuration, current_components, current_global,
    migrate_construction_pricing,
)
from engine.pricing_rules import append_binding, resolve_effective_price
from engine.quote_pricing import (
    _section_requirements, calculate_quote, construction_requirements, freeze_quote,
    get_or_create_quote_state, price_construction_section, quote_is_stale,
)


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = models.User(username="system-prices", password_hash="x", role="admin", display_name="Admin")
        db.add(actor); db.flush()
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[require_price_manager] = lambda: actor
        yield db, actor, TestClient(app)
    engine.dispose()


def add_item(db, actor, sku, unit="м", finish="Без цвета", cost=100, groups='["SLIDE_1", "SLIDE_2", "CS"]'):
    item = db.query(models.CatalogItem).filter_by(sku=sku).first()
    if item is None:
        item = models.CatalogItem(sku=sku, name=sku, unit=unit, group="Профили", system_groups=groups)
        db.add(item); db.flush()
    variant = next((v for v in item.finish_variants if v.name == finish), None)
    if variant is None:
        codes = {"Без цвета": "COLORLESS", "Анод/неокрас": "ANOD_UNPAINTED", "RAL стандарт": "RAL_STANDARD"}
        variant = models.CatalogFinishVariant(code=codes.get(finish, "BASE"), name=finish, cost=cost, price=cost)
        item.finish_variants.append(variant); db.flush()
        item.price_versions.append(models.CatalogPriceVersion(
            finish_variant_id=variant.id, cost=cost, profile_markup_percent=70, profile_discount_percent=5,
            waste_markup_percent=4, construction_markup_percent=20, construction_discount_percent=3,
            category="component", unit=unit, effective_from=datetime.utcnow()-timedelta(days=2),
            created_by=actor.id, reason="Initial"))
        db.flush()
    return item, variant


def add_project(db, actor, system="СЛАЙД", **values):
    project = models.Project(number="Test", customer="Test", created_by=actor.id)
    db.add(project); db.flush()
    payload = schemas.SectionCreate(**{'name': 'Образец', 'system': system, 'width': 2240,
        'height': 1600, 'panels': 3, 'quantity': 1, **values}).model_dump()
    section = models.Section(project_id=project.id, **payload)
    db.add(section); db.flush()
    return project, section


def price_slide_parts(db, actor, section):
    _, requirements = _section_requirements(section)
    for row in requirements:
        add_item(db, actor, row["sku"], row["unit"], row.get("finish") or "Без цвета")


def add_cs(db, actor, **values):
    outer, _ = add_item(db, actor, "Т40Т")
    cover, _ = add_item(db, actor, "Т40К", finish="Анод/неокрас")
    seal, _ = add_item(db, actor, "RS1002")
    pad, _ = add_item(db, actor, "CS-PVC-PAD", "шт")
    kit = models.CsSystem(code="CS_CLAMP", name="ЦС Т40", outer_profile_item_id=outer.id,
        cover_profile_item_id=cover.id, bubble_seal_item_id=seal.id, glass_pad_item_id=pad.id)
    db.add(kit); db.flush()
    project, section = add_project(db, actor, "ЦС", cs_system_id=kit.id, **values)
    _, requirements = construction_requirements(db, section)
    for row in requirements:
        add_item(db, actor, row["sku"], row["unit"], row.get("finish") or "Без цвета")
    return project, section, kit


def test_migration_preserves_rules_costs_standalone_future_and_snapshots(setup):
    db, actor, _ = setup
    item, finish = add_item(db, actor, "SHARED")
    now = datetime.utcnow()
    rule = models.CatalogPricingRule(scope_key="default", scope="default")
    for when, markup in [(now-timedelta(days=1), 31), (now+timedelta(days=1), 64)]:
        rule.versions.append(models.CatalogPricingRuleVersion(name="Old", effective_from=when,
            profile_markup_percent=markup, profile_discount_percent=7, waste_markup_percent=5,
            construction_markup_percent=markup+1, construction_discount_percent=8,
            created_by=actor.id, reason="Scheduled"))
    db.add(rule); append_binding(db, finish, "auto", actor.id, "Legacy", now-timedelta(hours=1))
    item.price_versions.append(models.CatalogPriceVersion(finish_variant_id=finish.id, cost=150,
        profile_markup_percent=10, construction_markup_percent=12, unit="м", category="component",
        effective_from=now+timedelta(days=2), created_by=actor.id, reason="Future cost"))
    db.commit()
    dates = [now, now+timedelta(days=1, hours=1), now+timedelta(days=3)]
    before = [resolve_effective_price(db, item, finish, at, use_legacy_rules=True) for at in dates]
    project, _ = add_project(db, actor)
    state = get_or_create_quote_state(db, project)
    state.public_payload = '{"untouched": true}'; state.internal_payload = '{"legacy": 1}'
    db.flush()
    migrate_construction_pricing(db, at=now); db.commit()
    for at, expected in zip(dates, before):
        actual = resolve_effective_price(db, item, finish, at)
        assert (actual.cost, actual.profile_markup_percent, actual.profile_discount_percent) == (
            expected.cost, expected.profile_markup_percent, expected.profile_discount_percent)
        for code in ("SLIDE_1", "SLIDE_2", "CS"):
            value = current_components(db, code, at)[component_key(item.id, finish.id)]
            assert (value.waste_percent, value.markup_percent, value.discount_percent) == (
                expected.waste_markup_percent, expected.construction_markup_percent, expected.construction_discount_percent)
            assert current_global(db, code, at).markup_percent == 0
    count = db.query(models.CatalogPriceVersion).count()
    assert migrate_construction_pricing(db, at=now) is False
    assert db.query(models.CatalogPriceVersion).count() == count
    assert state.public_payload == '{"untouched": true}' and state.internal_payload == '{"legacy": 1}'
    # Archived rules can no longer change current pricing.
    rule.versions[-1].profile_markup_percent = 999; db.flush()
    assert resolve_effective_price(db, item, finish, dates[-1]).profile_markup_percent == before[-1].profile_markup_percent


def test_independent_system_settings_preview_quote_parity_and_zero_writes(setup):
    db, actor, client = setup
    project, section = add_project(db, actor)
    price_slide_parts(db, actor, section)
    migrate_construction_pricing(db); db.commit()
    config = client.get('/api/construction-pricing/systems/SLIDE_1').json()
    row = config['components'][0]
    before_second = configuration(db, 'SLIDE_2')
    counts = {table.name: db.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar() for table in Base.metadata.sorted_tables}
    body = {'components': {row['key']: {'waste_percent': '10', 'markup_percent': '50', 'discount_percent': '5'}},
            'general': {'markup_percent': '11', 'discount_percent': '3'}, 'section_ids': [section.id]}
    result = client.post('/api/construction-pricing/systems/SLIDE_1/preview', json=body)
    assert result.status_code == 200, result.text
    preview = result.json()['samples'][0]
    assert preview['draft']['complete'], preview
    assert preview['draft']['total'] != preview['saved']['total']
    assert {table.name: db.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar() for table in Base.metadata.sorted_tables} == counts
    saved = client.put('/api/construction-pricing/systems/SLIDE_1', json={**body, 'token': config['token']})
    assert saved.status_code == 200, saved.text
    assert configuration(db, 'SLIDE_2')['token'] == before_second['token']
    quote, internal, _ = calculate_quote(db, project, get_or_create_quote_state(db, project))
    assert internal['sections'][0]['internal_total'] == preview['draft']['total']
    assert quote['export_allowed']
    again = client.put('/api/construction-pricing/systems/SLIDE_1', json={**body, 'token': config['token']})
    assert again.status_code == 409


def test_cs_stock_lengths_tape_pads_polygon_area_and_real_quote(setup):
    db, actor, client = setup
    project, section, _ = add_cs(db, actor, cs_config={'vertical': {'count': 1}, 'horizontal': {'count': 1}})
    section.height = 600; section.quantity = 2
    migrate_construction_pricing(db); db.commit()
    result = price_construction_section(db, section)
    assert not result['issues'], result['issues']
    cover = next(row for row in result['bom'] if row.get('role') == 'cover')
    assert Decimal(cover['quantity']) == 24  # four 3m sticks per 2240×600 section, twice
    pad = next(row for row in result['bom'] if row.get('role') == 'pad')
    assert Decimal(pad['quantity']) == 16  # four panes × two pads × two sections
    calc, requirements = construction_requirements(db, section)
    tape = next(row for row in result['bom'] if row.get('role') == 'tape')
    assert Decimal(tape['quantity']) == next(row['quantity'] for row in requirements if row.get('role') == 'tape')
    assert Decimal(next(row for row in result['bom'] if row['source'] == 'glass')['quantity']) == Decimal(str(calc.glass_area_m2))
    response = client.post('/api/construction-pricing/systems/CS/preview', json={'section_ids': [section.id]})
    assert response.status_code == 200, response.text
    sample = response.json()['samples'][0]
    public, internal, _ = calculate_quote(db, project, get_or_create_quote_state(db, project))
    assert internal['sections'][0]['internal_total'] == sample['draft']['total']
    assert public['export_allowed']
    assert public['lines'][0]['section_details']['cs_geometry']['panes']
    assert public['lines'][0]['section_details']['system'] == 'ЦС'


def test_cs_unfilled_is_not_free_but_explicit_zero_is_valid(setup):
    db, actor, client = setup
    _, section, _ = add_cs(db, actor, glass_supplied=False)
    item = db.query(models.CatalogItem).filter_by(sku='Т40Т').one()
    item.price_versions[0].cost = 0; item.finish_variants[0].cost = 0
    migrate_construction_pricing(db); db.commit()
    result = price_construction_section(db, section)
    assert any(row['sku'] == 'Т40Т' and row['detail'] == 'Себестоимость не заполнена' for row in result['issues'])
    response = client.post('/api/construction-pricing/systems/CS/preview', json={'section_ids': [section.id]}).json()
    assert response['samples'][0]['draft']['total'] is None
    latest = max(item.price_versions, key=lambda v: (v.effective_from, v.id))
    latest.cost_is_set = True; db.flush()
    assert not price_construction_section(db, section)['issues']


def test_manual_override_bypasses_component_chain_but_gets_system_stage(setup):
    db, actor, _ = setup
    _, section = add_project(db, actor, glass_supplied=False)
    price_slide_parts(db, actor, section); migrate_construction_pricing(db); db.commit()
    base = price_construction_section(db, section)
    row = base['bom'][0]
    override = {row['sku']: {'cost': '77', 'comment': 'one-off'}}
    draft = {'components': {row['component_key']: {'waste_percent': '100', 'markup_percent': '100', 'discount_percent': '0'}},
             'general': {'markup_percent': '20', 'discount_percent': '10'}}
    result = price_construction_section(db, section, overrides=override, draft=draft)
    overridden = next(value for value in result['bom'] if value['sku'] == row['sku'])
    assert Decimal(overridden['internal_total']) == (Decimal(overridden['quantity']) * 77).quantize(Decimal('.01'))
    assert overridden['base_cost_total'] == row['base_cost_total']
    assert Decimal(result['stages']['after_markup']) == (Decimal(result['stages']['subtotal']) * Decimal('1.2')).quantize(Decimal('.01'))
    quote, _, _ = calculate_quote(db, section.project, get_or_create_quote_state(db, section.project))
    assert all(line['name'] != 'Стекло' for line in quote['lines'][0]['breakdown'])


def test_cs_kit_changes_stale_only_consuming_quote_and_frozen_snapshot_survives(setup):
    db, actor, _ = setup
    project, section, kit = add_cs(db, actor, glass_supplied=False)
    migrate_construction_pricing(db); db.commit()
    state = get_or_create_quote_state(db, project)
    freeze_quote(db, project, actor)
    frozen = state.public_payload
    other = models.CsSystem(code='UNUSED', name='Unused', is_active=True)
    db.add(other); db.flush()
    assert not quote_is_stale(db, project, state)
    kit.name = 'Новое название'; db.flush()
    assert quote_is_stale(db, project, state)
    assert state.public_payload == frozen


@pytest.mark.parametrize('value', ['', '-1', 'NaN', 'Infinity', '100.00001', '10001'])
def test_reject_invalid_percent_without_write(setup, value):
    db, actor, client = setup
    migrate_construction_pricing(db); db.commit()
    config = configuration(db, 'SLIDE_1')
    response = client.put('/api/construction-pricing/systems/SLIDE_1', json={
        'token': config['token'], 'general': {'markup_percent': value, 'discount_percent': '0'}})
    assert response.status_code == 422
    assert configuration(db, 'SLIDE_1')['token'] == config['token']


def test_unavailable_examples_and_door_cs_are_explicit(setup):
    db, actor, client = setup
    _, section, _ = add_cs(db, actor)
    section.cs_config = {'doors': [{'side': 0}]}
    migrate_construction_pricing(db); db.commit()
    response = client.post('/api/construction-pricing/systems/CS/preview', json={'section_ids': [section.id, 999999]})
    assert response.status_code == 200
    assert all(not row['available'] and row['error'] for row in response.json()['samples'])


def test_mixed_order_applies_each_system_once_and_excludes_extras(setup):
    db, actor, _ = setup
    project, cs, _ = add_cs(db, actor, glass_supplied=False, quantity=3)
    _, slide = add_project(db, actor, glass_supplied=False, slide_rows=2, panels=4)
    slide.project = project
    price_slide_parts(db, actor, slide)
    project.extra_components = json.dumps([{'name': 'Отдельная услуга', 'qty': '1', 'unit_price': '555', 'actual_cost': '200'}])
    migrate_construction_pricing(db); db.commit()
    for code, markup, discount in [('CS', 33, 7), ('SLIDE_2', 12, 3)]:
        db.add(models.SystemPricingVersion(system_code=code, markup_percent=markup, discount_percent=discount,
            effective_from=datetime.utcnow(), created_by=actor.id, reason='Distinct system terms'))
    db.flush()
    expected = {s.id: price_construction_section(db, s)['stages']['total'] for s in [cs, slide]}
    public, internal, _ = calculate_quote(db, project, get_or_create_quote_state(db, project))
    assert not internal['issues'], internal['issues']
    assert {s['section_id']: s['internal_total'] for s in internal['sections']} == expected
    assert internal['project_extras'][0]['internal_total'] == '555.00'
    assert all(not any(b['name'] == 'Стекло' for b in line.get('breakdown', [])) for line in public['lines'])


def test_catalog_sale_only_edit_does_not_invalidate_construction_and_cost_does(setup):
    db, actor, _ = setup
    project, section = add_project(db, actor)
    price_slide_parts(db, actor, section); migrate_construction_pricing(db); db.commit()
    freeze_quote(db, project, actor)
    state = get_or_create_quote_state(db, project)
    row = price_construction_section(db, section)['bom'][0]
    price = db.get(models.CatalogPriceVersion, row['price_version_id'])
    price.profile_markup_percent = 999; price.profile_discount_percent = 99; db.flush()
    assert not quote_is_stale(db, project, state)
    price.cost += 1; db.flush()
    assert quote_is_stale(db, project, state)


def test_full_discount_keeps_minimum_and_unknown_cost_is_not_free_standalone(setup):
    from engine.quote_pricing import calculate_standalone_sale, QuotePricingError
    db, actor, client = setup
    project, section = add_project(db, actor)
    price_slide_parts(db, actor, section); migrate_construction_pricing(db); db.commit()
    config = configuration(db, 'SLIDE_1')
    body = {'general': {'markup_percent': '0', 'discount_percent': '100'}, 'section_ids': [section.id]}
    preview = client.post('/api/construction-pricing/systems/SLIDE_1/preview', json=body).json()['samples'][0]['draft']
    assert preview['complete'] and preview['total'] == '0.00' and preview['below_minimum']
    client.put('/api/construction-pricing/systems/SLIDE_1', json={**body, 'token': config['token']})
    public, _, _ = calculate_quote(db, project, get_or_create_quote_state(db, project))
    assert not public['export_allowed']
    item = db.query(models.CatalogItem).first(); variant = item.finish_variants[0]
    price = max(item.price_versions, key=lambda v: (v.effective_from, v.id)); price.cost_is_set = False; db.flush()
    with pytest.raises(QuotePricingError, match='не задана'):
        calculate_standalone_sale(db, [SimpleNamespace(catalog_item_id=item.id, finish_variant_id=variant.id, quantity=1)])


def test_cs_commercial_html_word_and_image_use_frozen_geometry(setup):
    import io
    import zipfile
    from engine.quote_diagrams import render_quote_room_png
    from engine.project_documents import render_project_document_html
    from engine.office_docx import build_project_docx
    db, actor, _ = setup
    project, section, kit = add_cs(db, actor, cs_config={'vertical': {'count': 1}})
    migrate_construction_pricing(db); db.commit()
    public = freeze_quote(db, project, actor)
    details = public['lines'][0]['section_details']
    image = render_quote_room_png(details)
    html = render_project_document_html(project, project.sections, 'commercial', quote=public)
    assert 'data:image/png;base64,' in html
    assert 'ЦС Т40' in html and 'рельс.' not in html
    docx = build_project_docx(project, project.sections, 'commercial', quote=public)
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        xml = archive.read('word/document.xml').decode()
        assert 'ЦС Т40' in xml and 'рельс.' not in xml
        assert any(name.startswith('word/media/') for name in archive.namelist())
    kit.name = 'Other kit'; section.width += 500; db.flush()
    assert render_quote_room_png(details) == image
    assert render_project_document_html(project, project.sections, 'commercial', quote=public) == html
