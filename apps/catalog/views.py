import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.references.models import FinishColor, Material, SteelGrade, Finish
from .filters import ProductFilter
from .models import Category, Product

PAGE_SIZE = 9
SORT_MAP = {
    'name': 'name',
    'new':  '-created_at',
}


def _product_qs():
    """Базовый QuerySet товаров с нужными join-ами."""
    return Product.objects.for_cards()


def _facet_ctx(request):
    """Опции фасетов сайдбара. Значения — из справочников (управляются в админке);
    показываем только те, что реально встречаются в активных вариантах."""
    used = {'productvariant__is_active': True, 'is_active': True}
    return {
        'materials':             Material.objects.filter(**used).distinct(),
        'steel_grades':          SteelGrade.objects.filter(**used).distinct(),
        'finishes':              Finish.objects.filter(**used).distinct(),
        'selected_materials':    request.GET.getlist('material'),
        'selected_steel_grades': request.GET.getlist('steel_grade'),
        'selected_finishes':     request.GET.getlist('finish'),
    }


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
        **_facet_ctx(request),
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
    images = list(product.images.order_by('sort_order'))

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
            'length_m':       v['length_m'],
        }
        for v in variants_data
    ]

    # Палитра: цвета каждой обработки, встречающейся в вариантах (из FinishColor)
    finish_ids = {v['finish_id'] for v in variants_data if v['finish_id']}
    finish_colors = {}
    if finish_ids:
        fc_qs = (
            FinishColor.objects
            .filter(finish_id__in=finish_ids, color__is_active=True)
            .select_related('color')
            .order_by('color__color_group', 'color__name')
        )
        for fc in fc_qs:
            c = fc.color
            finish_colors.setdefault(fc.finish_id, []).append({
                'id':       c.id,
                'name':     c.name,
                'hex':      c.hex_code,
                'ral_code': c.ral_code,
                'group':    c.color_group,
            })

    # Карта «цвет → фото»: точный цвет приоритетнее группы;
    # fallback до дефолтного фото товара — на клиенте
    color_images = {}
    for ci in product.color_images.select_related('color'):
        try:
            urls = {'card': ci.card.url, 'gallery': ci.gallery.url, 'zoom': ci.zoom.url}
        except Exception:
            continue
        if ci.color_id:
            color_images[f'color:{ci.color_id}'] = urls
        elif ci.color_group:
            color_images[f'group:{ci.color_group}'] = urls

    return render(request, 'catalog/product_detail.html', {
        'product':            product,
        'images':             images,
        'images_json':        images_data,
        'variants_json':      variants_data,
        'combinations_json':  combinations,
        'finish_colors_json': finish_colors,
        'color_images_json':  color_images,
        'schema_org':         _schema_org(request, product, images),
    })
