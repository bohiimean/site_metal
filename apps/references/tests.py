from django.test import TestCase

from .models import Parameter


class ParameterTests(TestCase):
    def test_format_value_appends_unit(self):
        length = Parameter.objects.create(name='Длина', unit='м')
        self.assertEqual(length.format_value('3'), '3 м')

    def test_format_value_without_unit_is_bare_value(self):
        size = Parameter.objects.create(name='Размер', unit='')
        self.assertEqual(size.format_value('20×20'), '20×20')

    def test_custom_label_falls_back_to_generic(self):
        width = Parameter.objects.create(name='Ширина', unit='мм')
        self.assertEqual(width.custom_label_display, 'Своё значение')
        width.custom_label = 'Своя ширина'
        self.assertEqual(width.custom_label_display, 'Своя ширина')

    def test_filter_key_is_stable_and_unique_per_parameter(self):
        a = Parameter.objects.create(name='Ширина')
        b = Parameter.objects.create(name='Толщина')
        self.assertEqual(a.filter_key, f'p{a.pk}')
        self.assertNotEqual(a.filter_key, b.filter_key)

    def test_ordering_follows_sort_order(self):
        Parameter.objects.create(name='Высота', sort_order=3)
        Parameter.objects.create(name='Длина', sort_order=1)
        Parameter.objects.create(name='Ширина', sort_order=2)
        self.assertEqual(
            list(Parameter.objects.values_list('name', flat=True)),
            ['Длина', 'Ширина', 'Высота'],
        )

    def test_str_shows_unit(self):
        self.assertEqual(str(Parameter(name='Длина', unit='м')), 'Длина, м')
        self.assertEqual(str(Parameter(name='Размер', unit='')), 'Размер')
