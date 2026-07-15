import json
from decimal import Decimal, InvalidOperation

from django.contrib import admin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.widgets import SELECT_CLASSES
from treebeard.forms import movenodeform_factory

from apps.references.models import SteelGrade, Material, Finish
from .models import Category, Product, ProductImage, ProductVariant


# Treebeard TreeAdmin несовместим с unfold (битая разметка таблицы, drag&drop
# рассчитан на классическую админку). Поэтому категории — обычный unfold
# ModelAdmin, а дерево управляется полями формы movenodeform:
# «Position» + «Relative to» (сосед/родитель). Дерево мелкое, правится редко.
_CategoryBaseForm = movenodeform_factory(Category)


class CategoryAdminForm(_CategoryBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Служебные селекты treebeard — не модельные поля, unfold их сам
        # не стилизует; навешиваем его классы вручную
        for name in ('treebeard_position', 'treebeard_ref_node'):
            if name in self.fields:
                self.fields[name].widget.attrs['class'] = ' '.join(SELECT_CLASSES)


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    form = CategoryAdminForm
    list_display = ['tree_name', 'slug', 'image_preview', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']
    ordering = ['path']  # порядок дерева (и карточек на «Продукции»)

    def tree_name(self, obj):
        indent = '— ' * (obj.depth - 1)
        return f'{indent}{obj.name}'
    tree_name.short_description = 'Название'
    tree_name.admin_order_field = 'path'

    def image_preview(self, obj):
        if obj.image:
            try:
                return format_html('<img src="{}" style="height:40px;">', obj.card.url)
            except Exception:
                pass
        return '—'
    image_preview.short_description = 'Картинка'


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 0
    fields = ['image', 'finish', 'color', 'color_group', 'sort_order', 'thumb_preview']
    readonly_fields = ['thumb_preview']
    autocomplete_fields = ['color']
    ordering_field = 'sort_order'
    verbose_name_plural = (
        'Изображения (обработка/цвет/группа пустые — фото галереи; '
        'заполнены — фото при выборе; точное побеждает общее)'
    )

    def thumb_preview(self, obj):
        if obj.pk and obj.image:
            try:
                return format_html('<img src="{}" style="height:60px;">', obj.thumb.url)
            except Exception:
                pass
        return '—'
    thumb_preview.short_description = 'Превью'


@admin.register(Product)
class ProductAdmin(ModelAdmin):
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

            # Steel grades (multi; только марки выбранного материала)
            grade_ids = [int(x) for x in (row.get('steel_grade_ids') or []) if x]
            if grade_ids:
                steel_grades = list(SteelGrade.objects.filter(
                    pk__in=grade_ids, material=material, is_active=True,
                ))
                if not steel_grades:
                    steel_grades = [None]
            else:
                steel_grades = [None]

            # Finishes (multi; 'none' = без обработки)
            raw_finish_ids = row.get('finish_ids') or []
            finishes = []
            for fid in raw_finish_ids:
                if fid in ('none', 0, '0', ''):
                    finishes.append(None)
                    continue
                try:
                    finishes.append(Finish.objects.get(pk=int(fid)))
                except (ValueError, Finish.DoesNotExist):
                    pass
            if not finishes:
                finishes = [None]

            unit     = row.get('unit', 'm')
            in_stock = row.get('in_stock', 'in_stock')
            custom_length = bool(row.get('custom_length'))
            custom_size   = bool(row.get('custom_size'))
            sku_prefix = (row.get('sku_prefix') or '').strip().upper()

            height_mm = None
            if row.get('height_mm'):
                try:
                    height_mm = Decimal(str(row['height_mm']))
                except (ValueError, InvalidOperation):
                    pass

            # Sizes (свободные строки: "6×6", "10×10", …)
            raw_sizes = row.get('sizes') or []
            sizes = []
            for sv in raw_sizes:
                sv = str(sv).strip()[:50]
                if sv and sv not in sizes:
                    sizes.append(sv)
            if not sizes:
                sizes = ['']

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

            # Generate: марки × обработки × размеры × длины
            for steel_grade in steel_grades:
                for finish in finishes:
                    for size in sizes:
                        for length_m in lengths:
                            sku = self._build_sku(
                                product, material, steel_grade, finish, size, length_m,
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
                                size=size,
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
                                    size=size,
                                    length_m=length_m,
                                    height_mm=height_mm,
                                    allow_custom_size=custom_size,
                                    allow_custom_length=custom_length,
                                )
                                v.full_clean()
                                v.save()
                                created += 1
                                parts = [
                                    steel_grade.name if steel_grade else None,
                                    finish.name if finish else None,
                                    size or None,
                                    f'{length_m} м' if length_m else None,
                                ]
                                created_list.append(
                                    f'{sku} ({", ".join(p for p in parts if p) or "—"})'
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

    def _build_sku(self, product, material, steel_grade, finish, size, length_m, prefix, used_skus):
        if prefix:
            parts = [prefix]
        else:
            parts = [product.slug[:10].upper()]
            parts.append(material.slug[:5].upper() if material.slug else f'M{material.pk}')

        # Марка, обработка и размер входят в SKU и при префиксе:
        # в одной строке их теперь может быть несколько
        if steel_grade:
            grade_part = ''.join(ch for ch in steel_grade.name.upper() if ch.isalnum())[:8]
            parts.append(grade_part or f'G{steel_grade.pk}')
        if finish:
            parts.append(finish.slug[:5].upper() if finish.slug else f'F{finish.pk}')

        if size:
            # «6×6», «6x6», «6х6» (лат./кир./знак умножения) → «6X6»
            size_part = ''.join(
                'X' if ch in 'X×Х' else ch
                for ch in size.upper() if ch.isalnum() or ch in '×.'
            )[:12]
            if size_part:
                parts.append(size_part)

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
class ProductVariantAdmin(ModelAdmin):
    list_display = [
        'sku', 'product_link', 'material', 'steel_grade',
        'finish', 'size', 'length_m', 'allow_custom_size', 'allow_custom_length',
        'unit', 'in_stock', 'is_active',
    ]
    list_display_links = ['sku']
    list_editable = ['allow_custom_size', 'allow_custom_length', 'in_stock', 'is_active']
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
            ('size', 'height_mm', 'length_m'),
            ('allow_custom_size', 'allow_custom_length'),
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
