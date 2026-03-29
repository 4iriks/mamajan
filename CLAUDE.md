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
| `Raluma/backend/main.py` | FastAPI app, lifespan, CORS, роутеры |
| `Raluma/backend/migrations.py` | ALTER TABLE миграции + миграции данных |
| `Raluma/backend/models.py` | SQLAlchemy модели |
| `Raluma/backend/schemas.py` | Pydantic схемы |
| `Raluma/backend/api/projects.py` | CRUD эндпоинты проектов/секций |
| `Raluma/backend/api/documents.py` | preview/pdf/overrides эндпоинты (производственный лист) |
| `Raluma/backend/engine/slide_calc.py` | Расчётный движок СЛАЙД → SlideCalcResult |
| `Raluma/backend/engine/pdf.py` | Jinja2 → WeasyPrint рендеринг HTML/PDF |
| `Raluma/backend/templates/section_sheet.html` | A4-шаблон производственного листа (Jinja2, contenteditable) |
| `Raluma/backend/assets/profiles/` | Картинки профилей (base64 в PDF) |

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
| `src/App.tsx` | Чистый роутер (~53 строки) |
| `src/pages/LoginPage.tsx` | Страница авторизации (~106 строк) |
| `src/pages/ProjectsPage.tsx` | Список проектов, StatusBadge, CRUD модалки (~477 строк) |
| `src/pages/AdminPage.tsx` | Админка: управление пользователями |
| `src/api/projects.ts` | TypeScript типы API + axios-вызовы |
| `PROGRESS.md` | Полная документация проекта |
| `REPORT.md` | Технический отчёт по всему проекту |

## Соглашения кода

### Новые поля в БД — чеклист:
1. `backend/models.py` — добавить `Column` в класс
2. `backend/schemas.py` — добавить поле в `Base`-схему
3. `backend/migrations.py` — добавить `ALTER TABLE ... ADD COLUMN` в `_ADD_COLUMNS`
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
- Рефакторинг: App.tsx → чистый роутер + LoginPage + ProjectsPage
- Рефакторинг: миграции из main.py вынесены в migrations.py
- **Производственный лист СЛАЙД**: расчётный движок + WeasyPrint PDF + iframe-предпросмотр с contenteditable редактированием, сохранение правок в БД (`document_overrides`), скачивание PDF
- **Производственный лист — доработки**: объединение щёток RU007/RU008 в одну ячейку (HardwareSubItem), inner-table layout для фурнитуры, добавлены картинки RS2021/RS1121/DIN7982/DIN7504M/DIN7504O/DIN912SW, страница 2 "Доп. комплектующие" с добавлением/удалением строк, увеличены шрифты (+2pt) и картинки (medium)
- **UX-доработки формы**: поле "Название" → "Секция №" + числовой инпут (слово "Секция" нередактируемо), убраны спиннеры со всех number-инпутов, числовые поля можно полностью очистить, дефолт порога "Стандартный анод" при создании секции
- **Производственный лист system_text**: "SLIDE-стандарт 1 ряд" (фиксированный, не зависит от рельсов)
- **SVG-схема вид сверху** в производственном листе: рельсы, панели с номерами, профили (пристеночный/замок/П-профиль/ручка/пузырьковый), межстекольный профиль, стрелка сдвига, метки ПОМЕЩЕНИЕ/УЛИЦА
- **Ревизия slide_calc.py**: исправлены 3 бага двойного умножения на Q (RS107, саморез 4,8×19, саморез 3,5×13), опечатка RS1081→RS2081 в чеклисте
- **copy_project**: заменён устаревший `handle_offset` на `handle_offset_left`/`handle_offset_right`, `document_overrides` не копируется (чистые расчёты в копии)

## Производственный лист — архитектура

```
[Кнопка "Производственный лист"] → ProductionSheetModal
  → <iframe src="/api/projects/{pid}/sections/{sid}/preview">
     — slide_calc.py считает профили/стёкла/фурнитуру/саморезы
     — section_sheet.html: contenteditable + data-field + data-original
     — JS postMessage({type:'dirty'}) при изменении
  → [Сохранить]: читает iframe DOM, PATCH /overrides → JSON в section.document_overrides
  → [Отменить]: iframe.reload()
  → [Скачать PDF]: GET /pdf → WeasyPrint → blob → <a download>
```

### Ключевые формулы СЛАЙД (1 ряд):
- `ppl/ppr = 16` если пристеночный; `pzl/pzr = 5` если пузырьковый
- `rpl/rpr = 59.5` если ручка-профиль+замок, `= 27` если ручка-профиль+П-профиль
- `krlr/krrr = 8` если ручка-профиль; `krlp/krrp = 16` если П-профиль+пузырьковый
- `a = handle_offset_left`, `b = handle_offset_right` (два отдельных отступа под ручку)
- P≥2: `middle_W = (W - ppr - ppl - rpr - rpl - pzl - pzr - krlr - krlp - krrr - krrp - a - b + 9.5*(P-1)) / P`
- P=1 (глухая): `middle_W = W - ppr - ppl - pzl - pzr`
- `glass_H = H - 106` (стандартный порог) или `H - 94` (накладной)

## Производственный лист — детали реализации

### Авторизация для iframe
iframe не отправляет `Authorization: Bearer` заголовок. Решение: JWT передаётся через `?token=` query param.
- Фронтенд: `src="${getPreviewUrl(pid, sid)}?token=${encodeURIComponent(token)}"`
- Бэкенд (`api/documents.py`): `_get_user_by_token()` читает токен из query param вместо заголовка

### Зум в предпросмотре
`section_sheet.html` задаёт `body { width: 287mm }` (A4 минус поля).
JS при загрузке применяет `transform: scale()` к `body` чтобы вписать в ширину iframe.
Высота передаётся через `postMessage({type:'height', height: N})` → `ProductionSheetModal` меняет `iframeHeight`.

### Картинки профилей в ассетах (`assets/profiles/`)
Jinja2-фильтр `img_b64` конвертирует имя файла → `data:image/jpeg;base64,...`.
Файлы есть: RS1002, RS1004, RS1006, RS1021, RS105, RS106, RS107, RS107L, RS107R, RS1082,
RS112, RS122, RS1325, RS205, RS2061, RS2081, RS2323, RS2333, RS2335, RS3014, RS3017,
RS3018, RS3019, RS3020, RSD1, RSD2, RU005, RU007.
Добавлены: RS2021.jpg, RS1121.png, DIN7982.png, DIN7504M.png, DIN7504O.png, DIN912SW.png.
**Отсутствуют** (image=None в slide_calc.py): RS1313, RS1315, RU008.
Временные замены: RS1313/RS1315 → RS1325.jpg; RU008 → RU007.jpg.

### Шаблон section_sheet.html — структура
A4 портретная, Jinja2 + contenteditable. Секции:
1. Шапка (проект / секция / система "SLIDE-стандарт 1 ряд")
2. Схемы: вид из помещения + вид сверху (SVG)
3. Параметры (цвет/стекло/порог/система + ширина/высота/панели/количество) + размеры стёкол
4. Нарезка профилей (3 колонки) + стекольный профиль (inner table с картинкой)
5. Фурнитура (inner table: картинка | название+артикул+кол-во) + Крепёж + Чек-лист
6. Комментарии к секции
7. Страница 2: "Дополнительные комплектующие" — contenteditable таблица с добавлением/удалением строк

### Фурнитура — HardwareSubItem
Щётки RU007/RU008 объединены в одну ячейку через `HardwareSubItem` dataclass.
Sub-items рендерятся nested table (label | article | qty) внутри основной ячейки.

### Системы СЛАЙД — важно
- "Стандарт 1 ряд" (3 рельсы) и "2 ряда от центра" (5 рельсов) — это ДВЕ РАЗНЫЕ системы
- Сейчас реализована ТОЛЬКО "Стандарт 1 ряд"
- "2 ряда от центра" — будущая отдельная система с другими расчётами
- system_text в производственном листе всегда "SLIDE-стандарт 1 ряд"

## Бэклог (не реализовано)
- **Исправить формулу самореза DIN7504M** (сейчас считает неправильно, ждём правильную формулу)
- **СЛАЙД "2 ряда от центра"** — отдельная система с другими расчётами
- **Фронтенд TODO** — см. `TODO_FRONTEND.md` (мёртвые поля cornerLeft/Right, externalWidth; нет дефолтов для КНИЖКА; тип rails)
- Alembic вместо ручных миграций
- Rate limiting на `/api/auth/login`
- JWT в httpOnly cookie
- Производственные листы для других систем (КНИЖКА, ЛИФТ, ЦС)
