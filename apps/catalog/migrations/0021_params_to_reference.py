"""Справочник параметров, шаг 2 из 3: перенос данных.

Зашитые ключи size / length / height становятся записями справочника
«Размер», «Длина», «Высота» с прежними единицами и подписями (создаются
только используемые) — на витрине после переноса ничего не меняется. Флаги allow_custom_* переезжают в
ProductParameter, фильтры разделов «Размер»/«Длина» — в фильтры «Параметр».

Обратный ход сопоставляет параметры по названию: «Размер»/«Длина»/«Высота»
возвращаются в старые поля, остальные (новые) параметры при откате теряются.
"""
from django.db import migrations

# kind → (название, единица, подпись своего значения, пример)
FORMER = [
    ('size',   'Размер', '',   'Свой размер', '20×20'),
    ('length', 'Длина',  'м',  'Своя длина',  '2.7'),
    ('height', 'Высота', 'мм', 'Своя высота', '40'),
]


def forwards(apps, schema_editor):
    Parameter = apps.get_model('references', 'Parameter')
    Product = apps.get_model('catalog', 'Product')
    ProductParameter = apps.get_model('catalog', 'ProductParameter')
    ProductParamValue = apps.get_model('catalog', 'ProductParamValue')
    CategoryFacet = apps.get_model('catalog', 'CategoryFacet')

    # Запись справочника создаётся, только если параметр где-то используется:
    # на пустой базе (новый стенд) справочник остаётся пустым
    by_kind = {}

    def parameter(kind):
        if kind not in by_kind:
            order, (_, name, unit, custom_label, example) = next(
                (i, row) for i, row in enumerate(FORMER, start=1) if row[0] == kind)
            by_kind[kind] = Parameter.objects.create(
                name=name, unit=unit, custom_label=custom_label,
                example=example, sort_order=order,
            )
        return by_kind[kind]

    for product in Product.objects.all():
        position = 0
        for kind, *_ in FORMER:
            values = list(
                ProductParamValue.objects
                .filter(product=product, kind=kind)
                .order_by('sort_order', 'id')
            )
            custom = getattr(product, f'allow_custom_{kind}')
            if not values and not custom:
                continue
            pp = ProductParameter.objects.create(
                product=product, parameter=parameter(kind),
                allow_custom=custom, sort_order=position,
            )
            position += 1
            for order, pv in enumerate(values):
                pv.product_parameter = pp
                pv.sort_order = order
                pv.save(update_fields=['product_parameter', 'sort_order'])

    for facet in CategoryFacet.objects.filter(facet__in=['size', 'length']):
        facet.parameter = parameter(facet.facet)
        facet.facet = 'param'
        facet.save(update_fields=['facet', 'parameter'])


def backwards(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    ProductParameter = apps.get_model('catalog', 'ProductParameter')
    ProductParamValue = apps.get_model('catalog', 'ProductParamValue')
    CategoryFacet = apps.get_model('catalog', 'CategoryFacet')

    kind_by_name = {name: kind for kind, name, *_ in FORMER}

    seen = set()
    for pp in (ProductParameter.objects.select_related('parameter')
               .order_by('product_id', 'sort_order', 'id')):
        kind = kind_by_name.get(pp.parameter.name)
        # Два параметра с одним названием у товара старая схема не вмещает
        if kind is None or (pp.product_id, kind) in seen:
            continue
        seen.add((pp.product_id, kind))
        # По id, а не экземплярами: при откате исторические модели могут
        # оказаться из разных реестров состояния, и Django их не сопоставит
        ProductParamValue.objects.filter(product_parameter_id=pp.pk).update(
            product_id=pp.product_id, kind=kind)
        if pp.allow_custom:
            Product.objects.filter(pk=pp.product_id).update(
                **{f'allow_custom_{kind}': True})
    # Значения параметров, которых в старой схеме нет, не во что вернуть
    ProductParamValue.objects.filter(kind__isnull=True).delete()

    for facet in CategoryFacet.objects.filter(facet='param').select_related('parameter'):
        kind = kind_by_name.get(facet.parameter.name) if facet.parameter_id else None
        if kind in ('size', 'length'):
            facet.facet = kind
            facet.parameter = None
            facet.save(update_fields=['facet', 'parameter'])
        else:
            facet.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0020_productparameter'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
