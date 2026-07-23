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

DNS: A-записи обоих доменов и их `www` (`example.ru`, `www.example.ru`,
`арвенокс.рф`, `www.арвенокс.рф`) должны указывать на сервер, чтобы сайт и
301-редирект второго домена работали. Для **выпуска** серта по DNS-01 A-записи
не обязательны (LE проверяет только TXT), но зоны должны быть делегированы на
NS reg.ru — иначе `dns_regru` не сможет создать TXT-запись.

## 2. Первый запуск

TLS выдаётся через Let's Encrypt по **HTTP-01** нативным `acme.sh` на хосте
(не контейнером): один сертификат на оба домена (`DOMAIN` + `REDIRECT_DOMAIN`
и их `www`). Почему так, а не контейнер/DNS-01:
- Docker Hub с этого хоста хронически отдаёт `429` — образ acme.sh не тянется;
- DNS-01 через API reg.ru невозможен: зоны на **хостинговом** NS
  `ns1.hosting.reg.ru`, а API поддерживает только **регистраторский**
  `ns1.reg.ru` (иначе `DOMAIN_IS_NOT_USE_REGRU_NSS`);
- HTTP-01 с этого хоста проходит нормально.

**Важно про IPv6:** у доменов не должно быть `AAAA`-записи на чужой/парковочный
IPv6, если сервер IPv6 не обслуживает — LE предпочитает IPv6 и валидация уходит
не на сервер (404). Проверить: `dig +short AAAA <домен>` должно быть пусто.
Лишние `AAAA` удалить в панели DNS до выпуска.

Установка acme.sh (GitHub с хоста доступен) и выпуск серта. `.рф` — в punycode:

```bash
# acme.sh + собственный cron продления
curl https://get.acme.sh | sh -s email=admin@example.ru

# пути docker-volume'ов, куда nginx смотрит за сертом и челленджем
CERTS=$(docker volume inspect metal_certbot_certs   -f '{{.Mountpoint}}')
WEBROOT=$(docker volume inspect metal_certbot_webroot -f '{{.Mountpoint}}')

# выпуск ОДНОГО серта на оба домена (все 4 имени — в SAN), HTTP-01 через webroot
/root/.acme.sh/acme.sh --issue --server letsencrypt --keylength 2048 \
    -w "$WEBROOT" \
    -d example.ru -d www.example.ru \
    -d xn--80aejuogkn.xn--p1ai -d www.xn--80aejuogkn.xn--p1ai

# установка серта в volume (nginx читает live/${DOMAIN}/) + reload nginx.
# acme.sh запоминает эти параметры и переприменяет их при автопродлении.
/root/.acme.sh/acme.sh --install-cert -d example.ru \
    --fullchain-file "$CERTS/live/example.ru/fullchain.pem" \
    --key-file       "$CERTS/live/example.ru/privkey.pem" \
    --reloadcmd "docker compose -f /opt/metal/docker-compose.prod.yml exec -T nginx nginx -s reload"
```

Продление полностью автоматическое: `acme.sh` ставит cron на хост при установке,
раз в сутки проверяет срок, продлевает через тот же webroot, переустанавливает
серт в volume и перезагружает nginx (`--reloadcmd`). Отдельный контейнер и
host-cron `nginx -s reload` из п.4 больше не нужны.

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
```

Продление TLS-серта отдельным cron не нужно — `acme.sh` завёл свой cron при
установке и сам продлевает + перезагружает nginx (см. п.2).

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

## 6. Особенности хостов без доступа к внешним CDN (напр. Timeweb)

У некоторых российских VPS сломан IPv4-маршрут до части зарубежных ресурсов,
из-за чего сборка образа падает. Обходы уже зашиты, но знать про них полезно:

- **apt** уведён на зеркало `mirror.yandex.ru` (build-arg `APT_MIRROR` в
  `docker/django/Dockerfile`). `deb.debian.org` по IPv4 с таких хостов виснет,
  и apt в сборке раздувается до OOM (exit 137). Переопределить зеркало:
  `docker compose ... build --build-arg APT_MIRROR=<host> web`.
- **Tailwind CLI** обычно качается с GitHub Releases. Если GitHub-CDN недоступен
  по IPv4 — положите бинарник заранее в `docker/django/vendor/tailwindcss`
  (в `.gitignore`, git его не трогает), Dockerfile возьмёт его вместо `curl`.
  Бинарник берётся с машины с интернетом:
  `curl -fSL -o docker/django/vendor/tailwindcss \`
  `  https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64`
  (для ARM-хоста — `...-linux-arm64`).
- **Docker Hub** периодически отдаёт `429 Too Many Requests` на анонимные pull —
  помогает повтор через паузу.
- На VPS с ≤4 ГБ RAM без swap сборка ловит OOM — заведите swap (`fallocate -l
  2G /swapfile && mkswap ... && swapon ...`, в `/etc/fstab`).

Благодаря этому обновление остаётся штатным: рабочее дерево на сервере чистое,
`git pull && docker compose -f docker-compose.prod.yml up -d --build` не
конфликтует (бинарник Tailwind — неотслеживаемый, зеркало зашито в Dockerfile).

### TLS через сертификат провайдера (ручной запасной вариант)

Основной путь — Let's Encrypt по HTTP-01 через нативный `acme.sh` (см. п.2):
продлевается сам. Ручной серт провайдера — только на случай, если и HTTP-01
недоступен (напр. LE вообще не достаёт хост).
**Такой серт не продлевается автоматически — придётся перевыпускать вручную
до истечения срока.** DV-сертификат провайдера (reg.ru и т.п.):

```bash
# fullchain = сертификат + цепочка (leaf первым), privkey = приватный ключ
cat certificate.crt certificate_ca.crt > fullchain.pem
# положить в volume, куда смотрит nginx:
docker run --rm -v metal_certbot_certs:/le -v "$PWD":/in nginx:1.27-alpine sh -c \
  'mkdir -p /le/live/$DOMAIN && cp /in/fullchain.pem /le/live/$DOMAIN/ && \
   cp /in/privkey.pem /le/live/$DOMAIN/ && chmod 600 /le/live/$DOMAIN/privkey.pem'
docker compose -f docker-compose.prod.yml up -d
```

При таком варианте `acme.sh` не нужен (серт кладётся в volume руками) —
не забудьте перевыпустить его до истечения срока.
