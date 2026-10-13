"""Отображение товара: описание и низ карточки в сетке.

Описание в админке — обычный текст: переносы строк и пустые строки между
абзацами, которые ввёл менеджер, должны сохраниться на странице товара.
Кнопка карточки («Изготовить») на узкой карточке (телефон: две колонки)
не должна обрезаться краем — низ карточки переносится на новую строку.
"""
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .helpers import make_category, make_product


class ProductDescriptionTests(TestCase):
    def setUp(self):
        self.cat = make_category()

    def get(self, description):
        product = make_product(self.cat, description=description)
        response = self.client.get(product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return response

    def test_line_break_kept(self):
        response = self.get('Первая строка.\r\nВторая строка.')
        self.assertContains(response, 'Первая строка.<br>Вторая строка.')

    def test_blank_line_starts_new_paragraph(self):
        response = self.get('Первый абзац.\r\n\r\nВторой абзац.')
        self.assertContains(response, '<p>Первый абзац.</p>')
        self.assertContains(response, '<p>Второй абзац.</p>')

    def test_html_escaped(self):
        response = self.get('<script>alert(1)</script>')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')


class ProductCardActionsTests(TestCase):
    def test_card_actions_row_uses_wrapping_component(self):
        cat = make_category()
        make_product(cat)
        response = self.client.get(reverse('catalog:index'))
        self.assertContains(response, 'class="product-card-actions"')

    def test_card_actions_component_wraps(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'main.css').read_text()
        start = css.index('.product-card-actions')
        rule = css[start:css.index('}', start)]
        self.assertIn('flex-wrap', rule)
