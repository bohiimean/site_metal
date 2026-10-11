from apps.catalog.models import Category, Product, ProductParameter, ProductParamValue


def make_category(name='Профили', slug='profili', parent=None):
    if parent is not None:
        return parent.add_child(name=name, slug=slug)
    return Category.add_root(name=name, slug=slug)


def make_product(category, name='Профиль', slug='profil', **kwargs):
    return Product.objects.create(name=name, slug=slug, category=category, **kwargs)


def add_param(product, parameter, values=(), allow_custom=False, sort_order=0):
    """Подключает параметр справочника к товару со списком значений."""
    pp = ProductParameter.objects.create(
        product=product, parameter=parameter,
        allow_custom=allow_custom, sort_order=sort_order,
    )
    for order, value in enumerate(values):
        ProductParamValue.objects.create(
            product_parameter=pp, value=value, sort_order=order,
        )
    return pp
