from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.pages.models import News, Page


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return ['home', 'products', 'catalog:index', 'pages:news_list']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Category.objects.filter(is_active=True)

    def location(self, obj):
        return reverse('catalog:detail', kwargs={'slug': obj.slug})


class PageSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return Page.objects.all()


class NewsSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return News.objects.filter(published_at__lte=timezone.now())

    def lastmod(self, obj):
        return obj.published_at


SITEMAPS = {
    'static': StaticSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
    'pages': PageSitemap,
    'news': NewsSitemap,
}
