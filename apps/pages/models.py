from django.db import models


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
