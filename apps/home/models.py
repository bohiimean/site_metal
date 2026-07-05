from django.db import models
from django.core.exceptions import ValidationError


class HomeBlock(models.Model):
    TYPE_MANUAL      = 'manual'
    TYPE_BY_CATEGORY = 'by_category'
    TYPE_CHOICES = [
        (TYPE_MANUAL,      'Ручная подборка'),
        (TYPE_BY_CATEGORY, 'Срез по категории'),
    ]

    title = models.CharField('Заголовок блока', max_length=200)
    type = models.CharField(
        'Тип блока', max_length=20,
        choices=TYPE_CHOICES, default=TYPE_MANUAL,
    )
    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Категория',
        help_text='Обязательно при типе «Срез по категории»',
    )
    link_text = models.CharField(
        'Текст ссылки', max_length=100, blank=True,
        help_text='Например: «Весь каталог →»',
    )
    link_url = models.CharField('URL ссылки', max_length=300, blank=True)
    limit = models.PositiveSmallIntegerField(
        'Кол-во карточек', default=4,
        help_text='Сколько товаров показывать в блоке',
    )
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Блок главной'
        verbose_name_plural = 'Блоки главной'
        ordering = ['sort_order']

    def __str__(self):
        return self.title

    def clean(self):
        if self.type == self.TYPE_BY_CATEGORY and not self.category_id:
            raise ValidationError({
                'category': 'Для блока «Срез по категории» необходимо выбрать категорию.',
            })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_products(self):
        """Возвращает товары блока согласно типу."""
        from apps.catalog.models import Product
        if self.type == self.TYPE_MANUAL:
            return (
                Product.objects
                .filter(home_block_items__block=self, is_active=True)
                .order_by('home_block_items__position')
                .select_related('category')
                .prefetch_related('images', 'variants')
            )[:self.limit]
        else:
            return (
                Product.objects
                .filter(category=self.category, is_active=True)
                .select_related('category')
                .prefetch_related('images', 'variants')
            )[:self.limit]


class HomeBlockItem(models.Model):
    block = models.ForeignKey(
        HomeBlock, on_delete=models.CASCADE,
        related_name='home_block_items',
        verbose_name='Блок',
    )
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE,
        related_name='home_block_items',
        verbose_name='Товар',
    )
    position = models.PositiveIntegerField('Позиция', default=0)

    class Meta:
        verbose_name = 'Товар в блоке'
        verbose_name_plural = 'Товары в блоке'
        ordering = ['position']
        unique_together = [('block', 'product')]

    def __str__(self):
        return f'{self.block} → {self.product}'
