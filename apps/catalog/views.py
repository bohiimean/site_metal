from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render

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

def _product_detail(request, product):
    variants_qs = (
        product.variants
        .filter(is_active=True)
        .select_related('material', 'steel_grade', 'finish')
        .order_by('sku')
    )
    images = list(product.images.order_by('sort_order'))

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
            urls = {'card': ci.card.url, 'gallery': ci.gallery.url}
        except Exception:
            continue
        if ci.color_id:
            color_images[f'color:{ci.color_id}'] = urls
        elif ci.color_group:
            color_images[f'group:{ci.color_group}'] = urls

    return render(request, 'catalog/product_detail.html', {
        'product':            product,
        'images':             images,
        'variants_json':      variants_data,
        'combinations_json':  combinations,
        'finish_colors_json': finish_colors,
        'color_images_json':  color_images,
    })
