# Ралюма — инструкции для Claude

## Структура репозитория
- Корень git-репозитория: `mamajan/` (не `mamajan/Raluma/`)
- Приложение: `mamajan/Raluma/` — фронтенд + бэкенд
- Архив: `mamajan/appglass/` — старый проект AppGlass (не трекается в git)
- Документация: `mamajan/docs/` — ТЗ и планы Raluma
- **Все git-команды запускать из `mamajan/`**

## Стек
- Frontend: React 18 + TypeScript + Vite + Tailwind + Framer Motion (`Raluma/src/`)
- Backend: FastAPI + SQLAlchemy + SQLite (`Raluma/backend/`)
- Инфра: Docker Compose + Caddy (auto-SSL)

## Деплой на сервер
```bash
# Только фронтенд (чаще всего):
ssh root@89.111.142.17 "cd /opt/mamajan/Raluma && git pull && docker compose build frontend && docker compose up -d"

# Бэкенд тоже изменился:
ssh root@89.111.142.17 "cd /opt/mamajan/Raluma && git pull && docker compose build && docker compose up -d"
```
> OOM killer на VPS: при `--no-cache` sshd может упасть — ждать ~30с и переподключаться.
> Сайт: `https://raluma.tech/`

## Ключевые файлы

### Backend
| Файл | Назначение |
|------|-----------|
| `Raluma/backend/main.py` | FastAPI app + миграции (ALTER TABLE в lifespan) |
| `Raluma/backend/models.py` | SQLAlchemy модели |
| `Raluma/backend/schemas.py` | Pydantic схемы |
| `Raluma/backend/api/projects.py` | CRUD эндпоинты проектов/секций |

### Frontend — editor/ модули
| Файл | Строк | Назначение |
|------|-------|-----------|
| `src/components/ProjectEditor.tsx` | ~640 | Оркестратор: загрузка проекта, header, project-level формы (статус/стекло/покраска/заказы), модалки |
| `src/components/editor/types.ts` | ~110 | `Section`, `OrderItem`, `ProjectEditorProps`, style-константы (`LBL`, `INP`, `SEL`, `SYSTEM_COLORS`) |
| `src/components/editor/converters.ts` | ~100 | `apiToLocal()` / `localToApi()` — camelCase ↔ snake_case |
| `src/components/editor/EditorSidebar.tsx` | ~220 | Список секций, системпикер (добавление новых секций), примечания проекта |
| `src/components/editor/SectionFormWrapper.tsx` | ~190 | Форма редактирования секции: хлебные крошки, FormTabs, кнопка сохранить, Ctrl+S, beforeunload guard |
| `src/components/editor/EditorVisualizer.tsx` | ~60 | SVG-схемы (mobile `xl:hidden` + desktop `sticky`), делегирует в SlideDiagrams |
| `src/components/editor/FormTabs.tsx` | ~430 | MainTab, SlideSystemTab, BookSystemTab, LiftSystemTab, CsShapeTab, DoorSystemTab |
| `src/components/editor/FormInputs.tsx` | ~120 | Checkbox, ToggleGroup, ProfileCheckbox, RadioList, SectionDivider |
| `src/components/editor/SlideDiagrams.tsx` | ~310 | SlideSchemeSVG (вид сверху с профилями), SlideRoomViewSVG (вид из помещения) |

### Другие важные файлы
| Файл | Назначение |
|------|-----------|
| `src/components/App.tsx` | Список проектов, авторизация, StatusBadge |
| `src/api/projects.ts` | TypeScript типы API + axios-вызовы |
| `PROGRESS.md` | Полная документация проекта |
| `REPORT.md` | Технический отчёт по всему проекту |

## Соглашения кода

### Новые поля в БД — чеклист:
1. `backend/models.py` — добавить `Column` в класс
2. `backend/schemas.py` — добавить поле в `Base`-схему
3. `backend/main.py` — добавить `ALTER TABLE ... ADD COLUMN` в список миграций lifespan
4. `src/api/projects.ts` — добавить в интерфейс `SectionOut` или `ProjectList`
5. `src/components/editor/types.ts` — добавить в `Section` interface
6. `src/components/editor/converters.ts` — добавить маппинг в `apiToLocal()` и `localToApi()`
7. `backend/api/projects.py` — добавить в `copy_project` если нужно копировать

### camelCase ↔ snake_case:
- TypeScript (`Section` interface в `editor/types.ts`): camelCase (`extraParts`, `profileLeftWall`)
- Python/API: snake_case (`extra_parts`, `profile_left_wall`)
- Конвертация через `apiToLocal()` и `localToApi()` в `editor/converters.ts`

### Системы секций:
`СЛАЙД` | `КНИЖКА` | `ЛИФТ` | `ЦС` | `КОМПЛЕКТАЦИЯ` (бывш. ДВЕРЬ — legacy)

### Архитектура фронтенда:
- `ProjectEditor` — оркестратор, НЕ содержит логику форм/визуализации
- Новые системы (формы) → добавлять таб в `FormTabs.tsx`
- Новые SVG-схемы → добавлять в `SlideDiagrams.tsx` (или создать аналогичный файл для другой системы)
- Новые input-компоненты → `FormInputs.tsx`

## Что реализовано
- ТЗ1: форма СЛАЙД (рельс, порог, фурнитура)
- ТЗ2: SlideSchemeSVG — схема сверху с УЛИЦА/ПОМЕЩЕНИЕ
- ТЗ3: примечания к секции, нумерация, кнопка "← К проекту", guard несохранённых изменений
- ТЗ4: SVG сечения профилей на схеме сверху
- ТЗ5: статусы производства, стекло, покраска, заказы
- ТЗ6: взаимоисключение RS112/RS1002, автовыбор RS112 при RS1081, переименование замков
- SlideRoomViewSVG — вид из помещения с размерными линиями
- Рефакторинг: ProjectEditor разбит на 8 модулей в `editor/`

## Бэклог (не реализовано)
- Валидация размеров (min=1 на числовых инпутах)
- Alembic вместо ручных миграций
- Rate limiting на `/api/auth/login`
- JWT в httpOnly cookie
- PDF экспорт
