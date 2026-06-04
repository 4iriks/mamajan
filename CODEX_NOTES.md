# Codex notes — Raluma

Дата старта заметок: 2026-06-01.

Цель файла: рабочая память по текущему веб-приложению `raluma/`. Сюда фиксируются важные наблюдения, актуальные правила и вопросы, чтобы дальше опираться на них при изменениях кода.

## Текущий фокус

- Работаем с веб-приложением `raluma/`: React + FastAPI.
- Папку/историю клона AppGlass сейчас не анализируем и не используем как рабочий скоуп.
- Материалы AppGlass можно считать только доменным фоном для терминов и формул, если пользователь явно вернёт этот контекст.
- СЛАЙД "2 ряда от центра" считаем ближайшим направлением, но не текущей задачей: сначала будут отдельные правки от заказчика.
- `CODEX_NOTES.md` оставляем как рабочие заметки Codex.

## Актуальные документы

- `CLAUDE.md` — главный актуальный ориентир по структуре, ключевым файлам, соглашениям и производственному листу.
- `for_miro.md` — краткое состояние, проверенное по коду на 2026-03-26, но уже частично устарело по производственному листу.
- `PRESENTATION.md` — полезное презентационное описание текущего состояния, включая PDF/производственный лист и тесты.
- `TODO_FRONTEND.md` — небольшой актуальный список фронтенд-долгов.
- `PROGRESS.md`, `REPORT.md`, `docs/08-11*.md` — исторически полезны, но требуют сверки с кодом перед выводами.

## Архитектура приложения

- Корень git-репозитория: `mamajan/`.
- Основное приложение в git записано как `Raluma/`. На Windows также доступно как `raluma/`; при ссылках и CI лучше учитывать регистр.
- Frontend: React 19, TypeScript, Vite 6, Tailwind 4, Framer Motion через пакет `framer-motion`/`motion` в зависимостях, Zustand, Axios, lucide-react.
- Backend: FastAPI, SQLAlchemy 2, SQLite, Pydantic 2, bcrypt, python-jose JWT, Jinja2, WeasyPrint.
- Деплой: Docker Compose, Caddy как frontend/static server и reverse proxy для `/api/*`.

## Backend

- Точка входа: `raluma/backend/main.py`.
- Модели: `models.py` (`User`, `Project`, `Section`).
- API:
  - `api/auth.py` — login/me.
  - `api/users.py` — CRUD пользователей, reset password.
  - `api/projects.py` — CRUD проектов, copy.
  - `api/sections.py` — CRUD секций.
  - `api/documents.py` — preview/pdf/overrides производственного листа.
- Миграции ручные: `migrations.py`, список `ALTER TABLE` в `_ADD_COLUMNS`.
- При добавлении поля нужно синхронно менять `models.py`, `schemas.py`, `migrations.py`, `src/api/projects.ts`, `editor/types.ts`, `editor/converters.ts`, иногда `copy_project`.

## Frontend

- Роутер: `src/App.tsx`.
- Страницы:
  - `/login` → `pages/LoginPage.tsx`.
  - `/` → `pages/ProjectsPage.tsx`.
  - `/projects/:id` → `components/ProjectEditor.tsx`.
  - `/admin` → `pages/AdminPage.tsx`.
- API-клиент: `src/api/client.ts`, JWT хранится в `localStorage`, 401 редиректит на `/login`.
- Auth state: `src/store/authStore.ts`.
- Toast: `src/store/toastStore.ts` + `components/Toast.tsx`.
- Theme: `src/store/themeStore.ts`, есть light/dark, по умолчанию light.
- `ProjectEditor.tsx` — оркестратор, логика форм вынесена в `src/components/editor/`.
- Создание проекта не выбирает систему. Системы добавляются как секции внутри проекта.
- `ProjectsPage` хранит статусы проекта: производство, этап, стекло, покраска, архив.
- `AdminPage` поддерживает CRUD сотрудников, сброс пароля и массовое создание.
- `SectionFormWrapper` показывает кнопки документов внутри активной секции. Полноценная модалка есть только для "Производственный лист"; остальные документы пока placeholder.

## Производственный лист

- Реализован только для секций `system === "СЛАЙД"`.
- Модалка: `src/components/ProductionSheetModal.tsx`.
- Preview открывается в iframe через `/api/projects/{pid}/sections/{sid}/preview?token=...`.
- Query-token нужен, потому что iframe не передаёт `Authorization: Bearer`.
- Бэкенд preview/pdf:
  - `api/documents.py`.
  - `engine/slide_calc.py`.
  - `engine/pdf.py`.
  - `templates/section_sheet.html`.
- Ручные правки preview сохраняются в `Section.document_overrides` JSON-строкой.
- PDF генерируется через WeasyPrint из того же Jinja2-шаблона.
- `section_sheet.html` содержит собственные SVG-схемы, таблицы, inline JS масштабирования, dirty-state и добавление/удаление строк "Дополнительные комплектующие".
- Актуальный шаблон задаёт `body { width: 206mm }`, а не `287mm` как написано в `CLAUDE.md`.
- PDF-страница 2 с доп. комплектующими появляется только если есть заполненные extra components; в preview она видна всегда для редактирования.

## Расчёт СЛАЙД

- `engine/slide_calc.py` — конкретный расчёт `calculate_slide(section)` для `SLIDE-стандарт 1 ряд`.
- Выход: `SlideCalcResult` с профилями, стеклом, фурнитурой, саморезами, чеклистом, текстами и `panel_rails`.
- В `CLAUDE.md` отмечено: "Стандарт 1 ряд" и "2 ряда от центра" являются разными системами; сейчас реализован только "Стандарт 1 ряд".
- В модели уже есть поля под `slide_rows`, центральную ручку/замок/защёлки, но это не означает готовый расчёт 2 рядов.
- В текущем UI `SlideSystemTab` уже показывает переключатель `1 ряд / 2 ряда` и поля центральных панелей. Это расходится с расчётом: `calculate_slide()` не учитывает полноценную систему 2 рядов.
- В `EditorSidebar` кнопка "2 ряда от центра" фактически вызывает `handleAdd('СЛАЙД', { slideRails: 5 })`, но не выставляет `slideRows: 2`. Новая секция выглядит как 5-рельсовый 1 ряд, пока пользователь сам не переключит "2 ряда" в форме.
- UI для СЛАЙД 1 ряд сейчас предлагает панели от 2, хотя `slide_calc.py` содержит отдельную ветку для `P == 1`.

## Известные долги

- `TODO_FRONTEND.md`:
  - `cornerLeft/cornerRight` и `externalWidth` есть в модели/конвертерах, но не отображаются в UI.
  - У `КНИЖКА` не все дефолты задаются при создании.
  - `rails` в API типизирован как `number`, в локальном `Section` как `3 | 5`.
- `CLAUDE.md`:
  - DIN7504M считается неправильно, ждём правильную формулу.
  - СЛАЙД "2 ряда от центра" не реализован как отдельная система.
  - Нет производственных листов для КНИЖКА/ЛИФТ/ЦС.
  - Alembic, rate limiting, httpOnly cookie — отложенный техдолг.
- `.pre-commit-config.yaml` использует пути `^raluma/backend/` и `cd raluma`, а git хранит папку как `Raluma/`. На Windows это не видно, на регистрозависимой системе regex/пути могут не сработать.
- `CLAUDE.md` местами говорит React 18, а `package.json` сейчас React 19.
- `Raluma/README.md`, `metadata.json` и `vite.config.ts` частично остались от AI Studio/Gemini шаблона (`react-example`, `GEMINI_API_KEY`, AI Studio README). На работу приложения это сейчас не влияет, но как документация устарело.
- Backend предупреждения pytest: Python 3.12 deprecations вокруг `datetime.utcnow()` в моделях/auth/projects и внутри зависимостей.

## Рабочие правила

- Не делать выводы по старым `docs/` без сверки с реальным кодом.
- Не трогать папку клона/AppGlass без явной просьбы.
- При изменении БД соблюдать сквозной чеклист полей.
- При фронтенд-изменениях держаться текущего стиля приложения, а не делать новый дизайн.
- Перед крупными правками полезно запускать `npm run check` и backend pytest, если задача затрагивает соответствующий слой.
- Для задач по производственному листу смотреть связку: `ProductionSheetModal.tsx` → `api/projects.ts` document helpers → `api/documents.py` → `engine/slide_calc.py` → `engine/pdf.py` → `templates/section_sheet.html` → `tests/test_documents.py` + `tests/test_slide_calc.py`.

## Проверенный baseline

- 2026-06-01: `npm.cmd run check` в `Raluma/` проходит без ошибок, есть 17 ESLint warnings.
- 2026-06-01: `pytest -q` в `Raluma/backend/` проходит: 139 passed, 143 warnings.
- 2026-06-04: начата ветка `feature/guest-mode-registration`.
- 2026-06-04: добавлен backend `/api/auth/register` для простой регистрации с автологином через JWT.
- 2026-06-04: добавлены stateless endpoints `/api/projects/local/sections/preview` и `/api/projects/local/sections/pdf` для гостевого производственного листа без записи в БД.
- 2026-06-04: добавлен frontend localStorage-адаптер `src/api/localProjects.ts`; публичный `src/api/projects.ts` сам выбирает backend или localStorage по наличию JWT.
- 2026-06-04: `npm.cmd run typecheck` проходит, `npm.cmd run lint` проходит без errors, 16 warnings.
- 2026-06-04: `/` и `/projects/:id` открыты без обязательного входа; `/admin` остался закрыт за авторизацией.
- 2026-06-04: `LoginPage` теперь поддерживает простую регистрацию (`логин`, `пароль`, опционально `имя`) и кнопку "Продолжить без входа".
- 2026-06-04: после входа при наличии локальных проектов `ProjectsPage` предлагает перенести их в серверный аккаунт; перенос создаёт проекты/секции на backend и чистит localStorage.
- 2026-06-04: добавлен `npm.cmd run smoke:guest` — headless Chrome/Edge smoke без внешних зависимостей. Сценарий: чистый гость → проект → секция СЛАЙД → гостевой производственный лист → регистрация → перенос → cleanup тестового проекта.
- 2026-06-04: локальный smoke должен открывать frontend через `http://localhost:3000`, потому что `.env.local` указывает API на `http://localhost:8000`; `127.0.0.1:3000` создаёт другой origin и может ломать CORS для backend-запросов.
- 2026-06-04: `npm.cmd run smoke:guest` проходит: тестовый проект переносится на сервер и удаляется после проверки.

## Открытые вопросы к пользователю

- Сводный актуальный `PROJECT_STATE.md` можно сделать позже, если документация начнёт мешать работе. Пока опираемся на `CLAUDE.md` + `CODEX_NOTES.md` + реальный код.
- Старые `docs/08-11*.md` считать архивом/историей, пока пользователь не попросит иное.
