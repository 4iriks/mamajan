# Фронтенд — отложенные вопросы

## Мёртвые поля в модели Section
- `cornerLeft` / `cornerRight` — есть в модели, маппятся в converters.ts, но нигде не отображаются в UI (FormTabs). Удалить или добавить в форму?
- `externalWidth` — аналогично, есть в модели но нет в UI

## Нет дефолтов при создании КНИЖКА
- `doorType`, `doorOpening`, `compensator`, `bookSystem` — не инициализируются в `defaultsForSystem()`. При создании новой секции КНИЖКА будут undefined. Пока не ломает, но может привести к багам.

## Тип rails
- В `SectionOut` (projects.ts): `rails?: number`
- В `Section` (types.ts): `rails?: 3 | 5`
- Работает через `as` type assertion в converters.ts. Не критично, но не type-safe.
