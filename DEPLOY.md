# Деплой на сервер

Стек на сервере: Docker Compose — Postgres + Redis + Django (Gunicorn) +
Nginx + certbot. Всё описано в `docker-compose.prod.yml`.

Хостинг — российский (ФЗ-152): Selectel / Timeweb / VK Cloud / Яндекс Облако.
Минимум: 2 vCPU / 2 ГБ RAM / 20 ГБ диска, Ubuntu 22.04+.

## 1. Подготовка сервера

```bash
# Docker + compose-плагин
curl -fsSL https://get.docker.com | sh

# Код
git clone <репозиторий> /opt/metal
cd /opt/metal

# Конфигурация
cp .env.example .env
nano .env   # заполнить: SECRET_KEY, ALLOWED_HOSTS, SITE_URL, DOMAIN,
            # DB_PASSWORD, TELEGRAM_*, ключи капчи
```

DNS: A-записи `example.ru` и `www.example.ru` должны указывать на сервер
**до** выпуска сертификата.

## 2. Первый запуск

Сертификат выпускается один раз вручную (nginx без него не стартует):

```bash
docker compose -f docker-compose.prod.yml run --rm -p 80:80 \
    --entrypoint "certbot certonly --standalone \
    -d example.ru -d www.example.ru \
    --email admin@example.ru --agree-tos --no-eff-email" certbot
```

Дальше — весь стек (миграции и collectstatic выполняются автоматически
в `start-prod.sh`):

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Проверка: `https://example.ru` открывается, `https://example.ru/admin/` пускает,
`docker compose -f docker-compose.prod.yml logs web` без ошибок.

После заполнения каталога стоит прогреть превью изображений, чтобы первый
посетитель не ждал генерации:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py generateimages
```

## 3. Обновление версии

```bash
cd /opt/metal
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Миграции применятся сами при старте контейнера.

## 4. Бэкапы (обязательно)

Файлы изображений живут на диске сервера (volume `metal_media_data`),
страховка — ночная синхронизация в S3-совместимый бакет (Selectel /
Яндекс Object Storage). Скрипт: `docker/backup.sh` (media + дамп Postgres).

Разовая настройка:

```bash
# rclone на хосте
curl https://rclone.org/install.sh | bash
rclone config   # создать remote "s3backup" типа s3 (ключи из панели провайдера)

# бакет должен существовать (создаётся в панели провайдера), например metal-backup
chmod +x /opt/metal/docker/backup.sh
```

Cron (`crontab -e` от root):

```cron
# Ночной бэкап media + БД
0 3 * * * /opt/metal/docker/backup.sh >> /var/log/metal-backup.log 2>&1
# Перечитать сертификат после возможного продления (certbot продлевает сам)
30 4 * * 1 docker compose -f /opt/metal/docker-compose.prod.yml exec nginx nginx -s reload
```

Восстановление после потери сервера: поднять новый сервер по шагам 1–2,
затем `rclone sync s3backup:metal-backup/media` в volume и
`gunzip -c dump.sql.gz | docker compose ... exec -T db psql -U metal metal`.

## 5. Что где лежит

| Компонент | Где |
|---|---|
| Код | `/opt/metal` (git) |
| Изображения (оригиналы + пресеты) | volume `metal_media_data` |
| БД | volume `metal_postgres_data` |
| Сертификаты | volume `metal_certbot_certs` |
| Статика (collectstatic) | volume `metal_static_data`, отдаёт nginx |
| Логи приложения | `docker compose -f docker-compose.prod.yml logs web` |
| Бэкапы БД локально | `/opt/backups/db` (14 дней) |
