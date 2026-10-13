"""Корзина и окно обратного звонка — поверх кнопки «наверх»: иначе на
телефоне круглая кнопка перекрывает «Отправить заявку» внизу корзины."""
import re

from django.test import TestCase
from django.urls import reverse


def z_index(html, marker):
    """z-index (Tailwind z-N / z-[N]) элемента, в атрибутах которого есть marker."""
    start = html.index(marker)
    tag = html[html.rindex('<', 0, start):html.index('>', start)]
    m = re.search(r'\bz-(?:\[(\d+)\]|(\d+))', tag)
    return int(m.group(1) or m.group(2))


class OverlayLayersTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('home')).content.decode()
        self.back_to_top = z_index(self.html, 'aria-label="Наверх"')

    def test_cart_drawer_above_back_to_top(self):
        self.assertGreater(z_index(self.html, 'x-show="$store.cartUI.open"'), self.back_to_top)

    def test_callback_modal_above_back_to_top(self):
        self.assertGreater(z_index(self.html, 'x-show="$store.callbackUI.open"'), self.back_to_top)
