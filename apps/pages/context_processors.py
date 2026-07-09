from .models import SiteSettings


def site_settings(request):
    """Прокидывает настройки сайта во все шаблоны как `site`."""
    return {'site': SiteSettings.load()}
