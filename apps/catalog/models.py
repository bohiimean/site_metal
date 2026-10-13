from django.db import models
from django.core.exceptions import ValidationError
from treebeard.mp_tree import MP_Node
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from apps.references.models import Material, SteelGrade, Finish, Color, Parameter
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
        ('color',       'Цвет'),
        ('param',       'Параметр'),
        ('in_stock',    'Только в наличии'),
    ]

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE,
        related_name='facets',
        verbose_name='Категория',
    )
    facet = models.CharField('Фильтр', max_length=20, choices=FACET_CHOICES)
    # Фильтр «Параметр» — по одному параметру справочника (ширина, длина…);
    # таких фильтров в разделе может быть несколько
    parameter = models.ForeignKey(
        Parameter, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='facets',
        verbose_name='Параметр',
        help_text='Только для фильтра «Параметр»',
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'facet'],
                condition=~models.Q(facet='param'),
                name='uniq_category_facet',
                violation_error_message='Такой фильтр в разделе уже есть.',
            ),
            models.UniqueConstraint(
                fields=['category', 'parameter'],
                condition=models.Q(facet='param'),
                name='uniq_category_param_facet',
                violation_error_message='Фильтр по этому параметру в разделе уже есть.',
            ),
        ]

    def __str__(self):
        if self.facet == 'param' and self.parameter_id:
            return f'{self.category} — {self.parameter.name}'
        return f'{self.category} — {self.get_facet_display()}'

    def clean(self):
        super().clean()
        if self.facet == 'param' and not self.parameter_id:
            raise ValidationError({'parameter': 'Выберите параметр для фильтра.'})
        if self.facet != 'param' and self.parameter_id:
            raise ValidationError({
                'parameter': 'Параметр выбирается только для фильтра «Параметр».',
            })


# Сколько карточек показывать в блоке «С этим также покупают»
RELATED_LIMIT = 4


class ProductQuerySet(models.QuerySet):
    def for_cards(self):
        """QuerySet для сетки карточек: с первым фото и материалами (подпись)."""
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
                    'option_nodes',
                    queryset=ProductOptionNode.objects
                    .filter(node_type='material')
                    .select_related('material')
                    .order_by('sort_order', 'id'),
                    to_attr='prefetched_materials',
                ),
            )
        )


class Product(models.Model):
    STOCK_CHOICES = [
        ('in_stock',     'В наличии'),
        ('on_order',     'Под заказ'),
        ('out_of_stock', 'Нет в наличии'),
    ]

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
    is_featured = models.BooleanField(
        'Популярный', default=False,
        help_text='Поднимается выше в каталоге и в списке товаров. Порядок '
                  'между популярными задаётся на странице «Порядок популярных».',
    )
    featured_order = models.PositiveIntegerField(
        'Порядок в популярных', default=0,
        help_text='Заполняется автоматически со страницы «Порядок популярных».',
    )
    in_stock = models.CharField(
        'Наличие', max_length=20,
        choices=STOCK_CHOICES, default='in_stock',
    )
    hide_related = models.BooleanField(
        'Скрыть блок «С этим также покупают»', default=False,
        help_text='Блока не будет на этом товаре — даже если подборка задана '
                  'или в категории есть другие товары.',
    )
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

    def get_related(self, limit=RELATED_LIMIT):
        """Товары для блока «С этим также покупают».

        Ручная подборка (ProductRelation) — главная и всегда побеждает целиком.
        Пусто — добираем автоматически, чтобы блок работал сразу, не дожидаясь,
        пока менеджер пройдёт по всему каталогу: сначала своя категория, затем
        соседи по родительскому разделу, затем остальной каталог (популярные
        вперёд). Одной своей категории мало: разделы бывают из одного товара.

        Флаг hide_related убирает блок совсем. Неактивные товары отсеиваются
        сами — for_cards() фильтрует is_active.
        """
        if self.hide_related:
            return []

        ids = list(
            ProductRelation.objects
            .filter(product=self)
            .order_by('position', 'id')
            .values_list('related_id', flat=True)[:limit]
        )
        if ids:
            by_id = Product.objects.for_cards().in_bulk(ids)
            # Порядок — как задал менеджер; выпавшие (неактивные) пропускаем
            manual = [by_id[pk] for pk in ids if pk in by_id]
            if manual:
                return manual

        picked, seen = [], {self.pk}

        def take(qs):
            if len(picked) >= limit:
                return
            for product in qs.exclude(pk__in=seen)[:limit - len(picked)]:
                picked.append(product)
                seen.add(product.pk)

        # Тот же порядок, что и дефолтная сортировка каталога
        # (SORT_MAP['new'] в views): сначала популярные
        base = Product.objects.for_cards().order_by(
            '-is_featured', 'featured_order', '-created_at')

        if self.category_id:
            take(base.filter(category_id=self.category_id))
            parent = self.category.get_parent()
            if parent:
                sibling_ids = [c.pk for c in parent.get_descendants(include_self=True)]
                take(base.filter(category_id__in=sibling_ids))
        take(base)
        return picked


class ProductRelation(models.Model):
    """Ручная подборка «С этим также покупают»: что показывать и в каком порядке.

    Связь односторонняя: добавили B к товару A — B появится на карточке A,
    но не наоборот. Так у каждого товара своя подборка, а не общий «клубок».
    Порядок — position, правится перетаскиванием в админке.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='related_links',
        verbose_name='Товар',
    )
    related = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='related_to',
        verbose_name='Рекомендуемый товар',
    )
    position = models.PositiveIntegerField('Позиция', default=0)

    class Meta:
        verbose_name = 'Рекомендуемый товар'
        verbose_name_plural = 'С этим также покупают'
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'related'],
                name='uniq_product_relation',
                violation_error_message='Этот товар уже есть в подборке.',
            ),
        ]

    def __str__(self):
        return f'{self.product} → {self.related}'

    def clean(self):
        super().clean()
        if self.related_id and self.related_id == self.product_id:
            raise ValidationError({
                'related': 'Товар нельзя рекомендовать сам к себе.',
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProductImageQuerySet(models.QuerySet):
    GALLERY_Q = models.Q(
        material__isnull=True, finish__isnull=True,
        color__isnull=True, color_group='',
    )

    def gallery(self):
        """Обычные фото товара (листаются миниатюрами)."""
        return self.filter(self.GALLERY_Q)

    def overrides(self):
        """Фото-правила с условиями показа — подменяют галерею при выборе."""
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
    """Фото товара — запись-правило. Роль определяется заполненными полями:

    - материал/обработка/цвет/группа пустые — обычное фото галереи
      (порядок — sort_order);
    - заполнены — условия показа при выборе на карточке. Марка стали в условия
      не входит намеренно: 304-золото и 430-золото выглядят одинаково.

    Фото с одинаковыми условиями — ракурсы одного исполнения (порядок —
    sort_order): на карточке они листаются миниатюрами, а при смене
    исполнения открывается ракурс с тем же номером.

    Подбор на клиенте: отсеять наборы, где хоть одно заполненное условие
    противоречит выбору → из оставшихся взять с максимумом совпавших условий →
    тай-брейк: цвет > обработка > материал → иначе галерея.
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
    # PROTECT намеренно: удаление записи справочника не должно молча уносить
    # с собой фото товаров
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name='Материал',
        help_text='Фото для этого материала (пусто — для любого)',
    )
    finish = models.ForeignKey(
        Finish, on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name='Обработка',
        help_text='Фото для этой обработки',
    )
    color = models.ForeignKey(
        Color, on_delete=models.PROTECT,
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

    def __str__(self):
        target = ', '.join(
            str(p) for p in (
                self.material, self.finish,
                self.color or self.get_color_group_display(),
            )
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


class ProductOptionNode(models.Model):
    """Узел дерева опций товара: материал → марка → обработка.

    Дерево задаёт разрешённые сочетания — это единственное место, где
    блокируются невозможные комбинации (у «Латуни» без дочерних марок нельзя
    выбрать «304»). Узлы ссылаются на глобальные справочники, а не хранят
    текст: фильтры каталога и условия фото работают по общим FK.

    Цвета отмечаются на узле-обработке: «Полировка» под 304 и «Полировка»
    под 430 — разные узлы, у каждого свой набор цветов из общего справочника.
    Записей-комбинаций (SKU) в базе нет.
    """
    NODE_TYPE_CHOICES = [
        ('material',    'Материал'),
        ('steel_grade', 'Марка'),
        ('finish',      'Обработка'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='option_nodes',
        verbose_name='Товар',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='children',
        verbose_name='Родитель',
    )
    node_type = models.CharField('Тип узла', max_length=20, choices=NODE_TYPE_CHOICES)
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='option_nodes',
        verbose_name='Материал',
    )
    steel_grade = models.ForeignKey(
        SteelGrade, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='option_nodes',
        verbose_name='Марка стали',
    )
    finish = models.ForeignKey(
        Finish, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='option_nodes',
        verbose_name='Обработка',
    )
    colors = models.ManyToManyField(
        Color, blank=True,
        related_name='option_nodes',
        verbose_name='Доступные цвета',
        help_text='Ручной набор цветов (используется, если палитра не выбрана). '
                  'Имеет смысл только на узле-обработке',
    )
    palette = models.ForeignKey(
        'references.ColorPalette', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='option_nodes',
        verbose_name='Палитра цветов',
        help_text='Задана — цвета берутся из палитры живьём: правка палитры '
                  'меняет все товары с ней. Пусто — берётся ручной набор ниже. '
                  'Имеет смысл только на узле-обработке.',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Узел опций товара'
        verbose_name_plural = 'Дерево опций товара'
        ordering = ['sort_order', 'id']
        constraints = [
            # Один и тот же справочный элемент не дублируется под одним родителем
            models.UniqueConstraint(
                fields=['product', 'parent', 'node_type',
                        'material', 'steel_grade', 'finish'],
                nulls_distinct=False,
                name='uniq_product_option_node',
                violation_error_message='Такой узел у товара уже есть.',
            ),
        ]

    def __str__(self):
        return f'{self.product} / {self.get_node_type_display()}: {self.ref}'

    @property
    def ref(self):
        """Справочный объект узла."""
        return self.material or self.steel_grade or self.finish

    def effective_colors(self):
        """Активные цвета обработки: живьём из палитры, иначе — ручной набор.

        Живая связь (без глобальных правил и цепочек разрешения): что выбрано
        на самом узле, то и действует. Отключил цвет в палитре — он пропал у
        всех обработок, ссылающихся на неё. Палитра выключена целиком →
        падаем на ручной набор (обычно пустой)."""
        if self.palette_id and self.palette and self.palette.is_active:
            return [c for c in self.palette.colors.all() if c.is_active]
        return [c for c in self.colors.all() if c.is_active]

    def clean(self):
        refs = {
            'material':    self.material_id,
            'steel_grade': self.steel_grade_id,
            'finish':      self.finish_id,
        }
        expected = refs.pop(self.node_type, None)
        if not expected or any(refs.values()):
            raise ValidationError(
                'У узла должен быть заполнен ровно один справочник, '
                'соответствующий типу узла.'
            )

        # Форма дерева: материал — корень; марка — под материалом своего
        # материала; обработка — под материалом или маркой
        if self.node_type == 'material':
            if self.parent_id:
                raise ValidationError({'parent': 'Материал — корневой узел, без родителя.'})
        elif self.node_type == 'steel_grade':
            if not self.parent_id or self.parent.node_type != 'material':
                raise ValidationError({'parent': 'Марка должна висеть под материалом.'})
            if self.steel_grade.material_id != self.parent.material_id:
                raise ValidationError({
                    'steel_grade': 'Марка принадлежит другому материалу — '
                                   f'ожидается «{self.steel_grade.material}».',
                })
        elif self.node_type == 'finish':
            if not self.parent_id or self.parent.node_type not in ('material', 'steel_grade'):
                raise ValidationError({'parent': 'Обработка должна висеть под материалом или маркой.'})
        if self.parent_id and self.parent.product_id != self.product_id:
            raise ValidationError({'parent': 'Родительский узел принадлежит другому товару.'})
        if self.palette_id and self.node_type != 'finish':
            raise ValidationError({'palette': 'Палитра задаётся только на узле-обработке.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProductParameter(models.Model):
    """Параметр справочника, подключённый к товару, со своим списком значений.

    Значения — плоский независимый список (ProductParamValue): невозможных
    сочетаний не создают и от дерева опций не зависят. allow_custom включает
    на карточке поле для своего значения покупателя — оно уйдёт в заявку.
    """
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='parameters',
        verbose_name='Товар',
    )
    # PROTECT: параметр, который есть у товаров, удалить нельзя — только
    # выключить; иначе молча пропали бы значения у всего каталога
    parameter = models.ForeignKey(
        Parameter, on_delete=models.PROTECT,
        related_name='product_links',
        verbose_name='Параметр',
    )
    allow_custom = models.BooleanField(
        'Своё значение', default=False,
        help_text='Покупатель может указать своё значение — его проверит менеджер',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Параметр товара'
        verbose_name_plural = 'Параметры товара'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'parameter'],
                name='uniq_product_parameter',
                violation_error_message='Этот параметр у товара уже есть.',
            ),
        ]

    def __str__(self):
        return f'{self.product} / {self.parameter.name}'


class ProductParamValue(models.Model):
    """Значение параметра товара: «3» у длины, «20×20» у размера.

    Хранится без единицы — её подставляет справочник (Parameter.unit).
    """
    product_parameter = models.ForeignKey(
        ProductParameter, on_delete=models.CASCADE,
        related_name='values',
        verbose_name='Параметр товара',
    )
    value = models.CharField('Значение', max_length=50)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Значение параметра'
        verbose_name_plural = 'Значения параметра'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product_parameter', 'value'],
                name='uniq_product_param_value',
                violation_error_message='Такое значение у этого параметра уже есть.',
            ),
        ]

    def __str__(self):
        return f'{self.product_parameter}: {self.value}'
