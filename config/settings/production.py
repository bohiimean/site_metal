from .base import *
from decouple import config

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# Переиспользование соединений с Postgres между запросами.
# Число одновременных соединений в проде ограничено воркерами Gunicorn
# (workers × threads), поэтому в max_connections Postgres не упираемся.
DATABASES['default']['CONN_MAX_AGE'] = 60

# Общий кэш для всех воркеров Gunicorn. Обязателен для django-ratelimit:
# с LocMemCache у каждого воркера свой счётчик, и лимит фактически
# умножается на число воркеров (плюс system check E003 не даёт мигрировать).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://redis:6379/1'),
    }
}

# За Nginx REMOTE_ADDR — это IP прокси-контейнера, одинаковый для всех
# посетителей. Реальный IP клиента Nginx передаёт в X-Real-IP.
RATELIMIT_IP_META_KEY = 'HTTP_X_REAL_IP'

# W001: django-ratelimit не знает встроенный RedisCache Django 4+ по имени
# и предупреждает. Фактически бэкенд подходит: общий для всех воркеров,
# incr атомарный (Redis INCRBY). E003 (не-shared кэш) НЕ глушить.
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.W001']

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS: 30 дней. Поднимать до года (и добавлять preload) только после
# того, как HTTPS стабильно работает на всех поддоменах.
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

if SITE_URL:
    CSRF_TRUSTED_ORIGINS = [SITE_URL]

# Всё в stdout — логи собирает Docker (docker compose logs web).
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        # Ошибки отправки в Telegram пишутся логгером apps.leads.views —
        # уровень INFO, чтобы exception с трейсбеком точно попал в вывод.
        'apps': {'level': 'INFO'},
        'django.request': {'level': 'WARNING'},
    },
}
