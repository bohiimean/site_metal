from apps.references.models import Material
from .models import Category


def footer_nav(request):
    """Ссылки для колонки «Каталог» в футере (site-wide).

    - `footer_sections` — до 2 основных разделов страницы «Продукция»
      (материалы с landing_title, те самые «баннеры»), ведут на каталог,
      отфильтрованный по материалу;
    - `footer_categories` — до 2 первых разделов каталога (корневые категории,
      плитки под баннерами).
    """
    footer_sections = list(
        Material.objects
        .filter(is_active=True)
        .exclude(landing_title='')[:2]
    )
    footer_categories = list(
        Category.get_root_nodes().filter(is_active=True)[:2]
    )
    return {
        'footer_sections': footer_sections,
        'footer_categories': footer_categories,
    }
