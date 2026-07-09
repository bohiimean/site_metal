from django.conf import settings


def captcha(request):
    """Клиентский ключ SmartCaptcha для виджета в формах.

    Пустой ключ — капча выключена: виджет не рендерится,
    сервер токен не требует (см. apps.leads.captcha).
    """
    return {'captcha_sitekey': settings.YANDEX_CAPTCHA_CLIENT_KEY}
