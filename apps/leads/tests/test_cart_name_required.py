"""Имя при оформлении заявки из корзины обязательно — как телефон:
без имени заявка не создаётся, в форме поле помечено звёздочкой."""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leads.models import Lead

from .test_cart_params import QUIET


@override_settings(**QUIET)
class CartNameRequiredTests(TestCase):
    def submit(self, **fields):
        payload = {
            'name': 'Иван', 'phone': '+79990000000',
            'agree': True, 'agree_terms': True, 'cart_snapshot': [],
        }
        payload.update(fields)
        response = self.client.post(
            reverse('leads:submit_cart'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def assert_rejected(self, result):
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'Укажите имя')
        self.assertFalse(Lead.objects.exists())

    def test_missing_name_rejected(self):
        payload = {'phone': '+79990000000', 'agree': True, 'agree_terms': True}
        response = self.client.post(
            reverse('leads:submit_cart'),
            data=json.dumps(payload), content_type='application/json',
        )
        self.assert_rejected(response.json())

    def test_empty_name_rejected(self):
        self.assert_rejected(self.submit(name=''))

    def test_whitespace_name_rejected(self):
        self.assert_rejected(self.submit(name='   '))

    def test_non_string_name_rejected(self):
        self.assert_rejected(self.submit(name=None))

    def test_name_saved_trimmed(self):
        result = self.submit(name='  Анна  ')
        self.assertTrue(result['ok'], result)
        self.assertEqual(Lead.objects.get(pk=result['id']).name, 'Анна')

    def test_form_marks_name_required(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Имя <span class="text-accent">*</span>')
