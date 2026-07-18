"""
Заполняет справочники Цвета / Обработки тестовыми данными для проверки
трёх режимов color_ui на карточке товара.

Создаёт три обработки:
  - «Полированная»      → swatches       (≤10 цветов, простые кружки)
  - «Покраска RAL»      → ral_palette    (40 RAL-цветов с поиском по группам)
  - «Под заказ»         → custom_request (5 популярных + свободный запрос)

А также вешает эти обработки узлами на дерево одного товара из seed_data
(если есть), чтобы сразу можно было открыть карточку и пощупать UI.

Использование:
    python manage.py seed_colors          # добавить / обновить
    python manage.py seed_colors --clear  # удалить все цвета/обработки и пересоздать
"""
from django.core.management.base import BaseCommand
from django.db import transaction


# ── Данные ──────────────────────────────────────────────────────────────────

SWATCHES_COLORS = [
    # name               hex       ral_code    group
    ('Натуральный',     '#C8C8C8', '',         'metallic'),
    ('Золото',          '#D4AF37', '',         'metallic'),
    ('Шампань',         '#F0DEB4', '',         'metallic'),
    ('Чёрный никель',   '#2C2C2C', '',         'black'),
    ('Медь',            '#B87333', '',         'brown'),
    ('Розовое золото',  '#B76E79', '',         'metallic'),
]

# 40 реальных RAL-оттенков для режима ral_palette
RAL_COLORS = [
    # name                  hex       ral_code    group
    ('Белый сигнальный',   '#F4F4F4', 'RAL 9003', 'white'),
    ('Белый кремовый',     '#FDF4E3', 'RAL 9001', 'white'),
    ('Белый чистый',       '#FFFFFF', 'RAL 9010', 'white'),
    ('Белый транспортный', '#F1F0EA', 'RAL 9016', 'white'),

    ('Серый агатовый',     '#B5B0A8', 'RAL 7038', 'gray'),
    ('Серый базальтовый',  '#5B6065', 'RAL 7012', 'gray'),
    ('Серый мышиный',      '#8F8B85', 'RAL 7005', 'gray'),
    ('Серый железный',     '#525D6E', 'RAL 7011', 'gray'),
    ('Серый кварцевый',    '#787B77', 'RAL 7039', 'gray'),
    ('Серый платиновый',   '#9DA4A9', 'RAL 7036', 'gray'),

    ('Чёрный',             '#0E0E10', 'RAL 9005', 'black'),
    ('Чёрный графитовый',  '#282D2E', 'RAL 9011', 'black'),
    ('Чёрный антрацит',    '#293133', 'RAL 7016', 'black'),

    ('Коричневый умбра',   '#59351E', 'RAL 8007', 'brown'),
    ('Коричневый орех',    '#7A4930', 'RAL 8011', 'brown'),
    ('Коричневый шоколад', '#47260C', 'RAL 8017', 'brown'),
    ('Бежевый кремовый',   '#CDBA88', 'RAL 1015', 'brown'),
    ('Коричневый охра',    '#C2814B', 'RAL 8024', 'brown'),

    ('Синий сигнальный',   '#1B44A0', 'RAL 5005', 'blue'),
    ('Синий небесный',     '#417DC4', 'RAL 5015', 'blue'),
    ('Синий голубой',      '#6395C5', 'RAL 5012', 'blue'),
    ('Синий ночной',       '#1C2B3A', 'RAL 5026', 'blue'),
    ('Синий ультрамарин',  '#2D2E7C', 'RAL 5002', 'blue'),

    ('Зелёный мох',        '#3A5B3A', 'RAL 6005', 'green'),
    ('Зелёный мятный',     '#3D6B5B', 'RAL 6029', 'green'),
    ('Зелёный травяной',   '#5B8135', 'RAL 6010', 'green'),
    ('Зелёный хаки',       '#5C7057', 'RAL 6003', 'green'),
    ('Зелёный белый',      '#CDD4C6', 'RAL 6019', 'green'),

    ('Бронза',             '#967117', 'RAL 1036', 'metallic'),
    ('Золото светлое',     '#D4A840', 'RAL 1004', 'metallic'),
    ('Серебро',            '#A9ADB0', 'RAL 9006', 'metallic'),
    ('Хром',               '#C0C0C0', 'RAL 9007', 'metallic'),

    ('Красный огненный',   '#C1121C', 'RAL 3000', 'other'),
    ('Оранжевый сигнальный','#E35B00', 'RAL 2010', 'other'),
    ('Жёлтый рапсовый',    '#F8A000', 'RAL 1021', 'other'),
    ('Фиолетовый',         '#643A6B', 'RAL 4006', 'other'),
    ('Тёмно-красный',      '#6C1D2E', 'RAL 3005', 'other'),
    ('Розовый',            '#D78EA8', 'RAL 3015', 'other'),
]

# 5 популярных для режима custom_request (берутся из SWATCHES_COLORS)
CUSTOM_POPULAR = ['Натуральный', 'Золото', 'Шампань', 'Чёрный никель', 'Медь']


class Command(BaseCommand):
    help = 'Заполняет цвета / обработки для тестирования трёх режимов color_ui'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Удалить все цвета/обработки/привязки перед созданием')

    def handle(self, *args, **options):
        if options['clear']:
            self._clear()

        with transaction.atomic():
            swatches_colors = self._seed_swatches_colors()
            ral_colors      = self._seed_ral_colors()
            self._seed_finishes(swatches_colors, ral_colors)
            self._seed_test_variants(swatches_colors, ral_colors)

        self.stdout.write(self.style.SUCCESS('Готово. Откройте карточку товара «Профиль П-образный 40×20×2 мм» для проверки.'))

    # ──────────────────────────────────────────────────────────────────────────

    def _clear(self):
        from apps.references.models import Color, Finish
        Color.objects.all().delete()
        Finish.objects.all().delete()
        self.stdout.write('  Цвета / обработки очищены')

    def _seed_swatches_colors(self):
        from apps.references.models import Color
        self.stdout.write('  Создаю swatches-цвета…')
        result = {}
        for name, hex_code, ral_code, group in SWATCHES_COLORS:
            obj, _ = Color.objects.update_or_create(
                name=name,
                defaults={'hex_code': hex_code, 'ral_code': ral_code, 'color_group': group},
            )
            result[name] = obj
        return result

    def _seed_ral_colors(self):
        from apps.references.models import Color
        self.stdout.write(f'  Создаю {len(RAL_COLORS)} RAL-цветов…')
        result = {}
        for name, hex_code, ral_code, group in RAL_COLORS:
            obj, _ = Color.objects.update_or_create(
                name=name,
                defaults={'hex_code': hex_code, 'ral_code': ral_code, 'color_group': group},
            )
            result[name] = obj
        return result

    def _seed_finishes(self, swatches_colors, ral_colors):
        """Обработки задают только режим селектора (color_ui) —
        набор цветов отмечается на узле-обработке дерева товара
        (см. _seed_test_variants)."""
        from apps.references.models import Finish
        self.stdout.write('  Создаю обработки…')

        pol, _ = Finish.objects.update_or_create(
            slug='polirovannaya',
            defaults={'name': 'Полированная', 'color_ui': Finish.COLOR_UI_SWATCHES},
        )
        ral, _ = Finish.objects.update_or_create(
            slug='pokraska-ral',
            defaults={'name': 'Покраска RAL', 'color_ui': Finish.COLOR_UI_RAL},
        )
        cust, _ = Finish.objects.update_or_create(
            slug='pod-zakaz',
            defaults={'name': 'Под заказ', 'color_ui': Finish.COLOR_UI_CUSTOM},
        )

        self.stdout.write('    Полированная  → swatches')
        self.stdout.write('    Покраска RAL  → ral_palette')
        self.stdout.write('    Под заказ     → custom_request')

        return pol, ral, cust

    def _seed_test_variants(self, swatches_colors, ral_colors):
        """Вешает три обработки (по одной на режим color_ui) узлами
        на первую марку тестового товара, каждую — со своим набором цветов."""
        from apps.catalog.models import Product, ProductOptionNode
        from apps.references.models import Finish

        product = Product.objects.filter(slug='profil-p-40x20x2').first()
        if not product:
            self.stdout.write(self.style.WARNING(
                '  Товар «profil-p-40x20x2» не найден — сначала запустите seed_data. '
                'Узлы не созданы, но обработки и цвета уже готовы.'
            ))
            return

        grade_node = (
            product.option_nodes
            .filter(node_type='steel_grade')
            .select_related('steel_grade')
            .first()
        )
        if not grade_node:
            self.stdout.write(self.style.WARNING('  У товара нет узла-марки — пропуск'))
            return

        self.stdout.write(f'  Вешаю тестовые обработки на «{grade_node.steel_grade}»…')

        def make(slug, colors):
            finish = Finish.objects.get(slug=slug)
            node, _ = ProductOptionNode.objects.get_or_create(
                product=product, parent=grade_node,
                node_type='finish', finish=finish,
            )
            node.colors.set(colors)
            self.stdout.write(f'    {finish.name}: {len(colors)} цветов')

        make('polirovannaya', list(swatches_colors.values()))    # swatches
        make('pokraska-ral',  list(ral_colors.values()))         # ral_palette
        make('pod-zakaz', [swatches_colors[n] for n in CUSTOM_POPULAR])  # custom_request

        self.stdout.write('  Готово. Узлы созданы.')
