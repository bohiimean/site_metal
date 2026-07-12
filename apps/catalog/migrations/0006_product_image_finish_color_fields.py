# Слияние ProductColorImage в ProductImage, шаг 1: новые поля.
# Перенос данных и удаление старой модели — в 0007 (FK-индексы создаются
# отложенно в конце миграции и конфликтуют со вставкой строк в ней же).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('references', '0004_alter_material_image'),
        ('catalog', '0005_alter_category_image_alter_productcolorimage_image_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='productimage',
            name='finish',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='references.finish',
                verbose_name='Обработка',
                help_text='Фото для этой обработки',
            ),
        ),
        migrations.AddField(
            model_name='productimage',
            name='color',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='references.color',
                verbose_name='Цвет',
                help_text='Фото под конкретный цвет',
            ),
        ),
        migrations.AddField(
            model_name='productimage',
            name='color_group',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('white', 'Белые'),
                    ('gray', 'Серые'),
                    ('black', 'Чёрные'),
                    ('brown', 'Коричневые'),
                    ('blue', 'Синие'),
                    ('green', 'Зелёные'),
                    ('metallic', 'Металлик'),
                    ('other', 'Другие'),
                ],
                verbose_name='Группа цветов',
                help_text='Или одно фото на всю группу (синие, серые, …)',
            ),
            preserve_default=False,
        ),
    ]
