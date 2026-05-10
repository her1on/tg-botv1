# Beauty Salon Bot

Telegram-бот для онлайн-записи в салон красоты + статический сайт с формой бронирования.

## Стек

- **Бот:** Python 3.11+, python-telegram-bot 21.6, psycopg2
- **БД:** Supabase (PostgreSQL)
- **Деплой бота:** Railway
- **Сайт:** Vanilla JS, Supabase JS Client (статика)

## Быстрый старт

```bash
git clone <repo>
cd beauty_salon_bot

pip install -r requirements.txt

cp .env.example .env
# заполните .env (см. раздел ниже)

python bot.py
```

## Переменные окружения

Создайте файл `.env` на основе `.env.example`:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от BotFather |
| `DATABASE_URL` | PostgreSQL URL (Supabase pooler, Session mode, порт 5432) |
| `OWNER_IDS` | Telegram user ID владельцев через запятую (например, `123456,789012`) |
| `SALON_NAME` | Название салона в сообщениях |
| `TIMEZONE` | Часовой пояс (например, `Europe/Moscow`) |
| `WORKING_DAYS` | Рабочие дни через запятую, 0=Пн, 6=Вс (например, `0,1,2,3,4,5`) |
| `SERVICES` | Список услуг через запятую |
| `TIME_SLOTS` | Доступное время через запятую в формате `HH:MM` |

## База данных

1. Откройте **Supabase → SQL Editor**
2. Выполните `supabase_migrations.sql` — создаст таблицы, индексы, триггер и RLS-политики

## Деплой на Railway

1. Подключите репозиторий в Railway
2. Установите регион **Europe West** (требуется для Supabase)
3. Добавьте переменные окружения из `.env`
4. `Procfile` уже настроен — Railway запустит бота автоматически

## Сайт

Статика лежит в `beauty-salon-booking/`. Настройте Supabase anon key в `beauty-salon-booking/js/config/env.js` и разместите папку на любом хостинге статики (Vercel, Netlify, GitHub Pages).
