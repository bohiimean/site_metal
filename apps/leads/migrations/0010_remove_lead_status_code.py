"""Статусы заявок справочником, шаг 3 из 3: убрать зашитый код статуса."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0009_statuses_to_reference'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='lead',
            name='status_code',
        ),
        migrations.AlterField(
            model_name='lead',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Создана'),
        ),
        migrations.AlterField(
            model_name='lead',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Обновлена'),
        ),
    ]
