"""Partner workflow and authorization tested over HTTP with a real SQLite DB."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import models
from api import auth, documents, pricing, projects, quotes, reviews, sections, users
from auth import create_access_token
from database import Base, get_db
from migrations import migrate_project_review
from project_access import review_status


@pytest.fixture
def workflow_app(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'review.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    actors = {}
    with Session(engine) as db:
        for name, role, reviewer in [
            ("dealer", "dealer", False),
            ("processor", "processor", False),
            ("other", "dealer", False),
            ("manager", "user", True),
            ("manager2", "user", True),
            ("employee", "user", False),
            ("admin", "admin", False),
        ]:
            user = models.User(
                username=name,
                display_name=name,
                password_hash="unused",
                role=role,
                can_review_projects=reviewer,
            )
            db.add(user)
            db.flush()
            actors[name] = {
                "id": user.id,
                "headers": {
                    "Authorization": f"Bearer {create_access_token(user.id, name, role)}"
                },
            }
        db.add(models.Customer(name="Client", name_key="client", is_active=True))
        db.commit()
    app = FastAPI()
    for module in (
        auth,
        users,
        reviews,
        projects,
        sections,
        quotes,
        pricing,
        documents,
    ):
        app.include_router(module.router)

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session
    with TestClient(app) as client:
        yield client, engine, actors
    engine.dispose()


def create(w, role="processor", *, priced=True, legacy=False):
    client, engine, actors = w
    result = client.post(
        "/api/projects", headers=actors[role]["headers"], json={"customer": "Client"}
    )
    assert result.status_code == 201, result.text
    pid = result.json()["id"]
    if priced:
        # Existing manual stock rows retain their previously set internal prices.
        with Session(engine) as db:
            project = db.get(models.Project, pid)
            project.extra_components = json.dumps(
                [
                    {
                        "id": "item",
                        "name": "Stock",
                        "qty": "2",
                        "unit": "шт",
                        "unit_price": "500",
                        "actual_cost": "100",
                    }
                ]
            )
            if legacy:
                project.review_status = "internal"
            db.commit()
    return pid


def state(w, pid, actor="processor"):
    return (
        w[0]
        .get(f"/api/projects/{pid}", headers=w[2][actor]["headers"])
        .json()["workflow"]
    )


def action(w, pid, action, actor="processor", **data):
    version = data.pop("expected_version", None)
    if version is None:
        version = state(w, pid, actor)["version"]
    return w[0].post(
        f"/api/projects/{pid}/review",
        headers=w[2][actor]["headers"],
        json={"action": action, "expected_version": version, **data},
    )


def approve(w, pid, actor="manager"):
    preview = w[0].get(f"/api/pricing/projects/{pid}", headers=w[2][actor]["headers"])
    assert preview.status_code == 200, preview.text
    return action(
        w, pid, "approve", actor, expected_preview_token=preview.json()["preview_token"]
    )


def test_full_cycle_expiry_renewal_and_reopening(workflow_app):
    w = workflow_app
    client, engine, actors = w
    pid = create(w)
    base = f"/api/projects/{pid}"
    owner = actors["processor"]["headers"]
    raw = client.get(base, headers=owner).json()
    assert "unit_price" not in raw["extra_components"]
    assert "actual_cost" not in raw["extra_components"]
    assert client.get(base + "/quote", headers=owner).status_code == 403
    assert client.get(base, headers=actors["manager"]["headers"]).status_code == 403
    assert action(w, pid, "submit").status_code == 200
    assert client.get(base, headers=actors["employee"]["headers"]).status_code == 403
    assert action(w, pid, "claim", "manager").status_code == 200
    assert action(w, pid, "return", "manager", comment="").status_code == 422
    assert (
        action(w, pid, "return", "manager", comment="Уточнить состав").status_code
        == 200
    )
    assert state(w, pid)["can_edit"]
    assert action(w, pid, "submit").status_code == 200
    assert action(w, pid, "claim", "manager2").status_code == 200
    assert approve(w, pid, "manager2").status_code == 200
    quote = client.get(base + "/quote", headers=owner).json()
    assert quote["totals"]["grand_total"] == "1000.00"
    assert state(w, pid)["status"] == "approved"
    first_revision = quote["revision"]
    with Session(engine) as db:
        original = (
            db.query(models.ProjectQuoteRevision)
            .filter_by(project_id=pid, revision=first_revision)
            .one()
            .public_payload
        )
        db.get(models.Project, pid).quote_valid_until = "2000-01-01"
        db.commit()
    assert state(w, pid)["status"] == "expired"
    assert client.get(base + "/quote", headers=owner).status_code == 403
    assert (
        client.get(
            base + f"/quote/revisions/{first_revision}", headers=owner
        ).status_code
        == 403
    )
    assert (
        client.get(base + "/documents/commercial/pdf", headers=owner).status_code == 403
    )
    assert action(w, pid, "renew").status_code == 200
    assert action(w, pid, "claim", "manager").status_code == 200
    assert approve(w, pid).status_code == 200
    assert state(w, pid)["approved_revision"] == first_revision + 1
    assert (
        client.get(
            base + f"/quote/revisions/{first_revision}", headers=owner
        ).status_code
        == 403
    )
    with Session(engine) as db:
        assert (
            db.query(models.ProjectQuoteRevision)
            .filter_by(project_id=pid, revision=first_revision)
            .one()
            .public_payload
            == original
        )
        assert (
            db.query(models.ProjectReviewEvent)
            .filter_by(project_id=pid, action="submit")
            .first()
            .snapshot
        )
    assert action(w, pid, "reopen").status_code == 200
    assert state(w, pid)["can_edit"]
    assert client.get(base + "/quote", headers=owner).status_code == 403


@pytest.mark.parametrize("role", ["dealer", "processor"])
def test_locked_content_all_actors_and_direct_documents(workflow_app, role):
    w = workflow_app
    client, _, actors = w
    pid = create(w, role, priced=False)
    base = f"/api/projects/{pid}"
    version = state(w, pid, role)["version"]
    owner = {**actors[role]["headers"], "X-Project-Version": str(version)}
    section = client.post(
        base + "/sections",
        headers=owner,
        json={"name": "Slide", "system": "СЛАЙД", "width": 2000, "height": 2400},
    )
    assert section.status_code == 201, section.text
    sid = section.json()["id"]
    assert (
        client.put(base, headers=owner, json={"comments": "stale"}).status_code == 409
    )
    assert action(w, pid, "submit", role).status_code == 200
    assert action(w, pid, "reopen", role).status_code == 403
    for who in [role, "admin", "manager"]:
        headers = {
            **actors[who]["headers"],
            "X-Project-Version": str(state(w, pid, role)["version"]),
        }
        assert (
            client.put(base, headers=headers, json={"comments": "bad"}).status_code
            == 403
        )
        assert (
            client.put(
                base + f"/sections/{sid}", headers=headers, json={"name": "bad"}
            ).status_code
            == 403
        )
        assert (
            client.delete(base + f"/sections/{sid}", headers=headers).status_code == 403
        )
        assert (
            client.patch(
                base + f"/sections/{sid}/overrides",
                headers=headers,
                json={"overrides": {}},
            ).status_code
            == 403
        )
        assert client.delete(base, headers=headers).status_code == 403
    assert client.get(base, headers=actors["other"]["headers"]).status_code == 403
    for suffix in [
        "/quote",
        "/quote/revisions",
        "/documents/delivery/pdf",
        "/documents/commercial/docx",
    ]:
        assert (
            client.get(base + suffix, headers=actors[role]["headers"]).status_code
            == 403
        )
    token = actors[role]["headers"]["Authorization"].split()[1]
    assert (
        client.get(base + f"/documents/commercial/preview?token={token}").status_code
        == 403
    )
    for suffix in ["/freeze", "/refresh"]:
        assert (
            client.post(
                base + "/quote" + suffix, headers=actors[role]["headers"]
            ).status_code
            == 403
        )
    assert client.post(
        "/api/pricing/sale/quote", headers=actors[role]["headers"], json={"items": []}
    ).status_code in {403, 422}


def test_bulk_permissions_copy_and_unsupported_approval(workflow_app):
    w = workflow_app
    client, _, actors = w
    dealer = create(w, "dealer", priced=False)
    processor = create(w, "processor", priced=False)
    for role, pid, expected in [("dealer", dealer, 403), ("processor", processor, 201)]:
        headers = {
            **actors[role]["headers"],
            "X-Project-Version": str(state(w, pid, role)["version"]),
        }
        response = client.post(
            f"/api/projects/{pid}/sections",
            headers=headers,
            json={"name": "Комплектация", "system": "КОМПЛЕКТАЦИЯ"},
        )
        assert response.status_code == expected, response.text
    assert action(w, processor, "submit").status_code == 200
    assert action(w, processor, "claim", "manager").status_code == 200
    before = state(w, processor)["version"]
    assert approve(w, processor).status_code == 409
    assert state(w, processor)["version"] == before
    assert state(w, processor)["status"] == "in_review"
    copied = client.post(
        f"/api/projects/{processor}/copy", headers=actors["processor"]["headers"]
    )
    assert copied.status_code == 201
    assert copied.json()["workflow"]["status"] == "draft"
    assert copied.json()["workflow"]["round"] == 0


def test_claim_race_and_reassignment(workflow_app):
    w = workflow_app
    client, _, actors = w
    pid = create(w)
    assert action(w, pid, "submit").status_code == 200
    version = state(w, pid)["version"]
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda actor: action(w, pid, "claim", actor, expected_version=version),
                ["manager", "manager2"],
            )
        )
    assert sorted(result.status_code for result in results)[0] == 200
    assert sum(result.status_code == 200 for result in results) == 1
    assert all(result.status_code in {200, 403, 409} for result in results)
    assert (
        action(
            w, pid, "reassign", "admin", manager_id=actors["employee"]["id"]
        ).status_code
        == 422
    )
    assert (
        action(
            w, pid, "reassign", "admin", manager_id=actors["manager2"]["id"]
        ).status_code
        == 200
    )
    preview = client.get(
        f"/api/pricing/projects/{pid}", headers=actors["manager2"]["headers"]
    ).json()
    headers = actors["manager2"]["headers"]
    assert (
        client.put(
            f"/api/projects/{pid}/quote/config",
            headers=headers,
            json={"validity_days": 15},
        ).status_code
        == 200
    )
    assert (
        action(
            w,
            pid,
            "approve",
            "manager2",
            expected_preview_token=preview["preview_token"],
        ).status_code
        == 409
    )
    assert approve(w, pid, "manager2").status_code == 200


def test_migration_is_idempotent_and_preserves_production(workflow_app):
    w = workflow_app
    _, engine, _ = w
    pid = create(w, legacy=True)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE projects SET status='Готов' WHERE id=:id"), {"id": pid}
        )
    migrate_project_review(engine)
    migrate_project_review(engine)
    with Session(engine) as db:
        project = db.get(models.Project, pid)
        assert project.review_status == "draft"
        assert project.status == "Готов"
        assert json.loads(project.extra_components)[0]["unit_price"] == "500"
        project.review_status = "approved"
        project.quote_valid_until = "2026-11-08"
        assert (
            review_status(
                project, now=datetime(2026, 11, 8, 20, 59, tzinfo=timezone.utc)
            )
            == "approved"
        )
        assert (
            review_status(project, now=datetime(2026, 11, 8, 21, tzinfo=timezone.utc))
            == "expired"
        )


def test_admin_assigns_processor_and_review_capability(workflow_app):
    client, _, actors = workflow_app
    headers = actors["admin"]["headers"]
    result = client.post(
        "/api/users",
        headers=headers,
        json={
            "username": "new-processor",
            "password": "abc",
            "display_name": "Processor",
            "role": "processor",
            "can_review_projects": True,
        },
    )
    assert result.status_code == 201
    assert not result.json()["can_review_projects"]
    assigned = client.put(
        f"/api/users/{actors['employee']['id']}",
        headers=headers,
        json={"can_review_projects": True},
    )
    assert assigned.json()["can_review_projects"]
    assert not assigned.json()["can_manage_prices"]


def test_migration_adds_columns_to_legacy_database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR)"))
        conn.execute(
            text(
                "CREATE TABLE projects (id INTEGER PRIMARY KEY, created_by INTEGER, status VARCHAR)"
            )
        )
        conn.execute(
            text("INSERT INTO users VALUES (1,'dealer'),(2,'user'),(3,'processor')")
        )
        conn.execute(
            text(
                "INSERT INTO projects VALUES (1,1,'Готов'),(2,2,'В работе'),(3,3,NULL)"
            )
        )
    migrate_project_review(engine)
    migrate_project_review(engine)
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT review_status FROM projects ORDER BY id")
        ).scalars().all() == ["draft", "internal", "draft"]
        assert conn.execute(
            text("SELECT status FROM projects ORDER BY id")
        ).scalars().all() == ["Готов", "В работе", None]
        assert conn.execute(
            text("SELECT can_review_projects FROM users")
        ).scalars().all() == [0, 0, 0]
    engine.dispose()


def test_partner_quote_previews_do_not_persist_drafts(workflow_app):
    w = workflow_app
    pid = create(w)
    assert action(w, pid, "submit").status_code == 200
    assert action(w, pid, "claim", "manager").status_code == 200
    for url in [f"/api/projects/{pid}/quote", f"/api/pricing/projects/{pid}"]:
        assert w[0].get(url, headers=w[2]["manager"]["headers"]).status_code == 200
    with Session(w[1]) as db:
        assert db.query(models.ProjectQuoteState).filter_by(project_id=pid).count() == 0
    assert approve(w, pid).status_code == 200
    with Session(w[1]) as db:
        assert (
            db.query(models.ProjectQuoteState).filter_by(project_id=pid).one().status
            == "fixed"
        )
