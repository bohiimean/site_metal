# Удаление вариантной модели — данные перенесены в дерево опций (0012)
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_variants_to_option_tree'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='productvariant',
            name='finish',
        ),
        migrations.RemoveField(
            model_name='productvariant',
            name='material',
        ),
        migrations.RemoveField(
            model_name='productvariant',
            name='product',
        ),
        migrations.RemoveField(
            model_name='productvariant',
            name='steel_grade',
        ),
        migrations.DeleteModel(
            name='ProductVariant',
        ),
    ]
