# Прогресс разработки
> Обновлён: 2026-02-25

---

## ✅ ГОТОВО

### Бэкенд (`Raluma/backend/`)
- [x] SQLite БД, таблицы User / Project / Section
- [x] JWT авторизация, bcrypt, 3 роли (user / admin / superadmin)
- [x] Seed: admin / admin123 при первом запуске
- [x] POST /api/auth/login, GET /api/auth/me
- [x] CRUD /api/users (admin only, с правами по ролям)
- [x] CRUD /api/projects (user видит свои, admin — все)
- [x] CRUD /api/projects/{id}/sections
- [x] POST /api/projects/{id}/copy
- [x] requirements.txt, всё установлено

### Фронтенд (`Raluma/src/`)
- [x] React Router: /login, /, /projects/:id, /admin
- [x] Реальный login через API (убран mock)
- [x] Zustand authStore (токен, пользователь, роли)
- [x] Axios клиент с JWT interceptors (401 → /login)
- [x] ProjectEditor: загрузка проекта из API, сохранение секций
- [x] AdminPage: CRUD пользователей, сброс пароля, генератор паролей
- [x] npm зависимости установлены (axios, react-router-dom, zustand)
- [x] TypeScript: 0 ошибок

---

## 🔜 ОСТАЛОСЬ

### Высокий приоритет
- [ ] Форма СЛАЙД Таб 2: порог, межстекольный профиль, профили лев/пр — не биндятся
- [ ] Форма СЛАЙД Таб 3: умные зависимости (профиль → варианты ручек/замков), защёлки, отступ
- [ ] Форма КНИЖКА: реальный расчёт через /api/projects/{id}/calculate
- [ ] Бэкенд: GET /api/projects/{id}/calculate → engine/comp_calc.py

### Средний приоритет
- [ ] Автосохранение секции или чёткий UX "изменил → сохранил"
- [ ] Пагинация проектов (UI есть, логики нет)
- [ ] PDF: производственный лист, накладная, заказ стекла, заявка в покраску

### Низкий приоритет
- [ ] Форма ЛИФТ и ЦС (сейчас заглушки)
- [ ] Docker: nginx + backend + frontend
- [ ] Сменить admin123 после деплоя

---

## КАК ЗАПУСКАТЬ

```bash
# Бэкенд
cd Raluma/backend
uvicorn main:app --reload --port 8000

# Фронтенд (отдельный терминал)
cd Raluma
npm run dev
# → http://localhost:3000
# Логин: admin / admin123
```
