# Mamajan / Raluma — Полный отчёт по проекту

> Дата: 2026-03-21

---

## 1. Что это

**Raluma** — внутренняя ERP-система для производства стеклянных безрамных перегородок. Заменяет устаревший испанский конфигуратор AppGlass (JSF, Java, 2016 года) собственным современным веб-приложением.

**Назначение:** конфигурация секций перегородок (5 систем), расчёт комплектующих и стёкол, отслеживание статусов производства, генерация документов (спецификации, накладные).

**Домен:** [raluma.tech](https://raluma.tech)
**Сервер:** 89.111.142.17 (VPS, Docker Compose + Caddy auto-SSL)

---

## 2. Стек

| Слой | Технологии |
|------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Zustand, Axios |
| Backend | FastAPI, SQLAlchemy, SQLite, bcrypt, python-jose (JWT) |
| Инфра | Docker Compose, Caddy (reverse proxy + auto-SSL), GitHub Actions CI |
| Скрапинг | Python, Selenium, requests (реверс-инжиниринг AppGlass) |
| Расчёты | Python (engine/) — формулы из AppGlass, верифицированные на 164 проектах |

---

## 3. Текущая структура репозитория

```
mamajan/                          ← корень git-репозитория
├── raluma/                       ← ПРИЛОЖЕНИЕ (основной продукт)
│   ├── backend/                  ← FastAPI бэкенд
│   │   ├── main.py               — app, lifespan, миграции ALTER TABLE
│   │   ├── models.py             — SQLAlchemy: User, Project, Section
│   │   ├── schemas.py            — Pydantic in/out схемы
│   │   ├── database.py           — SQLite engine + SessionLocal
│   │   ├── auth.py               — JWT + bcrypt
│   │   └── api/                  — роутеры (auth, users, projects, sections)
│   ├── src/                      ← React фронтенд
│   │   ├── App.tsx               — роутер, страница проектов, логин
│   │   ├── components/
│   │   │   ├── ProjectEditor.tsx  — редактор секций (~2050 строк)
│   │   │   ├── Toast.tsx          — уведомления
│   │   │   └── editor/            — вынесенные компоненты (types, tabs, SVG)
│   │   ├── api/                  — axios клиент + API-функции
│   │   ├── store/                — Zustand (auth, toast)
│   │   └── pages/AdminPage.tsx   — управление пользователями
│   ├── tests/                    — pytest (22 теста)
│   ├── scripts/backup.sh         — ежедневный бэкап SQLite (cron)
│   ├── docker-compose.yml        — backend + frontend контейнеры
│   ├── Dockerfile                — multi-stage (node build → caddy)
│   └── Caddyfile                 — reverse proxy конфиг
│
├── engine/                       ← РАСЧЁТНЫЙ ДВИЖОК (из AppGlass)
│   ├── comp_calc.py              — расчёт 19 типов комплектующих (5 систем)
│   ├── glass_calc.py             — расчёт размеров стёкол
│   ├── verify.py                 — верификация стёкол на 164 проектах
│   └── verify_comps.py           — верификация комплектующих
│
├── scraper/                      ← СКРАПЕР AppGlass (~80 скриптов)
│   ├── step1_login.py ... step51_formulas.py  — пошаговый парсинг
│   └── tmp_*.py                  — одноразовые скрипты анализа
│
├── output/                       ← СОБРАННЫЕ ДАННЫЕ (~300+ файлов)
│   ├── s*_*.json/html/png        — дампы страниц, скриншоты, JSON
│   ├── s*_*.pdf                  — скачанные PDF-проекты
│   └── pdfs/                     — доп. PDF
│
├── docs/                         ← ДОКУМЕНТАЦИЯ / ТЗ AppGlass
│   ├── 01_app_structure.md       — реверс-инжиниринг AppGlass (JSF, формы, диалоги)
│   ├── 02_project_workflow.md    — флоу работы с проектом в AppGlass (740 строк)
│   ├── 03_formulas.md            — ВСЕ формулы расчётов (19 артикулов, 5 систем)
│   ├── 04_pdf_format.md          — структура PDF-отчётов AppGlass
│   ├── 05_data_collection.md     — результаты массового скачивания
│   ├── 06_old_projects.md        — анализ 300 проектов базы
│   ├── 07_components_accuracy.md — точность формул (84.6%)
│   ├── 08_clone_spec.md          — спецификация клона (React + FastAPI)
│   ├── 09_dev_plan.md            — план разработки
│   ├── 10_ui_flow.md             — UI маршрутизация
│   ├── 11_progress.md            — прогресс на 2026-02-25
│   ├── REPORT_2026-02-25.md      — итоговый отчёт по реверсу AppGlass
│   └── TODO.md                   — дорожная карта (формулы, верификация)
│
├── tz/                           ← ТЕХНИЧЕСКИЕ ЗАДАНИЯ
│   ├── done/                     — выполненные (ТЗ1-6 + структура)
│   ├── ТЗ правки 01.03..docx.pdf
│   └── ПРАВКИ 02.03.26.pdf
│
├── analytics/                    ← АНАЛИТИКА (пустая, создана для будущего)
├── PROGRESS.md                   — документация проекта Raluma (устаревшая)
├── APPGLASS_REPORT.md            — 53KB отчёт по AppGlass
├── CLAUDE.md                     — инструкции для Claude
├── .gitignore
├── .github/workflows/ci.yml      — GitHub Actions (lint + test)
└── .pre-commit-config.yaml       — pre-commit (ruff + tsc + eslint)
```

### Мусор (удалить):
- `output;C/` — пустая папка (ошибка Windows)
- `scraper;C/` — пустая папка (ошибка Windows)
- `nul` — пустой файл (артефакт Windows)

---

## 4. Что сделано — AppGlass (реверс-инжиниринг)

### 4.1. Скрапинг
- Полный реверс-инжиниринг испанского JSF-приложения AppGlass 2.65.72
- 51 итерация скрапинга (step1 → step51), каждая раскрывает новый слой
- Спаршено 300+ проектов, скачано 164 PDF с реальными данными
- Извлечены все формы, диалоги, AJAX-обработчики, HTTP POST-цепочки

### 4.2. Формулы (engine/)
- **19 типов комплектующих** реализованы в `comp_calc.py`
- **Размеры стёкол** реализованы в `glass_calc.py`
- **5 систем**: B25, B17, C17, B16, C16
- **Верификация**: 164 реальных проекта
- **Общая точность**: 84.6% (от 32% у FD3110 С17 до 100% у D0001)

### 4.3. Документация
- 13 документов в `docs/` (~3500 строк)
- Полная спецификация формул, UI-флоу, PDF-формата
- Итоговый отчёт (`REPORT_2026-02-25.md`, 307 строк)

---

## 5. Что сделано — Raluma (приложение)

### 5.1. Бэкенд (FastAPI)
- JWT-авторизация (login, me, роли user/admin/superadmin)
- CRUD: пользователи, проекты, секции
- Копирование проектов (со всеми секциями)
- Миграции через ALTER TABLE в lifespan (без Alembic)
- Health check (`/health`)
- 22 теста (pytest), 100% pass

### 5.2. Фронтенд (React)
- **Логин** — JWT в localStorage, редирект
- **Список проектов** — таблица с поиском, вкладки Текущие/Архив
  - Колонки: Проект, Заказчик, Дата, Этап, Статус, Стекла, Покраска, Действия
  - Inline-переименование, копирование, удаление
  - Skeleton-загрузка, счётчик
- **Редактор проекта** — основной экран работы:
  - Сайдбар секций (цветные акценты по типу системы)
  - Формы для 5 систем: СЛАЙД, КНИЖКА, ЛИФТ, ЦС, КОМПЛЕКТАЦИЯ
  - SVG-схемы: вид сверху + вид из помещения (sticky справа на xl+)
  - Статусы производства (Статус / Стекла / Покраска) с датами
  - Заказ доп. комплектующих (таблица позиций)
  - Примечания к проекту
  - Ctrl+S сохранение, guard несохранённых изменений
  - Кнопки документов: Спецификация, Накладная, Заказ стекла, Заявка покраски (заглушки)
- **Админка** — CRUD пользователей, сброс пароля, массовое создание
- **Toast** — неблокирующие уведомления с прогресс-баром

### 5.3. Реализованные ТЗ
| ТЗ | Описание | Статус |
|----|----------|--------|
| ТЗ1 | Форма СЛАЙД (рельсы, порог, фурнитура) | Done |
| ТЗ2 | SVG схема вид сверху (УЛИЦА/ПОМЕЩЕНИЕ) | Done |
| ТЗ3 | Примечания, нумерация секций, навигация | Done |
| ТЗ4 | SVG сечения профилей на схеме | Done |
| ТЗ5 | Статусы производства, стекло, покраска | Done |
| ТЗ6 | Логика замков/ручек, взаимоисключение | Done |
| Правки 01.03 | Артикулы, SVG, панели, компактность | Done |
| Правки 02.03 | Вкладки Архив, документы, порядок схем | Done |

### 5.4. UI/UX улучшения (последние)
- Side-by-side layout: форма слева, SVG-схемы sticky справа (xl+)
- ProfileCheckbox → pill-кнопки (подсветка при активации)
- Кол-во панелей → ToggleGroup 1-5 вместо select
- Цветные акценты в сайдбаре по типу системы (СЛАЙД=синий, КНИЖКА=зелёный, ...)
- Кнопки действий в таблице проектов — всегда чуть видны
- Увеличена видимость профилей на SVG-схемах
- Компактная форма (уменьшен padding)
- Боковая панель сужена (300→260px)

### 5.5. Инфраструктура
- Docker Compose (backend + frontend контейнеры)
- Caddy reverse proxy + auto-SSL (raluma.tech)
- GitHub Actions CI (tsc + eslint + ruff + pytest)
- pre-commit hooks (ruff + tsc)
- Ежедневный бэкап SQLite (cron, 30 дней хранения)
- Ротация логов (logrotate)

---

## 6. База данных

### User
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| username | String UNIQUE | Логин |
| password_hash | String | bcrypt |
| display_name | String | ФИО |
| role | String | user / admin / superadmin |
| customer | String? | Организация |
| is_active | Boolean | |

### Project
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| number | String | Номер проекта |
| customer | String | Заказчик |
| status | String | РАСЧЕТ / В работе / Запущен / Готов / ... / Архив |
| production_stages | Integer | 1 или 2 этапа |
| current_stage | Integer | Текущий этап |
| glass_status | String | Без стекла / Заказаны / В цеху |
| paint_status | String | Без покраски / Задание / Отгружен / Получен |
| glass_invoice, glass_ready_date | String? | Счёт и дата |
| paint_ship_date, paint_received_date | String? | Даты покраски |
| extra_parts, comments | Text? | Примечания проекта |
| order_items | JSON? | Заказ доп. комплектующих |

### Section
| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer PK | |
| project_id | FK → projects | |
| system | String | СЛАЙД / КНИЖКА / ЛИФТ / ЦС / КОМПЛЕКТАЦИЯ |
| name, order | String, Integer | Название и порядок |
| width, height, panels, quantity | Float/Int | Размеры |
| glass_type, painting_type, ral_color | String | Стекло и покраска |
| rails, threshold, first_panel_inside | | СЛАЙД-параметры |
| profile_left/right_wall/lock_bar/p_bar/handle_bar/bubble | Boolean | Профили |
| lock_left/right, handle_left/right | String? | Замки, ручки |
| floor_latches_left/right | Boolean | Защёлки |
| doors, door_side, door_type, door_opening | | КНИЖКА/ДВЕРЬ |
| cs_shape, cs_width2 | | ЦС-параметры |
| extra_parts, comments | Text? | Примечания секции |

---

## 7. API

| Группа | Эндпоинты |
|--------|-----------|
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Projects | `GET/POST/PUT/DELETE /api/projects`, `POST /copy` |
| Sections | `GET/POST/PUT/DELETE /api/projects/{id}/sections` |
| Users | `GET/POST/PUT/DELETE /api/users`, `POST /reset-password` |
| System | `GET /health` |

---

## 8. Что НЕ сделано (бэклог)

### Приоритет 1 — Функционал
- [ ] Подключить расчёты из engine/ на фронтенд (формулы комплектующих + стёкол)
- [ ] PDF-генерация (Спецификация, Накладная, Заказ стекла, Заявка покраски)
- [ ] Парсинг прайсов поставщика (обновление цен)

### Приоритет 2 — Расширение
- [ ] Аккаунт менеджера (воронка, задачи, клиенты)
- [ ] Складской учёт (остатки, движение, приход/расход)
- [ ] История изменений секции (версионирование)

### Приоритет 3 — Техдолг
- [ ] Alembic вместо ручных ALTER TABLE миграций
- [ ] Rate limiting на /api/auth/login
- [ ] JWT в httpOnly cookie
- [ ] E2E тесты (Playwright)
- [ ] Разбить ProjectEditor.tsx на подкомпоненты
- [ ] Пагинация проектов

---

## 9. Предстоящая реструктуризация

### Цель: убрать грязь, централизовать

**Удалить мусор:**
- `output;C/`, `scraper;C/`, `nul`

**Создать `appglass/` — всё, связанное с AppGlass:**
- `scraper/` → `appglass/scraper/`
- `output/` → `appglass/output/`
- `engine/` → `appglass/engine/`
- `APPGLASS_REPORT.md` → `appglass/REPORT.md`
- `docs/01-07, REPORT` → `appglass/docs/` (реверс-инжиниринг документы)

**Добавить `appglass/` в `.gitignore`** — эти данные не нужны в git

**Оставить в `docs/`:**
- `08_clone_spec.md` — спека Raluma
- `09_dev_plan.md` — план разработки Raluma
- `10_ui_flow.md` — UI Raluma
- `11_progress.md` — прогресс Raluma
- `TODO.md` — дорожная карта

**`tz/`** — оставить как есть

**Итоговая чистая структура:**
```
mamajan/
├── raluma/           ← приложение
├── appglass/         ← всё от AppGlass (в .gitignore)
│   ├── scraper/
│   ├── output/
│   ├── engine/
│   ├── docs/
│   └── REPORT.md
├── docs/             ← документация Raluma
├── tz/               ← техзадания
├── analytics/        ← аналитика (будущее)
├── PROGRESS.md
├── CLAUDE.md
└── .gitignore
```

---

## 10. Оценка проекта

### Объём выполненной работы
| Блок | Часы (оценка) |
|------|--------------|
| Реверс-инжиниринг AppGlass | ~120 ч |
| Расчётный движок + верификация | ~60 ч |
| Бэкенд (FastAPI + API + auth) | ~40 ч |
| Фронтенд (React + редактор + SVG) | ~150 ч |
| Инфра (Docker, CI, деплой) | ~20 ч |
| ТЗ1-6 + правки | ~80 ч |
| UI/UX полировка | ~30 ч |
| **Итого** | **~500 ч** |

### Рыночная стоимость
- Фрилансер (2-4 т.р./ч): **1–2M руб.**
- Агентство: **3–5M руб.**
- С учётом расширений (расчёты, менеджер, склад): **4–8M руб.**
