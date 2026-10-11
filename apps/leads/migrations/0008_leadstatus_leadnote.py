"""Статусы заявок справочником, шаг 1 из 3: новые таблицы, старый статус
переименован в status_code (уйдёт в 0010) и рядом — ссылка на справочник."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0007_cart_snapshot_params'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='Название')),
                ('color', models.CharField(default='#6b7280', help_text='HEX-цвет метки статуса, например #3b82f6', max_length=7, verbose_name='Цвет')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_default', models.BooleanField(default=False, help_text='Этот статус получает каждая новая заявка с сайта. Может быть только один — отметка снимется с прежнего.', verbose_name='Для новых заявок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Статус заявки',
                'verbose_name_plural': 'Статусы заявок',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RenameField(
            model_name='lead',
            old_name='status',
            new_name='status_code',
        ),
        migrations.AddField(
            model_name='lead',
            name='status',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='leads', to='leads.leadstatus', verbose_name='Статус'),
        ),
        migrations.CreateModel(
            name='LeadNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_name', models.CharField(blank=True, max_length=150, verbose_name='Имя автора')),
                ('kind', models.CharField(choices=[('note', 'Заметка'), ('status', 'Смена статуса')], default='note', max_length=10, verbose_name='Тип')),
                ('text', models.TextField(verbose_name='Текст')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Когда')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='leads.lead', verbose_name='Заявка')),
            ],
            options={
                'verbose_name': 'Заметка по заявке',
                'verbose_name_plural': 'Заметки по заявке',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
