from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Product, ProductParameter


class SeedDataTests(TestCase):
    def test_seed_creates_products_with_reference_parameters(self):
        call_command('seed_data', stdout=StringIO())
        self.assertTrue(Product.objects.exists())
        self.assertTrue(ProductParameter.objects.exists())
        # У П-профиля из сида — размеры и длина со «своей длиной»
        p1 = Product.objects.get(slug='profil-p-40x20x2')
        params = {pp.parameter.name: pp for pp in p1.parameters.select_related('parameter')}
        self.assertEqual(
            [v.value for v in params['Размер'].values.all()], ['20×20', '40×20', '60×30'])
        self.assertTrue(params['Длина'].allow_custom)

    def test_seed_is_idempotent(self):
        call_command('seed_data', stdout=StringIO())
        count = ProductParameter.objects.count()
        call_command('seed_data', stdout=StringIO())
        self.assertEqual(ProductParameter.objects.count(), count)
