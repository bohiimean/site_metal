import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.references.models import Material, SteelGrade, Finish, Color
from .filters import ProductFilter
from .models import (
    Category, CategoryFacet, Product, ProductOptionNode, ProductParamValue,
)

PAGE_SIZE = 9
# Значения — кортежи полей для order_by. Дефолт «new» поднимает популярные
# (is_featured) наверх в заданном порядке (featured_order), остальное — по
# новизне. При явной сортировке по имени закрепление не применяется — это
# осознанный выбор посетителя.
SORT_MAP = {
    'name': ('name',),
    'new':  ('-is_featured', 'featured_order', '-created_at'),
}
DEFAULT_SORT = SORT_MAP['new']

# Набор фасетов по умолчанию — для категорий без своей настройки
# (CategoryFacet) и для страниц без категории (весь каталог, поиск)
DEFAULT_FACET_KEYS = ['material', 'steel_grade', 'finish', 'in_stock']


def _product_qs():
    """Базовый QuerySet товаров с нужными join-ами."""
    return Product.objects.for_cards()


def _facet_config(category):
    """Состав фасетов: (ключ, свой заголовок). Наследование вверх по дереву:
    первая категория (от текущей к корню), у которой есть хоть одна строка
    CategoryFacet, задаёт конфиг; показываются только её активные фасеты."""
    if category:
        for cat in [category] + list(reversed(category.get_ancestors())):
            rows = list(cat.facets.all())
            if rows:
                return [(r.facet, r.title) for r in rows if r.is_active]
    return [(k, '') for k in DEFAULT_FACET_KEYS]


def _facet_ctx(request, category=None):
    """Фасеты сайдбара: состав и порядок — из настройки раздела (CategoryFacet),
    значения — автоматически из дерева опций и параметров товаров раздела.
    Фасет без значений скрывается."""
    node_qs = ProductOptionNode.objects.filter(product__is_active=True)
    param_qs = ProductParamValue.objects.filter(product__is_active=True)
    if category:
        cat_ids = [c.pk for c in category.get_descendants(include_self=True)]
        node_qs = node_qs.filter(product__category_id__in=cat_ids)
        param_qs = param_qs.filter(product__category_id__in=cat_ids)

    titles = dict(CategoryFacet.FACET_CHOICES)
    facets = []
    for key, custom_title in _facet_config(category):
        options = []
        if key == 'material':
            options = Material.objects.filter(
                is_active=True, pk__in=node_qs.values('material_id'))
        elif key == 'steel_grade':
            options = SteelGrade.objects.filter(
                is_active=True, pk__in=node_qs.values('steel_grade_id'))
        elif key == 'finish':
            options = Finish.objects.filter(
                is_active=True, pk__in=node_qs.values('finish_id'))
        elif key == 'color':
            # Цвета раздела — объединение ручных наборов и палитр обработок
            manual_ids = node_qs.filter(
                colors__is_active=True).values_list('colors', flat=True)
            palette_color_ids = node_qs.filter(
                palette__is_active=True, palette__colors__is_active=True,
            ).values_list('palette__colors', flat=True)
            ids = set(manual_ids) | set(palette_color_ids)
            options = Color.objects.filter(is_active=True, pk__in=ids)
        elif key == 'size':
            values = param_qs.filter(kind='size').values_list('value', flat=True).distinct()
            options = [
                {'pk': s, 'name': s}
                for s in sorted(values, key=lambda s: (len(s), s))
            ]
        elif key == 'length':
            values = param_qs.filter(kind='length').values_list('value', flat=True).distinct()
            options = [
                {'pk': v, 'name': f'{v} м'}
                for v in sorted(values, key=lambda v: (len(v), v))
            ]

        if key != 'in_stock' and not options:
            continue  # в разделе нет значений — фасет не показываем
        facets.append({
            'name':     key,
            'title':    custom_title or titles[key],
            'options':  options,
            'selected': request.GET.getlist(key),
            'is_bool':  key == 'in_stock',
        })
    return {'facets': facets}


def search_view(request):
    q = request.GET.get('q', '').strip()
    qs = _product_qs()

    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(profile_code__icontains=q) |
            Q(category__name__icontains=q) |
            Q(option_nodes__material__name__icontains=q)
        )

    filterset = ProductFilter(request.GET, queryset=qs)
    products = filterset.qs.distinct()

    sort = request.GET.get('sort', 'new')
    products = products.order_by(*SORT_MAP.get(sort, DEFAULT_SORT))

    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_num = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page_num = 1
    page_obj = paginator.get_page(page_num)

    suggestions = Category.objects.filter(is_active=True, depth=1).order_by('path')[:3]
    is_htmx = request.headers.get('HX-Request') == 'true'

    ctx = {
        'q': q,
        'page_obj': page_obj,
        'paginator': paginator,
        'filterset': filterset,
        'sort': sort,
        'suggestions': suggestions,
        **_facet_ctx(request),
    }

    if is_htmx and page_num > 1:
        return render(request, 'catalog/_product_cards.html', ctx)
    if is_htmx:
        return render(request, 'catalog/_search_grid.html', ctx)
    return render(request, 'catalog/search.html', ctx)


def products_index(request):
    """Страница «Продукция»: основные разделы (материалы) + категории карточками."""
    main_sections = (
        Material.objects
        .filter(is_active=True)
        .exclude(landing_title='')
    )
    categories = Category.get_root_nodes().filter(is_active=True)
    return render(request, 'catalog/products_index.html', {
        'main_sections': main_sections,
        'categories': categories,
    })


def catalog_index(request):
    return _render_catalog(request, category=None)


def catalog_slug_view(request, slug):
    """Роутер: slug может быть продуктом или категорией."""
    product = Product.objects.filter(slug=slug, is_active=True).first()
    if product:
        return _product_detail(request, product)

    category = Category.objects.filter(slug=slug, is_active=True).first()
    if category:
        return _render_catalog(request, category=category)

    raise Http404


def _render_catalog(request, category):
    qs = _product_qs()
    if category:
        cat_ids = [c.pk for c in category.get_descendants(include_self=True)]
        qs = qs.filter(category_id__in=cat_ids)

    filterset = ProductFilter(request.GET, queryset=qs)
    products = filterset.qs.distinct()

    sort = request.GET.get('sort', 'new')
    products = products.order_by(*SORT_MAP.get(sort, DEFAULT_SORT))

    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_num = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page_num = 1
    page_obj = paginator.get_page(page_num)

    is_htmx = request.headers.get('HX-Request') == 'true'

    ctx = {
        'page_obj':          page_obj,
        'paginator':         paginator,
        'filterset':         filterset,
        'category':          category,
        'sort':              sort,
        'categories':        Category.objects.filter(is_active=True, depth=1),
        **_facet_ctx(request, category),
    }

    if is_htmx and page_num > 1:
        return render(request, 'catalog/_product_cards.html', ctx)
    if is_htmx:
        return render(request, 'catalog/_product_grid.html', ctx)
    return render(request, 'catalog/catalog.html', ctx)


# ─── Product detail ───────────────────────────────────────────

def _schema_org(request, product, images):
    """JSON-LD: Product + BreadcrumbList.

    Offer/цена не выводятся намеренно — цен на сайте нет (цену называет
    менеджер), а Offer без price невалиден для поисковиков.
    """
    product_schema = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': product.name,
        'url': request.build_absolute_uri(product.get_absolute_url()),
    }
    description = strip_tags(product.seo_description or product.description)
    if description:
        product_schema['description'] = Truncator(description).chars(500)
    if product.profile_code:
        product_schema['sku'] = product.profile_code
    if product.category:
        product_schema['category'] = product.category.name
    if images:
        try:
            product_schema['image'] = request.build_absolute_uri(images[0].gallery.url)
        except Exception:
            pass  # исходный файл недоступен — schema без картинки

    crumbs = [('Главная', '/'), ('Все товары', reverse('catalog:index'))]
    if product.category:
        crumbs.append((
            product.category.name,
            reverse('catalog:detail', kwargs={'slug': product.category.slug}),
        ))
    crumbs.append((product.name, product.get_absolute_url()))
    breadcrumb_schema = {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': i,
                'name': name,
                'item': request.build_absolute_uri(url),
            }
            for i, (name, url) in enumerate(crumbs, 1)
        ],
    }

    data = json.dumps([product_schema, breadcrumb_schema], ensure_ascii=False)
    # '<' экранируем, чтобы контент из админки не мог закрыть тег <script>
    return data.replace('<', '\\u003C')


def _color_dict(c):
    return {
        'id':       c.id,
        'name':     c.name,
        'hex':      c.hex_code,
        'ral_code': c.ral_code,
        'group':    c.color_group,
    }


def _option_tree(product):
    """Дерево опций для Alpine: материалы → марки → обработки (+ цвета листа).

    Обработка может висеть и прямо под материалом (материал без марок).
    Неактивные справочные записи скрываются вместе с поддеревом.
    """
    nodes = list(
        product.option_nodes
        .select_related('material', 'steel_grade', 'finish', 'palette')
        .prefetch_related('colors', 'palette__colors')
        .order_by('sort_order', 'id')
    )
    by_parent = {}
    for n in nodes:
        by_parent.setdefault(n.parent_id, []).append(n)

    def finish_dict(node):
        colors = [_color_dict(c) for c in node.effective_colors()]
        colors.sort(key=lambda c: (c['group'], c['name']))
        return {
            'id':       node.id,
            'finish_id': node.finish_id,
            'name':     node.finish.name,
            'color_ui': node.finish.color_ui,
            'colors':   colors,
        }

    tree = []
    for m_node in by_parent.get(None, []):
        if m_node.node_type != 'material' or not m_node.material.is_active:
            continue
        entry = {
            'id':          m_node.id,
            'material_id': m_node.material_id,
            'name':        m_node.material.name,
            'grades':      [],
            'finishes':    [],
        }
        for child in by_parent.get(m_node.id, []):
            if child.node_type == 'steel_grade' and child.steel_grade.is_active:
                grade = {
                    'id':       child.id,
                    'grade_id': child.steel_grade_id,
                    'name':     child.steel_grade.name,
                    'finishes': [
                        finish_dict(f) for f in by_parent.get(child.id, [])
                        if f.node_type == 'finish' and f.finish.is_active
                    ],
                }
                entry['grades'].append(grade)
            elif child.node_type == 'finish' and child.finish.is_active:
                entry['finishes'].append(finish_dict(child))
        tree.append(entry)
    return tree


def _photo_rules(product):
    """Фото-правила для клиентского подбора: условия + URL пресетов."""
    rules = []
    qs = (
        product.images.overrides()
        .select_related('color')
        .order_by('sort_order')
    )
    for img in qs:
        try:
            urls = {
                'thumb':   img.thumb.url,
                'card':    img.card.url,
                'gallery': img.gallery.url,
                'zoom':    img.zoom.url,
            }
        except Exception:
            continue  # исходный файл недоступен — правило пропускаем
        rules.append({
            'material_id': img.material_id,
            'finish_id':   img.finish_id,
            'color_id':    img.color_id,
            'color_group': img.color_group or None,
            'urls':        urls,
        })
    return rules


def _product_detail(request, product):
    # Миниатюры: обычные фото галереи; если менеджер загрузил только
    # фото-правила — показываем их, чтобы карточка не оставалась без фото
    images = list(product.images.gallery().order_by('sort_order'))
    if not images:
        images = list(product.images.overrides().order_by('sort_order'))

    # Данные изображений для Alpine (смена фото, srcset, лайтбокс).
    # gallery/zoom вписывают предмет целиком (ResizeToFit), без обрезки
    images_data = []
    for img in images:
        try:
            images_data.append({
                'thumb':   img.thumb.url,
                'gallery': img.gallery.url,
                'zoom':    img.zoom.url,
            })
        except Exception:
            continue  # исходный файл недоступен — пропускаем

    params = {'size': [], 'length': [], 'height': []}
    for pv in product.param_values.all():
        params.setdefault(pv.kind, []).append(pv.value)

    product_json = {
        'name':             product.name,
        'slug':             product.slug,
        'in_stock':         product.in_stock,
        'in_stock_display': product.get_in_stock_display(),
        'allow_custom_size':   product.allow_custom_size,
        'allow_custom_length': product.allow_custom_length,
        'allow_custom_height': product.allow_custom_height,
    }

    return render(request, 'catalog/product_detail.html', {
        'product':           product,
        'images':            images,
        'images_json':       images_data,
        'product_json':      product_json,
        'tree_json':         _option_tree(product),
        'params_json':       params,
        'photo_rules_json':  _photo_rules(product),
        'schema_org':        _schema_org(request, product, images),
    })
