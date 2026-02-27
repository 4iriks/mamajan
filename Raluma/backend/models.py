from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # user | admin | superadmin
    customer = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    projects = relationship("Project", back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False)
    customer = Column(String, nullable=False)
    system = Column(String, nullable=True)    # СЛАЙД | КНИЖКА | ЛИФТ | ЦС | ДВЕРЬ (legacy, теперь на секцию)
    subtype = Column(String, nullable=True)   # подтип системы
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    extra_parts = Column(String, nullable=True)
    comments = Column(String, nullable=True)

    owner = relationship("User", back_populates="projects")
    sections = relationship("Section", back_populates="project", cascade="all, delete-orphan", order_by="Section.order")


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    order = Column(Integer, default=0)
    name = Column(String, nullable=False)

    system = Column(String, nullable=True)       # СЛАЙД | КНИЖКА | ЛИФТ | ЦС | ДВЕРЬ

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
    rails = Column(Integer, nullable=True)               # 3 или 5
    threshold = Column(String, nullable=True)
    first_panel_inside = Column(String, nullable=True)   # Слева | Справа
    unused_track = Column(String, nullable=True)         # Без | Внешний | Внутренний
    inter_glass_profile = Column(String, nullable=True)
    profile_left = Column(String, nullable=True)
    profile_right = Column(String, nullable=True)
    lock = Column(String, nullable=True)
    handle = Column(String, nullable=True)
    floor_latches_left = Column(Boolean, default=False)
    floor_latches_right = Column(Boolean, default=False)
    handle_offset = Column(Integer, nullable=True)

    # СЛАЙД — профили (чекбоксы)
    profile_left_wall = Column(Boolean, default=False)          # Пристеночный RS1333/1335
    profile_left_lock_bar = Column(Boolean, default=False)      # Боковой профиль-замок RS1081
    profile_left_p_bar = Column(Boolean, default=False)         # Боковой П-профиль RS1082
    profile_left_handle_bar = Column(Boolean, default=False)    # Ручка-профиль RS112
    profile_left_bubble = Column(Boolean, default=False)        # Пузырьковый уплотнитель RS1002
    profile_right_wall = Column(Boolean, default=False)
    profile_right_lock_bar = Column(Boolean, default=False)
    profile_right_p_bar = Column(Boolean, default=False)
    profile_right_handle_bar = Column(Boolean, default=False)
    profile_right_bubble = Column(Boolean, default=False)
    lock_left = Column(String, nullable=True)    # Без замка / 1-сторонний / 2-сторонний
    lock_right = Column(String, nullable=True)
    book_subtype = Column(String, nullable=True)   # doors | angle | doors_and_angle
    handle_left = Column(String, nullable=True)    # ручка слева
    handle_right = Column(String, nullable=True)   # ручка справа

    # КНИЖКА
    doors = Column(Integer, nullable=True)
    door_side = Column(String, nullable=True)
    door_type = Column(String, nullable=True)
    door_opening = Column(String, nullable=True)
    compensator = Column(String, nullable=True)
    angle_left = Column(Float, nullable=True)
    angle_right = Column(Float, nullable=True)
    book_system = Column(String, nullable=True)  # B25 | B16 | B17 | C16 | C17

    # ДВЕРЬ / ЦС
    door_system = Column(String, nullable=True)   # одностворчатая | двустворчатая
    cs_shape = Column(String, nullable=True)       # Треугольник | Прямоугольник | Трапеция | Сложная форма
    cs_width2 = Column(Float, nullable=True)       # вторая ширина для трапеции

    project = relationship("Project", back_populates="sections")
