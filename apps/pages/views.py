from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import News, Page


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug)
    return render(request, 'pages/page_detail.html', {'page': page})


def news_list(request):
    news = News.objects.filter(published_at__lte=timezone.now())
    return render(request, 'pages/news_list.html', {'news_list': news})


def news_detail(request, slug):
    news = get_object_or_404(News, slug=slug, published_at__lte=timezone.now())
    return render(request, 'pages/news_detail.html', {'news': news})
