from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import CategoryFacet
from apps.references.models import Parameter

from .helpers import add_param, make_category, make_product


def category_url(category):
    return reverse('catalog:detail', kwargs={'slug': category.slug})


class ProductCardParamsTests(TestCase):
    def setUp(self):
        self.cat = make_category()
        self.product = make_product(self.cat)
        self.length = Parameter.objects.create(
            name='Длина', unit='м', custom_label='Своя длина', example='2.7')
        self.width = Parameter.objects.create(name='Ширина', unit='мм')

    def get_params(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return response.context['params_json']

    def test_product_without_parameters(self):
        self.assertEqual(self.get_params(), [])

    def test_parameters_in_product_order_with_full_description(self):
        add_param(self.product, self.width, ['20', '40'], sort_order=1)
        add_param(self.product, self.length, ['3', '2.7'], allow_custom=True, sort_order=0)

        params = self.get_params()

        self.assertEqual([p['name'] for p in params], ['Длина', 'Ширина'])
        length = params[0]
        self.assertEqual(length['id'], self.length.pk)
        self.assertEqual(length['unit'], 'м')
        self.assertEqual(length['custom_label'], 'Своя длина')
        self.assertEqual(length['example'], '2.7')
        self.assertEqual(length['values'], ['3', '2.7'])  # порядок менеджера
        self.assertTrue(length['allow_custom'])
        self.assertFalse(params[1]['allow_custom'])
        self.assertEqual(params[1]['custom_label'], 'Своё значение')

    def test_inactive_parameter_hidden_on_card(self):
        add_param(self.product, self.length, ['3'])
        self.width.is_active = False
        self.width.save()
        add_param(self.product, self.width, ['20'])

        self.assertEqual([p['name'] for p in self.get_params()], ['Длина'])

    def test_custom_only_parameter_shown_without_values(self):
        add_param(self.product, self.width, [], allow_custom=True)
        params = self.get_params()
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]['values'], [])
        self.assertTrue(params[0]['allow_custom'])

    def test_params_rendered_into_page(self):
        add_param(self.product, self.length, ['3'])
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'id="params-data"')
        self.assertContains(response, 'Длина')


class CatalogParamFacetTests(TestCase):
    def setUp(self):
        self.cat = make_category()
        self.width = Parameter.objects.create(name='Ширина', unit='мм')
        self.length = Parameter.objects.create(name='Длина', unit='м')

    def facets(self, category=None, **params):
        response = self.client.get(category_url(category or self.cat), params)
        self.assertEqual(response.status_code, 200)
        return {f['name']: f for f in response.context['facets']}

    def test_parameter_facet_lists_values_naturally_sorted_with_unit(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.length)
        p1 = make_product(self.cat, slug='a')
        p2 = make_product(self.cat, slug='b')
        add_param(p1, self.length, ['10', '3'])
        add_param(p2, self.length, ['2.7', '3'])

        facet = self.facets()[self.length.filter_key]

        self.assertEqual(facet['title'], 'Длина')
        self.assertEqual([o['pk'] for o in facet['options']], ['2.7', '3', '10'])
        self.assertEqual([o['name'] for o in facet['options']], ['2.7 м', '3 м', '10 м'])

    def test_custom_facet_title_wins(self):
        CategoryFacet.objects.create(
            category=self.cat, facet='param', parameter=self.length, title='Длина хлыста')
        add_param(make_product(self.cat), self.length, ['3'])
        self.assertEqual(self.facets()[self.length.filter_key]['title'], 'Длина хлыста')

    def test_facet_values_only_from_this_parameter(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        product = make_product(self.cat)
        add_param(product, self.width, ['20'])
        add_param(product, self.length, ['3'])

        facet = self.facets()[self.width.filter_key]
        self.assertEqual([o['pk'] for o in facet['options']], ['20'])

    def test_facet_ignores_inactive_products_and_other_categories(self):
        other = make_category(name='Другое', slug='drugoe')
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        add_param(make_product(self.cat, slug='on'), self.width, ['20'])
        add_param(make_product(self.cat, slug='off', is_active=False), self.width, ['30'])
        add_param(make_product(other, slug='alien'), self.width, ['40'])

        facet = self.facets()[self.width.filter_key]
        self.assertEqual([o['pk'] for o in facet['options']], ['20'])

    def test_facet_without_values_hidden(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        make_product(self.cat)
        self.assertNotIn(self.width.filter_key, self.facets())

    def test_inactive_parameter_facet_hidden(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        add_param(make_product(self.cat), self.width, ['20'])
        self.width.is_active = False
        self.width.save()
        self.assertNotIn(self.width.filter_key, self.facets())

    def test_inactive_facet_row_hidden(self):
        CategoryFacet.objects.create(
            category=self.cat, facet='param', parameter=self.width, is_active=False)
        CategoryFacet.objects.create(category=self.cat, facet='in_stock')
        add_param(make_product(self.cat), self.width, ['20'])
        self.assertNotIn(self.width.filter_key, self.facets())

    def test_facet_order_follows_config(self):
        CategoryFacet.objects.create(
            category=self.cat, facet='param', parameter=self.width, sort_order=2)
        CategoryFacet.objects.create(
            category=self.cat, facet='param', parameter=self.length, sort_order=1)
        product = make_product(self.cat)
        add_param(product, self.width, ['20'])
        add_param(product, self.length, ['3'])

        response = self.client.get(category_url(self.cat))
        names = [f['name'] for f in response.context['facets']]
        self.assertEqual(names, [self.length.filter_key, self.width.filter_key])

    def test_selected_values_marked(self):
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        add_param(make_product(self.cat), self.width, ['20', '40'])
        facet = self.facets(**{self.width.filter_key: '40'})[self.width.filter_key]
        self.assertEqual(facet['selected'], ['40'])

    def test_child_category_inherits_parameter_facet(self):
        child = make_category(name='Т-профили', slug='t-profili', parent=self.cat)
        CategoryFacet.objects.create(category=self.cat, facet='param', parameter=self.width)
        add_param(make_product(child), self.width, ['20'])
        self.assertIn(self.width.filter_key, self.facets(category=child))


class CatalogParamFilterTests(TestCase):
    def setUp(self):
        self.cat = make_category()
        self.width = Parameter.objects.create(name='Ширина', unit='мм')
        self.length = Parameter.objects.create(name='Длина', unit='м')

        self.a = make_product(self.cat, name='A', slug='a')
        add_param(self.a, self.width, ['20', '40'])
        add_param(self.a, self.length, ['3'])

        self.b = make_product(self.cat, name='B', slug='b')
        add_param(self.b, self.width, ['40'])
        add_param(self.b, self.length, ['6'])

        # «3» у C — это ширина, а не длина: фильтр по длине 3 его брать не должен
        self.c = make_product(self.cat, name='C', slug='c')
        add_param(self.c, self.width, ['3'])

    def slugs(self, url=None, **params):
        response = self.client.get(url or category_url(self.cat), params)
        self.assertEqual(response.status_code, 200)
        return sorted(p.slug for p in response.context['page_obj'].object_list)

    def test_no_filter_returns_all(self):
        self.assertEqual(self.slugs(), ['a', 'b', 'c'])

    def test_filter_by_single_value(self):
        self.assertEqual(self.slugs(**{self.width.filter_key: '20'}), ['a'])

    def test_filter_by_any_of_values(self):
        self.assertEqual(self.slugs(**{self.length.filter_key: ['3', '6']}), ['a', 'b'])

    def test_value_matched_within_its_parameter_only(self):
        self.assertEqual(self.slugs(**{self.length.filter_key: '3'}), ['a'])

    def test_two_parameters_combined_with_and(self):
        self.assertEqual(
            self.slugs(**{self.width.filter_key: '40', self.length.filter_key: '6'}),
            ['b'],
        )

    def test_product_not_duplicated_when_several_values_match(self):
        response = self.client.get(
            category_url(self.cat), {self.width.filter_key: ['20', '40']})
        slugs = [p.slug for p in response.context['page_obj'].object_list]
        self.assertEqual(sorted(slugs), ['a', 'b'])

    def test_unknown_value_returns_nothing_not_everything(self):
        self.assertEqual(self.slugs(**{self.width.filter_key: '999'}), [])

    def test_inactive_parameter_filter_ignored(self):
        self.width.is_active = False
        self.width.save()
        self.assertEqual(self.slugs(**{self.width.filter_key: '20'}), ['a', 'b', 'c'])

    def test_garbage_param_key_ignored(self):
        self.assertEqual(self.slugs(pabc='20', p999999='1'), ['a', 'b', 'c'])

    def test_filter_works_in_search(self):
        self.assertEqual(
            self.slugs(url=reverse('search'), q='', **{self.width.filter_key: '20'}),
            ['a'],
        )
