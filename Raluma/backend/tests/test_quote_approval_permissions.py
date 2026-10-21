"""Approval roles and safety barriers, using an isolated in-memory database."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models
from api import pricing, quotes
from auth import create_access_token
from database import Base, get_db


@pytest.fixture
def approval_app():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = {}
        for key, role, prices in (
            ("admin", "admin", False),
            ("superadmin", "superadmin", False),
            ("price_manager", "user", True),
            ("user", "user", False),
            ("dealer", "dealer", False),
        ):
            actor = models.User(
                username=key, display_name=key, password_hash="unused", role=role,
                is_active=True, can_manage_prices=prices,
            )
            db.add(actor)
            db.flush()
            users[key] = (
                actor.id,
                {"Authorization": "Bearer " + create_access_token(actor.id, key, role)},
            )
        project = models.Project(
            number="Approval", customer="Test", created_by=users["dealer"][0],
            extra_components=json.dumps([
                {"name": "Test item", "qty": "1", "unit": "шт",
                 "unit_price": "50", "actual_cost": "100"},
            ]),
        )
        db.add(project)
        db.commit()
        project_id = project.id

    def isolated_db():
        with Session(engine) as db:
            yield db

    app = FastAPI()
    app.include_router(quotes.router)
    app.include_router(pricing.router)
    app.dependency_overrides[get_db] = isolated_db
    with TestClient(app) as client:
        yield client, engine, project_id, users
    engine.dispose()


@pytest.mark.parametrize("role", ["admin", "superadmin"])
def test_admin_can_approve_and_freeze_without_price_manager_flag(approval_app, role):
    client, _, project_id, users = approval_app
    actor_id, headers = users[role]
    quote_url = f"/api/projects/{project_id}/quote"
    blocked = client.get(quote_url, headers=headers).json()
    assert not blocked["export_allowed"]
    assert any("Причины блокировки" in text for text in blocked["warnings"])
    assert not any("проверки менеджером" in text for text in blocked["warnings"])
    assert client.post(quote_url + "/freeze", headers=headers).status_code == 409

    approved = client.put(
        quote_url + "/overrides", headers=headers,
        json={"overrides": [], "margin_override_comment": "Согласовано для клиента"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["export_allowed"]
    internal = client.get(f"/api/pricing/projects/{project_id}", headers=headers).json()
    assert internal["margin_approval"]["valid"]
    assert internal["margin_approval"]["approved_by"] == actor_id
    assert internal["margin_approval"]["comment"] == "Согласовано для клиента"
    fixed = client.post(quote_url + "/freeze", headers=headers)
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["status"] == "fixed"
    assert fixed.json()["totals"]["grand_total"] == "50.00"

    changed = client.put(
        quote_url + "/config", headers=headers,
        json={"discounts": [{"id": "new", "scope": "order", "mode": "fixed", "value": "1"}]},
    )
    assert changed.status_code == 200, changed.text
    internal = client.get(f"/api/pricing/projects/{project_id}", headers=headers).json()
    assert not internal["margin_approval"]["valid"]
    assert client.post(quote_url + "/refresh", headers=headers).status_code == 409
    assert client.get(quote_url, headers=headers).json()["totals"]["grand_total"] == "50.00"


@pytest.mark.parametrize("role", ["price_manager", "user", "dealer"])
def test_non_admin_cannot_approve_even_with_price_access(approval_app, role):
    client, _, project_id, users = approval_app
    response = client.put(
        f"/api/projects/{project_id}/quote/overrides", headers=users[role][1],
        json={"overrides": [], "margin_override_comment": "Attempt"},
    )
    assert response.status_code == 403
    internal = client.get(
        f"/api/pricing/projects/{project_id}", headers=users["admin"][1]
    ).json()
    assert not internal["margin_approval"]["valid"]
    assert internal["margin_approval"]["approved_by"] is None


def test_admin_approval_does_not_bypass_missing_prices(approval_app):
    client, engine, project_id, users = approval_app
    with Session(engine) as db:
        project = db.get(models.Project, project_id)
        extras = json.loads(project.extra_components)
        extras.append({"name": "Unpriced item", "qty": "1", "unit": "шт"})
        project.extra_components = json.dumps(extras)
        db.commit()
    headers = users["admin"][1]
    quote_url = f"/api/projects/{project_id}/quote"
    response = client.put(
        quote_url + "/overrides", headers=headers,
        json={"overrides": [], "margin_override_comment": "Margin exception only"},
    )
    assert response.status_code == 200, response.text
    assert not response.json()["export_allowed"]
    assert response.json()["missing_price_count"] == 1
    assert client.post(quote_url + "/freeze", headers=headers).status_code == 409
