"""Project authorization and transactional guards shared by every API surface."""

from datetime import datetime, timezone, timedelta
import json

from fastapi import HTTPException
from sqlalchemy import update

import models

PARTNER_ROLES = {"dealer", "processor"}
ADMIN_ROLES = {"admin", "superadmin"}
MOSCOW = timezone(timedelta(hours=3))


def is_partner(actor):
    return actor.role in PARTNER_ROLES


def can_review(actor):
    return actor.role in ADMIN_ROLES or (
        actor.role == "user" and actor.can_review_projects
    )


def partner_project(project):
    return project.review_status != "internal" or (
        project.owner is not None and is_partner(project.owner)
    )


def review_status(project, *, now=None):
    status = project.review_status
    if status == "internal" and partner_project(project):
        status = "draft"
    if status == "approved":
        today = (
            (now or datetime.now(timezone.utc)).astimezone(MOSCOW).date().isoformat()
        )
        if not project.quote_valid_until or project.quote_valid_until < today:
            return "expired"
    return status


def can_read(project, actor):
    if is_partner(actor):
        return project.created_by == actor.id
    if not partner_project(project) or actor.role in ADMIN_ROLES:
        return True
    return bool(can_review(actor) and project.review_round > 0)


def get_project(db, project_id, actor):
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(404, "Проект не найден")
    if not can_read(project, actor):
        raise HTTPException(403, "Нет доступа к проекту")
    return project


def can_edit(project, actor):
    if not partner_project(project):
        return not is_partner(actor)
    return project.created_by == actor.id and review_status(project) in {
        "draft",
        "returned",
    }


def can_edit_quote(project, actor):
    if not partner_project(project):
        return not is_partner(actor)
    return bool(
        can_review(actor)
        and project.review_status == "in_review"
        and project.review_manager_id == actor.id
    )


def advance_version(db, project, expected=None, *, required=False):
    """CAS also obtains SQLite's write lock before any content/state changes."""
    version = project.review_version
    if (required and expected is None) or (
        expected is not None and expected != version
    ):
        raise HTTPException(
            409, "Проект изменился. Обновите страницу и повторите действие."
        )
    changed = db.execute(
        update(models.Project)
        .where(
            models.Project.id == project.id, models.Project.review_version == version
        )
        .values(review_version=version + 1)
        .execution_options(synchronize_session=False)
    ).rowcount
    if changed != 1:
        raise HTTPException(
            409, "Проект уже изменён другим пользователем. Обновите страницу."
        )
    db.refresh(project)


def require_content_write(db, project, actor, expected=None):
    if not can_edit(project, actor):
        raise HTTPException(403, "Проект заблокирован для изменений")
    advance_version(db, project, expected, required=partner_project(project))


def require_quote_write(db, project, actor):
    if not can_edit_quote(project, actor):
        raise HTTPException(
            403, "Коммерческие условия меняет ответственный менеджер при согласовании"
        )
    advance_version(db, project)


def require_quote_read(project, actor, revision=None):
    if not is_partner(actor):
        return
    if (
        review_status(project) != "approved"
        or not project.approved_quote_revision
        or (revision is not None and revision != project.approved_quote_revision)
    ):
        raise HTTPException(403, "КП недоступно. Необходимо согласование менеджером.")


def require_document(project, actor, doc_type, revision=None):
    if is_partner(actor):
        if doc_type not in {"sketch", "commercial"}:
            raise HTTPException(403, "Документ доступен только сотрудникам")
        if doc_type == "commercial":
            require_quote_read(project, actor, revision)


def validate_dealer_content(actor, *, system=None, extras=None, sections=()):
    if actor.role != "dealer":
        return
    if system in {"КОМПЛЕКТАЦИЯ", "ДВЕРЬ"} or any(
        section.system in {"КОМПЛЕКТАЦИЯ", "ДВЕРЬ"} for section in sections
    ):
        raise HTTPException(403, "Заказ комплектации доступен только переработчику")
    if extras:
        try:
            has_extras = bool(json.loads(extras))
        except (ValueError, TypeError):
            has_extras = True
        if has_extras:
            raise HTTPException(
                403, "Заказ отдельных комплектующих доступен только переработчику"
            )


def strip_prices(value):
    """Untrusted JSON fields may contain old commercial amounts at any depth."""
    if isinstance(value, list):
        return [strip_prices(item) for item in value]
    if isinstance(value, dict):
        return {
            key: strip_prices(item)
            for key, item in value.items()
            if key.endswith("_id")
            or not any(
                word in key.lower().replace("_", "")
                for word in ("price", "cost", "markup", "discount", "totalamount")
            )
        }
    return value


def sanitize_project_payload(payload, actor):
    if not is_partner(actor):
        return payload
    payload = strip_prices(payload)
    for key in (
        "extra_components",
        "order_items",
        "paint_manual_rows",
        "delivery_note_data",
    ):
        if payload.get(key):
            try:
                payload[key] = json.dumps(
                    strip_prices(json.loads(payload[key])), ensure_ascii=False
                )
            except (ValueError, TypeError):
                payload[key] = None if key != "extra_components" else "[]"
    for section in payload.get("sections", []):
        for key in ("extra_components", "document_overrides"):
            if section.get(key):
                try:
                    section[key] = json.dumps(
                        strip_prices(json.loads(section[key])), ensure_ascii=False
                    )
                except (ValueError, TypeError):
                    section[key] = "{}" if key == "document_overrides" else "[]"
    return payload


def workflow_payload(project, actor):
    status = review_status(project)
    owner = project.created_by == actor.id
    actions = []
    if partner_project(project):
        if owner and status in {"draft", "returned"}:
            actions.append("submit")
        if owner and status in {"approved", "expired"}:
            actions.append("reopen")
        if owner and status == "expired":
            actions.append("renew")
        if can_review(actor) and status == "submitted":
            actions.append("claim")
        if can_edit_quote(project, actor):
            actions.extend(["return", "approve"])
        if actor.role in ADMIN_ROLES and status == "in_review":
            actions.append("reassign")
    return {
        "status": status,
        "version": project.review_version,
        "round": project.review_round,
        "manager_id": project.review_manager_id,
        "manager_name": project.review_manager.display_name
        if project.review_manager
        else None,
        "comment": project.review_comment,
        "actions": actions,
        "can_edit": can_edit(project, actor),
        "can_edit_quote": can_edit_quote(project, actor),
        "can_view_quote": not is_partner(actor) or status == "approved",
        "approved_revision": project.approved_quote_revision
        if status == "approved"
        else None,
        "valid_until": project.quote_valid_until,
    }


def validate_partner_project_fields(actor, values, project=None):
    if not is_partner(actor):
        return
    fields = {
        "status",
        "glass_status",
        "glass_invoice",
        "glass_ready_date",
        "paint_status",
        "paint_ship_date",
        "paint_received_date",
        "order_items",
        "paint_manual_rows",
        "delivery_note_data",
        "extra_parts",
    }
    for key in fields & values.keys():
        value = values[key]
        previous = getattr(project, key, None) if project is not None else None
        if value != previous and not (
            value in (None, "", "[]", "{}") and previous in (None, "", "[]", "{}")
        ):
            raise HTTPException(403, "Производственные данные изменяет сотрудник")
