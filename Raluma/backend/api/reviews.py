"""Explicit partner project transitions; no email or notification side effects."""

from datetime import datetime
import hmac
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user
from database import get_db
from project_access import (
    ADMIN_ROLES,
    advance_version,
    can_review,
    get_project,
    partner_project,
    validate_dealer_content,
    workflow_payload,
)
from api.projects import _project_response
from engine.quote_pricing import (
    QuoteExportBlocked,
    current_quote_preview_token,
    freeze_quote,
    get_or_create_quote_state,
    refresh_quote_revision,
)

router = APIRouter(prefix="/api/projects", tags=["reviews"])


class ReviewAction(BaseModel):
    action: Literal[
        "submit", "claim", "return", "approve", "reopen", "renew", "reassign"
    ]
    expected_version: int = Field(ge=1)
    comment: str = Field(default="", max_length=5000)
    manager_id: int | None = None
    expected_preview_token: str | None = None


@router.get("/reviewers")
def reviewers(
    db: Session = Depends(get_db), actor: models.User = Depends(get_current_user)
):
    if actor.role not in ADMIN_ROLES:
        raise HTTPException(403, "Недостаточно прав")
    return [
        {"id": u.id, "name": u.display_name}
        for u in db.query(models.User).all()
        if u.is_active and can_review(u)
    ]


@router.get("/{project_id}/review/history")
def history(
    project_id: int,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_current_user),
):
    get_project(db, project_id, actor)
    return [
        {
            "id": e.id,
            "round": e.round,
            "action": e.action,
            "actor_id": e.actor_id,
            "created_at": e.created_at,
            "comment": e.comment,
        }
        for e in db.query(models.ProjectReviewEvent)
        .filter_by(project_id=project_id)
        .order_by(models.ProjectReviewEvent.id)
        .all()
    ]


@router.post("/{project_id}/review", response_model=schemas.ProjectOut)
def transition(
    project_id: int,
    data: ReviewAction,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_current_user),
):
    project = get_project(db, project_id, actor)
    if (
        not partner_project(project)
        or data.action not in workflow_payload(project, actor)["actions"]
    ):
        raise HTTPException(403, "Действие недоступно в текущем состоянии проекта")
    advance_version(db, project, data.expected_version, required=True)
    snapshot = None
    comment = data.comment.strip()
    if data.action in {"submit", "renew"}:
        validate_dealer_content(
            actor, extras=project.extra_components, sections=project.sections
        )
        if not project.sections and not json.loads(project.extra_components or "[]"):
            raise HTTPException(422, "Добавьте секцию или комплектацию перед отправкой")
        snapshot = schemas.ProjectOut.model_validate(project).model_dump_json()
        project.review_round += 1
        project.review_status = "submitted"
        project.review_manager_id = None
        project.review_comment = None
        project.approved_quote_revision = None
    elif data.action == "claim":
        project.review_status = "in_review"
        project.review_manager_id = actor.id
    elif data.action == "return":
        if not comment:
            raise HTTPException(422, "Укажите причину возврата")
        project.review_status = "returned"
        project.review_comment = comment
        project.approved_quote_revision = None
    elif data.action == "reopen":
        project.review_status = "draft"
        project.approved_quote_revision = None
        project.review_manager_id = None
        project.review_comment = None
    elif data.action == "reassign":
        manager = db.get(models.User, data.manager_id) if data.manager_id else None
        if manager is None or not manager.is_active or not can_review(manager):
            raise HTTPException(422, "Выберите действующего менеджера")
        project.review_manager_id = manager.id
        comment = f"Ответственный: {manager.display_name}. {comment}".strip()
    elif data.action == "approve":
        evaluation_at = datetime.utcnow()
        actual = current_quote_preview_token(db, project, at=evaluation_at)
        if not data.expected_preview_token or not hmac.compare_digest(
            actual, data.expected_preview_token
        ):
            raise HTTPException(
                409, "Расчёт изменился. Обновите и проверьте КП перед одобрением."
            )
        state = get_or_create_quote_state(db, project)
        try:
            if state.status == "fixed":
                # Renewal always creates a new immutable revision, even with identical prices.
                state.source_signature = ""
                quote = refresh_quote_revision(db, project, actor, at=evaluation_at)
            else:
                quote = freeze_quote(db, project, actor, at=evaluation_at)
        except QuoteExportBlocked as exc:
            db.rollback()
            raise HTTPException(
                409,
                {
                    "message": "Исправьте ошибки расчёта перед одобрением",
                    "quote": exc.public_payload,
                },
            ) from exc
        project.approved_quote_revision = quote["revision"]
        project.quote_valid_until = quote["valid_until"]
        project.review_status = "approved"
        project.review_comment = None
    db.add(
        models.ProjectReviewEvent(
            project_id=project.id,
            round=project.review_round,
            actor_id=actor.id,
            action=data.action,
            comment=comment or None,
            snapshot=snapshot,
        )
    )
    db.commit()
    db.refresh(project)
    return _project_response(project, actor)
