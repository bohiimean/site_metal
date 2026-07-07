from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render

from apps.references.models import Material
from .filters import ProductFilter
from .models import Category, Product

PAGE_SIZE = 9
SORT_MAP = {
    'price_asc':  'min_price',
    'price_desc': '-min_price',
    'new':        '-created_at',
}


def _product_qs():
    """Базовый QuerySet товаров с нужными join-ами."""
    return Product.objects.for_cards()


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

    materials = Material.objects.filter(is_active=True)
    suggestions = Category.objects.filter(is_active=True, depth=1)[:3]
    is_htmx = request.headers.get('HX-Request') == 'true'

    ctx = {
        'q': q,
        'page_obj': page_obj,
        'paginator': paginator,
        'filterset': filterset,
        'sort': sort,
        'materials': materials,
        'suggestions': suggestions,
        'selected_materials': request.GET.getlist('material'),
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

    materials = Material.objects.filter(is_active=True)
    is_htmx = request.headers.get('HX-Request') == 'true'

    ctx = {
        'page_obj':          page_obj,
        'paginator':         paginator,
        'filterset':         filterset,
        'category':          category,
        'sort':              sort,
        'materials':         materials,
        'categories':        Category.objects.filter(is_active=True, depth=1),
        'selected_materials': request.GET.getlist('material'),
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
        .select_related('material', 'steel_grade', 'finish', 'color', 'image')
        .order_by('price')
    )
    images = list(product.images.order_by('sort_order'))

    variants_data = []
    for v in variants_qs:
        img = v.image or (images[0] if images else None)
        try:
            card_url    = img.card.url    if img and img.image else None
            gallery_url = img.gallery.url if img and img.image else None
        except Exception:
            card_url = gallery_url = None

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
            'color_id':         v.color_id,
            'color_name':       v.color.name        if v.color else None,
            'color_hex':        v.color.hex_code     if v.color else None,
            'color_ral_code':   v.color.ral_code     if v.color else '',
            'color_group':      v.color.color_group  if v.color else '',
            'height_mm':        str(v.height_mm) if v.height_mm else None,
            'length_m':         str(v.length_m)  if v.length_m  else None,
            'price':            str(v.price),
            'unit':             v.unit,
            'unit_display':     v.get_unit_display(),
            'in_stock':         v.in_stock,
            'in_stock_display': v.get_in_stock_display(),
            'image_url':        card_url,
            'gallery_url':      gallery_url,
        })

    combinations = [
        {
            'material_id':    v['material_id'],
            'steel_grade_id': v['steel_grade_id'],
            'finish_id':      v['finish_id'],
            'color_id':       v['color_id'],
            'length_m':       v['length_m'],
        }
        for v in variants_data
    ]

    return render(request, 'catalog/product_detail.html', {
        'product':           product,
        'images':            images,
        'variants_json':     variants_data,
        'combinations_json': combinations,
    })
