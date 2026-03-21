# План разработки — Конфигуратор Ралюма
> Обновлён: 2026-02-25 v3. Актуальное состояние + план работ.

---

## ТЕКУЩЕЕ СОСТОЯНИЕ ФРОНТЕНДА (Raluma/)

Дизайнер уже сделал UI — тёмная тема, glassmorphism, Tailwind + Framer Motion.

**Что есть:**
- `App.tsx` — логин + список проектов + модалы (создать/удалить) — ГОТОВО (mock данные)
- `components/ProjectEditor.tsx` — редактор проекта с секциями, формы СЛАЙД + КНИЖКА (частично), SVG-схема, модал документа — ГОТОВО (нет стейт-биндинга, нет реального расчёта)
- Дизайн-система: цвета `#050a0c / #1a4b54 / #2a7a8a / #4fd1c5 / #00b894`

**Что ОТСУТСТВУЕТ на фронте:**
- [ ] React Router (сейчас view-state вместо URL маршрутов)
- [ ] Axios клиент + JWT interceptors
- [ ] Zustand authStore (текущий пользователь, токен)
- [ ] Реальный login через API
- [ ] AdminPage (/admin) — страницы нет вообще
- [ ] Реальный расчёт компонентов КНИЖКА (сейчас захардкожено)
- [ ] Полное подключение форм к стейту (много полей СЛАЙД не биндятся)

**Стек фронтенда:**
```
React 19 + TypeScript + Vite 6
Tailwind CSS 4 + Framer Motion (пакет "motion" v12)
Lucide React иконки
```

---

## АРХИТЕКТУРА

```
Raluma/
├── backend/          ← FastAPI (Python) — СТРОИМ
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── requirements.txt
│   └── api/
│       ├── auth.py       ← POST /api/auth/login, GET /api/auth/me
│       ├── users.py      ← GET/POST/PUT/DELETE /api/users (admin)
│       ├── projects.py   ← CRUD /api/projects
│       └── sections.py   ← CRUD /api/projects/{id}/sections
│
└── src/              ← React frontend — ДОРАБАТЫВАЕМ
    ├── App.tsx           ← добавить Router
    ├── store/
    │   └── authStore.ts  ← СОЗДАТЬ (Zustand)
    ├── api/
    │   ├── client.ts     ← СОЗДАТЬ (axios + interceptors)
    │   ├── auth.ts       ← СОЗДАТЬ
    │   └── projects.ts   ← СОЗДАТЬ
    ├── pages/
    │   └── AdminPage.tsx ← СОЗДАТЬ
    └── components/
        └── ProjectEditor.tsx ← доработать (реальные API calls)
```

---

## МОДЕЛИ ДАННЫХ

### User
```python
id: int
username: str          # логин (латиница, уникальный)
password_hash: str     # bcrypt
display_name: str      # отображаемое имя
role: str              # 'user' | 'admin' | 'superadmin'
customer: str | None   # привязка к заказчику (опционально)
is_active: bool
created_at: datetime
last_login: datetime | None
```

### Project
```python
id: int
number: str            # номер проекта (напр. "2041")
customer: str          # 'ПРОЗРАЧНЫЕ РЕШЕНИЯ' | 'КРОКНА ИНЖИНИРИНГ' | 'СТУДИЯ СПК'
system: str            # 'СЛАЙД' | 'КНИЖКА' | 'ЛИФТ' | 'ЦС'
created_at: datetime
updated_at: datetime
created_by: int        # FK → User
```

### Section
```python
id: int
project_id: int        # FK → Project
order: int             # порядок в проекте
name: str              # "Секция 1"
width: float           # ширина мм
height: float          # высота мм
panels: int            # кол-во панелей
quantity: int          # кол-во секций этого типа
glass_type: str
painting_type: str     # 'RAL стандарт' | 'RAL нестандарт' | 'Анодированный' | 'Без окрашивания'
ral_color: str | None
corner_left: bool
corner_right: bool
external_width: float | None

# СЛАЙД
rails: int | None          # 3 или 5
threshold: str | None
first_panel_inside: str | None
unused_track: str | None
inter_glass_profile: str | None
profile_left: str | None
profile_right: str | None
lock: str | None
handle: str | None
floor_latches_left: bool
floor_latches_right: bool
handle_offset: int | None

# КНИЖКА
doors: int | None
door_side: str | None      # 'лев.' | 'пр.'
door_type: int | None      # тип 1-7
door_opening: str | None
compensator: str | None
angle_left: float | None
angle_right: float | None
book_system: str | None    # 'B25' | 'B16' | 'B17' | 'C16' | 'C17'
```

---

## API ENDPOINTS

```
POST   /api/auth/login          → { access_token, user }
GET    /api/auth/me             → User (текущий пользователь)
POST   /api/auth/logout         → {}

GET    /api/users               → [User] (admin)
POST   /api/users               → User (admin)
GET    /api/users/{id}          → User (admin)
PUT    /api/users/{id}          → User (admin)
DELETE /api/users/{id}          → {} (admin)
POST   /api/users/{id}/reset-password → { new_password } (admin)

GET    /api/projects            → [Project] (свои / все для admin)
POST   /api/projects            → Project
GET    /api/projects/{id}       → Project
PUT    /api/projects/{id}       → Project
DELETE /api/projects/{id}       → {}

GET    /api/projects/{id}/sections      → [Section]
POST   /api/projects/{id}/sections      → Section
PUT    /api/projects/{id}/sections/{sid}→ Section
DELETE /api/projects/{id}/sections/{sid}→ {}

GET    /api/projects/{id}/calculate     → { components } (КНИЖКА: движок расчёта)
```

---

## ПЛАН РАБОТ

### ✅ Фаза 0: Фронтенд скелет (дизайнер сделал)
- [x] React + TypeScript + Vite + Tailwind
- [x] Login UI
- [x] Список проектов UI
- [x] Редактор проекта UI (частично)
- [x] Дизайн-система

### 🔨 Фаза 1: Бэкенд (СТРОИМ СЕЙЧАС)
- [ ] FastAPI приложение (main.py + CORS)
- [ ] SQLAlchemy + SQLite (database.py)
- [ ] Модели (User, Project, Section)
- [ ] Pydantic схемы
- [ ] JWT авторизация (login, me, logout)
- [ ] CRUD пользователей (admin only)
- [ ] CRUD проектов (с фильтрацией по роли)
- [ ] CRUD секций
- [ ] Seed: первый superadmin при старте
- [ ] requirements.txt

### 🔨 Фаза 2: Подключение фронта к бэку (ПОСЛЕ БЭКА)
- [ ] react-router-dom (маршруты)
- [ ] axios client + JWT interceptors
- [ ] Zustand authStore
- [ ] Реальный login (убрать mock)
- [ ] Загрузка проектов из API
- [ ] Сохранение проектов/секций через API
- [ ] AdminPage (/admin)

### 🔜 Фаза 3: КНИЖКА расчёт
- [ ] Эндпоинт /calculate подключает engine/comp_calc.py
- [ ] Фронт: реальный расчёт компонентов в форме КНИЖКА

### 🔜 Фаза 4: PDF документы
- [ ] ReportLab: производственный лист
- [ ] ReportLab: накладная, заказ стекла, заявка в покраску

### 🔜 Фаза 5: Доп. фичи
- [ ] Копирование проекта
- [ ] Пагинация (реальная)
- [ ] Docker production setup

---

## ТЕХНИЧЕСКИЙ СТЕК (ФИНАЛ)

```
Backend:
  Python 3.12
  FastAPI + Uvicorn
  SQLAlchemy 2.x
  Pydantic v2
  python-jose[cryptography] (JWT)
  passlib[bcrypt] (пароли)
  ReportLab (PDF)
  SQLite (MVP)

Frontend (уже установлено):
  React 19 + TypeScript + Vite 6
  Tailwind CSS 4 + motion (Framer Motion v12)
  Lucide React

Frontend (добавляем):
  react-router-dom
  axios
  zustand

Deploy:
  Docker + docker-compose
  nginx reverse proxy
```

---

## ЦВЕТА И ДИЗАЙН-СИСТЕМА (из существующего кода)

```
bg-dark:     #050a0c
bg-card:     #1a4b54
bg-teal:     #2a7a8a
accent:      #4fd1c5
success:     #00b894
success-hover: #00d1a7
red:         #ef4444 (delete actions)
border:      #2a7a8a/20 (прозрачный)
text-muted:  white/40
```

Все компоненты: rounded-2xl / rounded-[2rem], backdrop-blur, glassmorphism.
