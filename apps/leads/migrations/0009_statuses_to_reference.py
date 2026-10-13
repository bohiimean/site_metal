"""Статусы заявок справочником, шаг 2 из 3: стартовые статусы и перенос.

«Закрыта» по просьбе заказчика называется «Выполнена». Статусы создаются
всегда, даже на пустой базе: без статуса «для новых» заявке нечего присвоить.
Обратный ход: заявки со своими (новыми) статусами возвращаются в «Новые».
"""
from django.db import migrations

# code → (название, цвет, порядок, для новых)
INITIAL = [
    ('new',         'Новая',     '#f59e0b', 1, True),
    ('in_progress', 'В работе',  '#3b82f6', 2, False),
    ('closed',      'Выполнена', '#10b981', 3, False),
]


def forwards(apps, schema_editor):
    LeadStatus = apps.get_model('leads', 'LeadStatus')
    Lead = apps.get_model('leads', 'Lead')
    for code, name, color, order, is_default in INITIAL:
        status = LeadStatus.objects.create(
            name=name, color=color, sort_order=order, is_default=is_default)
        Lead.objects.filter(status_code=code).update(status_id=status.pk)
    # Неизвестные коды (не должно быть, но мало ли) — в «Новые»
    default = LeadStatus.objects.get(is_default=True)
    Lead.objects.filter(status__isnull=True).update(status_id=default.pk)


def backwards(apps, schema_editor):
    LeadStatus = apps.get_model('leads', 'LeadStatus')
    Lead = apps.get_model('leads', 'Lead')
    code_by_name = {name: code for code, name, *_ in INITIAL}
    for status in LeadStatus.objects.all():
        Lead.objects.filter(status_id=status.pk).update(
            status_code=code_by_name.get(status.name, 'new'))


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0008_leadstatus_leadnote'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
