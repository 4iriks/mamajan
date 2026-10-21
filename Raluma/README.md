<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/632644e7-8295-4f04-8459-b511a7a4c464

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Настройка цен конструкций

Экран `/admin/pricing` доступен администраторам и пользователям с правом управления ценами. Вход есть из каталога и списка проектов. Поддержаны Слайд 1 ряд, Слайд 2 ряда и ЦС без дверей.

Каталог хранит общую себестоимость и условия отдельной продажи детали. В настройке конструкций отходы, наценка и скидка задаются отдельно для каждой системы, позиции и исполнения. Общие наценка и скидка системы применяются после суммы комплектующих. Образцы используют тот же серверный расчёт, что и заказ, без дилерских условий, ручных цен и скидок исходного заказа. Примеры запоминаются в браузере отдельно для пользователя и системы, черновики восстанавливаются в текущей вкладке.

При первом запуске обновлённого backend миграция материализует действующие и запланированные старые цены. Новые общие проценты начинаются с нуля; старые правила больше не участвуют в расчёте. Зафиксированные КП и история сохраняются. Стартовые нулевые себестоимости Т40Т, Т40К, подкладок и скотча считаются незаполненными до явного ввода. Себестоимость `0`, введённая пользователем, допустима.

Проверка переноса на копии SQLite (файл назначения должен быть новым):

```sh
python scripts/verify-construction-pricing-migration.py backend/raluma.db tmp/pricing-verification.db
```

Скрипт открывает исходную базу только для чтения, создаёт SQLite backup и проверяет совпадение цен и неизменность снимков. Рабочую базу он не меняет. До обновления рабочего сервера необходимо отдельно сохранить её резервную копию.

Проверки frontend: `npm run check`, `npm run build`, `npm run smoke:pricing`, `npm run smoke:pricing:catalog`, `npm run smoke:pricing:confirmation`.

Для проверки браузера с настоящим API создайте отдельную тестовую базу командой `python scripts/seed-construction-pricing-qa.py tmp/pricing-browser.db`. Запустите backend с `DATABASE_URL`, указывающим на эту базу, на порту 8813 и `FRONTEND_URL=http://localhost:8833`; Vite — на порту 8833 с `VITE_API_URL=http://127.0.0.1:8813`. Затем выполните `npm run smoke:pricing:systems`. Этот тест изменяет только тестовые цены. Путь к Playwright можно задать переменной `PLAYWRIGHT_MODULE`, браузер — `QA_BROWSER_CHANNEL`.

`npm run smoke:pricing:editing` на той же изолированной базе проверяет очистку всех процентных полей, сохранение фокуса и чертежа при пересчёте, обновление только неизменённых полей при конфликте, восстановление черновиков и компактные карточки на семи ширинах экрана.
