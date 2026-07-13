import multiprocessing
import os

bind = '0.0.0.0:8000'

# Классическая формула для sync-воркеров. На типовом VPS с 2 vCPU это 5.
# Переопределяется через GUNICORN_WORKERS в .env.
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# Логи в stdout/stderr — собирает Docker
accesslog = '-'
errorlog = '-'

# Страховка от утечек памяти в долгоживущих воркерах:
# перезапуск воркера после N запросов, с разбросом, чтобы не одновременно.
max_requests = 1000
max_requests_jitter = 100

timeout = 60

# Control-socket gunicorn 26 по умолчанию создаёт в рабочей директории
# (/app/.gunicorn/gunicorn.ctl). Контейнер бежит под непривилегированным
# пользователем, /app ему не пишется → на каждом старте
# «[ERROR] Control server error: Permission denied: '/app/.gunicorn'».
# Управляющий интерфейс нам не нужен — выключаем, чтобы не засорять логи.
control_socket_disable = True
