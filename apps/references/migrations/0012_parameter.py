from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('references', '0011_alter_color_color_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='Parameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название')),
                ('unit', models.CharField(blank=True, help_text='Подставляется после значения на сайте: «м», «мм». Пусто — значение без единицы (например «20×20»).', max_length=20, verbose_name='Единица')),
                ('custom_label', models.CharField(blank=True, help_text='Кнопка на карточке, если товару разрешено своё значение: «Своя длина», «Свой размер». Пусто — «Своё значение».', max_length=100, verbose_name='Подпись своего значения')),
                ('example', models.CharField(blank=True, help_text='Подсказка в поле ввода: «2.7», «20×20».', max_length=50, verbose_name='Пример значения')),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='Порядок в списке выбора на странице товара.', verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Параметр',
                'verbose_name_plural': 'Параметры товаров',
                'ordering': ['sort_order', 'name'],
            },
        ),
    ]
