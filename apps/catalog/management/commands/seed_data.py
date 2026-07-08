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
            f'{counts["variants"]} вариантов, '
            f'{counts["blocks"]} блоков главной, '
            f'{counts["pages"]} страниц'
        ))

    # ──────────────────────────────────────────
    # ОЧИСТКА
    # ──────────────────────────────────────────

    def _clear(self):
        from apps.catalog.models import Category, Product, ProductImage, ProductVariant
        from apps.references.models import Material, SteelGrade, Finish, Color, FinishColor
        from apps.home.models import HomeBlock, HomeBlockItem
        from apps.pages.models import Page

        HomeBlockItem.objects.all().delete()
        HomeBlock.objects.all().delete()
        ProductVariant.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        FinishColor.objects.all().delete()
        Color.objects.all().delete()
        Finish.objects.all().delete()
        SteelGrade.objects.all().delete()
        Material.objects.all().delete()
        Page.objects.all().delete()

    # ──────────────────────────────────────────
    # СПРАВОЧНИКИ
    # ──────────────────────────────────────────

    def _seed_references(self):
        from apps.references.models import Material, SteelGrade, Finish, Color, FinishColor

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
            ('AISI 430',     stal),
            ('12Х18Н10Т',    nerzh),
            ('AISI 304',     nerzh),
            ('AISI 316L',    nerzh),
            ('ЛС59-1',       latun),
            ('Л63',          latun),
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

        # Привязки: обработка → доступные цвета
        for finish, color_names in [
            (pol, ['Натуральный', 'Золото', 'Шампань', 'Розовое золото']),
            (sat, ['Натуральный', 'Шампань', 'Чёрный никель']),
            (dek, ['Золото', 'Чёрный никель', 'Медь', 'Розовое золото']),
        ]:
            for cname in color_names:
                FinishColor.objects.get_or_create(finish=finish, color=colors[cname])

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

        # Легаси-ключи для _seed_products/_seed_home_blocks — демо-товары
        # раскладываются по новым категориям
        cats.update({
            'profil':    cats['napolnye'],
            'p_obr':     cats['napolnye'],
            'g_obr':     cats['vnesh_ugly'],
            't_obr':     cats['porog'],
            'list_met':  cats['otbojnik'],
            'nerzh_cat': cats['stupeni'],
            'latun_cat': cats['plintus'],
            'krepezh':   cats['shov'],
        })
        return cats

    # ──────────────────────────────────────────
    # ТОВАРЫ
    # ──────────────────────────────────────────

    def _seed_products(self, cats, refs):
        from apps.catalog.models import Product, ProductVariant

        self.stdout.write('  Товары и варианты…')

        stal   = refs['stal']
        nerzh  = refs['nerzh']
        latun  = refs['latun']
        alyum  = refs['alyum']
        g      = refs['grades']
        pol    = refs['pol']
        sat    = refs['sat']
        dek    = refs['dek']
        c      = refs['colors']

        def product(name, slug, cat, code='', desc='', is_new=False):
            p, _ = Product.objects.get_or_create(
                slug=slug,
                defaults=dict(
                    name=name, category=cat, profile_code=code,
                    description=desc, is_new=is_new,
                    seo_title=f'{name} — купить оптом | МЕТАПРОФ',
                    seo_description=f'{name}. Широкий выбор, доставка по Москве, резка в размер.',
                ),
            )
            return p

        # price/color в сигнатуре оставлены, чтобы не переписывать все вызовы:
        # цена ушла из модели (её называет менеджер), цвет — параметр заказа,
        # а не вариант. Одинаковые комбинации (бывшие цветовые варианты)
        # схлопываются проверкой на дубль.
        def variant(prod, sku, mat, price=None, unit='m', length=None, height=None,
                    grade=None, finish=None, color=None, stock='in_stock'):
            if ProductVariant.objects.filter(sku=sku).exists():
                return
            if ProductVariant.objects.filter(
                product=prod, material=mat, steel_grade=grade,
                finish=finish, length_m=length, height_mm=height,
            ).exists():
                return
            ProductVariant.objects.create(
                product=prod, sku=sku, material=mat,
                steel_grade=grade, finish=finish,
                unit=unit,
                length_m=length, height_mm=height,
                in_stock=stock,
            )

        all_products = []

        # ── П-образный профиль ─────────────────
        p1 = product('Профиль П-образный 40×20×2 мм', 'profil-p-40x20x2',
                     cats['p_obr'], 'П 40×20×2',
                     'П-образный профиль применяется при монтаже лёгких конструкций, рам и каркасов. '
                     'Высокая точность геометрии, равномерная толщина стенки.')
        variant(p1, 'P-40-ST3-3M',  stal, 380, length=3, grade=g['Ст3'])
        variant(p1, 'P-40-ST3-6M',  stal, 680, length=6, grade=g['Ст3'])
        variant(p1, 'P-40-430-6M',  stal, 820, length=6, grade=g['AISI 430'])
        all_products.append(p1)

        p2 = product('Профиль П-образный 60×30×2 мм', 'profil-p-60x30x2',
                     cats['p_obr'], 'П 60×30×2',
                     'Усиленный П-профиль для несущих конструкций. Материал — сталь Ст3 и нержавейка AISI 430.',
                     is_new=True)
        variant(p2, 'P-60-ST3-6M',  stal, 960,  length=6, grade=g['Ст3'])
        variant(p2, 'P-60-430-6M',  stal, 1150, length=6, grade=g['AISI 430'])
        variant(p2, 'P-60-304-6M',  nerzh, 2100, length=6, grade=g['AISI 304'])
        all_products.append(p2)

        p3 = product('Профиль П-образный 80×40×3 мм', 'profil-p-80x40x3',
                     cats['p_obr'], 'П 80×40×3',
                     'Профиль повышенной жёсткости. Применяется в промышленных конструкциях.')
        variant(p3, 'P-80-ST3-6M',  stal, 1380, length=6, grade=g['Ст3'])
        variant(p3, 'P-80-ST20-6M', stal, 1480, length=6, grade=g['Ст20'], stock='on_order')
        all_products.append(p3)

        p4 = product('Профиль П-образный 100×50×3 мм', 'profil-p-100x50x3',
                     cats['p_obr'], 'П 100×50×3')
        variant(p4, 'P-100-ST3-6M', stal, 1850, length=6, grade=g['Ст3'])
        variant(p4, 'P-100-430-6M', stal, 2200, length=6, grade=g['AISI 430'], stock='on_order')
        all_products.append(p4)

        # ── Г-образный профиль ─────────────────
        g1 = product('Профиль Г-образный 30×30×2 мм', 'profil-g-30x30x2',
                     cats['g_obr'], 'Г 30×30×2',
                     'Угловой профиль для отделки откосов, витрин, мебели. '
                     'Доступен в стальном и нержавеющем исполнении с декоративной обработкой.')
        variant(g1, 'G-30-ST3-3M',  stal,  280, length=3, grade=g['Ст3'])
        variant(g1, 'G-30-430-3M',  stal,  420, length=3, grade=g['AISI 430'])
        variant(g1, 'G-30-SAT-N',   nerzh, 890, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        variant(g1, 'G-30-POL-G',   nerzh, 1050, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Золото'])
        all_products.append(g1)

        g2 = product('Профиль Г-образный 50×50×3 мм', 'profil-g-50x50x3',
                     cats['g_obr'], 'Г 50×50×3',
                     'Крупный угловой профиль для промышленного применения и строительства.')
        variant(g2, 'G-50-ST3-3M',  stal,  540, length=3, grade=g['Ст3'])
        variant(g2, 'G-50-ST3-6M',  stal,  980, length=6, grade=g['Ст3'])
        variant(g2, 'G-50-430-6M',  stal, 1180, length=6, grade=g['AISI 430'], stock='on_order')
        all_products.append(g2)

        g3 = product('Профиль Г-образный 20×10×1,5 мм', 'profil-g-20x10x1-5',
                     cats['g_obr'], 'Г 20×10×1,5',
                     'Малый угловой профиль. Применяется в мебельной промышленности и интерьерной отделке.',
                     is_new=True)
        variant(g3, 'G-20-SAT-N',   nerzh, 540, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        variant(g3, 'G-20-DEK-BLK', nerzh, 620, length=3, grade=g['AISI 304'],
                finish=dek, color=c['Чёрный никель'])
        variant(g3, 'G-20-POL-GLD', nerzh, 680, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Золото'])
        all_products.append(g3)

        # ── Т-образный профиль ─────────────────
        t1 = product('Профиль Т-образный 40×20×2 мм', 'profil-t-40x20x2',
                     cats['t_obr'], 'Т 40×20×2',
                     'Т-профиль используется для декоративного разделения поверхностей, '
                     'окантовки плитки, облицовки колонн.')
        variant(t1, 'T-40-SAT-N',   nerzh, 760, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        variant(t1, 'T-40-POL-SH',  nerzh, 840, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Шампань'])
        variant(t1, 'T-40-DEK-G',   nerzh, 920, length=3, grade=g['AISI 304'],
                finish=dek, color=c['Золото'])
        all_products.append(t1)

        t2 = product('Профиль Т-образный 25×12×1,5 мм', 'profil-t-25x12',
                     cats['t_obr'], 'Т 25×12×1,5')
        variant(t2, 'T-25-SAT-N',   nerzh, 490, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        variant(t2, 'T-25-DEK-BK',  nerzh, 560, length=3, grade=g['AISI 304'],
                finish=dek, color=c['Чёрный никель'])
        all_products.append(t2)

        # ── Листовой металл ────────────────────
        l1 = product('Лист стальной горячекатаный 1500×3000 мм, δ=2 мм', 'list-st-gk-2mm',
                     cats['list_met'], 'Лист г/к 2,0',
                     'Горячекатаный стальной лист. Применяется в строительстве, машиностроении, '
                     'производстве металлоконструкций.')
        variant(l1, 'LS-GK-2-ST3',  stal, 4200, unit='sheet', grade=g['Ст3'])
        variant(l1, 'LS-GK-2-ST20', stal, 4600, unit='sheet', grade=g['Ст20'], stock='on_order')
        all_products.append(l1)

        l2 = product('Лист стальной холоднокатаный 1250×2500 мм, δ=1 мм', 'list-st-xk-1mm',
                     cats['list_met'], 'Лист х/к 1,0')
        variant(l2, 'LS-XK-1-ST3',  stal, 3100, unit='sheet', grade=g['Ст3'])
        all_products.append(l2)

        l3 = product('Лист нержавеющий зеркальный 1000×2000 мм, δ=1,5 мм', 'list-nerzh-zerkalo-1-5mm',
                     cats['list_met'], 'Лист н/ж зеркало 1,5',
                     'Зеркальный нержавеющий лист AISI 304. Используется в дизайне интерьеров, '
                     'облицовке лифтов, декоративных перегородках.',
                     is_new=True)
        variant(l3, 'LS-NZH-MIR-304-15', nerzh, 12500, unit='sheet', grade=g['AISI 304'],
                finish=pol, color=c['Натуральный'])
        all_products.append(l3)

        l4 = product('Лист нержавеющий сатинированный 1000×2000 мм, δ=1,5 мм', 'list-nerzh-satin-1-5mm',
                     cats['list_met'], 'Лист н/ж сатин 1,5',
                     'Сатинированный нержавеющий лист AISI 304. Популярен в ресторанной отделке, '
                     'кухонных фасадах, торговом оборудовании.')
        variant(l4, 'LS-NZH-SAT-304-15', nerzh, 10800, unit='sheet', grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        all_products.append(l4)

        l5 = product('Лист алюминиевый 1500×3000 мм, δ=2 мм', 'list-alyum-2mm',
                     cats['list_met'], 'Лист Al 2,0',
                     'Алюминиевый лист сплав АД31. Лёгкий, коррозионностойкий. '
                     'Применяется в вентиляционных системах и отделке фасадов.')
        variant(l5, 'LS-AL-2-AD31', alyum, 5800, unit='sheet', grade=g['АД31'])
        all_products.append(l5)

        # ── Латунные изделия ───────────────────
        lt1 = product('Труба латунная круглая ø20×1,5 мм', 'truba-latun-20x1-5',
                      cats['latun_cat'], 'Тр. лат. ø20×1,5',
                      'Латунная труба ЛС59-1. Применяется в сантехнике, '
                      'декоративных конструкциях, перилах.',
                      is_new=True)
        variant(lt1, 'TR-LAT-20-3M',  latun, 980,  length=3, grade=g['ЛС59-1'])
        variant(lt1, 'TR-LAT-20-6M',  latun, 1860, length=6, grade=g['ЛС59-1'])
        all_products.append(lt1)

        lt2 = product('Труба латунная квадратная 20×20×1,5 мм', 'truba-latun-kv-20x20',
                      cats['latun_cat'], 'Тр. лат. □20×20×1,5')
        variant(lt2, 'TR-LAT-KV20-3M', latun, 1120, length=3, grade=g['ЛС59-1'])
        all_products.append(lt2)

        lt3 = product('Пруток латунный ø10 мм', 'prutok-latun-10mm',
                      cats['latun_cat'], 'Прут. лат. ø10',
                      'Латунный пруток Л63. Применяется в точной механике, '
                      'изготовлении фурнитуры и декоративных элементов.')
        variant(lt3, 'PR-LAT-10-1M',  latun, 420, length=1, grade=g['Л63'])
        variant(lt3, 'PR-LAT-10-3M',  latun, 1180, length=3, grade=g['Л63'])
        all_products.append(lt3)

        lt4 = product('Лист латунный декоративный 600×1200 мм, δ=0,8 мм', 'list-latun-dek-0-8mm',
                      cats['latun_cat'], 'Лист лат. дек. 0,8',
                      'Декоративный латунный лист с золотистым блеском. '
                      'Применяется в интерьерном дизайне, изготовлении вывесок, экранов.')
        variant(lt4, 'LS-LAT-DEK-L63', latun, 3200, unit='sheet', grade=g['Л63'])
        all_products.append(lt4)

        # ── Нержавейка ─────────────────────────
        n1 = product('Труба нержавеющая круглая ø32×1,5 мм', 'truba-nerzh-32x1-5',
                     cats['nerzh_cat'], 'Тр. н/ж ø32×1,5',
                     'Труба нержавеющая AISI 304 полированная. Применяется в перилах, '
                     'поручнях, ограждениях, сантехнических системах.')
        variant(n1, 'TR-NZH-32-POL-3M', nerzh, 1650, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Натуральный'])
        variant(n1, 'TR-NZH-32-SAT-3M', nerzh, 1450, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        all_products.append(n1)

        n2 = product('Труба нержавеющая квадратная 30×30×1,5 мм', 'truba-nerzh-kv-30x30',
                     cats['nerzh_cat'], 'Тр. н/ж □30×30×1,5',
                     'Квадратная нержавеющая труба для перил, декоративных стоек, мебели.')
        variant(n2, 'TR-NZH-KV30-POL-3M', nerzh, 1820, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Натуральный'])
        variant(n2, 'TR-NZH-KV30-BLK-3M', nerzh, 2100, length=3, grade=g['AISI 304'],
                finish=dek, color=c['Чёрный никель'])
        variant(n2, 'TR-NZH-KV30-GLD-3M', nerzh, 2300, length=3, grade=g['AISI 304'],
                finish=dek, color=c['Золото'], stock='on_order')
        all_products.append(n2)

        n3 = product('Уголок нержавеющий 40×40×2 мм', 'ugolok-nerzh-40x40x2',
                     cats['nerzh_cat'], 'Уголок н/ж 40×40×2',
                     'Нержавеющий уголок AISI 304. Применяется для защиты углов '
                     'в общественных помещениях, на производстве и в медицинских учреждениях.')
        variant(n3, 'UG-NZH-40-SAT-3M', nerzh, 1240, length=3, grade=g['AISI 304'],
                finish=sat, color=c['Натуральный'])
        variant(n3, 'UG-NZH-40-POL-3M', nerzh, 1380, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Натуральный'])
        all_products.append(n3)

        n4 = product('Полоса нержавеющая 40×3 мм', 'polosa-nerzh-40x3',
                     cats['nerzh_cat'], 'Полоса н/ж 40×3')
        variant(n4, 'PL-NZH-40-3M',  nerzh, 980,  length=3, grade=g['AISI 304'])
        variant(n4, 'PL-NZH-40-6M',  nerzh, 1860, length=6, grade=g['AISI 304'], stock='on_order')
        all_products.append(n4)

        n5 = product('Труба нержавеющая ø16×1 мм', 'truba-nerzh-16x1',
                     cats['nerzh_cat'], 'Тр. н/ж ø16×1',
                     'Тонкостенная нержавеющая трубка для мебельного производства, '
                     'торгового оборудования, декоративных стоек.',
                     is_new=True)
        variant(n5, 'TR-NZH-16-POL-3M', nerzh, 920,  length=3, grade=g['AISI 304'],
                finish=pol, color=c['Натуральный'])
        variant(n5, 'TR-NZH-16-RG-3M',  nerzh, 1100, length=3, grade=g['AISI 304'],
                finish=pol, color=c['Розовое золото'])
        all_products.append(n5)

        # ── Крепёж ─────────────────────────────
        k1 = product('Болт М10×50 нержавеющий', 'bolt-m10x50-nerzh',
                     cats['krepezh'], 'Болт М10×50',
                     'Болт нержавеющий AISI 316L. Применяется в условиях повышенной влажности '
                     'и агрессивных сред. Класс прочности А2-70.')
        variant(k1, 'BLT-M10-50-316', nerzh, 28, unit='piece', grade=g['AISI 316L'])
        all_products.append(k1)

        k2 = product('Гайка М10 нержавеющая', 'gaika-m10-nerzh',
                     cats['krepezh'], 'Гайка М10')
        variant(k2, 'GKA-M10-316', nerzh, 12, unit='piece', grade=g['AISI 316L'])
        all_products.append(k2)

        k3 = product('Шпилька М8×1000 стальная', 'shpilka-m8x1000',
                     cats['krepezh'], 'Шпилька М8×1000',
                     'Стальная шпилька с непрерывной резьбой. Применяется в строительстве '
                     'и монтаже оборудования.')
        variant(k3, 'SHP-M8-1000-ST', stal, 95, unit='piece', grade=g['Ст3'])
        variant(k3, 'SHP-M8-1000-NZH', nerzh, 185, unit='piece', grade=g['AISI 304'], stock='on_order')
        all_products.append(k3)

        k4 = product('Анкерный болт М12×100 нержавеющий', 'anker-m12x100-nerzh',
                     cats['krepezh'], 'Анкер М12×100',
                     is_new=True)
        variant(k4, 'ANK-M12-100-316', nerzh, 145, unit='piece', grade=g['AISI 316L'])
        all_products.append(k4)

        return all_products

    # ──────────────────────────────────────────
    # БЛОКИ ГЛАВНОЙ
    # ──────────────────────────────────────────

    def _seed_home_blocks(self, cats, products):
        from apps.catalog.models import Category
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
        # Берём товары из разных категорий
        featured_slugs = [
            'profil-g-30x30x2', 'list-nerzh-zerkalo-1-5mm',
            'truba-latun-20x1-5', 'truba-nerzh-32x1-5',
        ]
        from apps.catalog.models import Product
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
        from apps.catalog.models import Category, Product, ProductVariant
        from apps.home.models import HomeBlock
        from apps.pages.models import Page
        return {
            'categories': Category.objects.count(),
            'products':   Product.objects.count(),
            'variants':   ProductVariant.objects.count(),
            'blocks':     HomeBlock.objects.count(),
            'pages':      Page.objects.count(),
        }
