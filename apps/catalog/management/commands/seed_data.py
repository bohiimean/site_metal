"""
Заполняет БД реалистичными тестовыми данными по металлопрокату.

Использование:
    python manage.py seed_data          # добавить данные
    python manage.py seed_data --clear  # очистить и пересоздать
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Заполняет БД тестовыми данными (металлопрокат)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Очистить все данные перед заполнением',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self._clear()
            self.stdout.write('  Данные очищены')

        with transaction.atomic():
            refs   = self._seed_references()
            cats   = self._seed_categories()
            prods  = self._seed_products(cats, refs)
            self._seed_home_blocks(cats, prods)
            self._seed_pages()

        counts = self._report()
        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: {counts["categories"]} категорий, '
            f'{counts["products"]} товаров, '
            f'{counts["nodes"]} узлов опций, '
            f'{counts["blocks"]} блоков главной, '
            f'{counts["pages"]} страниц'
        ))

    # ──────────────────────────────────────────
    # ОЧИСТКА
    # ──────────────────────────────────────────

    def _clear(self):
        from apps.catalog.models import (
            Category, Product, ProductImage, ProductOptionNode, ProductParamValue,
        )
        from apps.references.models import Material, SteelGrade, Finish, Color
        from apps.home.models import HomeBlock, HomeBlockItem
        from apps.pages.models import Page

        HomeBlockItem.objects.all().delete()
        HomeBlock.objects.all().delete()
        ProductOptionNode.objects.all().delete()
        ProductParamValue.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Color.objects.all().delete()
        Finish.objects.all().delete()
        SteelGrade.objects.all().delete()
        Material.objects.all().delete()
        Page.objects.all().delete()

    # ──────────────────────────────────────────
    # СПРАВОЧНИКИ
    # ──────────────────────────────────────────

    def _seed_references(self):
        from apps.references.models import Material, SteelGrade, Finish, Color

        self.stdout.write('  Справочники…')

        stal, _       = Material.objects.get_or_create(name='Сталь',        defaults={'slug': 'stal'})
        nerzh, _      = Material.objects.get_or_create(name='Нержавейка',   defaults={'slug': 'nerzhaveika'})
        latun, _      = Material.objects.get_or_create(name='Латунь',       defaults={'slug': 'latun'})
        alyum, _      = Material.objects.get_or_create(name='Алюминий',     defaults={'slug': 'alyuminiy'})

        # Основные разделы страницы «Продукция»
        Material.objects.filter(pk=nerzh.pk, landing_title='').update(
            landing_title='Изделия из нержавеющей стали')
        Material.objects.filter(pk=latun.pk, landing_title='').update(
            landing_title='Профиль из латуни')

        # Марки стали
        grades = {}
        for name, mat in [
            ('Ст3',          stal),
            ('Ст20',         stal),
            ('AISI 430',     nerzh),
            ('12Х18Н10Т',    nerzh),
            ('AISI 304',     nerzh),
            ('AISI 316L',    nerzh),
            ('АД31',         alyum),
        ]:
            g, _ = SteelGrade.objects.get_or_create(name=name, defaults={'material': mat})
            grades[name] = g

        # Обработки и цвета
        pol,  _ = Finish.objects.get_or_create(name='Полированная',   defaults={'slug': 'polirovannaya'})
        sat,  _ = Finish.objects.get_or_create(name='Сатинированная', defaults={'slug': 'satinirovannaya'})
        dek,  _ = Finish.objects.get_or_create(name='Декоративная',   defaults={'slug': 'dekorativnaya'})

        colors = {}
        for name, hex_code in [
            ('Натуральный',  '#C0C0C0'),
            ('Золото',       '#D4AF37'),
            ('Шампань',      '#F7E7CE'),
            ('Чёрный никель','#2C2C2C'),
            ('Медь',         '#B87333'),
            ('Розовое золото','#B76E79'),
        ]:
            c, _ = Color.objects.get_or_create(name=name, defaults={'hex_code': hex_code})
            colors[name] = c

        return {
            'stal': stal, 'nerzh': nerzh, 'latun': latun, 'alyum': alyum,
            'grades': grades,
            'pol': pol, 'sat': sat, 'dek': dek,
            'colors': colors,
        }

    # ──────────────────────────────────────────
    # КАТЕГОРИИ
    # ──────────────────────────────────────────

    def _seed_categories(self):
        from apps.catalog.models import Category

        self.stdout.write('  Категории…')

        def get_or_create_root(name, slug, **kw):
            try:
                return Category.objects.get(slug=slug)
            except Category.DoesNotExist:
                return Category.add_root(name=name, slug=slug, **kw)

        # Структура страницы «Продукция»: плоский список типов изделий.
        # Материал (нержавейка/латунь) — не категория, а фильтр каталога.
        structure = [
            ('napolnye',   'Профиль для напольных покрытий', 'profil-dlya-napolnyh-pokrytij'),
            ('plintus',    'Плинтус',                        'plintus'),
            ('porog',      'Порог стыковочный',              'porog-stykovochnyj'),
            ('stupeni',    'Профиль для защиты ступеней',    'profil-dlya-zashchity-stupenej'),
            ('vnutr_ugly', 'Профиль для внутренних углов',   'profil-dlya-vnutrennih-uglov'),
            ('vnesh_ugly', 'Профиль для внешних углов',      'profil-dlya-vneshnih-uglov'),
            ('vstavka',    'Вставка декоративная',           'vstavka-dekorativnaya'),
            ('otbojnik',   'Отбойник для стен',              'otbojnik-dlya-sten'),
            ('zerkalo',    'Профиль для зеркала и стекла',   'profil-dlya-zerkala-i-stekla'),
            ('shov',       'Шов деформационный',             'shov-deformacionnyj'),
        ]
        cats = {}
        for key, name, slug in structure:
            cats[key] = get_or_create_root(
                name, slug,
                h1=name,
                seo_title=f'{name} — купить оптом | МЕТАПРОФ',
                seo_description=f'{name} из нержавеющей стали и латуни. Доставка по Москве, резка в размер.',
            )
        return cats

    # ──────────────────────────────────────────
    # ТОВАРЫ
    # ──────────────────────────────────────────

    def _seed_products(self, cats, refs):
        from apps.catalog.models import Product, ProductOptionNode, ProductParamValue

        self.stdout.write('  Товары и опции…')

        nerzh  = refs['nerzh']
        latun  = refs['latun']
        alyum  = refs['alyum']
        g      = refs['grades']
        pol    = refs['pol']
        sat    = refs['sat']
        dek    = refs['dek']
        c      = refs['colors']

        def product(name, slug, cat, code='', desc='', is_new=False,
                    stock='in_stock', **flags):
            p, _ = Product.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    name=name, category=cat, profile_code=code,
                    description=desc, is_new=is_new, in_stock=stock,
                    seo_title=f'{name} — купить оптом | МЕТАПРОФ',
                    seo_description=f'{name}. Широкий выбор, доставка по Москве, резка в размер.',
                    **flags,
                ),
            )
            return p

        def tree(prod, spec):
            """Строит дерево опций товара.

            spec: [(material, [(grade|None, [(finish, [colors])])])]
            grade=None — обработки висят прямо под материалом.
            """
            if prod.option_nodes.exists():
                return
            for m_order, (mat, branches) in enumerate(spec):
                m_node = ProductOptionNode.objects.create(
                    product=prod, node_type='material',
                    material=mat, sort_order=m_order,
                )
                for b_order, (grade, finishes) in enumerate(branches):
                    if grade is not None:
                        parent = ProductOptionNode.objects.create(
                            product=prod, parent=m_node,
                            node_type='steel_grade',
                            steel_grade=grade, sort_order=b_order,
                        )
                    else:
                        parent = m_node
                    for f_order, (finish, colors) in enumerate(finishes):
                        f_node = ProductOptionNode.objects.create(
                            product=prod, parent=parent,
                            node_type='finish',
                            finish=finish, sort_order=f_order,
                        )
                        f_node.colors.set(colors)

        def params(prod, size=(), length=(), height=()):
            for kind, values in (('size', size), ('length', length), ('height', height)):
                for order, value in enumerate(values):
                    ProductParamValue.objects.get_or_create(
                        product=prod, kind=kind, value=value,
                        defaults={'sort_order': order},
                    )

        # Обязательный к работе пример из ТЗ: у 304 и 430 одна и та же
        # обработка — разные узлы с разными наборами цветов
        full_palette   = [c['Натуральный'], c['Золото'], c['Шампань'],
                          c['Чёрный никель'], c['Розовое золото'], c['Медь']]
        rich_palette   = [c['Натуральный'], c['Золото'], c['Шампань'], c['Чёрный никель']]
        short_palette  = [c['Натуральный'], c['Золото']]

        all_products = []

        # ── Профиль для напольных покрытий ─────
        p1 = product('Профиль П-образный 40×20×2 мм', 'profil-p-40x20x2',
                     cats['napolnye'], 'П 40×20×2',
                     'П-образный профиль применяется при монтаже лёгких конструкций, рам и каркасов. '
                     'Высокая точность геометрии, равномерная толщина стенки.',
                     allow_custom_length=True)
        tree(p1, [
            (nerzh, [
                (g['AISI 304'], [(pol, full_palette), (sat, rich_palette)]),
                (g['AISI 316L'], [(pol, short_palette)]),
            ]),
            (latun, [(None, [(pol, [c['Натуральный'], c['Медь']])])]),
        ])
        params(p1, size=['20×20', '40×20', '60×30'], length=['2.7', '3'])
        all_products.append(p1)

        p2 = product('Профиль Т-образный 25×12×1,5 мм', 'profil-t-25x12',
                     cats['napolnye'], 'Т 25×12×1,5',
                     'Т-профиль используется для декоративного разделения поверхностей, '
                     'окантовки плитки, облицовки колонн.',
                     is_new=True, allow_custom_size=True, allow_custom_length=True)
        tree(p2, [
            (nerzh, [
                (g['AISI 304'], [(pol, rich_palette), (sat, short_palette), (dek, full_palette)]),
                (g['12Х18Н10Т'], [(sat, [c['Натуральный']])]),
            ]),
        ])
        params(p2, size=['13×13', '25×12'], length=['2.7', '3'])
        all_products.append(p2)

        # ── Плинтус ────────────────────────────
        pl1 = product('Плинтус скрытого монтажа 60 мм', 'plintus-skrytogo-montazha-60',
                      cats['plintus'], 'ПЛ-С 60',
                      'Алюминиевый плинтус скрытого монтажа под шпаклёвку. '
                      'Создаёт эффект парящей стены.',
                      allow_custom_height=True)
        tree(pl1, [
            (alyum, [
                (g['АД31'], [(pol, [c['Натуральный'], c['Чёрный никель']]),
                             (sat, [c['Натуральный']])]),
            ]),
        ])
        params(pl1, length=['2.5', '3'], height=['40', '60', '80'])
        all_products.append(pl1)

        pl2 = product('Плинтус латунный 40 мм', 'plintus-latun-40',
                      cats['plintus'], 'ПЛ-Л 40',
                      'Латунный плинтус для интерьеров премиум-класса. '
                      'Тёплый золотистый оттенок, устойчивость к коррозии.',
                      is_new=True)
        tree(pl2, [
            (latun, [(None, [(pol, [c['Натуральный'], c['Медь']]),
                             (sat, [c['Натуральный']])])]),
        ])
        params(pl2, length=['2.5', '3'], height=['40', '60'])
        all_products.append(pl2)

        # ── Порог стыковочный ──────────────────
        pr1 = product('Порог стыковочный плоский 30 мм', 'porog-ploskij-30',
                      cats['porog'], 'ПС 30',
                      'Плоский стыковочный порог для соединения напольных покрытий '
                      'одного уровня.',
                      allow_custom_length=True)
        tree(pr1, [
            (nerzh, [
                (g['AISI 304'], [(pol, rich_palette), (sat, rich_palette)]),
                (g['AISI 430'], [(pol, short_palette), (sat, [c['Натуральный']])]),
            ]),
        ])
        params(pr1, size=['20', '30', '40'], length=['0.9', '1.35', '2.7'])
        all_products.append(pr1)

        # ── Профиль для защиты ступеней ────────
        st1 = product('Профиль для ступеней Г-образный 30×30 мм', 'profil-stupeni-g-30x30',
                      cats['stupeni'], 'Г 30×30',
                      'Угловой профиль для защиты кромок ступеней. '
                      'Противоскользящая функция, защита от сколов.')
        tree(st1, [
            (nerzh, [
                (g['AISI 304'], [(pol, full_palette), (sat, rich_palette), (dek, rich_palette)]),
            ]),
            (latun, [(None, [(pol, [c['Натуральный']])])]),
        ])
        params(st1, size=['20×20', '30×30', '40×20'], length=['2.7', '3'])
        all_products.append(st1)

        # ── Углы ───────────────────────────────
        u1 = product('Профиль для внешних углов 15×15 мм', 'profil-vneshnie-ugly-15',
                     cats['vnesh_ugly'], 'УВ 15×15',
                     'Профиль защищает внешние углы стен от сколов, '
                     'придаёт отделке законченный вид.',
                     is_new=True, allow_custom_length=True)
        tree(u1, [
            (nerzh, [
                (g['AISI 304'], [(pol, rich_palette), (sat, short_palette)]),
                (g['AISI 430'], [(sat, [c['Натуральный']])]),
            ]),
        ])
        params(u1, size=['10×10', '15×15', '20×20'], length=['2.7', '3'])
        all_products.append(u1)

        u2 = product('Профиль для внутренних углов 10×10 мм', 'profil-vnutrennie-ugly-10',
                     cats['vnutr_ugly'], 'УВн 10×10')
        tree(u2, [
            (nerzh, [
                (g['AISI 304'], [(pol, rich_palette)]),
            ]),
        ])
        params(u2, size=['10×10', '13×13'], length=['2.7'])
        all_products.append(u2)

        # ── Вставка декоративная ───────────────
        v1 = product('Вставка декоративная 10 мм', 'vstavka-dekorativnaya-10',
                     cats['vstavka'], 'ВД 10',
                     'Молдинг-вставка для декоративного оформления стен и мебельных фасадов.',
                     allow_custom_size=True)
        tree(v1, [
            (nerzh, [
                (g['AISI 304'], [(pol, full_palette), (dek, full_palette)]),
            ]),
            (latun, [(None, [(pol, [c['Натуральный'], c['Медь']])])]),
        ])
        params(v1, size=['6', '10', '15', '20'], length=['2.7', '3'])
        all_products.append(v1)

        # ── Отбойник ───────────────────────────
        o1 = product('Отбойник для стен 150 мм', 'otbojnik-150',
                     cats['otbojnik'], 'ОТБ 150',
                     'Защитный отбойник для стен в общественных помещениях, '
                     'больницах, паркингах.',
                     stock='on_order')
        tree(o1, [
            (nerzh, [
                (g['AISI 304'], [(sat, [c['Натуральный']])]),
                (g['AISI 430'], [(sat, [c['Натуральный']])]),
            ]),
            (alyum, [(g['АД31'], [(sat, [c['Натуральный']])])]),
        ])
        params(o1, length=['3'], height=['100', '150', '200'])
        all_products.append(o1)

        # ── Зеркало и стекло ───────────────────
        z1 = product('Профиль для зеркала П-образный 6 мм', 'profil-zerkalo-p-6',
                     cats['zerkalo'], 'ПЗ 6',
                     'Обрамление зеркал и стеклянных полотен. Скрывает кромку, '
                     'защищает амальгаму.',
                     is_new=True)
        tree(z1, [
            (nerzh, [
                (g['AISI 304'], [(pol, full_palette), (dek, rich_palette)]),
            ]),
            (latun, [(None, [(pol, [c['Натуральный']])])]),
        ])
        params(z1, size=['6', '8', '10'], length=['2.7', '3'])
        all_products.append(z1)

        # ── Шов деформационный ─────────────────
        s1 = product('Шов деформационный 50 мм', 'shov-deformacionnyj-50',
                     cats['shov'], 'ШД 50',
                     'Компенсирует температурные расширения стяжки и облицовки.')
        tree(s1, [
            (nerzh, [
                (g['AISI 304'], [(sat, [c['Натуральный']])]),
            ]),
            (alyum, [(g['АД31'], [(sat, [c['Натуральный']])])]),
        ])
        params(s1, size=['30', '50'], length=['2.5', '3'])
        all_products.append(s1)

        return all_products

    # ──────────────────────────────────────────
    # БЛОКИ ГЛАВНОЙ
    # ──────────────────────────────────────────

    def _seed_home_blocks(self, cats, products):
        from apps.catalog.models import Category, Product
        from apps.home.models import HomeBlock, HomeBlockItem

        self.stdout.write('  Блоки главной…')

        if HomeBlock.objects.exists():
            return

        # Ручная подборка «Хиты продаж»
        hits = HomeBlock.objects.create(
            title='Хиты продаж',
            type=HomeBlock.TYPE_MANUAL,
            link_text='Весь каталог →',
            link_url='/catalog/',
            limit=4,
            sort_order=10,
        )
        featured_slugs = [
            'profil-p-40x20x2', 'plintus-latun-40',
            'profil-stupeni-g-30x30', 'vstavka-dekorativnaya-10',
        ]
        for pos, slug in enumerate(featured_slugs):
            try:
                p = Product.objects.get(slug=slug)
                HomeBlockItem.objects.get_or_create(block=hits, product=p, defaults={'position': pos})
            except Product.DoesNotExist:
                pass

        # Блоки по категориям
        blocks_data = [
            ('Профиль для напольных покрытий', 'profil-dlya-napolnyh-pokrytij',  'Весь раздел →', '/catalog/profil-dlya-napolnyh-pokrytij/', 20),
            ('Плинтус',                        'plintus',                        'Весь раздел →', '/catalog/plintus/', 30),
            ('Профиль для защиты ступеней',    'profil-dlya-zashchity-stupenej', 'Весь раздел →', '/catalog/profil-dlya-zashchity-stupenej/', 40),
            ('Отбойник для стен',              'otbojnik-dlya-sten',             'Весь раздел →', '/catalog/otbojnik-dlya-sten/', 50),
        ]
        for title, cat_slug, link_text, link_url, order in blocks_data:
            try:
                cat = Category.objects.get(slug=cat_slug)
                HomeBlock.objects.get_or_create(
                    title=title,
                    defaults=dict(
                        type=HomeBlock.TYPE_BY_CATEGORY,
                        category=cat,
                        link_text=link_text,
                        link_url=link_url,
                        limit=4,
                        sort_order=order,
                    ),
                )
            except Category.DoesNotExist:
                pass

    # ──────────────────────────────────────────
    # СТРАНИЦЫ
    # ──────────────────────────────────────────

    def _seed_pages(self):
        from apps.pages.models import Page

        self.stdout.write('  Статические страницы…')

        pages_data = [
            {
                'slug': 'o-kompanii',
                'title': 'О компании',
                'seo_title': 'О компании МЕТАПРОФ — металлопрокат оптом',
                'seo_description': 'МЕТАПРОФ — оптовый поставщик металлопроката в Москве. '
                                   'Более 3 000 позиций в наличии. Доставка от 1 дня.',
                'content': (
                    '<h2>МЕТАПРОФ — ваш надёжный поставщик металла</h2>'
                    '<p>Компания МЕТАПРОФ работает на рынке металлопроката с 2010 года. '
                    'Мы специализируемся на поставках стального профиля, нержавейки, '
                    'латунных изделий и листового металла для производственных и '
                    'строительных предприятий Москвы и Московской области.</p>'
                    '<h3>Наши преимущества</h3>'
                    '<ul>'
                    '<li>Более 3 000 позиций в наличии на складе в Москве</li>'
                    '<li>Доставка по Москве за 1 рабочий день</li>'
                    '<li>Резка металла в размер по чертежу</li>'
                    '<li>Сертификаты ГОСТ на весь ассортимент</li>'
                    '<li>Индивидуальные условия для постоянных клиентов</li>'
                    '</ul>'
                    '<h3>Контакты</h3>'
                    '<p>г. Москва, ул. Промышленная, 1<br>'
                    'Телефон: +7 (495) 540-51-17<br>'
                    'Email: info@metaprof.ru</p>'
                ),
            },
            {
                'slug': 'dostavka',
                'title': 'Доставка',
                'seo_title': 'Доставка металлопроката по Москве | МЕТАПРОФ',
                'seo_description': 'Доставка стального профиля, нержавейки и листового металла '
                                   'по Москве от 1 рабочего дня. Самовывоз со склада.',
                'content': (
                    '<h2>Доставка металлопроката</h2>'
                    '<h3>По Москве и Московской области</h3>'
                    '<p>Доставляем металл на объект или склад покупателя. '
                    'Работаем с грузовыми автомобилями, оснащёнными кран-балкой для '
                    'выгрузки длинномерных материалов.</p>'
                    '<ul>'
                    '<li><strong>По Москве</strong> — доставка в день заказа или на следующий рабочий день</li>'
                    '<li><strong>МО до 50 км</strong> — доставка 1–2 рабочих дня</li>'
                    '<li><strong>МО 50–100 км</strong> — доставка 2–3 рабочих дня</li>'
                    '</ul>'
                    '<h3>Самовывоз</h3>'
                    '<p>Вы можете забрать заказ самостоятельно с нашего склада по адресу: '
                    'г. Москва, ул. Промышленная, 1. Склад работает: пн–пт 8:00–18:00, сб 9:00–15:00.</p>'
                    '<h3>Стоимость доставки</h3>'
                    '<p>Рассчитывается индивидуально в зависимости от объёма и адреса доставки. '
                    'Уточняйте у менеджера при оформлении заявки.</p>'
                ),
            },
            {
                'slug': 'oplata',
                'title': 'Оплата',
                'seo_title': 'Способы оплаты | МЕТАПРОФ',
                'seo_description': 'Способы оплаты металлопроката в МЕТАПРОФ: '
                                   'безналичный расчёт, отсрочка платежа для постоянных клиентов.',
                'content': (
                    '<h2>Оплата заказа</h2>'
                    '<p>Мы работаем с юридическими и физическими лицами. '
                    'Онлайн-оплата не предусмотрена — все расчёты ведутся через менеджера.</p>'
                    '<h3>Способы оплаты</h3>'
                    '<ul>'
                    '<li><strong>Безналичный расчёт</strong> — для юридических лиц и ИП. '
                    'Выставляем счёт, ждём оплату, затем отгружаем товар.</li>'
                    '<li><strong>Наличный расчёт</strong> — при самовывозе со склада.</li>'
                    '<li><strong>Отсрочка платежа</strong> — для постоянных клиентов '
                    'с объёмом закупок от 100 000 ₽/мес. по договору.</li>'
                    '</ul>'
                    '<h3>Документы</h3>'
                    '<p>Предоставляем полный пакет документов: счёт, счёт-фактуру, '
                    'товарную накладную, сертификаты качества.</p>'
                ),
            },
            {
                'slug': 'kontakty',
                'title': 'Контакты',
                'seo_title': 'Контакты МЕТАПРОФ — металлопрокат в Москве',
                'seo_description': 'Контакты компании МЕТАПРОФ. Адрес склада, телефон, '
                                   'режим работы.',
                'content': (
                    '<h2>Контакты</h2>'
                    '<p><strong>Адрес склада:</strong> г. Москва, ул. Промышленная, 1</p>'
                    '<p><strong>Телефон:</strong> <a href="tel:+74955405117">+7 (495) 540-51-17</a></p>'
                    '<p><strong>Email:</strong> info@metaprof.ru</p>'
                    '<h3>Режим работы</h3>'
                    '<ul>'
                    '<li>Понедельник – Пятница: 8:00 – 19:00</li>'
                    '<li>Суббота: 9:00 – 15:00</li>'
                    '<li>Воскресенье: выходной</li>'
                    '</ul>'
                    '<h3>Менеджеры по продажам</h3>'
                    '<p>Консультируем по ассортименту, ценам и срокам поставки: '
                    'пн–пт 9:00–18:00.</p>'
                ),
            },
            {
                'slug': 'politika-konfidentsialnosti',
                'title': 'Политика конфиденциальности',
                'seo_title': 'Политика конфиденциальности | МЕТАПРОФ',
                'seo_description': 'Политика обработки персональных данных МЕТАПРОФ.',
                'content': (
                    '<h2>Политика обработки персональных данных</h2>'
                    '<p><em>Дата вступления в силу: 1 января 2024 г.</em></p>'
                    '<h3>1. Общие положения</h3>'
                    '<p>Настоящая политика описывает порядок обработки персональных данных '
                    'пользователей сайта metaprof.ru в соответствии с Федеральным законом '
                    '№ 152-ФЗ «О персональных данных».</p>'
                    '<h3>2. Какие данные мы собираем</h3>'
                    '<p>При оформлении заявки мы собираем: имя, номер телефона, '
                    'комментарий к заказу. Данные используются исключительно '
                    'для обработки заявки и связи с вами.</p>'
                    '<h3>3. Хранение данных</h3>'
                    '<p>Персональные данные хранятся на серверах, расположенных '
                    'на территории Российской Федерации.</p>'
                    '<h3>4. Права субъекта ПДн</h3>'
                    '<p>Вы вправе отозвать согласие на обработку персональных данных, '
                    'направив запрос на email: privacy@metaprof.ru.</p>'
                ),
            },
        ]

        for data in pages_data:
            Page.objects.get_or_create(slug=data['slug'], defaults=data)

    # ──────────────────────────────────────────
    # ОТЧЁТ
    # ──────────────────────────────────────────

    def _report(self):
        from apps.catalog.models import Category, Product, ProductOptionNode
        from apps.home.models import HomeBlock
        from apps.pages.models import Page
        return {
            'categories': Category.objects.count(),
            'products':   Product.objects.count(),
            'nodes':      ProductOptionNode.objects.count(),
            'blocks':     HomeBlock.objects.count(),
            'pages':      Page.objects.count(),
        }
