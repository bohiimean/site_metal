"""Цвет статуса в селекте меняется сразу при выборе, не только после сохранения:
селект несёт карту «id статуса → цвет», страница перекрашивает его на лету."""
import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import Lead, LeadStatus


class StatusColorsMapTests(TestCase):
    def setUp(self):
        LeadStatus.objects.all().delete()
        self.new = LeadStatus.objects.create(name='Новая', color='#f59e0b', sort_order=1, is_default=True)
        self.work = LeadStatus.objects.create(name='В работе', color='#3b82f6', sort_order=2)
        self.off = LeadStatus.objects.create(name='Архив', color='#000000', sort_order=3, is_active=False)
        user = get_user_model().objects.create_superuser('anna', 'a@e.com', 'pass')
        self.client.force_login(user)
        self.lead = Lead.objects.create(name='Иван', phone='1', source='callback_request')

    def colors_in(self, html):
        maps = re.findall(r'data-status-colors="([^"]*)"', html)
        self.assertTrue(maps, 'у селекта статуса нет карты цветов')
        return [json.loads(m.replace('&quot;', '"')) for m in maps]

    def test_list_row_select_has_colors_of_offered_statuses(self):
        html = self.client.get(reverse('admin:leads_lead_changelist')).content.decode()
        colors = self.colors_in(html)[0]
        self.assertEqual(colors, {str(self.new.pk): '#f59e0b', str(self.work.pk): '#3b82f6'})

    def test_card_select_has_colors(self):
        html = self.client.get(
            reverse('admin:leads_lead_change', args=[self.lead.pk])).content.decode()
        colors = self.colors_in(html)[0]
        self.assertEqual(colors[str(self.work.pk)], '#3b82f6')

    def test_status_script_included(self):
        response = self.client.get(reverse('admin:leads_lead_changelist'))
        self.assertContains(response, 'lead_status.js')
