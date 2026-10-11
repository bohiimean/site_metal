"""Справочник параметров, шаг 1 из 3: новые таблицы и поля рядом со старыми.

Старые поля ProductParamValue (product, kind) становятся необязательными на
время переноса — так миграции можно откатить: при откате 0022 они
возвращаются пустыми, 0021 их заполняет, и только потом здесь снова NOT NULL.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0019_product_image_angles'),
        ('references', '0012_parameter'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductParameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allow_custom', models.BooleanField(default=False, help_text='Покупатель может указать своё значение — его проверит менеджер', verbose_name='Своё значение')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('parameter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='product_links', to='references.parameter', verbose_name='Параметр')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parameters', to='catalog.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Параметр товара',
                'verbose_name_plural': 'Параметры товара',
                'ordering': ['sort_order', 'id'],
                'constraints': [models.UniqueConstraint(fields=('product', 'parameter'), name='uniq_product_parameter', violation_error_message='Этот параметр у товара уже есть.')],
            },
        ),
        migrations.AddField(
            model_name='productparamvalue',
            name='product_parameter',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='values', to='catalog.productparameter', verbose_name='Параметр товара'),
        ),
        migrations.AlterField(
            model_name='productparamvalue',
            name='product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='param_values', to='catalog.product', verbose_name='Товар'),
        ),
        migrations.AlterField(
            model_name='productparamvalue',
            name='kind',
            field=models.CharField(choices=[('size', 'Размер'), ('length', 'Длина'), ('height', 'Высота')], max_length=10, null=True, verbose_name='Параметр'),
        ),
        migrations.AddField(
            model_name='categoryfacet',
            name='parameter',
            field=models.ForeignKey(blank=True, help_text='Только для фильтра «Параметр»', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='facets', to='references.parameter', verbose_name='Параметр'),
        ),
        migrations.AlterField(
            model_name='categoryfacet',
            name='facet',
            field=models.CharField(choices=[('material', 'Материал'), ('steel_grade', 'Марка стали'), ('finish', 'Обработка'), ('color', 'Цвет'), ('param', 'Параметр'), ('in_stock', 'Только в наличии')], max_length=20, verbose_name='Фильтр'),
        ),
        migrations.AlterUniqueTogether(
            name='categoryfacet',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='categoryfacet',
            constraint=models.UniqueConstraint(condition=models.Q(('facet', 'param'), _negated=True), fields=('category', 'facet'), name='uniq_category_facet', violation_error_message='Такой фильтр в разделе уже есть.'),
        ),
        migrations.AddConstraint(
            model_name='categoryfacet',
            constraint=models.UniqueConstraint(condition=models.Q(('facet', 'param')), fields=('category', 'parameter'), name='uniq_category_param_facet', violation_error_message='Фильтр по этому параметру в разделе уже есть.'),
        ),
    ]
