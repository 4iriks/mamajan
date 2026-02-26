from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── User ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    username: str
    display_name: str
    role: str = "user"
    customer: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    customer: Optional[str] = None
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


# ── Section ───────────────────────────────────────────────────────────────────

class SectionBase(BaseModel):
    name: str
    order: int = 0
    system: Optional[str] = None
    width: float = 2000
    height: float = 2400
    panels: int = 3
    quantity: int = 1
    glass_type: str = "10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
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
    # ДВЕРЬ / ЦС
    door_system: Optional[str] = None
    cs_shape: Optional[str] = None
    cs_width2: Optional[float] = None


class SectionCreate(SectionBase):
    pass


class SectionUpdate(SectionBase):
    pass


class SectionOut(SectionBase):
    id: int
    project_id: int

    model_config = {"from_attributes": True}


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    number: str
    customer: str
    system: Optional[str] = None
    subtype: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    number: Optional[str] = None
    customer: Optional[str] = None
    system: Optional[str] = None
    subtype: Optional[str] = None


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
