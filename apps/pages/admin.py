from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Page, News


@admin.register(Page)
class PageAdmin(ModelAdmin):
    list_display = ['title', 'slug']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        (None, {'fields': ['title', 'slug', 'content']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]


@admin.register(News)
class NewsAdmin(ModelAdmin):
    list_display = ['title', 'published_at']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    fieldsets = [
        (None, {'fields': ['title', 'slug', 'published_at', 'content']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]
