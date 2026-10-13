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

    # ─── Тексты витрины ───
    # Цен на сайте нет — их называет менеджер, поэтому вместо цены везде
    # стоит подпись. Держим её здесь, чтобы менеджер менял формулировку
    # («Цена по запросу» → «Стоимость рассчитает менеджер») без правки кода.
    price_label = models.CharField(
        'Цена: подпись', max_length=100, blank=True,
        default='Цена по запросу',
        help_text='Вместо цены в каталоге, на карточке товара и в корзине.',
    )
    price_label_short = models.CharField(
        'Цена: короткая подпись', max_length=40, blank=True,
        default='По запросу',
        help_text='То же для узких экранов — в сетке каталога на телефоне '
                  'длинная подпись не помещается рядом с кнопкой.',
    )
    price_note = models.CharField(
        'Цена: пояснение', max_length=200, blank=True,
        default='Точную стоимость рассчитает менеджер после отправки заявки',
        help_text='Строка под подписью на карточке товара. Пусто — не показывается.',
    )
    card_button_text = models.CharField(
        'Кнопка на карточке в каталоге', max_length=40, blank=True,
        default='Изготовить',
        help_text='Открывает страницу товара, где покупатель выберет '
                  'материал, обработку и размер.',
    )

    # ─── Футер ───
    footer_copyright = models.CharField(
        'Футер: копирайт', max_length=200, blank=True,
        default='Арвенокс. Все права защищены.',
        help_text='Год подставляется автоматически перед этим текстом.',
    )
    footer_legal = models.TextField(
        'Футер: юр. строка', max_length=300, blank=True,
        default='ИНН 7700000000 · г. Москва',
        help_text='Каждая строка выводится в футере с новой строки '
                  '(Enter = перенос).',
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


# Страницы, на согласие с которыми ставят галочку в формах заявок
PRIVACY_SLUG = 'politika-konfidentsialnosti'
TERMS_SLUG = 'usloviya-prodazhi'


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Новая редакция — только когда поменялся текст: правка заголовка
        # или SEO не меняет того, с чем соглашается клиент
        last = self.revisions.first()
        if last is None or last.content != self.content:
            PageRevision.objects.create(page=self, title=self.title, content=self.content)

    @classmethod
    def current_revision_of(cls, slug):
        """Текущая редакция страницы по slug или None, если страницы нет."""
        return (PageRevision.objects.filter(page__slug=slug)
                .order_by('-created_at', '-pk').first())


class PageRevision(models.Model):
    """Снимок текста страницы. Заявка ссылается на редакцию, действовавшую
    в момент отправки, — видно, какой именно текст условий или политики
    принял клиент, даже если страницу потом переписали."""
    # CASCADE: страницу без заявок можно удалить вместе с историей; если на
    # редакцию сослалась заявка, удаление остановит PROTECT в Lead
    page = models.ForeignKey(
        Page, on_delete=models.CASCADE, related_name='revisions',
        verbose_name='Страница',
    )
    title = models.CharField('Заголовок', max_length=300)
    content = models.TextField('Содержимое')
    created_at = models.DateTimeField('Действует с', auto_now_add=True)

    class Meta:
        verbose_name = 'Редакция страницы'
        verbose_name_plural = 'Редакции страниц'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        from django.utils import timezone
        return f'{self.title} — редакция от {timezone.localtime(self.created_at):%d.%m.%Y %H:%M}'


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
