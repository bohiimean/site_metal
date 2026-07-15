import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.references.models import MaterialColor, SteelGradeColor, Material, SteelGrade, Finish
from .filters import ProductFilter
from .models import Category, CategoryFacet, Product, ProductVariant

PAGE_SIZE = 9
SORT_MAP = {
    'name': 'name',
    'new':  '-created_at',
}

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


def _trim_length(value):
    s = str(value).rstrip('0').rstrip('.')
    return f'{s} м'


def _facet_ctx(request, category=None):
    """Фасеты сайдбара: состав и порядок — из настройки раздела (CategoryFacet),
    значения — автоматически из активных вариантов товаров раздела.
    Фасет без значений скрывается."""
    variant_qs = ProductVariant.objects.filter(is_active=True, product__is_active=True)
    if category:
        cat_ids = [c.pk for c in category.get_descendants(include_self=True)]
        variant_qs = variant_qs.filter(product__category_id__in=cat_ids)

    titles = dict(CategoryFacet.FACET_CHOICES)
    facets = []
    for key, custom_title in _facet_config(category):
        options = []
        if key == 'material':
            options = Material.objects.filter(
                is_active=True, pk__in=variant_qs.values('material_id'))
        elif key == 'steel_grade':
            options = SteelGrade.objects.filter(
                is_active=True, pk__in=variant_qs.values('steel_grade_id'))
        elif key == 'finish':
            options = Finish.objects.filter(
                is_active=True, pk__in=variant_qs.values('finish_id'))
        elif key == 'size':
            values = variant_qs.exclude(size='').values_list('size', flat=True).distinct()
            options = [
                {'pk': s, 'name': s}
                for s in sorted(values, key=lambda s: (len(s), s))
            ]
        elif key == 'length':
            values = variant_qs.exclude(length_m=None).values_list('length_m', flat=True).distinct()
            options = [{'pk': str(l), 'name': _trim_length(l)} for l in sorted(values)]

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
            Q(variants__material__name__icontains=q)
        )

    filterset = ProductFilter(request.GET, queryset=qs)
    products = filterset.qs.distinct()

    sort = request.GET.get('sort', 'new')
    products = products.order_by(SORT_MAP.get(sort, '-created_at'))

    paginator = Paginator(products, PAGE_SIZE)
    try:
        page_num = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page_num = 1
    page_obj = paginator.get_page(page_num)

    suggestions = Category.objects.filter(is_active=True, depth=1)[:3]
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
    products = products.order_by(SORT_MAP.get(sort, '-created_at'))

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


def _product_detail(request, product):
    variants_qs = (
        product.variants
        .filter(is_active=True)
        .select_related('material', 'steel_grade', 'finish')
        .order_by('sku')
    )
    # Миниатюры: обычные фото галереи; если менеджер загрузил только фото,
    # привязанные к обработке/цвету, — показываем их, чтобы карточка
    # не оставалась без фото до выбора нужной комбинации
    images = list(product.images.gallery().order_by('sort_order'))
    if not images:
        images = list(product.images.overrides().order_by('sort_order'))

    # Данные изображений для Alpine (смена фото, srcset, лайтбокс).
    # gallery/zoom вписывают предмет целиком (ResizeToFit), без обрезки.
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

    variants_data = []
    for v in variants_qs:
        variants_data.append({
            'id':               v.id,
            'sku':              v.sku,
            'material_id':      v.material_id,
            'material_name':    v.material.name,
            'steel_grade_id':   v.steel_grade_id,
            'steel_grade_name': v.steel_grade.name if v.steel_grade else None,
            'finish_id':        v.finish_id,
            'finish_name':      v.finish.name      if v.finish else None,
            'finish_color_ui':  v.finish.color_ui  if v.finish else 'swatches',
            'size':             v.size or None,
            'allow_custom_size': v.allow_custom_size,
            'height_mm':        str(v.height_mm) if v.height_mm else None,
            'length_m':         str(v.length_m)  if v.length_m  else None,
            'allow_custom_length': v.allow_custom_length,
            'unit':             v.unit,
            'unit_display':     v.get_unit_display(),
            'in_stock':         v.in_stock,
            'in_stock_display': v.get_in_stock_display(),
        })

    combinations = [
        {
            'material_id':    v['material_id'],
            'steel_grade_id': v['steel_grade_id'],
            'finish_id':      v['finish_id'],
            'size':           v['size'],
            'length_m':       v['length_m'],
        }
        for v in variants_data
    ]

    # Палитры: цвета марок (SteelGradeColor) + фолбэк-палитры материалов
    # (MaterialColor) — для вариантов без марки или марок без своих цветов.
    # Интерфейс выбора (свотчи/RAL/свой) определяет обработка (finish_color_ui)
    def _color_dict(c):
        return {
            'id':       c.id,
            'name':     c.name,
            'hex':      c.hex_code,
            'ral_code': c.ral_code,
            'group':    c.color_group,
        }

    grade_ids = {v['steel_grade_id'] for v in variants_data if v['steel_grade_id']}
    grade_colors = {}
    if grade_ids:
        gc_qs = (
            SteelGradeColor.objects
            .filter(steel_grade_id__in=grade_ids, color__is_active=True)
            .select_related('color')
            .order_by('color__color_group', 'color__name')
        )
        for gc in gc_qs:
            grade_colors.setdefault(gc.steel_grade_id, []).append(_color_dict(gc.color))

    material_ids = {v['material_id'] for v in variants_data if v['material_id']}
    material_colors = {}
    if material_ids:
        mc_qs = (
            MaterialColor.objects
            .filter(material_id__in=material_ids, color__is_active=True)
            .select_related('color')
            .order_by('color__color_group', 'color__name')
        )
        for mc in mc_qs:
            material_colors.setdefault(mc.material_id, []).append(_color_dict(mc.color))

    # Карта «обработка/цвет → фото». Ключи (клиент перебирает от точного
    # к общему: обработка+цвет → обработка+группа → цвет → группа → обработка):
    #   finish:<fid>|color:<cid> / finish:<fid>|group:<g> /
    #   color:<cid> / group:<g> / finish:<fid>
    color_images = {}
    finish_fallbacks = {}  # первое фото каждой обработки — показ, пока цвет не выбран
    for ci in product.images.overrides().order_by('sort_order').select_related('color'):
        try:
            urls = {
                'thumb':   ci.thumb.url,
                'card':    ci.card.url,
                'gallery': ci.gallery.url,
                'zoom':    ci.zoom.url,
            }
        except Exception:
            continue
        if ci.color_id:
            suffix = f'color:{ci.color_id}'
        elif ci.color_group:
            suffix = f'group:{ci.color_group}'
        else:
            suffix = ''
        if ci.finish_id and suffix:
            key = f'finish:{ci.finish_id}|{suffix}'
        elif ci.finish_id:
            key = f'finish:{ci.finish_id}'
        else:
            key = suffix
        color_images[key] = urls
        if ci.finish_id:
            finish_fallbacks.setdefault(ci.finish_id, urls)

    # Если у обработки нет своего фото «без цвета» — фоллбэком служит
    # её первое фото (setdefault не перетирает явный ключ finish:<id>)
    for fid, urls in finish_fallbacks.items():
        color_images.setdefault(f'finish:{fid}', urls)

    return render(request, 'catalog/product_detail.html', {
        'product':            product,
        'images':             images,
        'images_json':        images_data,
        'variants_json':      variants_data,
        'combinations_json':  combinations,
        'grade_colors_json':  grade_colors,
        'material_colors_json': material_colors,
        'color_images_json':  color_images,
        'schema_org':         _schema_org(request, product, images),
    })
