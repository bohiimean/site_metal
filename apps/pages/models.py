from django.db import models


class SiteSettings(models.Model):
    """Одиночная запись с настройками сайта, редактируемыми менеджером.

    Синглтон: всегда pk=1. В шаблоны попадает через context processor
    `apps.pages.context_processors.site_settings` как переменная `site`.
    """

    # ─── Промо-баннер 1 (тёмный, «Режем металл…») ───
    banner1_enabled = models.BooleanField('Баннер 1: показывать', default=True)
    banner1_title = models.CharField(
        'Баннер 1: заголовок', max_length=200, blank=True,
        default='Режем металл точно под ваш чертёж',
    )
    banner1_subtitle = models.CharField(
        'Баннер 1: подзаголовок', max_length=300, blank=True,
        default='Резка в размер — от листа до готовой заготовки за 1 рабочий день',
    )
    banner1_button_text = models.CharField(
        'Баннер 1: текст кнопки', max_length=60, blank=True, default='Узнать больше',
    )
    banner1_button_url = models.CharField(
        'Баннер 1: ссылка кнопки', max_length=300, blank=True, default='/produkciya/',
        help_text='Если пусто — кнопка откроет форму обратного звонка.',
    )

    # ─── Промо-баннер 2 (акцентный, «Оптовые закупки…») ───
    banner2_enabled = models.BooleanField('Баннер 2: показывать', default=True)
    banner2_title = models.CharField(
        'Баннер 2: заголовок', max_length=200, blank=True,
        default='Оптовые закупки от 50 000 ₽',
    )
    banner2_subtitle = models.CharField(
        'Баннер 2: подзаголовок', max_length=300, blank=True,
        default='Индивидуальные цены и отсрочка платежа для постоянных клиентов',
    )
    banner2_button_text = models.CharField(
        'Баннер 2: текст кнопки', max_length=60, blank=True, default='Оставить заявку',
    )
    banner2_button_url = models.CharField(
        'Баннер 2: ссылка кнопки', max_length=300, blank=True, default='',
        help_text='Если пусто — кнопка откроет форму обратного звонка.',
    )

    # ─── Футер ───
    footer_copyright = models.CharField(
        'Футер: копирайт', max_length=200, blank=True,
        default='Арвенокс. Все права защищены.',
        help_text='Год подставляется автоматически перед этим текстом.',
    )
    footer_legal = models.CharField(
        'Футер: юр. строка', max_length=200, blank=True,
        default='ИНН 7700000000 · г. Москва',
    )

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # синглтон удалять нельзя

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Page(models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField('Slug', max_length=300, unique=True)
    content = models.TextField('Содержимое')
    seo_title = models.CharField('SEO Title', max_length=200, blank=True)
    seo_description = models.TextField('SEO Description', blank=True)

    class Meta:
        verbose_name = 'Страница'
        verbose_name_plural = 'Страницы'
        ordering = ['title']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('pages:page_detail', kwargs={'slug': self.slug})


class News(models.Model):
    title = models.CharField('Заголовок', max_length=300)
    slug = models.SlugField('Slug', max_length=300, unique=True)
    content = models.TextField('Содержимое')
    published_at = models.DateTimeField('Дата публикации')
    seo_title = models.CharField('SEO Title', max_length=200, blank=True)
    seo_description = models.TextField('SEO Description', blank=True)

    class Meta:
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('pages:news_detail', kwargs={'slug': self.slug})
