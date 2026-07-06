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

    blocks_with_products = [
        (block, list(block.get_products()))
        for block in blocks
    ]

    categories = list(Category.objects.filter(is_active=True, depth=1))

    return render(request, 'home/index.html', {
        'blocks_with_products': blocks_with_products,
        'categories':           categories,
    })
