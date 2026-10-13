import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.leads.models import Lead, cart_item_params

QUIET = dict(
    YANDEX_CAPTCHA_SERVER_KEY='',
    TELEGRAM_BOT_TOKEN='',
    TELEGRAM_CHAT_ID='',
    RATELIMIT_ENABLE=False,
)


class CartItemParamsTests(TestCase):
    def test_new_format(self):
        item = {'params': [{'name': 'Ширина', 'value': '20 мм'},
                           {'name': 'Длина', 'value': '3 м (свой)'}]}
        self.assertEqual(cart_item_params(item), [
            ('Ширина', '20 мм'), ('Длина', '3 м (свой)'),
        ])

    def test_legacy_fields_of_old_leads(self):
        item = {'size': '20×20', 'length': '3 м', 'height': '40 мм'}
        self.assertEqual(cart_item_params(item), [
            ('Размер', '20×20'), ('Длина', '3 м'), ('Высота', '40 мм'),
        ])

    def test_empty_item(self):
        self.assertEqual(cart_item_params({}), [])

    def test_broken_entries_skipped(self):
        item = {'params': ['мусор', {'name': 'Длина'}, {'name': '', 'value': '3'},
                           {'name': 'Ширина', 'value': '20'}]}
        self.assertEqual(cart_item_params(item), [('Ширина', '20')])


@override_settings(**QUIET)
class SubmitCartParamsTests(TestCase):
    def setUp(self):
        cat = Category.add_root(name='Профили', slug='profili')
        self.product = Product.objects.create(name='Профиль Т', slug='profil-t', category=cat)

    def submit(self, items):
        response = self.client.post(
            reverse('leads:submit_cart'),
            data=json.dumps({
                'name': 'Иван', 'phone': '+79990000000',
                'agree': True, 'agree_terms': True,
                'cart_snapshot': items,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'], response.json())
        return Lead.objects.get(pk=response.json()['id']).cart_snapshot

    def test_params_saved_as_readable_list(self):
        snapshot = self.submit([{
            'slug': 'profil-t', 'qty': 2,
            'params': [{'name': 'Ширина', 'value': '20 мм'},
                       {'name': 'Длина', 'value': '3 м'}],
        }])
        self.assertEqual(snapshot[0]['params'], [
            {'name': 'Ширина', 'value': '20 мм'},
            {'name': 'Длина', 'value': '3 м'},
        ])
        self.assertEqual(snapshot[0]['name'], 'Профиль Т')

    def test_params_trimmed_empty_and_garbage_dropped(self):
        snapshot = self.submit([{
            'slug': 'profil-t',
            'params': [
                {'name': '  Ширина ', 'value': ' 20 мм '},
                {'name': 'Длина', 'value': ''},
                {'name': '', 'value': '5'},
                'мусор', None, {'name': ['x'], 'value': {'y': 1}},
            ],
        }])
        self.assertEqual(snapshot[0]['params'], [{'name': 'Ширина', 'value': '20 мм'}])

    def test_params_length_and_count_limited(self):
        many = [{'name': f'П{i}', 'value': 'v' * 500} for i in range(50)]
        snapshot = self.submit([{'slug': 'profil-t', 'params': many}])
        params = snapshot[0]['params']
        self.assertLessEqual(len(params), 20)
        self.assertTrue(all(len(p['value']) <= 200 for p in params))
        self.assertTrue(all(len(p['name']) <= 100 for p in params))

    def test_non_list_params_ignored(self):
        snapshot = self.submit([{'slug': 'profil-t', 'params': 'Длина 3'}])
        self.assertNotIn('params', snapshot[0])

    def test_no_params_key_when_nothing_selected(self):
        snapshot = self.submit([{'slug': 'profil-t'}])
        self.assertNotIn('params', snapshot[0])

    def test_legacy_cart_fields_converted(self):
        # Корзина, собранная до обновления, лежит в localStorage у покупателя
        snapshot = self.submit([{
            'slug': 'profil-t', 'size': '20×20', 'length': '3 м', 'height': '40 мм',
        }])
        self.assertEqual(snapshot[0]['params'], [
            {'name': 'Размер', 'value': '20×20'},
            {'name': 'Длина', 'value': '3 м'},
            {'name': 'Высота', 'value': '40 мм'},
        ])
        for legacy in ('size', 'length', 'height'):
            self.assertNotIn(legacy, snapshot[0])

    def test_items_differing_only_in_params_are_separate_rows(self):
        snapshot = self.submit([
            {'slug': 'profil-t', 'params': [{'name': 'Длина', 'value': '3 м'}]},
            {'slug': 'profil-t', 'params': [{'name': 'Длина', 'value': '6 м'}]},
        ])
        self.assertEqual(len(snapshot), 2)

    def test_identical_items_deduplicated(self):
        item = {'slug': 'profil-t', 'params': [{'name': 'Длина', 'value': '3 м'}]}
        snapshot = self.submit([item, dict(item)])
        self.assertEqual(len(snapshot), 1)

    def test_tree_options_still_saved(self):
        snapshot = self.submit([{
            'slug': 'profil-t', 'material': 'Нержавеющая сталь', 'finish': 'Полировка',
            'color': 'Золото', 'params': [{'name': 'Длина', 'value': '3 м'}],
        }])
        self.assertEqual(snapshot[0]['material'], 'Нержавеющая сталь')
        self.assertEqual(snapshot[0]['finish'], 'Полировка')
        self.assertEqual(snapshot[0]['color'], 'Золото')


class LeadDisplayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('admin', 'a@b.c', 'pass')
        self.client.force_login(self.user)

    def make_lead(self, snapshot):
        return Lead.objects.create(
            name='Иван', phone='+79990000000', source='cart', cart_snapshot=snapshot)

    def test_admin_shows_new_params(self):
        lead = self.make_lead([{
            'name': 'Профиль Т', 'qty': 1,
            'params': [{'name': 'Ширина', 'value': '20 мм'}],
        }])
        response = self.client.get(reverse('admin:leads_lead_change', args=[lead.pk]))
        self.assertContains(response, 'Ширина: 20 мм')

    def test_admin_shows_legacy_params_of_old_lead(self):
        lead = self.make_lead([{'name': 'Профиль Т', 'qty': 1, 'length': '3 м'}])
        response = self.client.get(reverse('admin:leads_lead_change', args=[lead.pk]))
        self.assertContains(response, 'Длина: 3 м')

    @override_settings(TELEGRAM_BOT_TOKEN='token', TELEGRAM_CHAT_ID='1', SITE_URL='')
    def test_telegram_message_lists_params(self):
        from apps.leads.views import _send_telegram
        lead = self.make_lead([{
            'name': 'Профиль Т', 'qty': 1,
            'params': [{'name': 'Ширина', 'value': '20 мм'},
                       {'name': 'Длина', 'value': '3 м <b>'}],
        }])
        with mock.patch('apps.leads.views.requests.post') as post:
            _send_telegram(lead.pk)
        text = post.call_args.kwargs['json']['text']
        self.assertIn('Ширина 20 мм', text)
        self.assertIn('Длина 3 м &lt;b&gt;', text)  # клиентский ввод экранирован

    @override_settings(TELEGRAM_BOT_TOKEN='token', TELEGRAM_CHAT_ID='1', SITE_URL='')
    def test_telegram_message_lists_legacy_params(self):
        from apps.leads.views import _send_telegram
        lead = self.make_lead([{'name': 'Профиль Т', 'qty': 1, 'size': '20×20'}])
        with mock.patch('apps.leads.views.requests.post') as post:
            _send_telegram(lead.pk)
        self.assertIn('Размер 20×20', post.call_args.kwargs['json']['text'])
