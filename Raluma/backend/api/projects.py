from datetime import datetime
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_user
from engine.legacy_values import normalize_center_handle_offset

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _next_invoice_number(db: Session) -> str:
    """Allocate one global number with a single atomic database statement.

    The counter update and project INSERT share the same transaction, so a
    failed project creation does not consume a number.  SQLite and PostgreSQL
    both serialize the ``ON CONFLICT ... RETURNING`` update.
    """

    value = db.execute(
        text(
            "INSERT INTO invoice_counters (name, value) "
            "VALUES ('project_invoice', 1) "
            "ON CONFLICT(name) DO UPDATE SET value = invoice_counters.value + 1 "
            "RETURNING value"
        )
    ).scalar_one()
    return f"{int(value):08d}"


def _extra_int(row: dict, snake: str, camel: str) -> int | None:
    value = row.get(snake, row.get(camel))
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_project_extras(raw: str | None, db: Session) -> str:
    """Validate catalog selections and refresh catalog-owned row fields."""

    try:
        rows = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail="Некорректный список комплектующих"
        ) from exc
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Некорректный список комплектующих")

    normalized: list[dict] = []
    for source in rows:
        if not isinstance(source, dict):
            continue
        row = dict(source)
        item_id = _extra_int(row, "catalog_item_id", "catalogItemId")
        variant_id = _extra_int(row, "finish_variant_id", "finishVariantId")
        if item_id is None:
            sku = str(row.get("sku") or row.get("article") or "").strip()
            name = str(row.get("name") or "").strip()
            if not name and not sku:
                continue
            if not name:
                name = sku
            try:
                quantity = Decimal(
                    str(row.get("qty", row.get("quantity", "1")) or "1").replace(
                        ",", "."
                    )
                )
            except (TypeError, ValueError, InvalidOperation) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Некорректное количество для {name}",
                ) from exc
            if not quantity.is_finite():
                raise HTTPException(
                    status_code=400,
                    detail=f"Некорректное количество для {name}",
                )
            if quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Количество для {name} должно быть больше нуля",
                )
            try:
                quantity_text = format(quantity.normalize(), "f")
            except (DecimalException, OverflowError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Некорректное количество для {name}",
                ) from exc
            color = str(row.get("color") or "").strip()
            category = str(row.get("category") or "component").strip().lower()
            if category not in {"profile", "component", "service"}:
                category = "component"
            delivery_stage = str(
                row.get("delivery_stage") or row.get("deliveryStage") or "both"
            )
            if delivery_stage not in {"1", "2", "both"}:
                delivery_stage = "both"
            normalized.append(
                {
                    "sku": sku,
                    "name": name,
                    "category": category,
                    "finish_name": str(
                        row.get("finish_name") or row.get("finishName") or ""
                    ).strip(),
                    "color": color,
                    "requires_paint": bool(color),
                    "size": str(row.get("size") or "").strip(),
                    "qty": quantity_text,
                    "unit": str(row.get("unit") or "шт").strip() or "шт",
                    "unit_price": str(
                        row.get("unit_price") or row.get("unitPrice") or ""
                    ).strip(),
                    "image_file": str(
                        row.get("image_file")
                        or row.get("imageFile")
                        or row.get("image")
                        or ""
                    ).strip(),
                    "delivery_stage": delivery_stage,
                }
            )
            continue
        item = db.get(models.CatalogItem, item_id)
        if item is None or not item.is_active:
            raise HTTPException(status_code=400, detail="Позиция каталога недоступна")
        variants = [variant for variant in item.finish_variants if variant.is_active]
        variant = next((entry for entry in variants if entry.id == variant_id), None)
        visible_variants = [
            entry
            for entry in variants
            if str(getattr(entry, "code", "") or "").strip().upper() != "BASE"
            and entry.name.strip().casefold() not in {"без цвета", "без окраски"}
        ]
        if variant_id is not None and variant is None:
            raise HTTPException(
                status_code=400,
                detail="Исполнение не относится к выбранному артикулу",
            )
        if variant is None and visible_variants:
            raise HTTPException(
                status_code=400, detail="Выберите исполнение из каталога"
            )
        if variant is None and variants:
            variant = variants[0]

        price_query = db.query(models.CatalogPriceVersion).filter(
            models.CatalogPriceVersion.catalog_item_id == item.id,
            models.CatalogPriceVersion.effective_from <= datetime.utcnow(),
        )
        if variant is not None:
            price_query = price_query.filter(
                models.CatalogPriceVersion.finish_variant_id == variant.id
            )
        active_price = price_query.order_by(
            models.CatalogPriceVersion.effective_from.desc(),
            models.CatalogPriceVersion.id.desc(),
        ).first()
        base_cost = Decimal(
            str(
                (variant.cost if variant.cost is not None else variant.price)
                if variant is not None
                else active_price.cost
                if active_price is not None
                else item.purchase_price or 0
            )
        )
        markup = Decimal(
            str(
                active_price.profile_markup_percent
                if active_price is not None
                else variant.profile_markup_percent
                if variant is not None
                else item.markup_percent or 0
            )
        )
        discount = Decimal(
            str(
                active_price.profile_discount_percent
                if active_price is not None
                else variant.profile_discount_percent
                if variant is not None
                else 0
            )
        )
        unit_price = (
            base_cost
            * (Decimal("1") + markup / Decimal("100"))
            * (Decimal("1") - discount / Decimal("100"))
        )

        if variant is not None:
            finish_name = (
                ""
                if str(getattr(variant, "code", "") or "").strip().upper() == "BASE"
                or variant.name.strip().casefold() in {"без цвета", "без окраски"}
                else variant.name
            )
            requires_paint = bool(variant.requires_paint)
            variant_id = variant.id
        else:
            finish_name = ""
            requires_paint = False

        color = str(row.get("color") or "").strip() if requires_paint else ""
        if requires_paint and not color:
            raise HTTPException(
                status_code=400,
                detail=f"Укажите цвет для {item.sku} {item.name}",
            )

        normalized.append(
            {
                "catalog_item_id": item.id,
                "finish_variant_id": variant_id,
                "sku": item.sku,
                "name": item.name,
                "category": (
                    active_price.category
                    if active_price is not None
                    and active_price.category in {"profile", "component", "service"}
                    else "service"
                    if "услуг" in str(item.group or "").casefold()
                    else "profile"
                    if any(
                        marker in str(item.group or "").casefold()
                        for marker in ("проф", "уплотн")
                    )
                    else "component"
                ),
                "finish_name": finish_name,
                "color": color,
                "requires_paint": requires_paint,
                "size": str(row.get("size") or "").strip(),
                "qty": str(row.get("qty", row.get("quantity", "1"))).strip(),
                "unit": str(item.unit or "шт").strip(),
                "unit_price": (
                    f"{unit_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
                ),
                "image_file": item.image_file or "",
                "delivery_stage": (
                    str(row.get("delivery_stage") or row.get("deliveryStage"))
                    if str(row.get("delivery_stage") or row.get("deliveryStage"))
                    in {"1", "2"}
                    else "both"
                ),
            }
        )
    return json.dumps(normalized, ensure_ascii=False)


def _get_project_or_404(
    project_id: int, db: Session, current_user: models.User
) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if current_user.role == "dealer" and project.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    return project


@router.get("", response_model=list[schemas.ProjectList])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Project)
    if current_user.role == "dealer":
        query = query.filter(models.Project.created_by == current_user.id)
    return query.order_by(models.Project.created_at.desc()).all()


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(
    data: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    values = data.model_dump()
    # Invoice numbers are immutable and always issued by the server.
    values.pop("invoice_number", None)
    order_number = str(values.get("order_number") or values.get("number") or "").strip()
    values["order_number"] = order_number or None
    values["number"] = order_number  # legacy compatibility alias
    values["extra_components"] = _normalize_project_extras(
        values.get("extra_components"), db
    )
    values["system"] = values.get("system") or ""  # legacy NOT NULL constraint
    project = models.Project(
        **values,
        invoice_number=_next_invoice_number(db),
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_project_or_404(project_id, db, current_user)


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    data: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db, current_user)
    values = data.model_dump(exclude_unset=True)
    if "extra_components" in values:
        values["extra_components"] = _normalize_project_extras(
            values.get("extra_components"), db
        )
    if "order_number" in values or "number" in values:
        raw_order_number = (
            values.get("order_number")
            if "order_number" in values
            else values.get("number")
        )
        order_number = str(raw_order_number or "").strip()
        values["order_number"] = order_number or None
        values["number"] = order_number
    for field, value in values.items():
        setattr(project, field, value)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _get_project_or_404(project_id, db, current_user)
    db.delete(project)
    db.commit()


@router.post("/{project_id}/copy", response_model=schemas.ProjectOut, status_code=201)
def copy_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    source = _get_project_or_404(project_id, db, current_user)
    new_project = models.Project(
        # A copy is a new estimate with its own invoice. The production order
        # number is assigned only after the copied estimate is approved.
        number="",
        order_number=None,
        invoice_number=_next_invoice_number(db),
        customer=source.customer,
        system=source.system,
        subtype=source.subtype,
        extra_parts=source.extra_parts,
        extra_components=source.extra_components,
        hardware_installation=source.hardware_installation,
        comments=source.comments,
        production_stages=source.production_stages,
        status=source.status,
        glass_status=source.glass_status,
        glass_invoice=source.glass_invoice,
        glass_ready_date=source.glass_ready_date,
        paint_status=source.paint_status,
        paint_ship_date=source.paint_ship_date,
        paint_received_date=source.paint_received_date,
        current_stage=source.current_stage,
        order_items=source.order_items,
        paint_manual_rows=source.paint_manual_rows,
        delivery_note_data=source.delivery_note_data,
        created_by=current_user.id,
    )
    db.add(new_project)
    db.flush()
    for s in source.sections:
        new_section = models.Section(
            project_id=new_project.id,
            order=s.order,
            name=s.name,
            system=s.system,
            width=s.width,
            height=s.height,
            panels=s.panels,
            quantity=s.quantity,
            glass_type=s.glass_type,
            glass_supplied=s.glass_supplied,
            price_group_id=s.price_group_id,
            painting_type=s.painting_type,
            ral_color=s.ral_color,
            corner_left=s.corner_left,
            corner_right=s.corner_right,
            external_width=s.external_width,
            rails=s.rails,
            threshold=s.threshold,
            first_panel_inside=s.first_panel_inside,
            unused_track=s.unused_track,
            inter_glass_profile=s.inter_glass_profile,
            profile_left=s.profile_left,
            profile_right=s.profile_right,
            lock=s.lock,
            handle=s.handle,
            floor_latches_left=s.floor_latches_left,
            floor_latches_right=s.floor_latches_right,
            handle_offset_left=s.handle_offset_left,
            handle_offset_right=s.handle_offset_right,
            profile_left_wall=s.profile_left_wall,
            profile_left_lock_bar=s.profile_left_lock_bar,
            profile_left_p_bar=s.profile_left_p_bar,
            profile_left_handle_bar=s.profile_left_handle_bar,
            profile_left_bubble=s.profile_left_bubble,
            profile_right_wall=s.profile_right_wall,
            profile_right_lock_bar=s.profile_right_lock_bar,
            profile_right_p_bar=s.profile_right_p_bar,
            profile_right_handle_bar=s.profile_right_handle_bar,
            profile_right_bubble=s.profile_right_bubble,
            lock_left=s.lock_left,
            lock_right=s.lock_right,
            slide_rows=s.slide_rows,
            center_handle=s.center_handle,
            center_lock=s.center_lock,
            center_handle_offset=normalize_center_handle_offset(
                s.center_handle, s.center_handle_offset
            ),
            center_floor_latches_left=s.center_floor_latches_left,
            center_floor_latches_right=s.center_floor_latches_right,
            book_subtype=s.book_subtype,
            handle_left=s.handle_left,
            handle_right=s.handle_right,
            doors=s.doors,
            door_side=s.door_side,
            door_type=s.door_type,
            door_opening=s.door_opening,
            compensator=s.compensator,
            angle_left=s.angle_left,
            angle_right=s.angle_right,
            book_system=s.book_system,
            book_left_door_hardware=s.book_left_door_hardware,
            book_right_door_hardware=s.book_right_door_hardware,
            book_left_door_opening=s.book_left_door_opening,
            book_right_door_opening=s.book_right_door_opening,
            book_left_door_width=s.book_left_door_width,
            book_right_door_width=s.book_right_door_width,
            book_left_fixed_left_enabled=s.book_left_fixed_left_enabled,
            book_left_fixed_left_width=s.book_left_fixed_left_width,
            book_left_fixed_right_enabled=s.book_left_fixed_right_enabled,
            book_left_fixed_right_width=s.book_left_fixed_right_width,
            book_right_fixed_left_enabled=s.book_right_fixed_left_enabled,
            book_right_fixed_left_width=s.book_right_fixed_left_width,
            book_right_fixed_right_enabled=s.book_right_fixed_right_enabled,
            book_right_fixed_right_width=s.book_right_fixed_right_width,
            book_obstacle_distance=s.book_obstacle_distance,
            book_left_stack_panels=s.book_left_stack_panels,
            book_handle_height=s.book_handle_height,
            book_extra_fixed_enabled=s.book_extra_fixed_enabled,
            book_extra_fixed_width=s.book_extra_fixed_width,
            book_extra_fixed_side=s.book_extra_fixed_side,
            book_extra_door_enabled=s.book_extra_door_enabled,
            book_extra_door_panel=s.book_extra_door_panel,
            book_extra_door_width=s.book_extra_door_width,
            book_extra_door_opening=s.book_extra_door_opening,
            lift_filling_type=s.lift_filling_type,
            lift_filling_custom=s.lift_filling_custom,
            lift_control_type=s.lift_control_type,
            lift_remote_1ch_qty=s.lift_remote_1ch_qty,
            lift_remote_6ch_qty=s.lift_remote_6ch_qty,
            lift_cable_side=s.lift_cable_side,
            lift_opening_type=s.lift_opening_type,
            door_system=s.door_system,
            cs_shape=s.cs_shape,
            cs_width2=s.cs_width2,
            extra_parts=s.extra_parts,
            extra_components=s.extra_components,
            comments=s.comments,
        )
        db.add(new_section)
    db.commit()
    db.refresh(new_project)
    return new_project
