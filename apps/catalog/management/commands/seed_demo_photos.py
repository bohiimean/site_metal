"""
Тестовые фото для проверки ракурсов исполнений на карточке товара.

Рисует картинки металлического профиля (вид спереди, сечение, крупный план)
в цвете исполнения и с подписью «исполнение — ракурс N/M» и вешает их на три
товара из seed_data — по сценарию на каждый:

  - Профиль для ступеней Г-образный — ракурсы у нескольких исполнений
    (у «Чёрного никеля» их меньше) + общий чертёж после ракурсов;
  - Профиль Т-образный — только фото исполнений, общей галереи нет;
  - Плинтус латунный — только общая галерея, без правил.

Повторный запуск пересоздаёт демо-фото, остальные фото товаров не трогает.
Только для dev: при DEBUG=False не запускается без --force.

Подписи на картинках — кириллицей, а встроенный шрифт Pillow её не знает:
нужен TTF с кириллицей (--font, иначе ищется DejaVu). Без него подписи
выйдут квадратиками — на проверку ракурсов это не влияет.

Использование:
    python manage.py seed_demo_photos
    python manage.py seed_demo_photos --font /tmp/Arial.ttf
    python manage.py seed_demo_photos --clear   # только удалить демо-фото
"""
import io
import random

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from apps.catalog.models import Product, ProductImage
from apps.references.models import Color, Finish, Material

W, H = 1600, 1200
BG = (246, 246, 244)
DEMO_PREFIX = 'demo-angle-'

# Сечения в долях единичного квадрата
SHAPES = {
    'L': [(0, 0), (1, 0), (1, .12), (.12, .12), (.12, 1), (0, 1)],
    'T': [(0, 0), (1, 0), (1, .16), (.58, .16), (.58, 1), (.42, 1), (.42, .16), (0, .16)],
    'plinth': [(0, 0), (.16, 0), (.16, .86), (1, .86), (1, 1), (0, 1)],
}

STEEL = (196, 200, 205)
BRASS = (201, 164, 92)

VIEWS = ['вид спереди', 'сечение', 'крупный план']


FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
]
FONT_PATH = None  # выставляется в handle()


def _font(size):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default(size)


def _mix(c, k):
    """k<1 — темнее, k>1 — светлее."""
    if k <= 1:
        return tuple(int(v * k) for v in c)
    return tuple(int(v + (255 - v) * (k - 1)) for v in c)


def _hex(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def metal(size, base, polished, seed=0):
    """Текстура металла: полировка — резкие блики, сатин — мягкий градиент
    с продольными рисками."""
    w, h = size
    stops = ([(0, .55), (.18, 1.35), (.3, .8), (.55, 1.15), (.62, 1.6), (.72, .7), (1, .5)]
             if polished else
             [(0, .75), (.35, 1.1), (.7, .95), (1, .7)])
    col = Image.new('RGB', (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        for (t0, k0), (t1, k1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                k = k0 + (k1 - k0) * (t - t0) / (t1 - t0)
                break
        col.putpixel((0, y), _mix(base, k))
    img = col.resize((w, h))
    if not polished:
        rnd = random.Random(seed)
        d = ImageDraw.Draw(img, 'RGBA')
        for _ in range(h // 2):
            y = rnd.randrange(h)
            a = rnd.randrange(10, 35)
            shade = 255 if rnd.random() < .5 else 0
            d.line([(0, y), (w, y)], fill=(shade, shade, shade, a))
    return img


def _shadow(canvas, box):
    sh = Image.new('L', canvas.size, 0)
    ImageDraw.Draw(sh).ellipse(box, fill=90)
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    canvas.paste((60, 60, 60), mask=sh)


def _shape_points(shape, x, y, size):
    return [(x + px * size, y + py * size) for px, py in SHAPES[shape]]


def render(view, shape, base, polished, caption, subcaption, seed):
    img = Image.new('RGB', (W, H), BG)
    if view == 'вид спереди':
        _shadow(img, (140, 700, 1460, 780))
        bar = metal((1300, 220), base, polished, seed)
        img.paste(bar, (150, 470))
        d = ImageDraw.Draw(img)
        d.rectangle((150, 470, 1449, 689), outline=_mix(base, .45), width=3)
        # Торцы: видно толщину профиля
        d.polygon([(1450, 470), (1485, 445), (1485, 665), (1450, 689)], fill=_mix(base, .6))
        d.polygon([(150, 470), (185, 445), (1485, 445), (1450, 470)], fill=_mix(base, 1.25))
    elif view == 'сечение':
        size, x, y = 640, 480, 250
        _shadow(img, (x - 20, y + size - 30, x + size + 20, y + size + 40))
        mask = Image.new('L', (W, H), 0)
        pts = _shape_points(shape, x, y, size)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        tex = metal((W, H), base, polished, seed)
        img.paste(tex, mask=mask)
        ImageDraw.Draw(img).polygon(pts, outline=_mix(base, .4), width=4)
    else:  # крупный план: поверхность под углом
        tex = metal((2200, 900), base, polished, seed).rotate(-12, expand=True, fillcolor=BG)
        img.paste(tex, (-300, 80))
        d = ImageDraw.Draw(img)
        d.line([(0, 330), (W, -10)], fill=_mix(base, 1.7), width=6)  # блик на ребре

    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 150, W, H), fill=(255, 255, 255))
    d.text((60, H - 130), caption, font=_font(52), fill=(30, 30, 30))
    d.text((60, H - 62), subcaption, font=_font(40), fill=(110, 110, 110))
    return img


def render_drawing(shape, caption):
    """Общее фото: чертёж сечения с размерами."""
    img = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    size, x, y = 620, 490, 240
    d.polygon(_shape_points(shape, x, y, size), outline=(40, 40, 40), width=5)
    ink, f = (90, 90, 90), _font(44)
    d.line([(x, y - 60), (x + size, y - 60)], fill=ink, width=3)
    d.text((x + size / 2 - 30, y - 125), '30', font=f, fill=ink)
    d.line([(x - 60, y), (x - 60, y + size)], fill=ink, width=3)
    d.text((x - 150, y + size / 2 - 25), '30', font=f, fill=ink)
    d.text((60, H - 130), caption, font=_font(52), fill=(30, 30, 30))
    d.text((60, H - 62), 'общее фото — идёт после ракурсов исполнения',
           font=_font(40), fill=(110, 110, 110))
    return img


class Command(BaseCommand):
    help = 'Тестовые фото ракурсов исполнений на трёх товарах (только dev)'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Только удалить демо-фото')
        parser.add_argument('--force', action='store_true',
                            help='Запустить при DEBUG=False')
        parser.add_argument('--font', help='TTF-шрифт с кириллицей для подписей')

    def handle(self, *args, **options):
        if not settings.DEBUG and not options['force']:
            raise CommandError('Это тестовые данные: при DEBUG=False нужен --force.')

        global FONT_PATH
        import os
        FONT_PATH = next((f for f in [options['font'], *FONT_CANDIDATES]
                          if f and os.path.exists(f)), None)
        if FONT_PATH is None:
            self.stderr.write('Нет шрифта с кириллицей (--font) — подписи будут квадратиками')

        removed = self._clear()
        if options['clear']:
            self.stdout.write(self.style.SUCCESS(f'Удалено демо-фото: {removed}'))
            return

        mat = {m.slug: m for m in Material.objects.all()}
        fin = {f.name: f for f in Finish.objects.all()}
        col = {c.name: c for c in Color.objects.filter(ral_code='')}
        nerzh, latun = self._find(mat, 'Нержавейка'), self._find(mat, 'Латунь')

        # (товар, сечение, общие фото, [(материал, обработка, цвет, число ракурсов)])
        plan = [
            ('profil-stupeni-g-30x30', 'L', ['чертёж'], [
                (nerzh, 'Полированная', None, 3),
                (nerzh, 'Полированная', 'Золото', 3),
                (nerzh, 'Полированная', 'Чёрный никель', 2),
                (nerzh, 'Сатинированная', None, 3),
                (latun, 'Полированная', None, 3),
            ]),
            ('profil-t-25x12', 'T', [], [
                (nerzh, 'Полированная', None, 3),
                (nerzh, 'Сатинированная', None, 3),
                (nerzh, 'Декоративная', 'Золото', 2),
            ]),
            ('plintus-latun-40', 'plinth', ['латунь'] * 3, []),
        ]

        created = 0
        with transaction.atomic():
            for slug, shape, general, sets in plan:
                product = Product.objects.filter(slug=slug).first()
                if product is None:
                    self.stderr.write(f'✗ {slug}: товара нет — сначала seed_data')
                    continue
                order = 0
                for i, kind in enumerate(general):
                    if kind == 'чертёж':
                        img = render_drawing(shape, 'Чертёж сечения')
                    else:
                        img = render(VIEWS[i % 3], shape, BRASS, True,
                                     'Латунь (общее фото)',
                                     f'фото {i + 1}/{len(general)} — {VIEWS[i % 3]}', i)
                    self._save(product, img, order, f'{slug}-general-{i}')
                    order += 1
                    created += 1
                for material, finish_name, color_name, count in sets:
                    finish = fin[finish_name]
                    color = col[color_name] if color_name else None
                    base = (_hex(color.hex_code) if color and color.hex_code
                            else BRASS if material == latun else STEEL)
                    title = ' · '.join(filter(None, [
                        material.name, finish.name, color_name]))
                    for n in range(count):
                        img = render(VIEWS[n], shape, base, finish_name != 'Сатинированная',
                                     title, f'ракурс {n + 1}/{count} — {VIEWS[n]}', n)
                        name = '-'.join(filter(None, [
                            slug, material.slug, finish.slug,
                            f'c{color.pk}' if color else '', str(n)]))
                        self._save(product, img, order, name,
                                   material=material, finish=finish, color=color)
                        order += 1
                        created += 1
                self.stdout.write(f'✓ {product.name}')

        self.stdout.write(self.style.SUCCESS(
            f'Демо-фото: удалено {removed}, создано {created}'))

    @staticmethod
    def _find(mat, name):
        for m in mat.values():
            if m.name == name:
                return m
        raise CommandError(f'Нет материала «{name}» — сначала seed_data')

    @staticmethod
    def _save(product, img, order, name, **conditions):
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=88)
        pi = ProductImage(product=product, sort_order=order, **conditions)
        pi.image.save(f'{DEMO_PREFIX}{name}.jpg', ContentFile(buf.getvalue()), save=False)
        pi.save()
        # Пресеты imagekit кэшируются по имени исходника, а имя при повторном
        # запуске то же: без force карточка показала бы прошлую картинку
        for spec in (pi.thumb, pi.card, pi.card_2x, pi.gallery, pi.zoom):
            spec.generate(force=True)

    @staticmethod
    def _clear():
        qs = ProductImage.objects.filter(image__contains=DEMO_PREFIX)
        n = 0
        for pi in qs:
            pi.image.delete(save=False)
            pi.delete()
            n += 1
        return n
