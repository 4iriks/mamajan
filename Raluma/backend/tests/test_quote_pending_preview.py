"""Current-order previews must not overwrite an already agreed quote."""

import json
import uuid

import pytest

import models
from database import SessionLocal


def _config(*, discount="0", cost="100"):
    return {
        "validity_days": 14,
        "manufacturing_term": "10 дней",
        "payment_terms": "70/30",
        "services": [{
            "id": "service-preview", "name": "Монтаж", "quantity": "1",
            "unit": "шт.", "sale_price": "1000", "actual_cost": cost,
        }],
        "discounts": [{
            "id": "order-fixed", "name": "Общая скидка", "scope": "order",
            "mode": "fixed", "value": discount,
        }],
    }


@pytest.fixture
def ordinary_manager(client, admin_headers):
    username = f"pending-preview-{uuid.uuid4().hex[:12]}"
    created = client.post("/api/users", headers=admin_headers, json={
        "username": username, "password": "preview123", "display_name": "Менеджер",
        "role": "user", "can_manage_prices": False,
    })
    assert created.status_code == 201, created.text
    login = client.post("/api/auth/login", json={"username": username, "password": "preview123"})
    assert login.status_code == 200, login.text
    yield {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.delete(f"/api/users/{created.json()['id']}", headers=admin_headers)


def _fixed_service(client, admin_headers, project):
    base = f"/api/projects/{project['id']}/quote"
    saved = client.put(f"{base}/config", headers=admin_headers, json=_config())
    assert saved.status_code == 200, saved.text
    fixed = client.post(f"{base}/freeze", headers=admin_headers)
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["totals"]["grand_total"] == "1000.00"
    return base


def _snapshots(project_id):
    with SessionLocal() as db:
        state = db.query(models.ProjectQuoteState).filter_by(project_id=project_id).one()
        revisions = db.query(models.ProjectQuoteRevision).filter_by(project_id=project_id).all()
        return state.public_payload, state.internal_payload, [
            (row.revision, row.public_payload, row.internal_payload) for row in revisions
        ]


def test_manager_sees_pending_amount_and_blocking_warnings_without_costs(
    client, admin_headers, ordinary_manager, project,
):
    base = _fixed_service(client, admin_headers, project)
    before = _snapshots(project["id"])
    config = _config(discount="950")
    config["services"][0].pop("actual_cost")
    saved = client.put(f"{base}/config", headers=ordinary_manager, json=config)
    assert saved.status_code == 200, saved.text
    assert saved.json()["totals"]["grand_total"] == "1000.00"
    result = client.get(f"/api/pricing/projects/{project['id']}", headers=ordinary_manager)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["pending_quote"]["totals"]["grand_total"] == "50.00"
    assert data["pending_quote"]["export_allowed"] is False
    assert any("минималь" in warning for warning in data["pending_warnings"])
    assert len(data["preview_token"]) == 64
    assert data["calculation"] == {}
    serialized = json.dumps(data["pending_quote"])
    for private_key in ("actual_cost", "base_cost", "minimum_total", "dealer_markup_percent", "bom"):
        assert private_key not in serialized
    assert "actual_cost" not in data["config"]["services"][0]
    public = client.get(base, headers=ordinary_manager).json()
    assert public["totals"]["grand_total"] == "1000.00"
    assert public["export_allowed"] is True
    assert _snapshots(project["id"]) == before


def test_refresh_rejects_obsolete_preview_even_when_public_price_is_unchanged(
    client, admin_headers, project,
):
    base = _fixed_service(client, admin_headers, project)
    before = _snapshots(project["id"])
    changed = client.put(f"{base}/config", headers=admin_headers, json=_config(discount="100"))
    assert changed.status_code == 200, changed.text
    first = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    assert first["pending_quote"]["totals"]["grand_total"] == "900.00"
    # Private cost changes must invalidate a confirmation too, even if the sale
    # price is identical. A token must cover more than the displayed grand total.
    changed = client.put(f"{base}/config", headers=admin_headers, json=_config(discount="100", cost="200"))
    assert changed.status_code == 200, changed.text
    blocked = client.post(f"{base}/refresh", headers=admin_headers, json={
        "expected_preview_token": first["preview_token"],
    })
    assert blocked.status_code == 409, blocked.text
    assert "после просмотра" in blocked.json()["detail"]
    assert _snapshots(project["id"]) == before
    latest = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    assert latest["preview_token"] != first["preview_token"]
    refreshed = client.post(f"{base}/refresh", headers=admin_headers, json={
        "expected_preview_token": latest["preview_token"],
    })
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["revision"] == 2
    assert refreshed.json()["totals"]["grand_total"] == "900.00"
    old = client.get(f"{base}/revisions/1", headers=admin_headers).json()
    assert old["totals"]["grand_total"] == "1000.00"


def test_current_preview_token_is_stable_and_legacy_refresh_remains_supported(
    client, admin_headers, project,
):
    base = _fixed_service(client, admin_headers, project)
    first = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    second = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    assert first["preview_token"] == second["preview_token"]
    changed = client.put(f"{base}/config", headers=admin_headers, json=_config(discount="100"))
    assert changed.status_code == 200, changed.text
    refreshed = client.post(f"{base}/refresh", headers=admin_headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["revision"] == 2


def test_first_fix_also_requires_the_confirmed_current_calculation(
    client, admin_headers, project,
):
    base = f"/api/projects/{project['id']}/quote"
    saved = client.put(f"{base}/config", headers=admin_headers, json=_config())
    assert saved.status_code == 200, saved.text
    preview = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    saved = client.put(f"{base}/config", headers=admin_headers, json=_config(discount="100"))
    assert saved.status_code == 200, saved.text
    blocked = client.post(f"{base}/freeze", headers=admin_headers, json={
        "expected_preview_token": preview["preview_token"],
    })
    assert blocked.status_code == 409, blocked.text
    assert client.get(base, headers=admin_headers).json()["status"] == "draft"
    latest = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
    fixed = client.post(f"{base}/freeze", headers=admin_headers, json={
        "expected_preview_token": latest["preview_token"],
    })
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["status"] == "fixed"
    assert fixed.json()["totals"]["grand_total"] == "900.00"


def test_override_price_change_preserves_calculation_precision(client, admin_headers, project):
    base = f"/api/projects/{project['id']}/quote"
    for price in ("1.231", "1.234"):
        saved = client.put(f"{base}/overrides", headers=admin_headers, json={
            "overrides": [{"sku": "PRECISE-UNIT", "cost": price, "comment": "Точная цена за единицу"}],
        })
        assert saved.status_code == 200, saved.text
        internal = client.get(f"/api/pricing/projects/{project['id']}", headers=admin_headers).json()
        assert internal["config"]["overrides"][0]["cost"] == price
