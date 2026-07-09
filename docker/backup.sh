#!/bin/bash
# Ночной бэкап, запускается cron'ом на хосте (см. DEPLOY.md).
#
# 1. media/  -> S3-совместимый бакет (rclone sync).
#    Картинки товаров лежат на диске сервера (volume metal_media_data),
#    бакет — только страховка на случай гибели сервера.
# 2. Postgres -> gzip-дамп локально + копия в тот же бакет.
#
# Требует на хосте: docker, настроенный rclone remote (rclone config).
set -euo pipefail

# ── Настройки ─────────────────────────────────────────────────────────
RCLONE_REMOTE="${RCLONE_REMOTE:-s3backup}"        # имя remote из `rclone config`
BUCKET="${BACKUP_BUCKET:-metal-backup}"           # имя бакета
COMPOSE_FILE="${COMPOSE_FILE:-/opt/metal/docker-compose.prod.yml}"
DUMP_DIR="${DUMP_DIR:-/opt/backups/db}"
KEEP_DUMPS_DAYS="${KEEP_DUMPS_DAYS:-14}"

# ── 1. media -> S3 ────────────────────────────────────────────────────
# Пресеты imagekit (media/CACHE/) не бэкапим — пересоздаются из оригиналов
docker run --rm \
    -v metal_media_data:/data:ro \
    -v /root/.config/rclone:/config/rclone:ro \
    rclone/rclone sync /data "${RCLONE_REMOTE}:${BUCKET}/media" \
    --exclude "/CACHE/**"

# ── 2. Дамп Postgres ──────────────────────────────────────────────────
mkdir -p "$DUMP_DIR"
STAMP=$(date +%Y-%m-%d_%H%M)
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
    | gzip > "${DUMP_DIR}/metal_${STAMP}.sql.gz"

docker run --rm \
    -v "$DUMP_DIR":/dumps:ro \
    -v /root/.config/rclone:/config/rclone:ro \
    rclone/rclone copy /dumps "${RCLONE_REMOTE}:${BUCKET}/db"

# Локально храним дампы ограниченное время
find "$DUMP_DIR" -name '*.sql.gz' -mtime +"$KEEP_DUMPS_DAYS" -delete

echo "Backup OK: $(date -Iseconds)"
