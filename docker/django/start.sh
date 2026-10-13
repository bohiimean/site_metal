#!/bin/bash
set -e

echo "==> Compiling Tailwind CSS..."
tailwindcss -i static/css/main.css -o static/css/output.css

echo "==> Starting Tailwind watcher..."
# Watch-режим Tailwind завершается, как только stdin отдаёт EOF. У контейнера,
# поднятого через `compose up -d`, stdin закрыт, поэтому watcher молча умирал
# на старте: CSS не пересобирался, и новые классы в шаблонах не работали, пока
# образ не пересоберут. `tail -f /dev/null` держит stdin открытым.
# (stdin_open в compose не помогает — проверено.)
tail -f /dev/null | tailwindcss -i static/css/main.css -o static/css/output.css --watch &

echo "==> Starting Django..."
exec python manage.py runserver 0.0.0.0:8000
