# Ралюма — инструкции для Claude

## Структура репозитория
- Корень git-репозитория: `mamajan/` (не `mamajan/Raluma/`)
- Приложение: `mamajan/Raluma/` — фронтенд + бэкенд
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
> ⚠️ OOM killer на VPS: при `--no-cache` sshd может упасть — ждать ~30с и переподключаться.
> Проверка здоровья: `curl https://raluma.ru/health`

## Ключевые файлы
| Файл | Назначение |
|------|-----------|
| `Raluma/src/components/ProjectEditor.tsx` | Главный редактор (~2000 строк) |
| `Raluma/backend/main.py` | FastAPI app + миграции (ALTER TABLE в lifespan) |
| `Raluma/backend/models.py` | SQLAlchemy модели |
| `Raluma/backend/schemas.py` | Pydantic схемы |
| `Raluma/src/api/projects.ts` | TypeScript типы + API-вызовы |
| `PROGRESS.md` | Полная документация проекта |

## Соглашения кода

### Новые поля в БД — чеклист:
1. `models.py` — добавить `Column` в класс
2. `schemas.py` — добавить поле в `Base`-схему
3. `main.py` — добавить `ALTER TABLE ... ADD COLUMN` в список миграций lifespan
4. `src/api/projects.ts` — добавить в интерфейс `SectionOut` или `ProjectList`
5. `ProjectEditor.tsx` — добавить в `Section` interface + `apiToLocal()` + `localToApi()`
6. `backend/api/projects.py` — добавить в `copy_project` если нужно копировать

### camelCase ↔ snake_case:
- TypeScript (`Section` interface): camelCase (`extraParts`, `profileLeftWall`)
- Python/API: snake_case (`extra_parts`, `profile_left_wall`)
- Конвертация через `apiToLocal()` и `localToApi()` в `ProjectEditor.tsx`

### Системы секций:
`СЛАЙД` | `КНИЖКА` | `ЛИФТ` | `ЦС` | `КОМПЛЕКТАЦИЯ` (бывш. ДВЕРЬ — legacy)

## Что реализовано
- ТЗ1: форма СЛАЙД (рельс, порог, фурнитура)
- ТЗ2: SlideSchemeSVG — схема сверху с УЛИЦА/ПОМЕЩЕНИЕ
- ТЗ3: примечания к секции, нумерация, кнопка "← К проекту", guard несохранённых изменений
- ТЗ4: SVG сечения профилей на схеме сверху
- ТЗ5: статусы производства, стекло, покраска, заказы
- ТЗ6: взаимоисключение RS112/RS1002, автовыбор RS112 при RS1081, переименование замков

## Бэклог (не реализовано)
- Валидация размеров (min=1 на числовых инпутах)
- Спиннер на кнопке сохранения секции
- Разбить ProjectEditor.tsx на подкомпоненты
- Alembic вместо ручных миграций
- Rate limiting на `/api/auth/login`
- JWT в httpOnly cookie
- PDF экспорт
