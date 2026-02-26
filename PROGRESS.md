# Ралюма — Статус проекта

> Последнее обновление: 2026-02-26

---

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Zustand, Axios, lucide-react |
| Backend | FastAPI, SQLAlchemy (ORM), SQLite, bcrypt, python-jose (JWT) |
| Инфра | Docker Compose, Caddy (reverse proxy + auto-SSL), GitHub → прямой деплой через git push |

---

## Архитектура

```
mamajan/
└── Raluma/
    ├── backend/
    │   ├── main.py           — FastAPI app, lifespan, CORS, /health
    │   ├── models.py         — SQLAlchemy модели: User, Project, Section
    │   ├── schemas.py        — Pydantic схемы (in/out)
    │   ├── database.py       — SQLite engine, SessionLocal, Base
    │   ├── auth.py           — JWT, bcrypt, get_current_user, require_admin
    │   └── api/
    │       ├── auth.py       — POST /api/auth/login, GET /api/auth/me
    │       ├── projects.py   — CRUD + copy /api/projects
    │       ├── sections.py   — CRUD /api/projects/{id}/sections
    │       └── users.py      — CRUD + reset-password /api/users
    └── src/
        ├── App.tsx           — Роутер, LoginPage, ProjectsPage, EditorPage
        ├── main.tsx          — StrictMode + BrowserRouter root
        ├── api/
        │   ├── client.ts     — Axios instance + JWT interceptor + 401→redirect
        │   ├── auth.ts       — login(), getMe()
        │   ├── projects.ts   — CRUD проектов и секций
        │   └── users.ts      — CRUD пользователей + resetPassword
        ├── store/
        │   ├── authStore.ts  — Zustand: user, token, setAuth, clearAuth, isAdmin, isSuperAdmin
        │   └── toastStore.ts — Zustand: toast очередь (success/error/info), auto-dismiss 4.5s
        ├── components/
        │   ├── ProjectEditor.tsx — Редактор секций (СЛАЙД/КНИЖКА/ЛИФТ/ЦС/ДВЕРЬ)
        │   └── Toast.tsx         — Toast-контейнер с анимациями и прогресс-баром
        └── pages/
            └── AdminPage.tsx — Управление пользователями (admin/superadmin)
```

---

## База данных

### User
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| username | String UNIQUE | Логин |
| password_hash | String | bcrypt |
| display_name | String | Имя для отображения |
| role | String | user \| admin \| superadmin |
| customer | String? | Привязка к организации |
| is_active | Boolean | Активен ли аккаунт |
| created_at | DateTime | |
| last_login | DateTime? | |

### Project
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| number | String | Номер проекта |
| customer | String | ПРОЗРАЧНЫЕ РЕШЕНИЯ \| КРОКНА ИНЖИНИРИНГ \| СТУДИЯ СПК |
| system | String | СЛАЙД \| КНИЖКА \| ЛИФТ \| ЦС \| ДВЕРЬ |
| subtype | String? | Подтип системы |
| created_at | DateTime | |
| updated_at | DateTime | auto-onupdate |
| created_by | Integer FK→users | |

### Section
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| project_id | Integer FK+INDEX | |
| order | Integer | Порядок секции |
| name | String | Название секции |
| width | Float | Ширина, мм |
| height | Float | Высота, мм |
| panels | Integer | Кол-во панелей |
| quantity | Integer | Кол-во секций |
| glass_type | String | Тип стекла |
| painting_type | String | RAL стандарт \| нестандарт \| Анодированный \| Без окрашивания |
| ral_color | String? | RAL код |
| corner_left/right | Boolean | Угловое примыкание |
| external_width | Float? | Внешняя ширина |
| **СЛАЙД** | | |
| rails | Integer? | 3 или 5 рядов |
| threshold | String? | Порог |
| first_panel_inside | String? | Слева \| Справа |
| unused_track | String? | Без \| Внешний \| Внутренний |
| inter_glass_profile | String? | |
| profile_left/right | String? | |
| lock | String? | Замок |
| handle | String? | Ручка |
| floor_latches_left/right | Boolean | Напольные фиксаторы |
| handle_offset | Integer? | Смещение ручки |
| **КНИЖКА** | | |
| doors | Integer? | Кол-во дверей |
| door_side | String? | Левая \| Правая |
| door_type | String? | |
| door_opening | String? | Внутрь \| Наружу |
| compensator | String? | |
| angle_left/right | Float? | Угол |
| book_system | String? | B25 \| B16 \| B17 \| C16 \| C17 |
| **ДВЕРЬ/ЦС** | | |
| door_system | String? | Одностворчатая \| Двустворчатая |
| cs_shape | String? | Треугольник \| Прямоугольник \| Трапеция \| Сложная форма |
| cs_width2 | Float? | Вторая ширина (трапеция) |

---

## API Эндпоинты

### Auth (`/api/auth`)
| Метод | URL | Auth | Описание |
|-------|-----|------|----------|
| POST | `/api/auth/login` | — | Логин, возвращает JWT |
| GET | `/api/auth/me` | JWT | Текущий пользователь |

### Projects (`/api/projects`)
| Метод | URL | Auth | Описание |
|-------|-----|------|----------|
| GET | `/api/projects` | JWT | Список проектов (user → свои, admin → все) |
| POST | `/api/projects` | JWT | Создать проект |
| GET | `/api/projects/{id}` | JWT | Проект + секции |
| PUT | `/api/projects/{id}` | JWT | Обновить проект |
| DELETE | `/api/projects/{id}` | JWT | Удалить проект (cascade секции) |
| POST | `/api/projects/{id}/copy` | JWT | Копировать проект со всеми секциями |

### Sections (`/api/projects/{id}/sections`)
| Метод | URL | Auth | Описание |
|-------|-----|------|----------|
| GET | `…/sections` | JWT | Список секций (sorted by order) |
| POST | `…/sections` | JWT | Создать секцию (auto order = max+1) |
| PUT | `…/sections/{sid}` | JWT | Обновить секцию |
| DELETE | `…/sections/{sid}` | JWT | Удалить секцию |

### Users (`/api/users`)
| Метод | URL | Auth | Описание |
|-------|-----|------|----------|
| GET | `/api/users` | admin+ | Список пользователей |
| POST | `/api/users` | admin+ | Создать пользователя |
| GET | `/api/users/{id}` | admin+ | Получить пользователя |
| PUT | `/api/users/{id}` | admin+ | Обновить пользователя |
| DELETE | `/api/users/{id}` | admin+ | Удалить пользователя |
| POST | `/api/users/{id}/reset-password` | admin+ | Сгенерировать новый пароль |

### System
| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/health` | Health check (DB ping → 200 OK / 503 Error) |

---

## Права доступа

| Роль | Проекты | Пользователи |
|------|---------|-------------|
| user | Только свои | — |
| admin | Все | Создавать/редактировать user |
| superadmin | Все | Все включая admin |

---

## Frontend — Страницы и компоненты

### `LoginPage` (`/login`)
- Форма логин/пароль
- JWT сохраняется в localStorage
- Редирект на `/` после успеха
- Анимация кнопки (loading spinner)

### `ProjectsPage` (`/`)
- Таблица проектов с фильтром по системе и поиском по номеру/заказчику
- Skeleton-строки при загрузке (6 штук)
- Inline-переименование двойным кликом на номер
- Кнопки: копировать, удалить (с модалом подтверждения)
- Кнопка "Новый проект" → модал с выбором типа/подтипа/заказчика
- Защита от двойного клика (`isCreating` state)
- Счётчик "Показано X из Y"
- Кнопка "Выйти" в навбаре

### `ProjectEditor` (`/projects/:id`)
- Сайдбар со списком секций
- Кнопка добавления секции
- Вкладки: Основное / Система / Фурнитура (зависит от типа системы)
- SVG-превью секции для СЛАЙД
- Кнопка "Сохранить секцию":
  - Желтая (`amber`) + текст "Сохранить изменения" при наличии несохранённых изменений
  - Зелёная (`#00b894`) + текст "Сохранить секцию" когда изменений нет
  - Спиннер во время сохранения
- Ctrl+S / ⌘+S → сохранить активную секцию
- `beforeunload` — предупреждение при закрытии вкладки с несохранёнными изменениями
- Toast-уведомления при успехе/ошибке (не блокирующие)
- Кнопка "Выйти" / "Сохранить и выйти" в хедере (адаптируется по isDirty)
- Кнопка "Производственный лист" → PreviewModal

### `AdminPage` (`/admin`)
- Таблица пользователей с поиском
- Создание/редактирование пользователей в модале
- Удаление с подтверждением
- Сброс пароля → показ нового пароля с кнопкой копирования
- Массовое добавление (bulk create из текстового поля)
- Toast при ошибках, state для отображения ошибки в таблице

### `Toast` (глобальный)
- Очередь до N тостов в правом нижнем углу
- Типы: success (зелёный), error (красный), info (бирюзовый)
- Прогресс-бар автозакрытия (4.5 сек)
- Кнопка ручного закрытия
- Spring-анимация появления/исчезновения

---

## Системы секций

| Система | Вкладки | Особенности |
|---------|---------|-------------|
| СЛАЙД | Основное, Система, Фурнитура | Рейки 3/5, SVG-превью, замок, ручка, напольные фиксаторы |
| КНИЖКА | Основное, Система | Двери, сторона, угол, система (B25/B16/B17/C16/C17) |
| ЛИФТ | Основное, Система | Кол-во панелей |
| ЦС | Основное, Форма | Треугольник/Прямоугольник/Трапеция/Сложная форма |
| ДВЕРЬ | Основное, Система | Одностворчатая/Двустворчатая, направление открывания |

---

## История изменений

### 2026-02-26 — Рефакторинг: система на секцию
- `backend/models.py` — `Section.system` (nullable), `Project.system` → nullable (legacy)
- `backend/schemas.py` — `SectionBase.system: Optional[str]`, `ProjectBase.system: Optional[str]`
- `backend/main.py` — миграция `ALTER TABLE sections ADD COLUMN system`, data migration из project.system
- `src/api/projects.ts` — `SectionOut.system?: string`, `createProject` только `number`+`customer`
- `src/App.tsx` — убраны: фильтр систем, колонка "Система", выбор системы/подтипа при создании; таблица 4 колонки
- `src/components/ProjectEditor.tsx`:
  - Система выбирается при создании секции (picker в сайдбаре по кнопке +)
  - Вкладки убраны — всё на одной прокручиваемой странице
  - Секции в сайдбаре показывают цветной бейдж системы
  - Проект может содержать секции разных систем одновременно

### 2026-02-26 — Мобильная адаптация
- `Toast.tsx` — полная ширина на мобиле (`bottom-4 right-4`, `w-[calc(100vw-2rem)]`)
- `App.tsx`:
  - Navbar: иконки без текста на мобиле, аватар без имени/роли
  - Таблица: уменьшен padding (`px-3 py-4`), скрыты Заказчик/Дата на мобиле, действия всегда видны
  - Модал создания: `p-5 sm:p-10`, `overflow-y-auto max-h-[95vh]`
- `ProjectEditor.tsx`:
  - Хедер: компактный на мобиле (иконки без текста, номер проекта без деталей)
  - Кнопка переключения sidebar (`<ClipboardList>`) в хедере на мобиле
  - Body: `flex-col sm:flex-row` — сайдбар или редактор (mobile two-panel nav)
  - Сайдбар: кнопка «Редактировать» в нижней части
  - Пустое состояние: кнопка «Открыть секции» на мобиле
  - Все вкладки: `grid-cols-1` → `sm:grid-cols-2` (MainTab, SlideSystemTab, SlideHardwareTab, BookSystemTab, LiftSystemTab, DoorSystemTab)
  - SVG схема: `overflow-x-auto` + `min-w-[360px]`
  - Контентная карточка: `p-4 sm:p-8`, `rounded-2xl sm:rounded-[2rem]`
- `AdminPage.tsx`:
  - Toolbar: `flex-col sm:flex-row`, кнопка «Массовое» — только иконка на мобиле
  - Таблица: уменьшен padding, скрыты Имя/Заказчик/Статус на мобиле
  - Модал редактирования: `p-6 sm:p-10`, `max-h-[95vh]`

### 2026-02-26 — Аудит + полировка
**Backend:**
- `sections.py` — заменить `count()` на `func.max(order) + 1` (корректный порядок после удалений)
- `models.py` — `index=True` на `Section.project_id` (устраняет full scan)
- `main.py` — `/health` делает `SELECT 1`; возвращает HTTP 503 при падении БД

**Frontend:**
- `Toast.tsx` + `toastStore.ts` — глобальная toast-система, все `alert()` заменены
- `App.tsx` — skeleton-строки вместо "Загрузка...", `toast.error/success` везде
- `ProjectEditor.tsx`:
  - `isDirty` state — отслеживание несохранённых изменений
  - Кнопка "Сохранить" желтеет при `isDirty`
  - Ctrl+S / ⌘+S для быстрого сохранения
  - `beforeunload` — предупреждение при уходе со страницы с несохранёнными данными
  - `handleAddSection` — больше не добавляет `tmp-` секцию при ошибке API
  - `handleDeleteSection` — toast при ошибке вместо silent catch
- `AdminPage.tsx` — `loadError` state + toast при всех операциях

### 2026-01-xx — Ранние версии
- Базовая аутентификация JWT
- CRUD проектов и секций
- Редактор секций для всех 5 систем
- Роли пользователей (user/admin/superadmin)
- Копирование проектов
- Caddy reverse proxy + auto-SSL
- Docker Compose деплой
- Восстановление сессии при перезагрузке (`/api/auth/me` on init)

---

## Что ещё можно сделать (backlog)

- [ ] Автосохранение секции при переключении на другую (дебаунс или prompt)
- [ ] Пагинация/виртуальный список при большом количестве проектов
- [ ] Экспорт в PDF (производственный лист уже есть UI, нет бэкенда)
- [ ] История изменений секции
- [ ] Миграции через Alembic (сейчас — ручные ALTER TABLE в lifespan)
- [ ] Тесты (pytest для API, Playwright для E2E)
- [ ] Refresh token (сейчас JWT без expiry refresh)
