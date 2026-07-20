from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Material, SteelGrade, Finish, Color, ColorPalette


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ['name', 'slug', 'landing_title', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(SteelGrade)
class SteelGradeAdmin(ModelAdmin):
    list_display = ['name', 'material', 'is_active']
    list_editable = ['is_active']
    list_filter = ['material']
    search_fields = ['name']
    autocomplete_fields = ['material']


@admin.register(Finish)
class FinishAdmin(ModelAdmin):
    list_display  = ['name', 'slug', 'color_ui', 'is_active']
    list_editable = ['color_ui', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Color)
class ColorAdmin(ModelAdmin):
    list_display  = ['color_swatch', 'name', 'hex_code', 'ral_code', 'color_group', 'is_active']
    list_editable = ['color_group', 'is_active']
    list_filter   = ['color_group']
    search_fields = ['name', 'ral_code']

    def color_swatch(self, obj):
        if obj.hex_code:
            from django.utils.html import format_html
            return format_html(
                '<span style="display:inline-block;width:16px;height:16px;'
                'border-radius:50%;background:{};border:1px solid rgba(0,0,0,.15);'
                'vertical-align:middle;"></span>',
                obj.hex_code,
            )
        return '—'
    color_swatch.short_description = ''


@admin.register(ColorPalette)
class ColorPaletteAdmin(ModelAdmin):
    list_display  = ['name', 'color_count', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']
    filter_horizontal = ['colors']

    def color_count(self, obj):
        return obj.colors.count()
    color_count.short_description = 'Цветов'
