from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Material, SteelGrade, Finish, Color, MaterialColor, SteelGradeColor
from .widgets import GroupedColorCheckboxWidget


def _colors_field(help_text):
    return forms.ModelMultipleChoiceField(
        queryset=Color.objects.filter(is_active=True).order_by('color_group', 'name'),
        required=False,
        label='Доступные цвета',
        help_text=help_text,
        widget=GroupedColorCheckboxWidget(),
    )


def _sync_colors(link_model, owner_field, owner, selected_colors):
    """Приводит привязки цветов (MaterialColor/SteelGradeColor) к выбору формы."""
    selected = set(c.pk for c in selected_colors)
    existing = set(
        link_model.objects.filter(**{owner_field: owner}).values_list('color_id', flat=True)
    )
    for pk in selected - existing:
        link_model.objects.create(**{owner_field: owner, 'color_id': pk})
    for pk in existing - selected:
        link_model.objects.filter(**{owner_field: owner, 'color_id': pk}).delete()


# ─── Materials ────────────────────────────────────────────────────────────────

class MaterialAdminForm(forms.ModelForm):
    colors = _colors_field(
        'Палитра материала — фолбэк: используется для вариантов без марки '
        '(например, алюминий) и для марок, у которых не отмечен ни один цвет. '
        'Палитра, заданная у марки, имеет приоритет.'
    )

    class Meta:
        model = Material
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['colors'].initial = list(
                self.instance.material_colors.values_list('color_id', flat=True)
            )


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    form = MaterialAdminForm
    list_display = ['name', 'slug', 'landing_title', 'color_count', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def color_count(self, obj):
        return obj.material_colors.count()
    color_count.short_description = 'Цветов'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_colors(MaterialColor, 'material', obj, form.cleaned_data.get('colors', []))


# ─── Steel grades ─────────────────────────────────────────────────────────────

class SteelGradeAdminForm(forms.ModelForm):
    colors = _colors_field(
        'Отметьте цвета, доступные для товаров из этой марки. '
        'Если ни один не отмечен — используется палитра материала. '
        'На карточке товара палитра показывается при выбранной обработке.'
    )

    class Meta:
        model = SteelGrade
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['colors'].initial = list(
                self.instance.grade_colors.values_list('color_id', flat=True)
            )


@admin.register(SteelGrade)
class SteelGradeAdmin(ModelAdmin):
    form = SteelGradeAdminForm
    list_display = ['name', 'material', 'color_count', 'is_active']
    list_editable = ['is_active']
    list_filter = ['material']
    search_fields = ['name']
    autocomplete_fields = ['material']

    def color_count(self, obj):
        return obj.grade_colors.count()
    color_count.short_description = 'Цветов'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        _sync_colors(SteelGradeColor, 'steel_grade', obj, form.cleaned_data.get('colors', []))


# ─── Finish ───────────────────────────────────────────────────────────────────

@admin.register(Finish)
class FinishAdmin(ModelAdmin):
    list_display  = ['name', 'slug', 'color_ui', 'is_active']
    list_editable = ['color_ui', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


# ─── Color ────────────────────────────────────────────────────────────────────

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
