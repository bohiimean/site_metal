from django.contrib import admin
from adminsortable2.admin import SortableAdminMixin, SortableInlineAdminMixin
from .models import HomeBlock, HomeBlockItem


class HomeBlockItemInline(SortableInlineAdminMixin, admin.TabularInline):
    model = HomeBlockItem
    extra = 0
    fields = ['product', 'position']
    autocomplete_fields = ['product']
    verbose_name = 'Товар'
    verbose_name_plural = 'Товары в блоке (только для ручной подборки)'


@admin.register(HomeBlock)
class HomeBlockAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ['title', 'type', 'category', 'limit', 'is_active', 'sort_order']
    list_editable = ['is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['title']
    autocomplete_fields = ['category']
    inlines = [HomeBlockItemInline]
    fieldsets = [
        (None, {'fields': ['title', 'type', 'category', 'is_active']}),
        ('Параметры', {'fields': ['limit', 'link_text', 'link_url', 'sort_order']}),
    ]
