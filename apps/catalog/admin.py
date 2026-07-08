import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from apps.references.models import SteelGrade, Material, Finish
from .models import Category, Product, ProductImage, ProductColorImage, ProductVariant


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


class ProductColorImageInline(admin.TabularInline):
    model = ProductColorImage
    extra = 0
    fields = ['color', 'color_group', 'image', 'thumb_preview']
    readonly_fields = ['thumb_preview']
    autocomplete_fields = ['color']
    verbose_name_plural = 'Фото по цветам (точный цвет ИЛИ группа; fallback: цвет → группа → фото товара)'

    def thumb_preview(self, obj):
        if obj.pk and obj.image:
            try:
                return format_html('<img src="{}" style="height:60px;">', obj.thumb.url)
            except Exception:
                pass
        return '—'
    thumb_preview.short_description = 'Превью'


@admin.register(Product)
class ProductAdmin(SortableAdminBase, admin.ModelAdmin):
    change_form_template = 'admin/catalog/product/change_form.html'

    list_display = ['name', 'category', 'is_active', 'is_new', 'created_at']
    list_editable = ['is_active', 'is_new']
    list_filter = ['is_active', 'is_new', 'category']
    search_fields = ['name', 'slug', 'profile_code']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline, ProductColorImageInline]
    fieldsets = [
        (None, {'fields': ['name', 'slug', 'category', 'profile_code', 'is_new', 'is_active']}),
        ('Описание', {'fields': ['description']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]

    # ── Change view: inject generator context ─────────────────────────────────

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'gen_materials':    Material.objects.filter(is_active=True).order_by('name'),
            'gen_finishes':     Finish.objects.filter(is_active=True).order_by('name'),
            'gen_unit_choices': ProductVariant.UNIT_CHOICES,
            'gen_stock_choices': ProductVariant.STOCK_CHOICES,
            'variants_count':   ProductVariant.objects.filter(product_id=object_id).count(),
        })
        return super().change_view(request, object_id, form_url, extra_context)

    # ── URLs ──────────────────────────────────────────────────────────────────

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        return [
            path('api/steel-grades/', self.admin_site.admin_view(self._api_steel_grades),
                 name='catalog_product_api_steel_grades'),
            path('<int:product_id>/generate-variants/',
                 self.admin_site.admin_view(self._generate_variants_view),
                 name='catalog_product_generate_variants'),
        ] + urls

    # ── API endpoints ─────────────────────────────────────────────────────────

    def _api_steel_grades(self, request):
        material_id = request.GET.get('material')
        qs = SteelGrade.objects.filter(is_active=True).order_by('name')
        if material_id:
            qs = qs.filter(material_id=material_id)
        return JsonResponse([{'id': g.id, 'name': g.name} for g in qs], safe=False)

    # ── Generator view (POST-only; UI встроен в change_form товара) ──────────

    def _generate_variants_view(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)

        if request.method != 'POST':
            return HttpResponseRedirect(
                reverse('admin:catalog_product_change', args=[product.pk])
            )

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Неверный формат данных'}, status=400)
        return JsonResponse(self._process_generator(product, data))

    def _process_generator(self, product, data):
        rows = data.get('rows', [])
        created, skipped, errors, created_list = 0, 0, [], []
        used_skus = set()

        for i, row in enumerate(rows):
            label = f'Строка {i + 1}'

            # Material (required)
            try:
                material = Material.objects.get(pk=int(row['material_id']))
            except (KeyError, ValueError, Material.DoesNotExist):
                errors.append(f'{label}: не выбран материал')
                continue

            # Steel grade (optional)
            steel_grade = None
            try:
                if row.get('steel_grade_id'):
                    steel_grade = SteelGrade.objects.get(pk=int(row['steel_grade_id']))
            except (ValueError, SteelGrade.DoesNotExist):
                pass

            # Finish (optional)
            finish = None
            try:
                if row.get('finish_id'):
                    finish = Finish.objects.get(pk=int(row['finish_id']))
            except (ValueError, Finish.DoesNotExist):
                pass

            unit     = row.get('unit', 'm')
            in_stock = row.get('in_stock', 'in_stock')
            sku_prefix = (row.get('sku_prefix') or '').strip().upper()

            height_mm = None
            if row.get('height_mm'):
                try:
                    height_mm = Decimal(str(row['height_mm']))
                except (ValueError, InvalidOperation):
                    pass

            # Lengths
            raw_lengths = row.get('lengths') or []
            lengths = []
            for lv in raw_lengths:
                try:
                    lengths.append(Decimal(str(lv)))
                except (ValueError, InvalidOperation):
                    pass
            if not lengths:
                lengths = [None]

            # Generate
            for length_m in lengths:
                sku = self._build_sku(
                    product, material, finish, length_m,
                    sku_prefix, used_skus,
                )
                used_skus.add(sku)

                if ProductVariant.objects.filter(sku=sku).exists():
                    skipped += 1
                    continue

                # Комбинация уже существует под другим SKU — не дублируем
                if ProductVariant.objects.filter(
                    product=product,
                    material=material,
                    steel_grade=steel_grade,
                    finish=finish,
                    length_m=length_m,
                    height_mm=height_mm,
                ).exists():
                    skipped += 1
                    continue

                try:
                    v = ProductVariant(
                        product=product,
                        sku=sku,
                        material=material,
                        steel_grade=steel_grade,
                        finish=finish,
                        unit=unit,
                        in_stock=in_stock,
                        length_m=length_m,
                        height_mm=height_mm,
                    )
                    v.full_clean()
                    v.save()
                    created += 1
                    length_label = f'{length_m} м' if length_m else '—'
                    created_list.append(f'{sku} ({length_label})')
                except Exception as e:
                    errors.append(f'{label} [{sku}]: {e}')
                    skipped += 1

        return {
            'created': created,
            'skipped': skipped,
            'errors': errors,
            'created_list': created_list,
        }

    def _build_sku(self, product, material, finish, length_m, prefix, used_skus):
        if prefix:
            parts = [prefix]
        else:
            parts = [product.slug[:10].upper()]
            parts.append(material.slug[:5].upper() if material.slug else f'M{material.pk}')
            if finish:
                parts.append(finish.slug[:5].upper() if finish.slug else f'F{finish.pk}')

        if length_m:
            l = str(length_m).rstrip('0').rstrip('.')
            parts.append(f'{l}M')

        base = '-'.join(parts)[:90]
        sku = base
        counter = 2
        while sku in used_skus or ProductVariant.objects.filter(sku=sku).exists():
            sku = f'{base}-{counter}'
            counter += 1
        return sku


# ─── Фильтр по товару для списка вариантов ───────────────────────────────────

class ProductListFilter(admin.SimpleListFilter):
    """Принимает ?product__id=X из ссылки на странице товара.
    Показывает фильтр в сайдбаре только когда он активен."""
    title = 'Товар'
    parameter_name = 'product__id'

    def lookups(self, request, model_admin):
        pk = request.GET.get(self.parameter_name)
        if pk:
            try:
                p = Product.objects.get(pk=pk)
                return [(pk, p.name)]
            except Product.DoesNotExist:
                pass
        return []

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(product_id=self.value())
        return queryset


# ─── ProductVariant standalone admin ─────────────────────────────────────────

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        'sku', 'product_link', 'material', 'steel_grade',
        'finish', 'length_m', 'unit', 'in_stock', 'is_active',
    ]
    list_display_links = ['sku']
    list_editable = ['in_stock', 'is_active']
    list_filter = [ProductListFilter, 'material', 'finish', 'in_stock', 'is_active']
    search_fields = ['sku', 'product__name']
    list_per_page = 50
    list_max_show_all = 200
    list_select_related = ['product', 'material', 'steel_grade', 'finish']
    raw_id_fields = ['product']
    # autocomplete_fields (Select2) не совместим с зависимыми селектами:
    # ручная подмена options через JS не обновляет состояние Select2.
    # Справочники (материал/марка/обработка) короткие — обычный select работает нормально.
    fieldsets = [
        (None, {'fields': [
            ('sku', 'is_active'),
            'product',
            ('material', 'steel_grade'),
            'finish',
            ('height_mm', 'length_m'),
            'unit',
            'in_stock',
        ]}),
    ]

    def product_link(self, obj):
        url = reverse('admin:catalog_product_change', args=[obj.product_id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Товар'
    product_link.admin_order_field = 'product__name'

    class Media:
        js = ('admin/js/variant_dependent_selects.js',)
