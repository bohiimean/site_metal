import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from apps.references.models import SteelGrade, Color, Material, Finish
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


@admin.register(Product)
class ProductAdmin(SortableAdminBase, admin.ModelAdmin):
    change_form_template = 'admin/catalog/product/change_form.html'

    list_display = ['name', 'category', 'is_active', 'is_new', 'created_at']
    list_editable = ['is_active', 'is_new']
    list_filter = ['is_active', 'is_new', 'category']
    search_fields = ['name', 'slug', 'profile_code']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline]
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
            path('api/colors/', self.admin_site.admin_view(self._api_colors),
                 name='catalog_product_api_colors'),
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

    def _api_colors(self, request):
        finish_id = request.GET.get('finish')
        if not finish_id:
            return JsonResponse([], safe=False)
        qs = (
            Color.objects
            .filter(finish_colors__finish_id=finish_id, is_active=True)
            .distinct()
            .order_by('color_group', 'name')
        )
        return JsonResponse([
            {'id': c.id, 'name': c.name, 'hex': c.hex_code,
             'ral': c.ral_code, 'group': c.color_group}
            for c in qs
        ], safe=False)

    # ── Generator view ────────────────────────────────────────────────────────

    def _generate_variants_view(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)

        if request.method == 'POST':
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({'error': 'Неверный формат данных'}, status=400)
            return JsonResponse(self._process_generator(product, data))

        context = {
            **self.admin_site.each_context(request),
            'product': product,
            'materials': Material.objects.filter(is_active=True).order_by('name'),
            'finishes': Finish.objects.filter(is_active=True).order_by('name'),
            'unit_choices': ProductVariant.UNIT_CHOICES,
            'stock_choices': ProductVariant.STOCK_CHOICES,
            'opts': Product._meta,
            'title': 'Генератор вариантов',
            'subtitle': product.name,
        }
        return render(request, 'admin/catalog/product/generate_variants.html', context)

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

            # Price (required)
            try:
                price = Decimal(str(row['price']))
                if price <= 0:
                    raise ValueError
            except (KeyError, ValueError, InvalidOperation):
                errors.append(f'{label}: укажите корректную цену')
                continue

            unit     = row.get('unit', 'm')
            in_stock = row.get('in_stock', 'in_stock')
            sku_prefix = (row.get('sku_prefix') or '').strip().upper()

            height_mm = None
            if row.get('height_mm'):
                try:
                    height_mm = Decimal(str(row['height_mm']))
                except (ValueError, InvalidOperation):
                    pass

            # Colors
            color_ids = [int(x) for x in (row.get('color_ids') or []) if x]
            if color_ids and finish:
                colors = list(
                    Color.objects.filter(
                        pk__in=color_ids,
                        finish_colors__finish=finish,
                        is_active=True,
                    ).distinct()
                )
            else:
                colors = [None]

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
            for color in colors:
                for length_m in lengths:
                    sku = self._build_sku(
                        product, material, finish, color, length_m,
                        sku_prefix, used_skus,
                    )
                    used_skus.add(sku)

                    if ProductVariant.objects.filter(sku=sku).exists():
                        skipped += 1
                        continue

                    try:
                        v = ProductVariant(
                            product=product,
                            sku=sku,
                            material=material,
                            steel_grade=steel_grade,
                            finish=finish,
                            color=color,
                            price=price,
                            unit=unit,
                            in_stock=in_stock,
                            length_m=length_m,
                            height_mm=height_mm,
                        )
                        v.full_clean()
                        v.save()
                        created += 1
                        color_label = color.name if color else '—'
                        length_label = f'{length_m} м' if length_m else '—'
                        created_list.append(
                            f'{sku} ({color_label}, {length_label})'
                        )
                    except Exception as e:
                        errors.append(f'{label} [{sku}]: {e}')
                        skipped += 1

        return {
            'created': created,
            'skipped': skipped,
            'errors': errors,
            'created_list': created_list,
        }

    def _build_sku(self, product, material, finish, color, length_m, prefix, used_skus):
        if prefix:
            parts = [prefix]
        else:
            parts = [product.slug[:10].upper()]
            parts.append(material.slug[:5].upper() if material.slug else f'M{material.pk}')
            if finish:
                parts.append(finish.slug[:5].upper() if finish.slug else f'F{finish.pk}')

        if color:
            parts.append(f'C{color.pk}')
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
        'finish', 'color', 'length_m', 'price', 'unit', 'in_stock', 'is_active',
    ]
    list_display_links = ['sku']
    list_editable = ['price', 'in_stock', 'is_active']
    list_filter = [ProductListFilter, 'material', 'finish', 'in_stock', 'is_active']
    search_fields = ['sku', 'product__name']
    list_per_page = 50
    list_max_show_all = 200
    list_select_related = ['product', 'material', 'steel_grade', 'finish', 'color']
    raw_id_fields = ['product', 'image']
    # autocomplete_fields (Select2) не совместим с зависимыми селектами:
    # ручная подмена options через JS не обновляет состояние Select2.
    # Справочники (материал/марка/обработка/цвет) короткие — обычный select работает нормально.
    fieldsets = [
        (None, {'fields': [
            ('sku', 'is_active'),
            'product',
            ('material', 'steel_grade'),
            ('finish', 'color'),
            'image',
            ('height_mm', 'length_m'),
            ('price', 'unit'),
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
