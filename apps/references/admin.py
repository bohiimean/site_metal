from django.contrib import admin
from .models import Material, SteelGrade, Finish, Color, FinishColor


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(SteelGrade)
class SteelGradeAdmin(admin.ModelAdmin):
    list_display = ['name', 'material', 'is_active']
    list_editable = ['is_active']
    list_filter = ['material']
    search_fields = ['name']
    autocomplete_fields = ['material']


class FinishColorInline(admin.TabularInline):
    model = FinishColor
    extra = 1
    autocomplete_fields = ['color']
    verbose_name = 'Цвет'
    verbose_name_plural = 'Доступные цвета'


@admin.register(Finish)
class FinishAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    inlines = [FinishColorInline]


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['name', 'hex_code', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']
