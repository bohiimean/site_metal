import json

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.dateformat import format as date_format
from django.utils.text import Truncator
from django.utils.timezone import localtime
from unfold.admin import ModelAdmin
from .models import Lead, LeadNote, LeadStatus, cart_item_params


@admin.register(LeadStatus)
class LeadStatusAdmin(ModelAdmin):
    list_display = ['color_swatch', 'name', 'sort_order', 'is_default', 'is_active', 'lead_count']
    list_display_links = ['name']
    list_editable = ['sort_order', 'is_active']
    search_fields = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_leads=Count('leads'))

    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:14px;height:14px;border-radius:3px;'
            'background:{}"></span>', obj.color,
        )
    color_swatch.short_description = ''

    def lead_count(self, obj):
        # Статус с заявками удалить нельзя (PROTECT) — только выключить
        return obj._leads
    lead_count.short_description = 'Заявок'
    lead_count.admin_order_field = '_leads'


class LeadStatusFieldMixin:
    """Выбор статуса: только активные (плюс текущий, даже выключенный),
    у поля — полоса цвета статуса. Карта цветов (data-status-colors) нужна,
    чтобы полоса перекрашивалась сразу при выборе (static/js/admin/lead_status.js)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get('status')
        if field is None:
            return
        current = self.instance.status if self.instance.pk else None
        field.queryset = LeadStatus.objects.filter(
            Q(is_active=True) | Q(pk=getattr(current, 'pk', None)))
        field.empty_label = None
        # Админка оборачивает селект ссылками «добавить/изменить статус» —
        # при смене статуса заявки они только мешают; стиль — на сам селект
        widget = field.widget
        if hasattr(widget, 'widget'):
            widget.can_add_related = widget.can_change_related = False
            widget.can_delete_related = widget.can_view_related = False
            widget = widget.widget
        widget.attrs['data-status-colors'] = json.dumps(
            {str(st.pk): st.color for st in field.queryset})
        if current:
            widget.attrs['style'] = f'border-left: 6px solid {current.color}'


class LeadForm(LeadStatusFieldMixin, forms.ModelForm):
    class Meta:
        model = Lead
        fields = '__all__'


def notes_summary(count, last_text):
    """Подпись в колонке «Заметки»: 💬 2 · «последняя…» или «＋ добавить»."""
    if not count:
        return '＋ добавить'
    return f'💬 {count} · «{Truncator(last_text).chars(30)}»'


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    form = LeadForm
    list_display = ['id', 'name', 'phone', 'contact_display', 'source_badge',
                    'status', 'notes_link', 'created_short']
    list_editable = ['status']
    list_filter = ['status', 'source']
    search_fields = ['name', 'phone']
    readonly_fields = ['created_at', 'updated_at', 'cart_snapshot_display',
                       'consent_pdn', 'pdn_revision_link',
                       'consent_terms', 'terms_revision_link', 'notes_button']
    fieldsets = [
        ('Контакт', {'fields': ['name', 'phone', 'contact_method', 'contact_value', 'comment']}),
        ('Согласия', {'fields': ['consent_pdn', 'pdn_revision_link',
                                 'consent_terms', 'terms_revision_link']}),
        ('Статус', {'fields': ['source', 'status']}),
        ('Корзина', {'fields': ['cart_snapshot_display']}),
        ('Заметки менеджера', {'fields': ['notes_button']}),
        ('Даты', {'fields': ['created_at', 'updated_at']}),
    ]

    class Media:
        js = ['js/admin/lead_notes.js', 'js/admin/lead_status.js']
        css = {'all': ['css/admin/lead_notes.css']}

    def get_queryset(self, request):
        manual = LeadNote.objects.filter(lead=OuterRef('pk'), kind='note')
        return (
            super().get_queryset(request)
            .select_related('status')
            .annotate(
                _notes_count=Count('notes', filter=Q(notes__kind='note')),
                _last_note=Subquery(manual.order_by('-created_at', '-id').values('text')[:1]),
            )
        )

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', LeadForm)
        return super().get_changelist_form(request, **kwargs)

    # ── Статусы: смена в карточке, в строке списка и массово ───────────────

    def save_model(self, request, obj, form, change):
        old = None
        if change and obj.pk:
            old = (Lead.objects.filter(pk=obj.pk).select_related('status')
                   .values_list('status', flat=True).first())
            old = LeadStatus.objects.filter(pk=old).first() if old else None
        super().save_model(request, obj, form, change)
        if change:
            LeadNote.log_status_change(obj, old, obj.status, request.user)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not self.has_change_permission(request):
            return actions
        for status in LeadStatus.objects.filter(is_active=True):
            name = f'set_status_{status.pk}'
            actions[name] = (self._status_action(status), name, f'Статус → {status.name}')
        return actions

    @staticmethod
    def _status_action(status):
        def action(modeladmin, request, queryset):
            for lead in queryset.select_related('status'):
                if lead.status_id == status.pk:
                    continue
                old = lead.status
                lead.status = status
                lead.save(update_fields=['status', 'updated_at'])
                LeadNote.log_status_change(lead, old, status, request.user)
        return action

    # ── Заметки: окно поверх страницы ───────────────────────────────────────

    def get_urls(self):
        return [
            path('<path:object_id>/notes/',
                 self.admin_site.admin_view(self.notes_view),
                 name='leads_lead_notes'),
        ] + super().get_urls()

    def notes_view(self, request, object_id):
        """Содержимое окна заметок: таблица истории и форма добавления.
        GET — показать, POST — добавить заметку и вернуть обновлённое окно."""
        try:
            lead = Lead.objects.filter(pk=int(object_id)).first()
        except ValueError:
            lead = None
        if not self.has_view_or_change_permission(request, lead):
            raise PermissionDenied
        if lead is None:
            raise Http404

        can_change = self.has_change_permission(request, lead)
        error, status = '', 200
        if request.method == 'POST':
            if not can_change:
                raise PermissionDenied
            text = request.POST.get('text', '').strip()
            if not text:
                error, status = 'Заметка пустая.', 400
            elif len(text) > LeadNote.MAX_LENGTH:
                error, status = f'Слишком длинно: не больше {LeadNote.MAX_LENGTH} символов.', 400
            else:
                LeadNote.objects.create(
                    lead=lead, author=request.user,
                    author_name=LeadNote.name_of(request.user), text=text,
                )

        notes = list(lead.notes.all())
        manual = [n for n in notes if n.kind == 'note']
        return render(request, 'admin/leads/lead/notes_window.html', {
            'lead': lead,
            'notes': notes,
            'can_change': can_change,
            'error': error,
            'text': request.POST.get('text', '') if error else '',
            'notes_url': reverse('admin:leads_lead_notes', args=[lead.pk]),
            'count': len(manual),
            'summary': notes_summary(len(manual), manual[-1].text if manual else ''),
            'last_text': manual[-1].text if manual else '',
            'max_length': LeadNote.MAX_LENGTH,
        }, status=status)

    def notes_link(self, obj):
        # Одна строка с многоточием (lead_notes.css), полный текст последней
        # заметки — в подсказке: длинная заметка не раздвигает таблицу
        url = reverse('admin:leads_lead_notes', args=[obj.pk])
        return format_html(
            '<a href="{}" data-lead-notes="{}" data-notes-label="list" '
            'class="lead-notes-link" title="{}">{}</a>',
            url, url, obj._last_note or '',
            notes_summary(obj._notes_count, obj._last_note or ''),
        )
    notes_link.short_description = 'Заметки'

    def created_short(self, obj):
        # Короткая дата в одну строку — длинная «11 октября 2026 г. 13:37»
        # не помещалась в таблицу рядом со статусом и заметками
        return date_format(localtime(obj.created_at), 'd.m.Y H:i')
    created_short.short_description = 'Создана'
    created_short.admin_order_field = 'created_at'

    def notes_button(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('admin:leads_lead_notes', args=[obj.pk])
        count = obj.notes.filter(kind='note').count()
        return format_html(
            '<a href="{}" data-lead-notes="{}" data-notes-label="card" '
            'class="lead-notes-button">💬 Открыть заметки ({})</a>',
            url, url, count,
        )
    notes_button.short_description = 'История'

    def _revision_link(self, revision):
        if revision is None:
            return '—'
        url = reverse('admin:pages_pagerevision_change', args=[revision.pk])
        return format_html('<a href="{}">{}</a>', url, revision)

    def pdn_revision_link(self, obj):
        return self._revision_link(obj.pdn_revision)
    pdn_revision_link.short_description = 'Редакция политики ПДн'

    def terms_revision_link(self, obj):
        return self._revision_link(obj.terms_revision)
    terms_revision_link.short_description = 'Редакция условий продажи'

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
            for name, value in cart_item_params(item):
                extras.append(format_html(
                    '<span style="color:#555">📐 {}: {}</span>', name, value,
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
