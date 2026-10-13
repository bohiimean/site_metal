"""Перенос зашитых статусов заявок (new / in_progress / closed) в справочник."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('leads', '0007_cart_snapshot_params')]


def latest():
    graph = MigrationExecutor(connection).loader.graph
    return [n for n in graph.leaf_nodes() if n[0] == 'leads']


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class StatusMigrationTests(TransactionTestCase):
    def tearDown(self):
        migrate(latest())

    def test_forward_maps_old_codes_to_reference(self):
        old = migrate(BEFORE)
        Lead = old.get_model('leads', 'Lead')
        ids = {
            code: Lead.objects.create(name=code, phone='1', status=code).pk
            for code in ('new', 'in_progress', 'closed')
        }

        new = migrate(latest())
        Lead = new.get_model('leads', 'Lead')
        self.assertEqual(Lead.objects.get(pk=ids['new']).status.name, 'Новая')
        self.assertEqual(Lead.objects.get(pk=ids['in_progress']).status.name, 'В работе')
        self.assertEqual(Lead.objects.get(pk=ids['closed']).status.name, 'Выполнена')

    def test_backward_restores_codes(self):
        new = migrate(latest())
        LeadStatus = new.get_model('leads', 'LeadStatus')
        Lead = new.get_model('leads', 'Lead')
        work, _ = LeadStatus.objects.get_or_create(
            name='В работе', defaults={'sort_order': 2, 'color': '#3b82f6'})
        custom = LeadStatus.objects.create(name='Ждёт оплаты', sort_order=5)
        a = Lead.objects.create(name='a', phone='1', status=work).pk
        b = Lead.objects.create(name='b', phone='1', status=custom).pk

        old = migrate(BEFORE)
        Lead = old.get_model('leads', 'Lead')
        self.assertEqual(Lead.objects.get(pk=a).status, 'in_progress')
        # Своего статуса в старой схеме нет — заявка возвращается в «Новые»,
        # а не теряется
        self.assertEqual(Lead.objects.get(pk=b).status, 'new')
