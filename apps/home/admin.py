from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import HomeBlock, HomeBlockItem


class HomeBlockItemInline(TabularInline):
    model = HomeBlockItem
    extra = 0
    fields = ['product', 'position']
    autocomplete_fields = ['product']
    verbose_name = 'Товар'
    verbose_name_plural = 'Товары в блоке (только для ручной подборки)'
    ordering_field = 'position'


@admin.register(HomeBlock)
class HomeBlockAdmin(ModelAdmin):
    list_display = ['title', 'type', 'category', 'limit', 'is_active', 'sort_order']
    list_editable = ['is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['title']
    autocomplete_fields = ['category']
    inlines = [HomeBlockItemInline]
    ordering_field = 'sort_order'
    fieldsets = [
        (None, {'fields': ['title', 'type', 'category', 'is_active']}),
        ('Параметры', {'fields': ['limit', 'link_text', 'link_url', 'sort_order']}),
    ]
