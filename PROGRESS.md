# Ралюма — Статус проекта

> Последнее обновление: 2026-03-09 (вечер)

---

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Zustand, Axios, lucide-react |
| Backend | FastAPI, SQLAlchemy (ORM), SQLite, bcrypt, python-jose (JWT) |
| Инфра | Docker Compose, Caddy (reverse proxy + auto-SSL), GitHub Actions CI, pre-commit hooks |

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
    ├── tests/
    │   ├── conftest.py       — фикстуры: client, admin_headers, project, section
    │   ├── test_health.py    — 1 тест
    │   ├── test_auth.py      — 6 тестов
    │   ├── test_projects.py  — 8 тестов
    │   └── test_sections.py  — 7 тестов
    ├── pytest.ini            — testpaths, pythonpath
    ├── requirements-dev.txt  — pytest + httpx
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
        │   ├── ProjectEditor.tsx — Редактор секций (СЛАЙД/КНИЖКА/ЛИФТ/ЦС/ДВЕРЬ) — 1046 строк
        │   ├── editor/
        │   │   ├── types.ts          — Section, OrderItem, интерфейсы, стилевые константы, цвета систем
        │   │   ├── converters.ts     — apiToLocal(), localToApi()
        │   │   ├── FormInputs.tsx    — Checkbox, ToggleGroup, RadioList, SectionDivider, ProfileCheckbox
        │   │   ├── FormTabs.tsx      — MainTab, SlideSystemTab, BookSystemTab, LiftSystemTab, CsShapeTab, DoorSystemTab
        │   │   └── SlideDiagrams.tsx — SlideSchemeSVG, SlideRoomViewSVG
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

### 2026-03-01 — ТЗ1, ТЗ2, ТЗ3, ТЗ4, ТЗ5, ТЗ6

#### ТЗ1 — Правки формы СЛАЙД
- **Неиспользуемый рельс**: переименован из "Свободная нить", перемещён в левую колонку после "Кол-во панелей", опции изменены на `['Внутренний', 'Внешний', 'Нет']`
- **Порог**: перемещён в правую колонку перед межстекольным профилем
- **Угловое соединение**: скрыто через `{false && ...}` (данные сохраняются в модели)
- **Кнопка "← К проекту"**: в шапке редактора секции — возвращает на экран пикера систем без выхода из проекта

#### ТЗ2 — Схема вид сверху (SlideSchemeSVG)
- Полная переработка SVG-компонента `SlideSchemeSVG`
- Метки **УЛИЦА** (снаружи) / **ПОМЕЩЕНИЕ** (изнутри)
- Корректное распределение панелей по рельсам с учётом `unusedTrack`
- Неиспользуемый рельс — пунктирная серая линия с подписью
- Стрелка направления сдвига
- Вертикальные перемычки для межстекольного профиля RS1061

#### ТЗ3 — Примечания, нумерация, навигация
- **Поля секции**: `extra_parts` и `comments` добавлены в модель `Section`, схему Pydantic, миграции, фронтенд-интерфейс и форму секции (для всех систем)
- **Нумерация при удалении**: `handleAddSection` использует `maxNum` вместо `sections.length` (нет дублей после удаления)
- **Backend order**: `sections.py` использует `func.max(order) + 1` вместо `count()` — корректный порядок после удалений

#### ТЗ4 — Боковые профили на схеме сверху
- Функции `drawLeftProfiles` / `drawRightProfiles` — SVG-сечения профилей для каждого рельса
- **RS1333/1335** (пристеночный) — два прямоугольника
- **RS1081** (профиль-замок) — H-образная форма
- **RS1082** (П-профиль) — L-образная форма
- **RS112** (ручка-профиль) — T-образная форма
- **RS1002** (пузырьковый уплотнитель) — окружность
- Межстекольный профиль **RS1061** — тонкая вертикальная полоса между панелями

#### ТЗ5 — Статусы производства
- **Производственные этапы**: 1 или 2 этапа, переключатель текущего этапа
- **Статус проекта**: 9 значений (Расчёт, В работе, Запущен, Готов, Отгружен и др.)
- **Стекло**: статус + счёт-фактура + ориентир готовности (скрыт для 1-го этапа двухэтапных)
- **Покраска**: статус + даты отгрузки/получения
- **Заказ доп. комплектующих**: таблица с позициями (название, счёт, даты оплаты/доставки)
- **Примечания к проекту**: `extra_parts` и `comments` на уровне проекта
- `App.tsx`: колонки Статус и Покраска в таблице проектов, `colSpan` исправлен 4→6

#### ТЗ6 — Логика фурнитуры СЛАЙД
- **RS112 и RS1002 взаимоисключающие**: клик на один снимает другой
- **RS1081 авто-выбирает RS112**: при включении профиля-замка ручка-профиль выбирается автоматически
- **RS1082 + RS112/RS1002**: с П-профилем можно выбрать только один из двух
- **RS1002 заблокирован при RS1081**: `disabled` когда lockBar активен
- **Видимость замков/ручек**: логика `showLockLeft/Right`, `showNoLock`, `showHandle` пересчитана
- **Переименование замков**: миграция `UPDATE sections SET lock_left/right` — новые названия `ЗАМОК-ЗАЩЕЛКА 1стор` / `ЗАМОК-ЗАЩЕЛКА 2стор с ключом`
- **Отступ под ручку**: поле показывается только при выборе стеклянной ручки или ручки-скобы
- **Предупреждение о пороге**: ⚠ при `threshold = null`

#### Вид из помещения (SlideRoomViewSVG)
- Новый SVG-компонент для СЛАЙД
- Рама с профилями, панели с нумерацией и стрелками сдвига
- Размерные линии: ширина каждой панели, общая ширина, высота

---

### 2026-03-09 — CI/CD, тесты, инфраструктура

#### CI/CD
- **GitHub Actions** (`.github/workflows/ci.yml`): frontend (tsc + eslint) + backend (ruff + pytest) на каждый push/PR в main
- **pre-commit** (`.pre-commit-config.yaml`): ruff + ruff-format для Python, tsc + eslint для TypeScript — блокирует коммит при ошибках
- **ESLint 9** (`eslint.config.js`): flat config с typescript-eslint, react-hooks, react-refresh

#### Тесты (22 теста, 100% pass)
- `tests/conftest.py` — session-scoped TestClient + fixtures; `engine.dispose()` перед удалением test DB (fix Windows PermissionError)
- `test_health.py` — health endpoint
- `test_auth.py` — login success/fail, /me, invalid token
- `test_projects.py` — CRUD + copy + auth guard
- `test_sections.py` — CRUD + order increment after delete + auth guard

#### Рефакторинг ProjectEditor.tsx
- 2160 строк → 1046 строк
- Вынесено в `editor/`: types.ts, converters.ts, FormInputs.tsx, FormTabs.tsx, SlideDiagrams.tsx

#### Инфра сервера
- `scripts/backup.sh` — ежедневный бэкап SQLite (`/var/lib/docker/volumes/raluma_db_data/_data/raluma.db`), хранить 30 дней, логи в `/var/log/raluma-backup.log`
- Cron: `0 3 * * * /opt/mamajan/Raluma/scripts/backup.sh >> /var/log/raluma-backup.log 2>&1`
- `/etc/docker/daemon.json` — лимиты логов контейнеров: `max-size: 10m`, `max-file: 3`
- `/etc/logrotate.d/raluma` — ротация backup.log: еженедельно, 8 недель, compress

---

### 2026-03-09 — Правки по ТЗ (01.03 + 02.03)

#### Главная страница проектов (`App.tsx`)
- **Вкладки Текущие / Архив**: проекты со статусом «Архив» уходят в отдельную вкладку
- **Дата** → показывает `updated_at` (при смене статуса из архива дата обновляется)
- **Заказчики**: в дефолтах dropdown — ООО КРОКНА ИНЖИНИРИНГ, ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ, ООО СТУДИЯ СПК

#### Редактор проекта (`ProjectEditor.tsx`)
- **Кнопки документов** (Спецификация, Накладная и др.) скрываются при открытой секции — видны только на уровне проекта
- **Новые кнопки-заглушки**: Производственный лист, Схема
- **Форма секции**: убраны «Доп. комплектующие», остались только «Комментарии»
- **Порядок схем**: Вид из помещения — первым, Вид сверху — вторым (в обоих местах: inline + sticky sidebar)

#### Форма СЛАЙД (`FormTabs.tsx`)
- **Кол-во панелей**: 3-рельс → опции 1-3; 5-рельс → опции 1-5; при переключении рельс — значение обрезается до допустимого
- **Артикулы обновлены**: RS1333/1335 → RS2333/2335, RS1081 → RS2081, RS1061 → RS2061

#### Схема вид сверху (`SlideDiagrams.tsx`)
- Убраны текстовые метки УЛИЦА / ПОМЕЩЕНИЕ / «неиспользуемый рельс»
- Убрана высота из панелей схемы сверху (высота остаётся только на виде из помещения)
- Стрелка сдвига стала крупнее (длина 130, strokeWidth 2)
- Добавлены ограничительные линии по бокам секции
- **Зеркалирование**: при «1-я панель Слева» — порядок рельсов в панелях инвертируется

---

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

### UX / Frontend
- [ ] Валидация размеров секции — ширина/высота не может быть 0 или отрицательной (добавить `min="1"` на инпуты)
- [ ] Спиннер на большой кнопке сохранения внизу формы секции (сейчас спиннер только в хедере)
- [ ] Автосохранение секции при переключении на другую (дебаунс или prompt) — частично решено модалом, но можно добавить автосохранение по таймеру
- [ ] Пагинация/виртуальный список при большом количестве проектов

### Архитектура
- [ ] Вынести дублирующийся код профилей слева/справа в компонент `ProfilePanel` с параметром `side: 'left' | 'right'`

### Backend
- [ ] Миграции через Alembic (сейчас — ручные ALTER TABLE в lifespan)
- [ ] Rate limiting на `/api/auth/login` (защита от brute-force)
- [ ] Экспорт в PDF / Производственный лист / Схема — кнопки-заглушки, логика не реализована
- [ ] E2E тесты (Playwright)

### Инфра / Безопасность
- [ ] JWT в httpOnly cookie вместо localStorage (защита от XSS) — некритично для внутреннего инструмента
- [ ] Refresh token (сейчас JWT без expiry refresh)
- [ ] История изменений секции
- [ ] Мониторинг (uptime check, алерты)
