import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leads.models import Lead, LeadNote, LeadStatus

QUIET = dict(
    YANDEX_CAPTCHA_SERVER_KEY='',
    TELEGRAM_BOT_TOKEN='',
    TELEGRAM_CHAT_ID='',
    RATELIMIT_ENABLE=False,
)


def make_statuses():
    new = LeadStatus.objects.create(name='Новая', color='#f59e0b', sort_order=1, is_default=True)
    work = LeadStatus.objects.create(name='В работе', color='#3b82f6', sort_order=2)
    done = LeadStatus.objects.create(name='Выполнена', color='#10b981', sort_order=3)
    return new, work, done


def make_lead(**kwargs):
    kwargs.setdefault('name', 'Иван')
    kwargs.setdefault('phone', '+79990000000')
    kwargs.setdefault('source', 'callback_request')
    return Lead.objects.create(**kwargs)


class LeadStatusModelTests(TestCase):
    def setUp(self):
        # Миграция заводит стартовые статусы — для модельных тестов начинаем с чистого листа
        LeadStatus.objects.all().delete()
        self.new, self.work, self.done = make_statuses()

    def test_new_lead_gets_default_status(self):
        self.assertEqual(make_lead().status, self.new)

    def test_explicit_status_kept(self):
        self.assertEqual(make_lead(status=self.work).status, self.work)

    def test_only_one_default_status(self):
        self.work.is_default = True
        self.work.save()
        self.new.refresh_from_db()
        self.assertFalse(self.new.is_default)
        self.assertEqual(LeadStatus.get_default(), self.work)
        self.assertEqual(make_lead().status, self.work)

    def test_default_status_cannot_be_deactivated(self):
        self.new.is_active = False
        with self.assertRaises(ValidationError):
            self.new.full_clean()

    def test_default_falls_back_to_first_active_when_none_marked(self):
        LeadStatus.objects.filter(pk=self.new.pk).update(is_default=False, is_active=False)
        self.assertEqual(LeadStatus.get_default(), self.work)

    def test_used_status_cannot_be_deleted(self):
        make_lead(status=self.work)
        with self.assertRaises(ProtectedError):
            self.work.delete()

    def test_ordering(self):
        self.assertEqual(
            list(LeadStatus.objects.values_list('name', flat=True)),
            ['Новая', 'В работе', 'Выполнена'],
        )


class InitialStatusesTests(TestCase):
    def test_starting_statuses_created_by_migration(self):
        # Справочник не пустой сразу после деплоя: прежние три статуса
        rows = list(LeadStatus.objects.order_by('sort_order').values_list(
            'name', 'is_default', 'is_active'))
        self.assertEqual(rows, [
            ('Новая', True, True),
            ('В работе', False, True),
            ('Выполнена', False, True),
        ])


@override_settings(**QUIET)
class SubmitAssignsDefaultStatusTests(TestCase):
    def test_cart_lead_gets_default_status(self):
        response = self.client.post(
            reverse('leads:submit_cart'),
            data=json.dumps({'name': 'Иван', 'phone': '+79990000000',
                             'agree': True, 'agree_terms': True, 'cart_snapshot': []}),
            content_type='application/json',
        )
        lead = Lead.objects.get(pk=response.json()['id'])
        self.assertEqual(lead.status, LeadStatus.get_default())
        self.assertEqual(lead.status.name, 'Новая')

    def test_callback_lead_gets_default_status(self):
        self.client.post(reverse('leads:submit_callback'),
                         {'name': 'Олег', 'phone': '+79161234567', 'agree': 'on'})
        lead = Lead.objects.get(phone='+79161234567')
        self.assertEqual(lead.status.name, 'Новая')


class AdminBase(TestCase):
    def setUp(self):
        LeadStatus.objects.all().delete()
        self.new, self.work, self.done = make_statuses()
        self.user = get_user_model().objects.create_superuser(
            'anna', 'anna@example.com', 'pass', first_name='Анна')
        self.client.force_login(self.user)
        self.lead = make_lead()

    def notes_url(self, lead=None):
        return reverse('admin:leads_lead_notes', args=[(lead or self.lead).pk])

    def changelist_url(self):
        return reverse('admin:leads_lead_changelist')

    def change_url(self, lead=None):
        return reverse('admin:leads_lead_change', args=[(lead or self.lead).pk])

    def post_card(self, status, lead=None):
        lead = lead or self.lead
        return self.client.post(self.change_url(lead), {
            'name': lead.name, 'phone': lead.phone,
            'contact_method': lead.contact_method, 'contact_value': lead.contact_value,
            'comment': lead.comment, 'source': lead.source,
            'status': status.pk,
        })


class StatusChangeLoggingTests(AdminBase):
    def test_status_change_in_card_logged(self):
        response = self.post_card(self.work)
        self.assertEqual(response.status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, self.work)
        note = self.lead.notes.get()
        self.assertEqual(note.kind, 'status')
        self.assertEqual(note.text, 'Статус: Новая → В работе')
        self.assertEqual(note.author, self.user)
        self.assertEqual(note.author_name, 'Анна')

    def test_saving_card_without_status_change_logs_nothing(self):
        self.post_card(self.new)
        self.assertFalse(self.lead.notes.exists())

    def test_status_change_from_list_row_logged(self):
        response = self.client.post(self.changelist_url(), {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.lead.pk),
            'form-0-status': str(self.done.pk),
            '_save': 'Сохранить',
        })
        self.assertEqual(response.status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, self.done)
        self.assertEqual(self.lead.notes.get().text, 'Статус: Новая → Выполнена')

    def test_bulk_action_changes_status_and_logs_only_real_changes(self):
        already = make_lead(name='Олег', status=self.work)
        response = self.client.post(self.changelist_url(), {
            'action': f'set_status_{self.work.pk}',
            '_selected_action': [str(self.lead.pk), str(already.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, self.work)
        self.assertEqual(self.lead.notes.get().text, 'Статус: Новая → В работе')
        self.assertFalse(already.notes.exists())

    def test_bulk_actions_built_from_active_statuses(self):
        self.done.is_active = False
        self.done.save()
        response = self.client.get(self.changelist_url())
        self.assertContains(response, f'set_status_{self.work.pk}')
        self.assertNotContains(response, f'set_status_{self.done.pk}')

    def test_inactive_status_not_offered_in_card(self):
        self.done.is_active = False
        self.done.save()
        response = self.client.get(self.change_url())
        choices = [c[0] for c in response.context['adminform'].form.fields['status'].choices]
        self.assertIn(self.work.pk, [getattr(v, 'value', v) for v in choices])
        self.assertNotIn(self.done.pk, [getattr(v, 'value', v) for v in choices])

    def test_inactive_current_status_still_shown_in_card(self):
        lead = make_lead(name='Олег', status=self.done)
        self.done.is_active = False
        self.done.save()
        response = self.client.get(self.change_url(lead))
        choices = [getattr(c[0], 'value', c[0])
                   for c in response.context['adminform'].form.fields['status'].choices]
        self.assertIn(self.done.pk, choices)

    def test_status_filter_lists_reference_statuses(self):
        response = self.client.get(self.changelist_url())
        self.assertContains(response, 'Выполнена')
        response = self.client.get(self.changelist_url(), {'status__id__exact': self.work.pk})
        self.assertEqual(list(response.context['cl'].result_list), [])


class NotesWindowTests(AdminBase):
    def add_note(self, text, lead=None):
        return self.client.post(self.notes_url(lead), {'text': text})

    def test_window_lists_notes_in_chronological_order(self):
        LeadNote.objects.create(lead=self.lead, author=self.user, author_name='Анна',
                                text='Перезвонить после 16')
        LeadNote.objects.create(lead=self.lead, author=None, author_name='Олег',
                                kind='status', text='Статус: Новая → В работе')
        response = self.client.get(self.notes_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index('Перезвонить после 16'), html.index('Статус: Новая → В работе'))
        self.assertIn('Анна', html)
        self.assertIn('Олег', html)
        self.assertIn('<table', html)
        self.assertIn('name="text"', html)

    def test_add_note(self):
        response = self.add_note('  Выставлен счёт №118  ')
        self.assertEqual(response.status_code, 200)
        note = self.lead.notes.get()
        self.assertEqual(note.text, 'Выставлен счёт №118')
        self.assertEqual(note.kind, 'note')
        self.assertEqual(note.author, self.user)
        self.assertContains(response, 'Выставлен счёт №118')

    def test_empty_note_rejected(self):
        response = self.add_note('   ')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.lead.notes.exists())

    def test_too_long_note_rejected(self):
        response = self.add_note('x' * 2001)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.lead.notes.exists())

    def test_note_text_escaped(self):
        self.add_note('<script>alert(1)</script>')
        response = self.client.get(self.notes_url())
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_notes_of_other_lead_not_shown(self):
        other = make_lead(name='Олег')
        LeadNote.objects.create(lead=other, author_name='Анна', text='чужая заметка')
        self.assertNotContains(self.client.get(self.notes_url()), 'чужая заметка')

    def test_unknown_lead_404(self):
        response = self.client.get(reverse('admin:leads_lead_notes', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_view_only_manager_can_read_but_not_write(self):
        viewer = get_user_model().objects.create_user('viewer', password='pass', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_lead'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.notes_url()).status_code, 200)
        self.assertEqual(self.add_note('попытка').status_code, 403)
        self.assertFalse(self.lead.notes.exists())

    def test_staff_without_permissions_denied(self):
        nobody = get_user_model().objects.create_user('nobody', password='pass', is_staff=True)
        self.client.force_login(nobody)
        self.assertEqual(self.client.get(self.notes_url()).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.notes_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_deleting_lead_removes_notes(self):
        self.add_note('заметка')
        self.lead.delete()
        self.assertFalse(LeadNote.objects.exists())

    def test_deleting_author_keeps_note_and_name(self):
        other = get_user_model().objects.create_superuser('oleg', 'o@e.com', 'pass')
        self.client.force_login(other)
        self.add_note('от Олега')
        other.delete()
        note = self.lead.notes.get()
        self.assertIsNone(note.author)
        self.assertEqual(note.author_name, 'oleg')


class NotesEntryPointsTests(AdminBase):
    def test_list_column_shows_count_and_last_note(self):
        LeadNote.objects.create(lead=self.lead, author_name='Анна', text='Первая')
        LeadNote.objects.create(lead=self.lead, author_name='Анна',
                                text='Оплачено, передано на отгрузку со склада в Подольске')
        response = self.client.get(self.changelist_url())
        self.assertContains(response, self.notes_url())
        self.assertContains(response, '💬 2')
        self.assertContains(response, 'Оплачено, передано')
        self.assertNotContains(response, 'со склада в Подольске')  # обрезано

    def test_list_column_offers_adding_when_empty(self):
        response = self.client.get(self.changelist_url())
        self.assertContains(response, self.notes_url())
        self.assertContains(response, 'добавить')

    def test_notes_column_goes_before_created_at(self):
        response = self.client.get(self.changelist_url())
        headers = [h['text'] for h in response.context['result_headers']]
        self.assertEqual(headers.index('Заметки') + 1, headers.index('Создана'))

    def test_card_has_notes_button_before_dates(self):
        response = self.client.get(self.change_url())
        html = response.content.decode()
        self.assertIn(self.notes_url(), html)
        fieldset_names = [fs.name for fs in response.context['adminform']]
        self.assertEqual(fieldset_names.index('Заметки менеджера') + 1, fieldset_names.index('Даты'))

    def test_notes_script_included(self):
        response = self.client.get(self.changelist_url())
        self.assertContains(response, 'lead_notes.js')
