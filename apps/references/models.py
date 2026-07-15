from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

from apps.validators import IMAGE_UPLOAD_VALIDATORS, UPLOAD_HELP_TEXT


class Material(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Slug', max_length=100, unique=True)
    landing_title = models.CharField(
        'Заголовок на странице «Продукция»', max_length=200, blank=True,
        help_text='Например «Изделия из нержавеющей стали». '
                  'Пусто — материал не показывается основным разделом.',
    )
    image = models.ImageField(
        'Изображение', upload_to='materials/', blank=True,
        validators=IMAGE_UPLOAD_VALIDATORS,
        help_text='Для карточки основного раздела на странице «Продукция». ' + UPLOAD_HELP_TEXT,
    )
    is_active = models.BooleanField('Активен', default=True)

    card = ImageSpecField(
        source='image',
        processors=[ResizeToFill(800, 450)],
        format='WEBP',
        options={'quality': 85},
    )

    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['name']

    def __str__(self):
        return self.name


class SteelGrade(models.Model):
    name = models.CharField('Марка', max_length=100)
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        related_name='steel_grades',
        verbose_name='Материал',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Марка стали'
        verbose_name_plural = 'Марки стали'
        ordering = ['material', 'name']

    def __str__(self):
        return f'{self.name} ({self.material})'


class Finish(models.Model):
    COLOR_UI_SWATCHES = 'swatches'
    COLOR_UI_RAL      = 'ral_palette'
    COLOR_UI_CUSTOM   = 'custom_request'
    COLOR_UI_CHOICES  = [
        ('swatches',       'Свотчи (≤10 цветов)'),
        ('ral_palette',    'Каталог RAL с поиском'),
        ('custom_request', '5 популярных + свой цвет'),
    ]

    name     = models.CharField('Название', max_length=100)
    slug     = models.SlugField('Slug', max_length=100, unique=True)
    color_ui = models.CharField(
        'Интерфейс выбора цвета', max_length=20,
        choices=COLOR_UI_CHOICES, default='swatches',
        help_text='Шлифованный/Полированный → «Каталог RAL». Под покраску → «5 популярных + свой цвет».',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Обработка'
        verbose_name_plural = 'Обработки'
        ordering = ['name']

    def __str__(self):
        return self.name


class Color(models.Model):
    COLOR_GROUP_CHOICES = [
        ('white',    'Белые'),
        ('gray',     'Серые'),
        ('black',    'Чёрные'),
        ('brown',    'Коричневые'),
        ('blue',     'Синие'),
        ('green',    'Зелёные'),
        ('metallic', 'Металлик'),
        ('other',    'Другие'),
    ]

    name        = models.CharField('Название', max_length=100)
    hex_code    = models.CharField('HEX-код', max_length=7, blank=True)
    ral_code    = models.CharField('RAL-код', max_length=20, blank=True,
                                   help_text='Например: RAL 9010')
    color_group = models.CharField('Группа цвета', max_length=20,
                                   choices=COLOR_GROUP_CHOICES, blank=True)
    is_active   = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Цвет'
        verbose_name_plural = 'Цвета'
        ordering = ['name']

    def __str__(self):
        return self.name


class MaterialColor(models.Model):
    """Палитра материала — фолбэк для вариантов, у которых нет своей палитры
    марки: либо марка не задана вовсе (алюминий: «анодированный»/«сырой»),
    либо у марки не отмечен ни один цвет.

    Приоритет на карточке товара: палитра марки (SteelGradeColor) →
    палитра материала (MaterialColor) → цвета нет.
    """
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        related_name='material_colors',
        verbose_name='Материал',
    )
    color = models.ForeignKey(
        Color, on_delete=models.CASCADE,
        related_name='material_colors',
        verbose_name='Цвет',
    )

    class Meta:
        verbose_name = 'Цвет материала'
        verbose_name_plural = 'Цвета материалов'
        unique_together = [('material', 'color')]

    def __str__(self):
        return f'{self.material} — {self.color}'


class SteelGradeColor(models.Model):
    """Палитра марки стали: какие цвета доступны для товаров из этой марки.

    Палитра привязана к марке, а интерфейс выбора цвета (свотчи/RAL/свой) —
    к обработке (Finish.color_ui). На карточке товара цвет показывается только
    при выбранной обработке: цвет — результат обработки. Если у марки палитра
    пуста или марки у варианта нет — используется палитра материала
    (MaterialColor).
    """
    steel_grade = models.ForeignKey(
        SteelGrade, on_delete=models.CASCADE,
        related_name='grade_colors',
        verbose_name='Марка стали',
    )
    color = models.ForeignKey(
        Color, on_delete=models.CASCADE,
        related_name='grade_colors',
        verbose_name='Цвет',
    )

    class Meta:
        verbose_name = 'Цвет марки стали'
        verbose_name_plural = 'Цвета марок стали'
        unique_together = [('steel_grade', 'color')]

    def __str__(self):
        return f'{self.steel_grade} — {self.color}'
