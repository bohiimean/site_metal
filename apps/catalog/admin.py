from django.contrib import admin
from django.http import JsonResponse
from django.utils.html import format_html
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from apps.references.models import SteelGrade, Color
from .models import Category, Product, ProductImage, ProductVariant


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    form = movenodeform_factory(Category)
    list_display = ['name', 'slug', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']


class ProductImageInline(SortableInlineAdminMixin, admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ['image', 'sort_order', 'thumb_preview']
    readonly_fields = ['thumb_preview']

    def thumb_preview(self, obj):
        if obj.pk and obj.image:
            try:
                return format_html('<img src="{}" style="height:60px;">', obj.thumb.url)
            except Exception:
                pass
        return '—'
    thumb_preview.short_description = 'Превью'


class ProductVariantInline(admin.StackedInline):
    model = ProductVariant
    extra = 0
    fields = [
        ('sku', 'is_active'),
        ('material', 'steel_grade'),
        ('finish', 'color'),
        'image',
        ('height_mm', 'length_m'),
        ('price', 'unit'),
        'in_stock',
    ]
    autocomplete_fields = ['material', 'steel_grade', 'finish', 'color']

    class Media:
        js = ('admin/js/variant_dependent_selects.js',)


@admin.register(Product)
class ProductAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'is_new', 'created_at']
    list_editable = ['is_active', 'is_new']
    list_filter = ['is_active', 'is_new', 'category']
    search_fields = ['name', 'slug', 'profile_code']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline, ProductVariantInline]
    fieldsets = [
        (None, {'fields': ['name', 'slug', 'category', 'profile_code', 'is_new', 'is_active']}),
        ('Описание', {'fields': ['description']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        return [
            path('api/steel-grades/', self.admin_site.admin_view(self._api_steel_grades)),
            path('api/colors/',       self.admin_site.admin_view(self._api_colors)),
        ] + urls

    def _api_steel_grades(self, request):
        material_id = request.GET.get('material')
        qs = SteelGrade.objects.filter(is_active=True).order_by('name')
        if material_id:
            qs = qs.filter(material_id=material_id)
        return JsonResponse([{'id': g.id, 'name': g.name} for g in qs], safe=False)

    def _api_colors(self, request):
        finish_id = request.GET.get('finish')
        if not finish_id:
            return JsonResponse([], safe=False)
        qs = (
            Color.objects
            .filter(finish_colors__finish_id=finish_id, is_active=True)
            .distinct()
            .order_by('name')
        )
        return JsonResponse(
            [{'id': c.id, 'name': c.name, 'hex': c.hex_code} for c in qs],
            safe=False,
        )
