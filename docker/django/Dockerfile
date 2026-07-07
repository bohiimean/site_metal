# syntax=docker/dockerfile:1.6

# ─── Stage 1: builder ─────────────────────────────────────────────────
# Ставим зависимости в отдельный venv, чтобы в финальный образ не тащить
# gcc/libpq-dev — они нужны только для сборки psycopg2 из исходников.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
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

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Tailwind CLI — нужен только в dev (watch). В проде CSS собран заранее и
# копируется через COPY . .; тем не менее оставляем бинарь, чтобы образ
# был универсален. Он ~50 МБ, но альтернатива — Node — намного жирнее.
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then TW_ARCH="arm64"; else TW_ARCH="x64"; fi && \
    curl -sLo /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-${TW_ARCH}" && \
    chmod +x /usr/local/bin/tailwindcss

# Non-root пользователь — критично для прода: даже если приложение
# взломают, атакующий не получит root в контейнере.
RUN groupadd --system --gid 1001 app \
 && useradd  --system --uid 1001 --gid app --home /app --shell /bin/bash app

# Копируем venv из builder-стадии
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Копируем код с правильным владельцем
COPY --chown=app:app . .

# Директории для media/staticfiles — принадлежат app-юзеру.
# В docker-compose они переопределяются volumes, в проде остаются.
RUN mkdir -p /app/media /app/staticfiles && chown -R app:app /app/media /app/staticfiles

USER app

EXPOSE 8000
