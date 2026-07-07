from django.db import models
from django.core.exceptions import ValidationError
from treebeard.mp_tree import MP_Node
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from apps.references.models import Material, SteelGrade, Finish, Color, FinishColor


class Category(MP_Node):
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True)
    seo_title = models.CharField('SEO Title', max_length=200, blank=True)
    seo_description = models.TextField('SEO Description', blank=True)
    h1 = models.CharField('H1', max_length=200, blank=True)
    is_active = models.BooleanField('Активна', default=True)

    node_order_by = ['name']

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


class ProductQuerySet(models.QuerySet):
    def for_cards(self):
        """QuerySet для сетки карточек: с min_price, первым фото и первым вариантом."""
        from django.db.models import Min, Prefetch
        return (
            self.filter(is_active=True)
            .annotate(min_price=Min('variants__price'))
            .select_related('category')
            .prefetch_related(
                Prefetch(
                    'images',
                    queryset=ProductImage.objects.order_by('sort_order'),
                    to_attr='prefetched_images',
                ),
                Prefetch(
                    'variants',
                    queryset=ProductVariant.objects.filter(is_active=True).order_by('price'),
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

    def get_min_price(self):
        result = self.variants.filter(is_active=True).order_by('price').first()
        return result.price if result else None

    def get_first_image(self):
        return self.images.order_by('sort_order').first()


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Товар',
    )
    image = models.ImageField('Изображение', upload_to='products/original/')
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    # Пресеты (WebP) — генерируются лениво при первом обращении
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
    gallery = ImageSpecField(
        source='image',
        processors=[ResizeToFill(1000, 750)],
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

    def __str__(self):
        return f'Фото #{self.sort_order} — {self.product}'


class ProductVariant(models.Model):
    UNIT_CHOICES = [
        ('m',     'за метр'),
        ('piece', 'за штуку'),
        ('sheet', 'за лист'),
        ('kg',    'за кг'),
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
    color = models.ForeignKey(
        Color, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Цвет',
    )
    image = models.ForeignKey(
        ProductImage, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Изображение варианта',
        help_text='Если не задано — показывается первое фото товара',
    )

    height_mm = models.DecimalField(
        'Высота, мм', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    length_m = models.DecimalField(
        'Длина, м', max_digits=8, decimal_places=2,
        null=True, blank=True,
    )
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    unit = models.CharField('Единица цены', max_length=10, choices=UNIT_CHOICES, default='m')
    in_stock = models.CharField(
        'Наличие', max_length=20,
        choices=STOCK_CHOICES, default='in_stock',
    )
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Вариант товара'
        verbose_name_plural = 'Варианты товара'
        ordering = ['price']

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

        # 3. Цвет допустим только при заданной обработке, и пара (finish, color)
        #    должна существовать в FinishColor
        if self.color_id and not self.finish_id:
            raise ValidationError({
                'color': 'Нельзя выбрать цвет без обработки.',
            })

        if self.color_id and self.finish_id:
            if not FinishColor.objects.filter(
                finish_id=self.finish_id,
                color_id=self.color_id,
            ).exists():
                raise ValidationError({
                    'color': 'Такая комбинация обработки и цвета недопустима.',
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_image(self):
        """Возвращает изображение варианта или первое фото товара."""
        return self.image or self.product.get_first_image()
