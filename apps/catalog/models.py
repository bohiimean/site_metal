from django.db import models
from django.core.exceptions import ValidationError
from treebeard.mp_tree import MP_Node
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from apps.references.models import Material, SteelGrade, Finish, Color
from apps.validators import IMAGE_UPLOAD_VALIDATORS, UPLOAD_HELP_TEXT


class Category(MP_Node):
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True)
    image = models.ImageField(
        'Изображение', upload_to='categories/', blank=True,
        validators=IMAGE_UPLOAD_VALIDATORS,
        help_text='Для карточки на странице «Продукция». ' + UPLOAD_HELP_TEXT,
    )
    seo_title = models.CharField('SEO Title', max_length=200, blank=True)
    seo_description = models.TextField('SEO Description', blank=True)
    h1 = models.CharField('H1', max_length=200, blank=True)
    is_active = models.BooleanField('Активна', default=True)

    card = ImageSpecField(
        source='image',
        processors=[ResizeToFill(600, 450)],
        format='WEBP',
        options={'quality': 85},
    )

    # node_order_by не задаём намеренно: порядок категорий ручной —
    # задаётся в админке полями «Position»/«Relative to» (movenodeform)
    # и определяет порядок карточек на «Продукции»

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name

    def get_full_slug_path(self):
        return '/'.join(a.slug for a in self.get_ancestors()) + f'/{self.slug}/'

    def clean(self):
        super().clean()
        if self.slug and Product.objects.filter(slug=self.slug).exists():
            raise ValidationError({
                'slug': 'Такой slug уже используется товаром. Выберите другой.',
            })


class CategoryFacet(models.Model):
    """Настройка фильтров раздела каталога (управляется менеджером).

    Наследование: у категории нет ни одной строки → берётся конфиг ближайшего
    предка; нет ни у кого → стандартный набор (см. DEFAULT_FACET_KEYS в views).
    Значения внутри фасета считаются автоматически из активных вариантов
    товаров раздела; фасет без значений скрывается, даже если включён.
    """
    FACET_CHOICES = [
        ('material',    'Материал'),
        ('steel_grade', 'Марка стали'),
        ('finish',      'Обработка'),
        ('size',        'Размер'),
        ('length',      'Длина'),
        ('in_stock',    'Только в наличии'),
    ]

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE,
        related_name='facets',
        verbose_name='Категория',
    )
    facet = models.CharField('Фильтр', max_length=20, choices=FACET_CHOICES)
    title = models.CharField(
        'Свой заголовок', max_length=100, blank=True,
        help_text='Пусто — стандартный («Марка стали» и т.п.)',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Фильтр раздела'
        verbose_name_plural = 'Фильтры раздела'
        ordering = ['sort_order']
        unique_together = [('category', 'facet')]

    def __str__(self):
        return f'{self.category} — {self.get_facet_display()}'


class ProductQuerySet(models.QuerySet):
    def for_cards(self):
        """QuerySet для сетки карточек: с первым фото и первым вариантом."""
        from django.db.models import Prefetch
        return (
            self.filter(is_active=True)
            .select_related('category')
            .prefetch_related(
                Prefetch(
                    'images',
                    queryset=ProductImage.objects.gallery_first(),
                    to_attr='prefetched_images',
                ),
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.filter(is_active=True).order_by('sku'),
                    to_attr='prefetched_variants',
                ),
            )
        )


class Product(models.Model):
    name = models.CharField('Название', max_length=300)
    slug = models.SlugField('Slug', max_length=300, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Категория',
    )
    description = models.TextField('Описание', blank=True)
    profile_code = models.CharField('Номенклатурный код', max_length=100, blank=True)
    is_new = models.BooleanField('Новинка', default=False)
    seo_title = models.CharField('SEO Title', max_length=200, blank=True)
    seo_description = models.TextField('SEO Description', blank=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('catalog:detail', kwargs={'slug': self.slug})

    def clean(self):
        super().clean()
        if self.slug and Category.objects.filter(slug=self.slug).exists():
            raise ValidationError({
                'slug': 'Такой slug уже используется категорией. Выберите другой.',
            })

    def get_first_image(self):
        return self.images.gallery_first().first()


class ProductImageQuerySet(models.QuerySet):
    GALLERY_Q = models.Q(finish__isnull=True, color__isnull=True, color_group='')

    def gallery(self):
        """Обычные фото товара (листаются миниатюрами)."""
        return self.filter(self.GALLERY_Q)

    def overrides(self):
        """Фото под обработку/цвет — подменяют галерею при выборе на карточке."""
        return self.exclude(self.GALLERY_Q)

    def gallery_first(self):
        """Все фото: сначала галерея, затем привязанные к обработке/цвету.
        Для мест, где нужно хоть какое-то фото (сетка карточек), даже если
        менеджер загрузил только привязанные."""
        return self.annotate(
            _is_override=models.Case(
                models.When(self.GALLERY_Q, then=0),
                default=1,
                output_field=models.IntegerField(),
            ),
        ).order_by('_is_override', 'sort_order')


class ProductImage(models.Model):
    """Фото товара. Роль строки определяется заполненными полями:

    - finish/color/группа пустые — обычное фото галереи (порядок — sort_order);
    - заполнены — фото, показываемое при выборе на карточке.
    Fallback-цепочка на клиенте (от точного к общему):
    обработка+цвет → обработка+группа → цвет → группа → обработка → галерея.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Товар',
    )
    image = models.ImageField(
        'Изображение', upload_to='products/original/',
        validators=IMAGE_UPLOAD_VALIDATORS,
        help_text=UPLOAD_HELP_TEXT,
    )
    finish = models.ForeignKey(
        Finish, on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name='Обработка',
        help_text='Фото для этой обработки',
    )
    color = models.ForeignKey(
        Color, on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name='Цвет',
        help_text='Фото под конкретный цвет',
    )
    color_group = models.CharField(
        'Группа цветов', max_length=20,
        choices=Color.COLOR_GROUP_CHOICES, blank=True,
        help_text='Или одно фото на всю группу (синие, серые, …)',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    objects = ProductImageQuerySet.as_manager()

    # Пресеты (WebP) — генерируются лениво при первом обращении.
    # thumb/card кадрируют (ResizeToFill) — для миниатюр и сетки это ок;
    # gallery/zoom вписывают целиком (ResizeToFit) — на карточке товара
    # предмет должен быть виден полностью, без обрезки.
    thumb = ImageSpecField(
        source='image',
        processors=[ResizeToFill(120, 90)],
        format='WEBP',
        options={'quality': 85},
    )
    card = ImageSpecField(
        source='image',
        processors=[ResizeToFill(600, 450)],
        format='WEBP',
        options={'quality': 85},
    )
    card_2x = ImageSpecField(
        source='image',
        processors=[ResizeToFill(1200, 900)],
        format='WEBP',
        options={'quality': 82},
    )
    gallery = ImageSpecField(
        source='image',
        processors=[ResizeToFit(1000, 750)],
        format='WEBP',
        options={'quality': 90},
    )
    zoom = ImageSpecField(
        source='image',
        processors=[ResizeToFit(2000, 2000)],
        format='WEBP',
        options={'quality': 92},
    )

    class Meta:
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'
        ordering = ['sort_order']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'finish', 'color'],
                condition=models.Q(color__isnull=False),
                nulls_distinct=False,
                name='uniq_product_image_finish_color',
                violation_error_message='Фото для этой пары «обработка + цвет» уже есть.',
            ),
            models.UniqueConstraint(
                fields=['product', 'finish', 'color_group'],
                condition=~models.Q(color_group=''),
                nulls_distinct=False,
                name='uniq_product_image_finish_group',
                violation_error_message='Фото для этой пары «обработка + группа цветов» уже есть.',
            ),
            models.UniqueConstraint(
                fields=['product', 'finish'],
                condition=models.Q(
                    finish__isnull=False, color__isnull=True, color_group='',
                ),
                name='uniq_product_image_finish_only',
                violation_error_message='Фото для этой обработки (без цвета) уже есть.',
            ),
        ]

    def __str__(self):
        target = ', '.join(
            str(p) for p in (self.finish, self.color or self.get_color_group_display())
            if p
        )
        if target:
            return f'{self.product} — {target}'
        return f'Фото #{self.sort_order} — {self.product}'

    def clean(self):
        if self.color_id and self.color_group:
            raise ValidationError(
                'Укажите либо конкретный цвет, либо группу цветов — не оба сразу.'
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    UNIT_CHOICES = [
        ('m',     'метр'),
        ('piece', 'штука'),
        ('sheet', 'лист'),
        ('kg',    'кг'),
    ]
    STOCK_CHOICES = [
        ('in_stock',    'В наличии'),
        ('on_order',    'Под заказ'),
        ('out_of_stock', 'Нет в наличии'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='Товар',
    )
    sku = models.CharField('Артикул', max_length=100, unique=True)

    material = models.ForeignKey(
        Material, on_delete=models.PROTECT,
        verbose_name='Материал',
    )
    steel_grade = models.ForeignKey(
        SteelGrade, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Марка стали',
    )
    finish = models.ForeignKey(
        Finish, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Обработка',
    )

    size = models.CharField(
        'Размер', max_length=50, blank=True,
        help_text='Например: 6×6, 10×10, 40×20',
    )
    allow_custom_size = models.BooleanField(
        'Свой размер', default=False,
        help_text='На карточке товара появится поле «Свой размер» — '
                  'клиент укажет нужный размер, он уйдёт в заявку',
    )
    height_mm = models.DecimalField(
        'Высота, мм', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    length_m = models.DecimalField(
        'Длина, м', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    allow_custom_length = models.BooleanField(
        'Своя длина', default=False,
        help_text='На карточке товара появится поле «Своя длина» — '
                  'клиент укажет нужную длину, она уйдёт в заявку',
    )
    unit = models.CharField('Единица измерения', max_length=10, choices=UNIT_CHOICES, default='m')
    in_stock = models.CharField(
        'Наличие', max_length=20,
        choices=STOCK_CHOICES, default='in_stock',
    )
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Вариант товара'
        verbose_name_plural = 'Варианты товара'
        ordering = ['sku']

    def __str__(self):
        return f'{self.product} / {self.sku}'

    def clean(self):
        # 1. Марка стали должна принадлежать выбранному материалу
        if self.steel_grade_id and self.material_id:
            if self.steel_grade.material_id != self.material_id:
                raise ValidationError({
                    'steel_grade': (
                        'Марка стали не соответствует выбранному материалу. '
                        f'Ожидается материал «{self.steel_grade.material}».'
                    )
                })

        # 2. Если у материала нет активных марок — steel_grade должен быть пустым
        if self.material_id and not self.steel_grade_id:
            pass  # пустой steel_grade всегда допустим

        if self.steel_grade_id and self.material_id:
            has_grades = SteelGrade.objects.filter(
                material_id=self.material_id, is_active=True,
            ).exists()
            if not has_grades:
                raise ValidationError({
                    'steel_grade': 'У выбранного материала нет активных марок стали.',
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
