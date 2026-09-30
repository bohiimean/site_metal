from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline
from .models import Page, PageRevision, News, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    """Синглтон-настройки: без списка/добавления/удаления —
    сразу редактирование единственной записи."""

    fieldsets = [
        ('Тексты витрины', {'fields': [
            'price_label', 'price_label_short', 'price_note', 'card_button_text',
        ]}),
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


class PageRevisionInline(TabularInline):
    """История редакций: создаётся сама при изменении текста, правке не подлежит."""
    model = PageRevision
    fields = ['revision_link']
    readonly_fields = ['revision_link']
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name_plural = 'Редакции текста'

    def revision_link(self, obj):
        url = reverse('admin:pages_pagerevision_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj)
    revision_link.short_description = 'Редакция'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(ModelAdmin):
    list_display = ['title', 'slug']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        (None, {'fields': ['title', 'slug', 'content']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]
    inlines = [PageRevisionInline]


@admin.register(PageRevision)
class PageRevisionAdmin(ModelAdmin):
    """Только просмотр: редакция — доказательство того, какой текст принял
    клиент, поэтому её нельзя ни изменить, ни удалить."""
    list_display = ['__str__', 'page', 'created_at']
    list_filter = ['page']
    fields = ['page', 'title', 'created_at', 'content_display']
    readonly_fields = fields

    def content_display(self, obj):
        # Текст страницы — HTML из админки, на витрине выводится так же (|safe)
        return format_html('<div class="page-content">{}</div>', mark_safe(obj.content))
    content_display.short_description = 'Текст'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
