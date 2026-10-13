"""Перенос размер/длина/высота из зашитых ключей в справочник параметров.

Состояние «до» — миграции catalog 0019 / references 0011 (последние перед
справочником). «После» — последние миграции приложений.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [
    ('catalog', '0019_product_image_angles'),
    ('references', '0011_alter_color_color_group'),
]


def latest():
    graph = MigrationExecutor(connection).loader.graph
    return [n for n in graph.leaf_nodes() if n[0] in ('catalog', 'references')]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class ParamsMigrationForwardTests(TransactionTestCase):
    def setUp(self):
        old = migrate(BEFORE)
        Category = old.get_model('catalog', 'Category')
        Product = old.get_model('catalog', 'Product')
        Value = old.get_model('catalog', 'ProductParamValue')
        Facet = old.get_model('catalog', 'CategoryFacet')

        cat = Category.objects.create(
            name='Профили', slug='profili', path='0001', depth=1, numchild=0)
        self.full = Product.objects.create(
            name='Полный', slug='full', category=cat, allow_custom_length=True)
        for order, v in enumerate(['40×20', '20×20']):
            Value.objects.create(product=self.full, kind='size', value=v, sort_order=order)
        Value.objects.create(product=self.full, kind='length', value='3', sort_order=0)
        Value.objects.create(product=self.full, kind='height', value='40', sort_order=0)

        self.custom_only = Product.objects.create(
            name='Только своя высота', slug='custom', category=cat,
            allow_custom_height=True)
        self.bare = Product.objects.create(name='Пустой', slug='bare', category=cat)

        Facet.objects.create(category=cat, facet='material', sort_order=0)
        Facet.objects.create(category=cat, facet='size', title='Сечение', sort_order=1)
        Facet.objects.create(category=cat, facet='length', sort_order=2, is_active=False)
        self.cat_id = cat.pk

        self.apps = migrate(latest())

    def tearDown(self):
        migrate(latest())

    def params_of(self, product_id):
        PP = self.apps.get_model('catalog', 'ProductParameter')
        return [
            (pp.parameter.name,
             list(pp.values.order_by('sort_order', 'id').values_list('value', flat=True)),
             pp.allow_custom)
            for pp in PP.objects.filter(product_id=product_id)
            .select_related('parameter').order_by('sort_order', 'id')
        ]

    def test_reference_has_three_former_parameters(self):
        Parameter = self.apps.get_model('references', 'Parameter')
        rows = list(Parameter.objects.order_by('sort_order').values_list(
            'name', 'unit', 'custom_label', 'is_active'))
        self.assertEqual(rows, [
            ('Размер', '', 'Свой размер', True),
            ('Длина', 'м', 'Своя длина', True),
            ('Высота', 'мм', 'Своя высота', True),
        ])

    def test_values_and_flags_moved_in_order(self):
        self.assertEqual(self.params_of(self.full.pk), [
            ('Размер', ['40×20', '20×20'], False),
            ('Длина', ['3'], True),
            ('Высота', ['40'], False),
        ])

    def test_custom_flag_without_values_kept(self):
        self.assertEqual(self.params_of(self.custom_only.pk), [('Высота', [], True)])

    def test_product_without_params_gets_none(self):
        self.assertEqual(self.params_of(self.bare.pk), [])

    def test_facets_converted_keeping_settings(self):
        Facet = self.apps.get_model('catalog', 'CategoryFacet')
        rows = list(
            Facet.objects.filter(category_id=self.cat_id).order_by('sort_order')
            .values_list('facet', 'parameter__name', 'title', 'is_active'))
        self.assertEqual(rows, [
            ('material', None, '', True),
            ('param', 'Размер', 'Сечение', True),
            ('param', 'Длина', '', False),
        ])


class ParamsMigrationBackwardTests(TransactionTestCase):
    def setUp(self):
        new = migrate(latest())
        Category = new.get_model('catalog', 'Category')
        Product = new.get_model('catalog', 'Product')
        Parameter = new.get_model('references', 'Parameter')
        PP = new.get_model('catalog', 'ProductParameter')
        Value = new.get_model('catalog', 'ProductParamValue')
        Facet = new.get_model('catalog', 'CategoryFacet')

        cat = Category.objects.create(
            name='Профили', slug='profili', path='0001', depth=1, numchild=0)
        product = Product.objects.create(name='Товар', slug='p', category=cat)
        # Строки, созданные миграцией, TransactionTestCase мог уже вычистить
        length, _ = Parameter.objects.get_or_create(
            name='Длина', defaults={'unit': 'м', 'sort_order': 2})
        width = Parameter.objects.create(name='Ширина', unit='мм', sort_order=10)

        pp = PP.objects.create(product=product, parameter=length, allow_custom=True)
        Value.objects.create(product_parameter=pp, value='6', sort_order=0)
        Value.objects.create(product_parameter=pp, value='3', sort_order=1)
        pw = PP.objects.create(product=product, parameter=width, sort_order=1)
        Value.objects.create(product_parameter=pw, value='20', sort_order=0)

        Facet.objects.create(category=cat, facet='param', parameter=length, sort_order=1)
        Facet.objects.create(category=cat, facet='param', parameter=width, sort_order=2)
        self.product_id, self.cat_id = product.pk, cat.pk

        self.apps = migrate(BEFORE)

    def tearDown(self):
        migrate(latest())

    def test_former_parameters_restored_to_old_fields(self):
        Product = self.apps.get_model('catalog', 'Product')
        Value = self.apps.get_model('catalog', 'ProductParamValue')
        product = Product.objects.get(pk=self.product_id)
        self.assertTrue(product.allow_custom_length)
        self.assertFalse(product.allow_custom_size)
        self.assertEqual(
            list(Value.objects.filter(product_id=self.product_id)
                 .order_by('kind', 'sort_order').values_list('kind', 'value')),
            [('length', '6'), ('length', '3')],
        )

    def test_facets_restored_new_parameters_dropped(self):
        Facet = self.apps.get_model('catalog', 'CategoryFacet')
        self.assertEqual(
            list(Facet.objects.filter(category_id=self.cat_id).values_list('facet', flat=True)),
            ['length'],
        )
