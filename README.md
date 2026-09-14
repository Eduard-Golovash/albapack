# Packaging Market
Интернет-магазин упаковки.

## Стек

- **Backend:** Django 5.2 + DRF + SimpleJWT
- **Frontend:** Django Templates + HTMX + Alpine.js
- **DB:** PostgreSQL (prod), SQLite (dev)
- **Async:** Celery + Redis
- **Payments:** Stripe

## Локальный запуск

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактировать .env
python manage.py migrate
python manage.py runserver

## Ветвление (Git Flow)

- main — продакшн
- develop — разработка
- feature/* — фичи
- hotfix/* — срочные фиксы

## Статус
🚧 В разработке
