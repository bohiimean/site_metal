# Уникальность override-фото. Отдельно от 0006: создание unique-индексов
# нельзя выполнять в одной транзакции со вставкой строк (pending trigger events).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_merge_color_images'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='productimage',
            constraint=models.UniqueConstraint(
                fields=['product', 'finish', 'color'],
                condition=models.Q(color__isnull=False),
                nulls_distinct=False,
                name='uniq_product_image_finish_color',
                violation_error_message='Фото для этой пары «обработка + цвет» уже есть.',
            ),
        ),
        migrations.AddConstraint(
            model_name='productimage',
            constraint=models.UniqueConstraint(
                fields=['product', 'finish', 'color_group'],
                condition=~models.Q(color_group=''),
                nulls_distinct=False,
                name='uniq_product_image_finish_group',
                violation_error_message='Фото для этой пары «обработка + группа цветов» уже есть.',
            ),
        ),
        migrations.AddConstraint(
            model_name='productimage',
            constraint=models.UniqueConstraint(
                fields=['product', 'finish'],
                condition=models.Q(finish__isnull=False, color__isnull=True, color_group=''),
                name='uniq_product_image_finish_only',
                violation_error_message='Фото для этой обработки (без цвета) уже есть.',
            ),
        ),
    ]
