from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.catalog.models import CategoryFacet, ProductParameter, ProductParamValue
from apps.catalog.utils import natural_sort_key
from apps.references.models import Parameter

from .helpers import add_param, make_category, make_product


class NaturalSortKeyTests(TestCase):
    def test_numbers_sorted_by_value_not_as_text(self):
        self.assertEqual(
            sorted(['10', '2.7', '3'], key=natural_sort_key),
            ['2.7', '3', '10'],
        )

    def test_comma_decimal_separator(self):
        self.assertEqual(
            sorted(['3', '2,5', '12'], key=natural_sort_key),
            ['2,5', '3', '12'],
        )

    def test_compound_sizes_sorted_by_numbers_inside(self):
        self.assertEqual(
            sorted(['100×20', '20×20', '40×20', '20×10'], key=natural_sort_key),
            ['20×10', '20×20', '40×20', '100×20'],
        )

    def test_mixed_text_does_not_crash(self):
        values = ['под заказ', '3', 'abc', '2']
        result = sorted(values, key=natural_sort_key)
        self.assertEqual(result[:2], ['2', '3'])
        self.assertEqual(set(result), set(values))


class ProductParameterTests(TestCase):
    def setUp(self):
        self.cat = make_category()
        self.product = make_product(self.cat)
        self.length = Parameter.objects.create(name='Длина', unit='м')

    def test_parameter_attached_to_product_once(self):
        add_param(self.product, self.length, ['3'])
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                ProductParameter.objects.create(product=self.product, parameter=self.length)

    def test_value_unique_within_product_parameter(self):
        pp = add_param(self.product, self.length, ['3'])
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                ProductParamValue.objects.create(product_parameter=pp, value='3')

    def test_same_value_allowed_in_different_parameters(self):
        height = Parameter.objects.create(name='Высота', unit='мм')
        add_param(self.product, self.length, ['3'])
        add_param(self.product, height, ['3'])
        self.assertEqual(ProductParamValue.objects.filter(value='3').count(), 2)

    def test_values_ordered_by_sort_order(self):
        pp = add_param(self.product, self.length, ['3', '2.7', '6'])
        self.assertEqual(
            [v.value for v in pp.values.all()],
            ['3', '2.7', '6'],
        )

    def test_product_parameters_ordered_by_sort_order(self):
        height = Parameter.objects.create(name='Высота', unit='мм')
        add_param(self.product, self.length, ['3'], sort_order=1)
        add_param(self.product, height, ['40'], sort_order=0)
        self.assertEqual(
            [pp.parameter.name for pp in self.product.parameters.all()],
            ['Высота', 'Длина'],
        )

    def test_used_parameter_cannot_be_deleted(self):
        add_param(self.product, self.length, ['3'])
        with self.assertRaises(ProtectedError):
            self.length.delete()

    def test_deleting_product_removes_its_parameters_and_values(self):
        add_param(self.product, self.length, ['3'])
        self.product.delete()
        self.assertFalse(ProductParameter.objects.exists())
        self.assertFalse(ProductParamValue.objects.exists())
        self.assertTrue(Parameter.objects.filter(pk=self.length.pk).exists())


class CategoryFacetParameterTests(TestCase):
    def setUp(self):
        self.cat = make_category()
        self.width = Parameter.objects.create(name='Ширина', unit='мм')
        self.length = Parameter.objects.create(name='Длина', unit='м')

    def test_param_facet_requires_parameter(self):
        facet = CategoryFacet(category=self.cat, facet='param')
        with self.assertRaises(ValidationError):
            facet.full_clean()

    def test_regular_facet_must_not_have_parameter(self):
        facet = CategoryFacet(category=self.cat, facet='material', parameter=self.width)
        with self.assertRaises(ValidationError):
            facet.full_clean()

    def test_several_parameter_facets_in_one_category(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.length)
        self.assertEqual(self.cat.facets.count(), 2)

    def test_same_parameter_facet_twice_rejected(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                CategoryFacet.objects.create(
                    category=self.cat, facet='param', parameter=self.width)

    def test_same_regular_facet_twice_still_rejected(self):
        CategoryFacet.objects.create(category=self.cat, facet='material')
        with self.assertRaises((IntegrityError, ValidationError)):
            with transaction.atomic():
                CategoryFacet.objects.create(category=self.cat, facet='material')

    def test_deleting_unused_parameter_removes_its_facets(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        self.width.delete()
        self.assertFalse(self.cat.facets.exists())

    def test_old_size_and_length_facet_keys_are_gone(self):
        keys = dict(CategoryFacet.FACET_CHOICES)
        self.assertNotIn('size', keys)
        self.assertNotIn('length', keys)
        self.assertIn('param', keys)
