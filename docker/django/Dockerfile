# syntax=docker/dockerfile:1.6

# ─── Stage 1: builder ─────────────────────────────────────────────────
# Ставим зависимости в отдельный venv, чтобы в финальный образ не тащить
# gcc/libpq-dev — они нужны только для сборки psycopg2 из исходников.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# На части российских хостингов (напр. Timeweb) нет рабочего IPv4-маршрута до
# deb.debian.org, из-за чего apt внутри сборки зависает, раздувается и падает
# по OOM. Уводим apt на зеркало с рабочим IPv4 (Яндекс). Проект и так
# хостится в РФ (ФЗ-152), поэтому RU-зеркало здесь уместно по умолчанию.
ARG APT_MIRROR=mirror.yandex.ru
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Отдельный venv — легко скопировать в runtime-стадию одной инструкцией
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Файл requirements переопределяется через build-arg:
# - local.txt для docker-compose (дефолт, с debug-toolbar)
# - production.txt для прода
ARG REQUIREMENTS=requirements/local.txt

COPY requirements/ /tmp/requirements/
RUN pip install -r "/tmp/${REQUIREMENTS}"


# ─── Stage 2: runtime ─────────────────────────────────────────────────
# Только runtime-либа для psycopg2 (libpq5), без gcc/build-essential.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# То же зеркало, что и в builder-стадии (см. комментарий выше).
ARG APT_MIRROR=mirror.yandex.ru
RUN sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CLI: в dev — watch из start.sh, в проде — однократная сборка
# минифицированного CSS ниже. Бинарь ~50 МБ, но альтернатива — Node — жирнее.
#
# Обычно качаем с GitHub Releases. На хостах без рабочего IPv4-маршрута до
# GitHub-CDN (напр. Timeweb) кладём бинарник заранее в
# docker/django/vendor/tailwindcss (он в .gitignore, не отслеживается) —
# тогда используется он, curl не нужен. См. DEPLOY.md.
ARG TAILWIND_VERSION=v3.4.17
COPY docker/django/vendor/ /tmp/tw-vendor/
RUN set -eux; \
    ARCH=$(uname -m); if [ "$ARCH" = "aarch64" ]; then TW_ARCH="arm64"; else TW_ARCH="x64"; fi; \
    if [ -f /tmp/tw-vendor/tailwindcss ]; then \
        cp /tmp/tw-vendor/tailwindcss /usr/local/bin/tailwindcss; \
    else \
        curl -fsSLo /usr/local/bin/tailwindcss \
          "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${TW_ARCH}"; \
    fi; \
    chmod +x /usr/local/bin/tailwindcss; \
    rm -rf /tmp/tw-vendor

# Non-root пользователь — критично для прода: даже если приложение
# взломают, атакующий не получит root в контейнере.
RUN groupadd --system --gid 1001 app \
 && useradd  --system --uid 1001 --gid app --home /app --shell /bin/bash app

# Копируем venv из builder-стадии
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Копируем код с правильным владельцем
COPY --chown=app:app . .

# Production-CSS собирается на этапе сборки образа: start-prod.sh ничего
# не компилирует. В dev файл перекрывается bind-mount'ом `.:/app`
# и пересобирается watcher'ом из start.sh.
RUN tailwindcss -i static/css/main.css -o static/css/output.css --minify \
    && chown app:app static/css/output.css

# Директории для media/staticfiles — принадлежат app-юзеру.
# В docker-compose они переопределяются volumes, в проде остаются.
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles

USER app

EXPOSE 8000
