import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VALIDATE_URL = 'https://smartcaptcha.yandexcloud.net/validate'


def client_ip(request):
    """IP клиента: за Nginx — из X-Real-IP (см. RATELIMIT_IP_META_KEY)."""
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')


def verify_captcha(token, ip=''):
    """Серверная проверка токена Яндекс SmartCaptcha.

    Возвращает True, если проверка пройдена. Политика fail-open (рекомендация
    Яндекса): при недоступности сервиса капчи пропускаем заявку — потеря
    заявки хуже, чем редкий спам; от потока мусора страхует ratelimit.
    Пустые ключи (dev) — капча выключена целиком.
    """
    secret = settings.YANDEX_CAPTCHA_SERVER_KEY
    if not secret:
        return True
    if not token:
        return False
    try:
        resp = requests.post(
            VALIDATE_URL,
            data={'secret': secret, 'token': token, 'ip': ip},
            timeout=3,
        )
        if resp.status_code != 200:
            logger.error(
                'SmartCaptcha validate вернула HTTP %s — пропускаем (fail-open)',
                resp.status_code,
            )
            return True
        return resp.json().get('status') == 'ok'
    except Exception:
        logger.exception('SmartCaptcha validate недоступна — пропускаем (fail-open)')
        return True
