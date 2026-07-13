from django.shortcuts import render

from apps.catalog.models import Category
from .models import HomeBlock


def index(request):
    blocks = (
        HomeBlock.objects
        .filter(is_active=True)
        .select_related('category')
        .order_by('sort_order')
    )

    # Пустые блоки не показываем: если во всех блоках нет товаров (или блоков
    # нет вовсе), шаблон через {% empty %} выведет публичный CTA, а не пустоту.
    blocks_with_products = [
        (block, products)
        for block in blocks
        if (products := list(block.get_products()))
    ]

    categories = list(Category.objects.filter(is_active=True, depth=1))

    return render(request, 'home/index.html', {
        'blocks_with_products': blocks_with_products,
        'categories':           categories,
    })
