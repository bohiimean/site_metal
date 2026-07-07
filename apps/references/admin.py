from django import forms
from django.contrib import admin

from .models import Material, SteelGrade, Finish, Color, FinishColor
from .widgets import GroupedColorCheckboxWidget


# ─── Materials ────────────────────────────────────────────────────────────────

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


# ─── Steel grades ─────────────────────────────────────────────────────────────

@admin.register(SteelGrade)
class SteelGradeAdmin(admin.ModelAdmin):
    list_display = ['name', 'material', 'is_active']
    list_editable = ['is_active']
    list_filter = ['material']
    search_fields = ['name']
    autocomplete_fields = ['material']


# ─── Finish ───────────────────────────────────────────────────────────────────

class FinishAdminForm(forms.ModelForm):
    colors = forms.ModelMultipleChoiceField(
        queryset=Color.objects.filter(is_active=True).order_by('color_group', 'name'),
        required=False,
        label='Доступные цвета',
        help_text='Отметьте цвета, доступные для этой обработки.',
        widget=GroupedColorCheckboxWidget(),
    )

    class Meta:
        model = Finish
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['colors'].initial = list(
                self.instance.finish_colors.values_list('color_id', flat=True)
            )


@admin.register(Finish)
class FinishAdmin(admin.ModelAdmin):
    form = FinishAdminForm
    list_display  = ['name', 'slug', 'color_ui', 'color_count', 'is_active']
    list_editable = ['color_ui', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def color_count(self, obj):
        return obj.finish_colors.count()
    color_count.short_description = 'Цветов'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        selected = set(c.pk for c in form.cleaned_data.get('colors', []))
        existing = set(obj.finish_colors.values_list('color_id', flat=True))

        for pk in selected - existing:
            FinishColor.objects.create(finish=obj, color_id=pk)
        for pk in existing - selected:
            FinishColor.objects.filter(finish=obj, color_id=pk).delete()


# ─── Color ────────────────────────────────────────────────────────────────────

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
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
