from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import Lead


def make_status_action(status, label):
    def action(modeladmin, request, queryset):
        queryset.update(status=status)
    action.__name__ = f'set_status_{status}'
    action.short_description = label
    return action


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = ['id', 'name', 'phone', 'contact_display', 'source_badge', 'status_badge', 'created_at']
    list_filter = ['status', 'source']
    search_fields = ['name', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'cart_snapshot_display']
    actions = [
        make_status_action('in_progress', 'Взять в работу'),
        make_status_action('closed',      'Закрыть'),
        make_status_action('new',         'Вернуть в «Новые»'),
    ]
    fieldsets = [
        ('Контакт', {'fields': ['name', 'phone', 'contact_method', 'contact_value', 'comment', 'consent_pdn']}),
        ('Статус', {'fields': ['source', 'status']}),
        ('Корзина', {'fields': ['cart_snapshot_display']}),
        ('Даты', {'fields': ['created_at', 'updated_at']}),
    ]

    def contact_display(self, obj):
        if obj.contact_method == 'phone':
            return obj.get_contact_method_display()
        return f'{obj.get_contact_method_display()}: {obj.contact_value}' if obj.contact_value else obj.get_contact_method_display()
    contact_display.short_description = 'Способ связи'

    def source_badge(self, obj):
        colors = {'cart': '#3b82f6', 'callback_request': '#8b5cf6'}
        color = colors.get(obj.source, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            color, obj.get_source_display(),
        )
    source_badge.short_description = 'Источник'

    def status_badge(self, obj):
        colors = {'new': '#f59e0b', 'in_progress': '#3b82f6', 'closed': '#10b981'}
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 6px;border-radius:3px;font-size:11px">{}</span>',
            color, obj.get_status_display(),
        )
    status_badge.short_description = 'Статус'

    def cart_snapshot_display(self, obj):
        if not obj.cart_snapshot:
            return '— (заявка на звонок)'

        def _row(item):
            base = format_html(
                '{} &nbsp;·&nbsp; ×{}',
                item.get('name', '?'),
                item.get('qty', 1),
            )
            extras = []
            spec = ' / '.join(
                str(item[f]) for f in ('material', 'steel_grade', 'finish')
                if item.get(f)
            )
            if spec:
                extras.append(format_html(
                    '<span style="color:#555">⚙ {}</span>', spec,
                ))
            if item.get('color'):
                extras.append(format_html(
                    '<span style="color:#555">🎨 {}</span>', item['color'],
                ))
            if item.get('size'):
                extras.append(format_html(
                    '<span style="color:#555">📐 размер: {}</span>', item['size'],
                ))
            if item.get('length'):
                extras.append(format_html(
                    '<span style="color:#555">📏 длина: {}</span>', item['length'],
                ))
            if item.get('height'):
                extras.append(format_html(
                    '<span style="color:#555">📏 высота: {}</span>', item['height'],
                ))
            if item.get('note'):
                extras.append(format_html(
                    '<span style="color:#666">💬 {}</span>', item['note'],
                ))
            if item.get('is_active') is False:
                extras.append(mark_safe('<span style="color:#c62828">товар недоступен</span>'))
            if not extras:
                return base
            return format_html('{} &nbsp;·&nbsp; {}', base, mark_safe(' &nbsp;·&nbsp; '.join(str(e) for e in extras)))

        return format_html_join(mark_safe('<br>'), '{}', ((_row(i),) for i in obj.cart_snapshot))
    cart_snapshot_display.short_description = 'Состав корзины'
