"""Длинная заметка не раздвигает таблицу заявок: в колонке — одна строка
фиксированной ширины с многоточием, полный текст — во всплывающей подсказке."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import Lead, LeadNote


class NotesColumnLayoutTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser('anna', 'a@e.com', 'pass')
        self.client.force_login(user)
        self.lead = Lead.objects.create(name='Иван', phone='1', source='callback_request')

    def test_long_note_full_text_in_tooltip(self):
        long_text = 'Клиент просил перезвонить после обеда, уточнить длину хлыста и доставку'
        LeadNote.objects.create(lead=self.lead, author_name='Анна', text=long_text)
        response = self.client.get(reverse('admin:leads_lead_changelist'))
        self.assertContains(response, f'title="{long_text}"')

    def test_notes_link_uses_single_line_class(self):
        response = self.client.get(reverse('admin:leads_lead_changelist'))
        self.assertContains(response, 'class="lead-notes-link"')

    def test_tooltip_escaped(self):
        LeadNote.objects.create(lead=self.lead, author_name='Анна', text='"><script>x</script>')
        response = self.client.get(reverse('admin:leads_lead_changelist'))
        self.assertNotContains(response, '"><script>x</script>')
