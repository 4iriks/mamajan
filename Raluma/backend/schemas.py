from datetime import datetime
from typing import Any, Optional, List
from pydantic import BaseModel, Field, model_validator

from engine.glass_types import NON_SLIDE_DEFAULT_GLASS_TYPE, default_glass_type
from engine.lift_config import (
    LIFT_CABLE_SIDES,
    LIFT_CONTROL_TYPES,
    LIFT_CUSTOM_FILLINGS,
    LIFT_FILLING_OPTIONS,
    LIFT_OPENING_TYPES,
    LIFT_SPLIT_OPENING,
)
from engine.lift_calc import lift_geometry_error


# ── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── User ──────────────────────────────────────────────────────────────────────


class UserBase(BaseModel):
    username: str
    display_name: str
    role: str = "user"
    customer: Optional[str] = None
    employee_number: Optional[str] = None
    position: Optional[str] = None
    dealer_company: Optional[str] = None
    dealer_contact_name: Optional[str] = None
    dealer_phone: Optional[str] = None
    dealer_email: Optional[str] = None
    dealer_city: Optional[str] = None
    dealer_address: Optional[str] = None
    dealer_inn: Optional[str] = None
    dealer_discount_percent: Optional[float] = None
    dealer_notes: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    customer: Optional[str] = None
    employee_number: Optional[str] = None
    position: Optional[str] = None
    dealer_company: Optional[str] = None
    dealer_contact_name: Optional[str] = None
    dealer_phone: Optional[str] = None
    dealer_email: Optional[str] = None
    dealer_city: Optional[str] = None
    dealer_address: Optional[str] = None
    dealer_inn: Optional[str] = None
    dealer_discount_percent: Optional[float] = None
    dealer_notes: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserMe(UserOut):
    pass


class ResetPasswordResponse(BaseModel):
    new_password: str


# ── Catalog ───────────────────────────────────────────────────────────────────


class CatalogItemBase(BaseModel):
    sku: str
    name: str
    group: str = "Профили"
    system: str = "СЛАЙД"
    unit: str = "шт"
    purchasePrice: float = 0
    markupPercent: float = 0
    weight: float = 0
    wastePercent: float = 0
    sectionWidthMm: float = 0
    sectionHeightMm: float = 0
    imageFile: Optional[str] = None
    paintMode: str = "Не красится"
    colorVariants: List[str] = Field(default_factory=list)
    supplier: Optional[str] = None
    isActive: bool = True
    note: Optional[str] = None


class CatalogItemCreate(CatalogItemBase):
    pass


class CatalogItemUpdate(CatalogItemBase):
    pass


# ── Section ───────────────────────────────────────────────────────────────────


class SectionBase(BaseModel):
    name: str
    order: int = 0
    system: Optional[str] = None
    width: float = 2000
    height: float = 2400
    panels: int = 3
    quantity: int = 1
    glass_type: str = NON_SLIDE_DEFAULT_GLASS_TYPE
    painting_type: str = "RAL стандарт"
    ral_color: Optional[str] = None
    corner_left: bool = False
    corner_right: bool = False
    external_width: Optional[float] = None
    # СЛАЙД
    rails: Optional[int] = None
    threshold: Optional[str] = None
    first_panel_inside: Optional[str] = None
    unused_track: Optional[str] = None
    inter_glass_profile: Optional[str] = None
    profile_left: Optional[str] = None
    profile_right: Optional[str] = None
    lock: Optional[str] = None
    handle: Optional[str] = None
    floor_latches_left: bool = False
    floor_latches_right: bool = False
    handle_offset: Optional[int] = None
    handle_offset_left: Optional[int] = None
    handle_offset_right: Optional[int] = None
    # СЛАЙД — профили (чекбоксы)
    profile_left_wall: bool = False
    profile_left_lock_bar: bool = False
    profile_left_p_bar: bool = False
    profile_left_handle_bar: bool = False
    profile_left_bubble: bool = False
    profile_right_wall: bool = False
    profile_right_lock_bar: bool = False
    profile_right_p_bar: bool = False
    profile_right_handle_bar: bool = False
    profile_right_bubble: bool = False
    lock_left: Optional[str] = None
    lock_right: Optional[str] = None
    # СЛАЙД 2 ряда
    slide_rows: Optional[int] = 1
    center_handle: Optional[str] = None
    center_lock: Optional[str] = None
    center_handle_offset: Optional[int] = None
    center_floor_latches_left: bool = False
    center_floor_latches_right: bool = False
    book_subtype: Optional[str] = None
    handle_left: Optional[str] = None
    handle_right: Optional[str] = None
    # КНИЖКА
    doors: Optional[int] = None
    door_side: Optional[str] = None
    door_type: Optional[str] = None
    door_opening: Optional[str] = None
    compensator: Optional[str] = None
    angle_left: Optional[float] = None
    angle_right: Optional[float] = None
    book_system: Optional[str] = None
    book_left_door_hardware: Optional[str] = None
    book_right_door_hardware: Optional[str] = None
    book_left_door_opening: Optional[str] = None
    book_right_door_opening: Optional[str] = None
    book_obstacle_distance: Optional[float] = None
    book_left_stack_panels: Optional[int] = None
    book_handle_height: Optional[float] = None
    book_extra_fixed_enabled: bool = False
    book_extra_fixed_width: Optional[float] = None
    book_extra_fixed_side: Optional[str] = None
    book_extra_door_enabled: bool = False
    book_extra_door_panel: Optional[int] = None
    book_extra_door_width: Optional[float] = None
    book_extra_door_opening: Optional[str] = None
    # ЛИФТ
    lift_filling_type: str = "СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    lift_filling_custom: Optional[str] = None
    lift_control_type: str = "Пульт ДУ"
    lift_remote_channels: Optional[int] = Field(default=None, exclude=True)
    lift_remote_1ch_qty: int = Field(default=0, ge=0)
    lift_remote_6ch_qty: int = Field(default=0, ge=0)
    lift_cable_side: str = "Справа"
    lift_opening_type: str = "Сдвиг вниз"
    # ДВЕРЬ / ЦС
    door_system: Optional[str] = None
    cs_shape: Optional[str] = None
    cs_width2: Optional[float] = None
    # Примечания к секции
    extra_parts: Optional[str] = None
    extra_components: Optional[str] = "[]"
    comments: Optional[str] = None
    # Производственный лист — ручные правки
    document_overrides: Optional[str] = "{}"

    @model_validator(mode="before")
    @classmethod
    def set_system_glass_default(cls, values):
        if not isinstance(values, dict):
            return values
        if str(values.get("glass_type") or "").strip():
            return values
        normalized = dict(values)
        normalized["glass_type"] = default_glass_type(values.get("system"))
        return normalized

    @model_validator(mode="after")
    def validate_lift_fields(self):
        if str(self.system or "").strip().upper() != "ЛИФТ":
            return self
        if self.panels not in {2, 3, 4}:
            raise ValueError("Для ЛИФТ количество панелей должно быть 2, 3 или 4")
        if self.width <= 0 or self.height <= 0 or self.quantity <= 0:
            raise ValueError("Размеры и количество секций ЛИФТ должны быть больше нуля")
        if self.lift_filling_type not in LIFT_FILLING_OPTIONS:
            raise ValueError("Недопустимый вариант заполнения ЛИФТ")
        if (
            self.lift_filling_type in LIFT_CUSTOM_FILLINGS
            and not str(self.lift_filling_custom or "").strip()
        ):
            raise ValueError("Для варианта ДРУГОЕ укажите название заполнения")
        if self.lift_control_type not in LIFT_CONTROL_TYPES:
            raise ValueError("Недопустимый вариант управления ЛИФТ")
        if self.lift_cable_side not in LIFT_CABLE_SIDES:
            raise ValueError("Недопустимая сторона ввода кабеля ЛИФТ")
        if self.lift_opening_type not in LIFT_OPENING_TYPES:
            raise ValueError("Недопустимый вариант открывания ЛИФТ")
        if self.panels != 4 and self.lift_opening_type == LIFT_SPLIT_OPENING:
            raise ValueError(
                "Верхняя и нижняя глухие панели доступны только для 4 панелей"
            )
        if self.lift_remote_channels is not None and self.lift_remote_channels <= 0:
            raise ValueError("Количество каналов должно быть больше нуля")
        geometry_error = lift_geometry_error(self)
        if geometry_error:
            raise ValueError(geometry_error)
        return self


class SectionCreate(SectionBase):
    pass


class SectionUpdate(SectionBase):
    pass


class SectionOut(SectionBase):
    id: int
    project_id: int

    model_config = {"from_attributes": True}


# ── Section templates ────────────────────────────────────────────────────────


class SectionTemplateBase(BaseModel):
    name: str
    system: str
    template_data: dict[str, Any]
    sort_order: int = 0


class SectionTemplateCreate(SectionTemplateBase):
    pass


class SectionTemplateUpdate(BaseModel):
    name: Optional[str] = None
    system: Optional[str] = None
    template_data: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None


class SectionTemplateOut(SectionTemplateBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Project ───────────────────────────────────────────────────────────────────


class ProjectBase(BaseModel):
    number: str
    customer: str
    system: Optional[str] = None
    subtype: Optional[str] = None
    extra_parts: Optional[str] = None
    comments: Optional[str] = None
    production_stages: Optional[int] = 1
    current_stage: Optional[int] = 1
    status: Optional[str] = None
    glass_status: Optional[str] = None
    glass_invoice: Optional[str] = None
    glass_ready_date: Optional[str] = None
    paint_status: Optional[str] = None
    paint_ship_date: Optional[str] = None
    paint_received_date: Optional[str] = None
    order_items: Optional[str] = None
    paint_manual_rows: Optional[str] = None
    delivery_note_data: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    number: Optional[str] = None
    customer: Optional[str] = None
    system: Optional[str] = None
    subtype: Optional[str] = None
    extra_parts: Optional[str] = None
    comments: Optional[str] = None
    production_stages: Optional[int] = None
    current_stage: Optional[int] = None
    status: Optional[str] = None
    glass_status: Optional[str] = None
    glass_invoice: Optional[str] = None
    glass_ready_date: Optional[str] = None
    paint_status: Optional[str] = None
    paint_ship_date: Optional[str] = None
    paint_received_date: Optional[str] = None
    order_items: Optional[str] = None
    paint_manual_rows: Optional[str] = None
    delivery_note_data: Optional[str] = None


class ProjectOut(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int
    sections: List[SectionOut] = []

    model_config = {"from_attributes": True}


class ProjectList(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

    model_config = {"from_attributes": True}
