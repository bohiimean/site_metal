import json

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import ProductParameter, ProductParamValue
from apps.references.models import Parameter

from .helpers import add_param, make_category, make_product


class AdminTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            'admin', 'admin@example.com', 'pass')
        self.client.force_login(self.user)
        self.cat = make_category()
        self.product = make_product(self.cat)
        self.length = Parameter.objects.create(
            name='Длина', unit='м', custom_label='Своя длина', example='3', sort_order=1)
        self.width = Parameter.objects.create(name='Ширина', unit='мм', sort_order=2)

    def change_url(self, product=None):
        return reverse('admin:catalog_product_change', args=[(product or self.product).pk])

    def post_product(self, free_params, product=None):
        """Сохраняет форму товара как кнопка «Сохранить» в админке."""
        product = product or self.product
        raw = free_params if isinstance(free_params, str) else json.dumps(free_params)
        data = {
            'name': product.name,
            'slug': product.slug,
            'category': product.category_id,
            'profile_code': product.profile_code,
            'in_stock': product.in_stock,
            'is_active': 'on',
            'description': '',
            'seo_title': '',
            'seo_description': '',
            'free_params': raw,
            '_continue': '1',
        }
        for prefix in ('images', 'related_links'):
            data.update({
                f'{prefix}-TOTAL_FORMS': '0',
                f'{prefix}-INITIAL_FORMS': '0',
                f'{prefix}-MIN_NUM_FORMS': '0',
                f'{prefix}-MAX_NUM_FORMS': '1000',
            })
        response = self.client.post(self.change_url(product), data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None)
                         and response.context.get('errors'))
        return response

    def state(self):
        """Параметры товара из БД в форме [(название, [значения], свой?)]."""
        return [
            (pp.parameter.name, [v.value for v in pp.values.all()], pp.allow_custom)
            for pp in self.product.parameters.select_related('parameter')
        ]


class ProductChangeViewTests(AdminTestCase):
    def test_change_page_renders_with_parameter_data(self):
        add_param(self.product, self.length, ['3', '6'], allow_custom=True)
        response = self.client.get(self.change_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="param-state-data"')
        self.assertContains(response, 'name="free_params"')

    def test_param_state_lists_product_parameters_in_order(self):
        add_param(self.product, self.width, ['20'], sort_order=1)
        add_param(self.product, self.length, ['3', '6'], allow_custom=True, sort_order=0)

        state = self.client.get(self.change_url()).context['param_state_json']

        self.assertEqual(state, [
            {'parameter_id': self.length.pk, 'values': ['3', '6'], 'custom': True},
            {'parameter_id': self.width.pk, 'values': ['20'], 'custom': False},
        ])

    def test_dicts_describe_parameters_with_suggestions_from_other_products(self):
        other = make_product(self.cat, slug='other')
        third = make_product(self.cat, slug='third')
        add_param(other, self.length, ['6', '2.7'])
        add_param(third, self.length, ['12', '6'])
        add_param(third, self.width, ['40'])
        add_param(self.product, self.length, ['3'])

        dicts = self.client.get(self.change_url()).context['option_dicts_json']
        params = {p['id']: p for p in dicts['parameters']}

        length = params[self.length.pk]
        self.assertEqual(length['name'], 'Длина')
        self.assertEqual(length['unit'], 'м')
        self.assertEqual(length['custom_label'], 'Своя длина')
        self.assertEqual(length['example'], '3')
        self.assertTrue(length['is_active'])
        # Без повторов, по числу; значения другого параметра не подмешиваются
        self.assertEqual(length['suggestions'], ['2.7', '3', '6', '12'])
        self.assertEqual(params[self.width.pk]['suggestions'], ['40'])

    def test_dicts_parameters_follow_reference_order(self):
        dicts = self.client.get(self.change_url()).context['option_dicts_json']
        self.assertEqual([p['name'] for p in dicts['parameters']], ['Длина', 'Ширина'])

    def test_inactive_parameter_marked_in_dicts(self):
        self.width.is_active = False
        self.width.save()
        dicts = self.client.get(self.change_url()).context['option_dicts_json']
        params = {p['id']: p for p in dicts['parameters']}
        self.assertFalse(params[self.width.pk]['is_active'])


class ProductSaveParamsTests(AdminTestCase):
    def test_creates_parameters_in_given_order(self):
        self.post_product([
            {'parameter_id': self.width.pk, 'values': ['20', '40'], 'custom': False},
            {'parameter_id': self.length.pk, 'values': ['3'], 'custom': True},
        ])
        self.assertEqual(self.state(), [
            ('Ширина', ['20', '40'], False),
            ('Длина', ['3'], True),
        ])

    def test_reorders_parameters_and_values(self):
        add_param(self.product, self.length, ['3', '6'], sort_order=0)
        add_param(self.product, self.width, ['20'], sort_order=1)

        self.post_product([
            {'parameter_id': self.width.pk, 'values': ['20'], 'custom': False},
            {'parameter_id': self.length.pk, 'values': ['6', '3'], 'custom': False},
        ])

        self.assertEqual(self.state(), [
            ('Ширина', ['20'], False),
            ('Длина', ['6', '3'], False),
        ])

    def test_removes_parameters_and_values_not_in_form(self):
        add_param(self.product, self.length, ['3', '6'])
        add_param(self.product, self.width, ['20'])

        self.post_product([
            {'parameter_id': self.length.pk, 'values': ['6'], 'custom': False},
        ])

        self.assertEqual(self.state(), [('Длина', ['6'], False)])
        self.assertEqual(ProductParamValue.objects.count(), 1)

    def test_empty_list_removes_all_parameters(self):
        add_param(self.product, self.length, ['3'])
        self.post_product([])
        self.assertFalse(self.product.parameters.exists())

    def test_parameter_without_values_and_custom_not_saved(self):
        self.post_product([
            {'parameter_id': self.length.pk, 'values': [], 'custom': False},
            {'parameter_id': self.width.pk, 'values': [], 'custom': True},
        ])
        self.assertEqual(self.state(), [('Ширина', [], True)])

    def test_values_cleaned_trimmed_deduplicated_and_truncated(self):
        long_value = 'x' * 80
        self.post_product([
            {'parameter_id': self.length.pk,
             'values': [' 3 ', '3', '', '   ', 6, long_value],
             'custom': False},
        ])
        self.assertEqual(self.state(), [('Длина', ['3', '6', 'x' * 50], False)])

    def test_unknown_parameter_ignored(self):
        self.post_product([
            {'parameter_id': 999999, 'values': ['1'], 'custom': False},
            {'parameter_id': 'abc', 'values': ['1'], 'custom': False},
            {'parameter_id': self.length.pk, 'values': ['3'], 'custom': False},
        ])
        self.assertEqual(self.state(), [('Длина', ['3'], False)])

    def test_duplicate_parameter_entry_first_wins(self):
        self.post_product([
            {'parameter_id': self.length.pk, 'values': ['3'], 'custom': False},
            {'parameter_id': self.length.pk, 'values': ['6'], 'custom': True},
        ])
        self.assertEqual(self.state(), [('Длина', ['3'], False)])

    def test_malformed_entries_skipped(self):
        self.post_product([
            'мусор', None, 42,
            {'parameter_id': self.length.pk, 'values': 'не список', 'custom': False},
            {'parameter_id': self.width.pk, 'values': ['20'], 'custom': False},
        ])
        self.assertEqual(self.state(), [('Ширина', ['20'], False)])

    def test_invalid_json_keeps_parameters_and_warns(self):
        add_param(self.product, self.length, ['3'])
        response = self.post_product('{не json')
        self.assertEqual(self.state(), [('Длина', ['3'], False)])
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('Параметры не сохранены' in m for m in messages), messages)

    def test_old_dict_format_rejected_without_changes(self):
        add_param(self.product, self.length, ['3'])
        response = self.post_product({'length': {'values': ['6'], 'custom': True}})
        self.assertEqual(self.state(), [('Длина', ['3'], False)])
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('Параметры не сохранены' in m for m in messages), messages)

    def test_form_without_free_params_field_leaves_parameters(self):
        add_param(self.product, self.length, ['3'])
        data = {
            'name': self.product.name, 'slug': self.product.slug,
            'category': self.cat.pk, 'in_stock': 'in_stock', 'is_active': 'on',
            'images-TOTAL_FORMS': '0', 'images-INITIAL_FORMS': '0',
            'related_links-TOTAL_FORMS': '0', 'related_links-INITIAL_FORMS': '0',
        }
        response = self.client.post(self.change_url(), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.state(), [('Длина', ['3'], False)])

    def test_inactive_parameter_already_on_product_kept(self):
        add_param(self.product, self.width, ['20'])
        self.width.is_active = False
        self.width.save()
        self.post_product([
            {'parameter_id': self.width.pk, 'values': ['20', '30'], 'custom': False},
        ])
        self.assertEqual(self.state(), [('Ширина', ['20', '30'], False)])


class ParameterAdminTests(AdminTestCase):
    def test_changelist_shows_usage(self):
        add_param(self.product, self.length, ['3'])
        response = self.client.get(reverse('admin:references_parameter_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Длина')

    def test_add_parameter_via_admin(self):
        response = self.client.post(reverse('admin:references_parameter_add'), {
            'name': 'Толщина', 'unit': 'мм', 'custom_label': 'Своя толщина',
            'example': '1.5', 'sort_order': '5', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Parameter.objects.filter(name='Толщина', unit='мм').exists())

    def test_category_page_offers_parameter_facets(self):
        response = self.client.get(reverse('admin:catalog_category_change', args=[self.cat.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="facets-__prefix__-parameter"')


class ProductParameterQuerysetTests(AdminTestCase):
    def test_product_parameter_count_after_saves_is_stable(self):
        payload = [{'parameter_id': self.length.pk, 'values': ['3'], 'custom': False}]
        self.post_product(payload)
        self.post_product(payload)
        self.assertEqual(ProductParameter.objects.filter(product=self.product).count(), 1)
