import json

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action
from unfold.widgets import SELECT_CLASSES
from treebeard.forms import movenodeform_factory

from apps.references.models import Material, SteelGrade, Finish, Color, ColorPalette
from .models import (
    Category, CategoryFacet, Product, ProductImage,
    ProductOptionNode, ProductParamValue,
)


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


class CategoryFacetInline(TabularInline):
    model = CategoryFacet
    extra = 0
    fields = ['facet', 'title', 'sort_order', 'is_active']
    ordering_field = 'sort_order'
    verbose_name_plural = (
        'Фильтры раздела (нет ни одной строки — наследуются от родительской '
        'категории или показывается стандартный набор; фасет без значений '
        'в разделе скрывается сам)'
    )


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    form = CategoryAdminForm
    inlines = [CategoryFacetInline]
    list_display = ['tree_name', 'slug', 'image_preview', 'is_active']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']
    ordering = ['path']  # порядок дерева (и карточек на «Продукции»)
    actions_list = ['reorder_roots']

    @action(description='Порядок разделов', url_path='reorder', permissions=['change'])
    def reorder_roots(self, request):
        """Drag&drop-порядок корневых категорий.

        Отдельного поля порядка у категорий нет: порядок карточек на
        «Продукции», чипов на главной и колонки футера — это порядок дерева
        treebeard, поэтому сохранение переставляет сами корневые узлы.
        """
        if request.method == 'POST':
            current = {c.pk for c in Category.get_root_nodes()}
            try:
                ids = [int(v) for v in request.POST.get('order', '').split(',') if v]
            except ValueError:
                ids = []
            if set(ids) != current or len(ids) != len(current):
                messages.error(
                    request,
                    'Не удалось сохранить порядок: список разделов изменился. '
                    'Обновите страницу и попробуйте ещё раз.',
                )
            else:
                with transaction.atomic():
                    prev_pk = None
                    for pk in ids:
                        if prev_pk is not None:
                            # Перечитываем оба узла: после каждого move
                            # treebeard меняет path у соседей
                            Category.objects.get(pk=pk).move(
                                Category.objects.get(pk=prev_pk), 'right',
                            )
                        prev_pk = pk
                messages.success(request, 'Порядок разделов сохранён.')
            return redirect('admin:catalog_category_changelist')

        return render(request, 'admin/catalog/category/reorder.html', {
            **self.admin_site.each_context(request),
            'title': 'Порядок разделов',
            'opts': self.model._meta,
            'roots': Category.get_root_nodes(),
        })

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
    fields = ['image', 'material', 'finish', 'color', 'color_group',
              'sort_order', 'thumb_preview']
    readonly_fields = ['thumb_preview']
    autocomplete_fields = ['color']
    ordering_field = 'sort_order'
    verbose_name_plural = (
        'Фото (условия пустые — фото галереи; заполнены — правило показа '
        'при выборе; побеждает правило с максимумом совпавших условий, '
        'тай-брейк: цвет > обработка > материал)'
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

    list_display = ['name', 'category', 'in_stock', 'is_active',
                    'is_new', 'is_featured', 'created_at']
    list_editable = ['in_stock', 'is_active', 'is_new', 'is_featured']
    list_filter = ['is_active', 'is_new', 'is_featured', 'in_stock', 'category']
    search_fields = ['name', 'slug', 'profile_code']
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ['category']
    inlines = [ProductImageInline]
    # Популярные — сверху и в админском списке; порядок между ними — featured_order
    ordering = ['-is_featured', 'featured_order', '-created_at']
    actions_list = ['reorder_featured']

    @action(description='Порядок популярных', url_path='reorder-featured',
            permissions=['change'])
    def reorder_featured(self, request):
        """Drag&drop-порядок только популярных товаров (is_featured=True).

        Отдельная страница вместо перетаскивания всего списка: курируется
        небольшой набор, порядок пишется в featured_order. На витрине этот же
        порядок поднимает популярные наверх (SORT_MAP['new'])."""
        featured = Product.objects.filter(is_featured=True)
        if request.method == 'POST':
            current = {p.pk for p in featured}
            try:
                ids = [int(v) for v in request.POST.get('order', '').split(',') if v]
            except ValueError:
                ids = []
            if set(ids) != current or len(ids) != len(current):
                messages.error(
                    request,
                    'Не удалось сохранить порядок: список популярных изменился. '
                    'Обновите страницу и попробуйте ещё раз.',
                )
            else:
                with transaction.atomic():
                    for order, pk in enumerate(ids):
                        Product.objects.filter(pk=pk).update(featured_order=order)
                messages.success(request, 'Порядок популярных сохранён.')
            return redirect('admin:catalog_product_changelist')

        return render(request, 'admin/catalog/product/reorder_featured.html', {
            **self.admin_site.each_context(request),
            'title': 'Порядок популярных',
            'opts': self.model._meta,
            'products': featured.select_related('category')
            .order_by('featured_order', '-created_at'),
        })
    # Свободные параметры и флаги «свой размер/длина/высота» редактируются
    # в секции «Дерево опций» на странице товара, не отдельными полями
    fieldsets = [
        (None, {'fields': ['name', 'slug', 'category', 'profile_code',
                           'in_stock', 'is_new', 'is_active']}),
        ('Описание', {'fields': ['description']}),
        ('SEO', {'classes': ['collapse'], 'fields': ['seo_title', 'seo_description']}),
    ]

    # ── Change view: данные для секции «Дерево опций» ────────────────────────

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'option_dicts_json': self._option_dicts(),
            'option_state_json': self._option_state(object_id),
            'param_state_json': self._param_state(object_id),
        })
        return super().change_view(request, object_id, form_url, extra_context)

    def _option_dicts(self):
        """Глобальные справочники для отрисовки чекбокс-дерева."""
        materials = []
        for m in Material.objects.filter(is_active=True).order_by('name'):
            materials.append({
                'id': m.pk,
                'name': m.name,
                'grades': [
                    {'id': g.pk, 'name': g.name}
                    for g in m.steel_grades.filter(is_active=True).order_by('name')
                ],
            })
        finishes = [
            {'id': f.pk, 'name': f.name}
            for f in Finish.objects.filter(is_active=True).order_by('name')
        ]
        group_labels = dict(Color.COLOR_GROUP_CHOICES)
        colors = [
            {
                'id': c.pk, 'name': c.name, 'hex': c.hex_code,
                'ral': c.ral_code, 'group': c.color_group,
                'group_label': group_labels.get(c.color_group, 'Без группы'),
            }
            for c in Color.objects.filter(is_active=True)
            .order_by('color_group', 'name')
        ]
        palettes = [
            {
                'id': p.pk,
                'name': p.name,
                'color_ids': [c.pk for c in p.colors.all()],
            }
            for p in ColorPalette.objects.filter(is_active=True)
            .prefetch_related('colors').order_by('name')
        ]
        return {
            'materials': materials, 'finishes': finishes,
            'colors': colors, 'palettes': palettes,
        }

    def _option_state(self, object_id):
        """Текущее дерево товара в формате, который редактирует JS-секция."""
        nodes = list(
            ProductOptionNode.objects
            .filter(product_id=object_id)
            .prefetch_related('colors')
            .order_by('sort_order', 'id')
        )
        by_parent = {}
        for n in nodes:
            by_parent.setdefault(n.parent_id, []).append(n)

        def finish_entry(node):
            return {
                'finish_id': node.finish_id,
                'color_ids': [c.pk for c in node.colors.all()],
            }

        state = []
        for m in by_parent.get(None, []):
            if m.node_type != 'material':
                continue
            entry = {'material_id': m.material_id, 'grades': [], 'finishes': []}
            for child in by_parent.get(m.pk, []):
                if child.node_type == 'steel_grade':
                    entry['grades'].append({
                        'grade_id': child.steel_grade_id,
                        'finishes': [
                            finish_entry(f) for f in by_parent.get(child.pk, [])
                            if f.node_type == 'finish'
                        ],
                    })
                elif child.node_type == 'finish':
                    entry['finishes'].append(finish_entry(child))
            state.append(entry)
        return state

    def _param_state(self, object_id):
        """Свободные параметры товара для секции опций."""
        try:
            product = Product.objects.get(pk=object_id)
        except Product.DoesNotExist:
            return {}
        state = {}
        for kind, _ in ProductParamValue.KIND_CHOICES:
            state[kind] = {
                'values': list(
                    product.param_values.filter(kind=kind)
                    .order_by('sort_order', 'id')
                    .values_list('value', flat=True)
                ),
                'custom': getattr(product, f'allow_custom_{kind}'),
            }
        return state

    # ── Сохранение дерева ────────────────────────────────────────────────────

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        raw = request.POST.get('options_tree')
        if raw is not None:  # add-форма: секции опций ещё нет
            try:
                desired = json.loads(raw)
                if not isinstance(desired, list):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                self.message_user(
                    request, 'Дерево опций не сохранено: неверный формат данных.',
                    level='error',
                )
            else:
                self._sync_option_tree(obj, desired)

        raw = request.POST.get('free_params')
        if raw is not None:
            try:
                desired = json.loads(raw)
                if not isinstance(desired, dict):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                self.message_user(
                    request, 'Параметры не сохранены: неверный формат данных.',
                    level='error',
                )
            else:
                self._sync_free_params(obj, desired)

    def _sync_free_params(self, product, desired):
        """Приводит значения размер/длина/высота и флаги «свой …» к форме."""
        update_fields = []
        for kind, _ in ProductParamValue.KIND_CHOICES:
            entry = desired.get(kind)
            if not isinstance(entry, dict):
                continue

            values, seen = [], set()
            for v in entry.get('values') or []:
                v = str(v).strip()[:50]
                if v and v not in seen:
                    seen.add(v)
                    values.append(v)

            existing = {
                pv.value: pv
                for pv in ProductParamValue.objects.filter(product=product, kind=kind)
            }
            for order, value in enumerate(values):
                pv = existing.pop(value, None)
                if pv is None:
                    ProductParamValue.objects.create(
                        product=product, kind=kind, value=value, sort_order=order,
                    )
                elif pv.sort_order != order:
                    pv.sort_order = order
                    pv.save(update_fields=['sort_order'])
            for pv in existing.values():
                pv.delete()

            flag = f'allow_custom_{kind}'
            custom = bool(entry.get('custom'))
            if getattr(product, flag) != custom:
                setattr(product, flag, custom)
                update_fields.append(flag)
        if update_fields:
            product.save(update_fields=update_fields)

    def _sync_option_tree(self, product, desired):
        """Приводит узлы товара к состоянию из формы (создание/обновление/
        удаление). Марки чужого материала и неизвестные id молча
        отбрасываются — в форму они могут попасть только руками."""
        grades_by_material = {}
        for g in SteelGrade.objects.filter(is_active=True):
            grades_by_material.setdefault(g.material_id, set()).add(g.pk)
        material_ids = set(
            Material.objects.filter(is_active=True).values_list('pk', flat=True))
        finish_ids = set(
            Finish.objects.filter(is_active=True).values_list('pk', flat=True))
        color_ids = set(
            Color.objects.filter(is_active=True).values_list('pk', flat=True))

        keep = set()

        def get_node(parent, node_type, **ref):
            node, _ = ProductOptionNode.objects.get_or_create(
                product=product, parent=parent, node_type=node_type, **ref,
            )
            keep.add(node.pk)
            return node

        def as_int(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        def sync_finish(parent, entry, order):
            fid = as_int(entry.get('finish_id'))
            if fid not in finish_ids:
                return
            node = get_node(parent, 'finish', finish_id=fid)
            if node.sort_order != order:
                node.sort_order = order
                node.save()
            selected = [
                c for c in map(as_int, entry.get('color_ids') or [])
                if c in color_ids
            ]
            node.colors.set(selected)

        for m_order, m_entry in enumerate(desired):
            if not isinstance(m_entry, dict):
                continue
            mid = as_int(m_entry.get('material_id'))
            if mid not in material_ids:
                continue
            m_node = get_node(None, 'material', material_id=mid)
            if m_node.sort_order != m_order:
                m_node.sort_order = m_order
                m_node.save()

            for g_order, g_entry in enumerate(m_entry.get('grades') or []):
                if not isinstance(g_entry, dict):
                    continue
                gid = as_int(g_entry.get('grade_id'))
                if gid not in grades_by_material.get(mid, set()):
                    continue
                g_node = get_node(m_node, 'steel_grade', steel_grade_id=gid)
                if g_node.sort_order != g_order:
                    g_node.sort_order = g_order
                    g_node.save()
                for f_order, f_entry in enumerate(g_entry.get('finishes') or []):
                    if isinstance(f_entry, dict):
                        sync_finish(g_node, f_entry, f_order)

            for f_order, f_entry in enumerate(m_entry.get('finishes') or []):
                if isinstance(f_entry, dict):
                    sync_finish(m_node, f_entry, f_order)

        # Всё, чего нет в форме, — удаляется (дочерние уходят каскадом)
        ProductOptionNode.objects.filter(product=product).exclude(pk__in=keep).delete()
