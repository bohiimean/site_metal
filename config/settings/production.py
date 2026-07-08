from .base import *
from decouple import config

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# Переиспользование соединений с Postgres между запросами.
# Число одновременных соединений в проде ограничено воркерами Gunicorn
# (workers × threads), поэтому в max_connections Postgres не упираемся.
DATABASES['default']['CONN_MAX_AGE'] = 60

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
