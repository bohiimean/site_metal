#!/bin/bash
# Production-запуск: миграции → статика → Gunicorn.
# CSS уже собран на этапе сборки образа (см. Dockerfile).
set -e

echo "==> Applying migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Starting Gunicorn..."
exec gunicorn config.wsgi:application --config docker/django/gunicorn.conf.py
