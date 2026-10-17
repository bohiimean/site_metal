"""Статика на проде — с хэшем содержимого в имени файла.

Nginx отдаёт /static/ с кэшем на 30 дней. Пока имя не менялось
(`output.css`), после выкатки браузер брал CSS из кэша: новая разметка
лайтбокса со старыми стилями — фото в натуральную величину, без фона,
крестик сплющенным овалом посреди экрана. С хэшем в имени новая
вёрстка ссылается на новый файл, и браузер его загружает.
"""
import re
import shutil
import tempfile
from pathlib import Path

from django.conf import global_settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from config.settings import production

HASHED = r'\.[0-9a-f]{12}\.'
# До исправления STORAGES в production не задан — берётся дефолт Django
PROD_STORAGES = getattr(production, 'STORAGES', global_settings.STORAGES)


class ProductionStaticCacheBustingTests(TestCase):
    """Главная страница с production-хранилищем статики после collectstatic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_root = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.static_root)
        cls.prod_static = override_settings(
            STORAGES=PROD_STORAGES, STATIC_ROOT=cls.static_root,
        )
        cls.prod_static.enable()
        cls.addClassCleanup(cls.prod_static.disable)
        call_command('collectstatic', interactive=False, verbosity=0)

    def setUp(self):
        self.html = self.client.get(reverse('home')).content.decode()

    def assert_hashed_link(self, name):
        stem, ext = name.rsplit('.', 1)
        m = re.search(
            rf'/static/({re.escape(stem)}{HASHED}{re.escape(ext)})"', self.html,
        )
        self.assertIsNotNone(m, f'{name} подключён без хэша в имени')
        self.assertTrue(
            (Path(self.static_root) / m.group(1)).is_file(),
            f'{m.group(1)} нет среди собранной статики — nginx отдаст 404',
        )

    def test_css_link_has_content_hash(self):
        self.assert_hashed_link('css/output.css')

    def test_scripts_have_content_hash(self):
        self.assert_hashed_link('vendor/alpine-3.14.9.min.js')
        self.assert_hashed_link('vendor/htmx-2.0.4.min.js')

    def test_no_unhashed_static_links(self):
        unhashed = [
            path for path in re.findall(r'/static/([^"\'\s>]+)', self.html)
            if not re.search(HASHED, path)
        ]
        self.assertEqual(unhashed, [])


class ChangedCssGetsNewUrlTests(TestCase):
    """Изменился CSS — изменился и адрес: закэшированная копия не подхватится."""

    def setUp(self):
        self.src = Path(tempfile.mkdtemp())
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.src)
        self.addCleanup(shutil.rmtree, self.root)
        (self.src / 'css').mkdir()
        self.css = self.src / 'css' / 'output.css'

    def collected_url(self, content):
        from django.templatetags.static import static

        self.css.write_text(content)
        with override_settings(
            STORAGES=PROD_STORAGES, STATIC_ROOT=self.root,
            STATICFILES_DIRS=[self.src],
            # Только каталог проекта: статику приложений здесь собирать незачем
            STATICFILES_FINDERS=[
                'django.contrib.staticfiles.finders.FileSystemFinder',
            ],
        ):
            call_command('collectstatic', interactive=False, verbosity=0)
            return static('css/output.css')

    def test_url_changes_with_content(self):
        before = self.collected_url('.lightbox{max-width:100%}')
        after = self.collected_url('.lightbox{max-width:100%;max-height:100%}')
        self.assertNotEqual(before, after)

    def test_url_stable_without_changes(self):
        css = '.lightbox{max-width:100%}'
        self.assertEqual(self.collected_url(css), self.collected_url(css))

