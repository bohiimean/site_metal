from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from .models import Page, News, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    """Синглтон-настройки: без списка/добавления/удаления —
    сразу редактирование единственной записи."""

    fieldsets = [
        ('Промо-баннер 1 (тёмный)', {'fields': [
            'banner1_enabled', 'banner1_title', 'banner1_subtitle',
            'banner1_button_text', 'banner1_button_url',
        ]}),
        ('Промо-баннер 2 (акцентный)', {'fields': [
            'banner2_enabled', 'banner2_title', 'banner2_subtitle',
            'banner2_button_text', 'banner2_button_url',
        ]}),
        ('Футер', {'fields': ['footer_copyright', 'footer_legal']}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return redirect(reverse('admin:pages_sitesettings_change', args=[obj.pk]))


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
