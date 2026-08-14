from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(
        String, default="user", nullable=False
    )  # user | dealer | admin | superadmin
    customer = Column(String, nullable=True)
    employee_number = Column(String, nullable=True)
    position = Column(String, nullable=True)
    dealer_company = Column(String, nullable=True)
    dealer_contact_name = Column(String, nullable=True)
    dealer_phone = Column(String, nullable=True)
    dealer_email = Column(String, nullable=True)
    dealer_city = Column(String, nullable=True)
    dealer_address = Column(String, nullable=True)
    dealer_inn = Column(String, nullable=True)
    dealer_discount_percent = Column(Float, nullable=True)
    dealer_notes = Column(Text, nullable=True)
    can_manage_prices = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    projects = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    customer = Column(String, nullable=False)
    system = Column(
        String, nullable=True
    )  # СЛАЙД | КНИЖКА | ЛИФТ | ЦС | ДВЕРЬ (legacy, теперь на секцию)
    subtype = Column(String, nullable=True)  # подтип системы
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    extra_parts = Column(String, nullable=True)
    extra_components = Column(Text, default="[]", nullable=False)
    hardware_installation = Column(String, default="installed", nullable=False)
    comments = Column(String, nullable=True)
    # ТЗ5 — статус производства
    production_stages = Column(Integer, default=1)  # 1 или 2
    current_stage = Column(Integer, default=1)  # текущий этап для 2-этапных
    status = Column(String, nullable=True)  # статус проекта
    glass_status = Column(String, nullable=True)
    glass_invoice = Column(String, nullable=True)  # номер счёта на стекло
    glass_ready_date = Column(String, nullable=True)  # дата готовности стёкол (ISO)
    paint_status = Column(String, nullable=True)
    paint_ship_date = Column(String, nullable=True)  # отгружен на покраску
    paint_received_date = Column(String, nullable=True)  # получен с покраски
    order_items = Column(
        String, nullable=True
    )  # JSON: [{id,name,invoice,paidDate,deliveredDate}]
    paint_manual_rows = Column(String, nullable=True)  # JSON: ручные строки заявки на покраску
    delivery_note_data = Column(Text, nullable=True)  # JSON: реквизиты и кол-во мест накладной

    owner = relationship("User", back_populates="projects")
    sections = relationship(
        "Section",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Section.order",
    )
    quote_state = relationship(
        "ProjectQuoteState",
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    order = Column(Integer, default=0)
    name = Column(String, nullable=False)

    system = Column(String, nullable=True)  # СЛАЙД | КНИЖКА | ЛИФТ | ЦС | ДВЕРЬ

    # Общие поля
    width = Column(Float, default=2000)
    height = Column(Float, default=2400)
    panels = Column(Integer, default=3)
    quantity = Column(Integer, default=1)
    glass_type = Column(String, default="10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ")
    painting_type = Column(String, default="RAL стандарт")
    ral_color = Column(String, nullable=True)
    corner_left = Column(Boolean, default=False)
    corner_right = Column(Boolean, default=False)
    external_width = Column(Float, nullable=True)

    # СЛАЙД
    rails = Column(Integer, nullable=True)  # 3 или 5
    threshold = Column(String, nullable=True)
    first_panel_inside = Column(String, nullable=True)  # Слева | Справа
    unused_track = Column(String, nullable=True)  # Без | Внешний | Внутренний
    inter_glass_profile = Column(String, nullable=True)
    profile_left = Column(String, nullable=True)
    profile_right = Column(String, nullable=True)
    lock = Column(String, nullable=True)
    handle = Column(String, nullable=True)
    floor_latches_left = Column(Boolean, default=False)
    floor_latches_right = Column(Boolean, default=False)
    handle_offset = Column(
        Integer, nullable=True
    )  # legacy — оставлен для совместимости
    handle_offset_left = Column(Integer, nullable=True)  # отступ a (левое стекло)
    handle_offset_right = Column(Integer, nullable=True)  # отступ b (правое стекло)

    # СЛАЙД — профили (чекбоксы)
    profile_left_wall = Column(Boolean, default=False)  # Пристеночный RS1333/1335
    profile_left_lock_bar = Column(
        Boolean, default=False
    )  # Боковой профиль-замок RS1081
    profile_left_p_bar = Column(Boolean, default=False)  # Боковой П-профиль RS1082
    profile_left_handle_bar = Column(Boolean, default=False)  # Ручка-профиль RS112
    profile_left_bubble = Column(
        Boolean, default=False
    )  # Пузырьковый уплотнитель RS1002
    profile_right_wall = Column(Boolean, default=False)
    profile_right_lock_bar = Column(Boolean, default=False)
    profile_right_p_bar = Column(Boolean, default=False)
    profile_right_handle_bar = Column(Boolean, default=False)
    profile_right_bubble = Column(Boolean, default=False)
    lock_left = Column(String, nullable=True)  # Без замка / 1-сторонний / 2-сторонний
    lock_right = Column(String, nullable=True)
    # СЛАЙД 2 ряда — подтип и центральные панели
    slide_rows = Column(Integer, default=1)  # 1 или 2 ряда
    center_handle = Column(String, nullable=True)
    center_lock = Column(String, nullable=True)
    center_handle_offset = Column(Integer, nullable=True)  # отступ C
    center_floor_latches_left = Column(Boolean, default=False)
    center_floor_latches_right = Column(Boolean, default=False)
    book_subtype = Column(String, nullable=True)  # doors | angle | doors_and_angle
    handle_left = Column(String, nullable=True)  # ручка слева
    handle_right = Column(String, nullable=True)  # ручка справа

    # КНИЖКА
    doors = Column(Integer, nullable=True)
    door_side = Column(String, nullable=True)
    door_type = Column(String, nullable=True)
    door_opening = Column(String, nullable=True)
    compensator = Column(String, nullable=True)
    angle_left = Column(Float, nullable=True)
    angle_right = Column(Float, nullable=True)
    book_system = Column(String, nullable=True)  # B25 | B16 | B17 | C16 | C17
    book_left_door_hardware = Column(String, nullable=True)  # handle | lock
    book_right_door_hardware = Column(String, nullable=True)  # handle | lock
    book_left_door_opening = Column(String, nullable=True)
    book_right_door_opening = Column(String, nullable=True)
    book_obstacle_distance = Column(Float, nullable=True)
    book_left_stack_panels = Column(Integer, nullable=True)
    book_handle_height = Column(Float, nullable=True)
    book_extra_fixed_enabled = Column(Boolean, default=False)
    book_extra_fixed_width = Column(Float, nullable=True)
    book_extra_fixed_side = Column(String, nullable=True)  # left | right
    book_extra_door_enabled = Column(Boolean, default=False)
    book_extra_door_panel = Column(Integer, nullable=True)
    book_extra_door_width = Column(Float, nullable=True)
    book_extra_door_opening = Column(String, nullable=True)

    # ЛИФТ
    lift_filling_type = Column(
        String, default="СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ"
    )
    lift_filling_custom = Column(String, nullable=True)
    lift_control_type = Column(String, default="Пульт ДУ")
    lift_remote_channels = Column(Integer, nullable=True)
    lift_remote_1ch_qty = Column(Integer, default=0, nullable=False)
    lift_remote_6ch_qty = Column(Integer, default=0, nullable=False)
    lift_cable_side = Column(String, default="Справа")
    lift_opening_type = Column(String, default="Сдвиг вниз")

    # ДВЕРЬ / ЦС
    door_system = Column(String, nullable=True)  # одностворчатая | двустворчатая
    cs_shape = Column(
        String, nullable=True
    )  # Треугольник | Прямоугольник | Трапеция | Сложная форма
    cs_width2 = Column(Float, nullable=True)  # вторая ширина для трапеции

    # Примечания к секции
    extra_parts = Column(String, nullable=True)
    extra_components = Column(Text, default="[]")
    comments = Column(String, nullable=True)

    # Производственный лист — ручные правки поверх расчёта
    document_overrides = Column(Text, default="{}")

    project = relationship("Project", back_populates="sections")


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    group = Column(String, default="Профили", nullable=False)
    system = Column(String, default="СЛАЙД", nullable=False)
    unit = Column(String, default="шт", nullable=False)
    purchase_price = Column(Float, default=0, nullable=False)
    markup_percent = Column(Float, default=0, nullable=False)
    weight = Column(Float, default=0, nullable=False)
    waste_percent = Column(Float, default=0, nullable=False)
    section_width_mm = Column(Float, default=0, nullable=False)
    section_height_mm = Column(Float, default=0, nullable=False)
    image_file = Column(String, nullable=True)
    paint_mode = Column(String, default="Не красится", nullable=False)
    color_variants = Column(Text, default="[]", nullable=False)
    supplier = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    price_versions = relationship(
        "CatalogPriceVersion",
        back_populates="catalog_item",
        cascade="all, delete-orphan",
        order_by="CatalogPriceVersion.effective_from.desc()",
    )


class CatalogPriceVersion(Base):
    """Неизменяемая версия цены каталога.

    Старые ``CatalogItem.purchase_price`` и ``markup_percent`` остаются только
    для обратной совместимости каталога и никогда не используются в КП.
    """

    __tablename__ = "catalog_price_versions"

    id = Column(Integer, primary_key=True, index=True)
    catalog_item_id = Column(
        Integer, ForeignKey("catalog_items.id"), nullable=False, index=True
    )
    cost = Column(Numeric(14, 2), nullable=False)
    profile_markup_percent = Column(Numeric(8, 4), default=0, nullable=False)
    profile_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    waste_markup_percent = Column(Numeric(8, 4), default=0, nullable=False)
    construction_markup_percent = Column(Numeric(8, 4), default=0, nullable=False)
    construction_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    category = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    min_margin_percent = Column(Numeric(8, 4), default=0, nullable=False)
    effective_from = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    rollback_of_id = Column(
        Integer, ForeignKey("catalog_price_versions.id"), nullable=True
    )

    catalog_item = relationship("CatalogItem", back_populates="price_versions")


class DealerPricingTerms(Base):
    """Скрытые условия дилерского аккаунта для расчёта КП."""

    __tablename__ = "dealer_pricing_terms"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    dealer_markup_percent = Column(Numeric(8, 4), default=0, nullable=False)
    profile_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    construction_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    component_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    service_discount_percent = Column(Numeric(8, 4), default=0, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)


class PricingSettings(Base):
    """Глобальные переключатели расчёта, одна строка с id=1."""

    __tablename__ = "pricing_settings"

    id = Column(Integer, primary_key=True, default=1)
    include_waste_markup = Column(Boolean, default=False, nullable=False)
    default_vat_rate = Column(Numeric(6, 3), default=20, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class ProjectQuoteState(Base):
    """Единственная актуальная редакция коммерческого предложения проекта."""

    __tablename__ = "project_quote_states"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id"), nullable=False, unique=True, index=True
    )
    revision = Column(Integer, default=1, nullable=False)
    status = Column(String, default="draft", nullable=False)  # draft | fixed
    public_payload = Column(Text, default="{}", nullable=False)
    internal_payload = Column(Text, default="{}", nullable=False)
    services_payload = Column(Text, default="[]", nullable=False)
    overrides_payload = Column(Text, default="[]", nullable=False)
    vat_mode = Column(String, default="none", nullable=False)
    vat_rate = Column(Numeric(6, 3), default=20, nullable=False)
    validity_days = Column(Integer, default=14, nullable=False)
    manufacturing_term = Column(String, default="", nullable=False)
    payment_terms = Column(String, default="", nullable=False)
    margin_override_comment = Column(Text, nullable=True)
    margin_override_context_signature = Column(String, nullable=True)
    margin_override_target_revision = Column(Integer, nullable=True)
    margin_override_approved_by = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    margin_override_approved_at = Column(DateTime, nullable=True)
    source_signature = Column(String, default="", nullable=False)
    source_project_updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    fixed_at = Column(DateTime, nullable=True)
    fixed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="quote_state")
