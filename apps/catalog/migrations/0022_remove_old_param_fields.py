"""Справочник параметров, шаг 3 из 3: убрать зашитые size / length / height."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0021_params_to_reference'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='productparamvalue',
            name='uniq_product_param_value',
        ),
        migrations.RemoveField(
            model_name='productparamvalue',
            name='product',
        ),
        migrations.RemoveField(
            model_name='productparamvalue',
            name='kind',
        ),
        migrations.AlterField(
            model_name='productparamvalue',
            name='product_parameter',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='catalog.productparameter', verbose_name='Параметр товара'),
        ),
        migrations.AlterField(
            model_name='productparamvalue',
            name='value',
            field=models.CharField(max_length=50, verbose_name='Значение'),
        ),
        migrations.AlterModelOptions(
            name='productparamvalue',
            options={'ordering': ['sort_order', 'id'], 'verbose_name': 'Значение параметра', 'verbose_name_plural': 'Значения параметра'},
        ),
        migrations.AddConstraint(
            model_name='productparamvalue',
            constraint=models.UniqueConstraint(fields=('product_parameter', 'value'), name='uniq_product_param_value', violation_error_message='Такое значение у этого параметра уже есть.'),
        ),
        migrations.RemoveField(
            model_name='product',
            name='allow_custom_size',
        ),
        migrations.RemoveField(
            model_name='product',
            name='allow_custom_length',
        ),
        migrations.RemoveField(
            model_name='product',
            name='allow_custom_height',
        ),
    ]
