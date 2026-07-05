#!/bin/bash
set -e

echo "==> Compiling Tailwind CSS..."
tailwindcss -i static/css/main.css -o static/css/output.css

echo "==> Starting Tailwind watcher..."
tailwindcss -i static/css/main.css -o static/css/output.css --watch &

echo "==> Starting Django..."
exec python manage.py runserver 0.0.0.0:8000
