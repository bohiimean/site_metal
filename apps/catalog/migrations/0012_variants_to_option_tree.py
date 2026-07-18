# Перенос данных вариантной модели в дерево опций:
# уникальные комбинации материал/марка/обработка вариантов → узлы;
# размеры/длины/высоты → значения свободных параметров;
# палитры марок/материалов (SteelGradeColor/MaterialColor) → цвета на
# узле-обработке; наличие и флаги «свой размер/длина» — на товар.
# Работает до удаления ProductVariant (0013) и палитр (references 0008).
from django.db import migrations


def _trim(dec):
    s = str(dec)
    return s.rstrip('0').rstrip('.') if '.' in s else s


def forwards(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    Variant = apps.get_model('catalog', 'ProductVariant')
    Node = apps.get_model('catalog', 'ProductOptionNode')
    Param = apps.get_model('catalog', 'ProductParamValue')
    GradeColor = apps.get_model('references', 'SteelGradeColor')
    MatColor = apps.get_model('references', 'MaterialColor')

    grade_colors, mat_colors = {}, {}
    for gc in GradeColor.objects.all():
        grade_colors.setdefault(gc.steel_grade_id, []).append(gc.color_id)
    for mc in MatColor.objects.all():
        mat_colors.setdefault(mc.material_id, []).append(mc.color_id)

    for product in Product.objects.all():
        variants = list(
            Variant.objects.filter(product=product, is_active=True).order_by('sku')
        )
        if not variants:
            continue

        stocks = {v.in_stock for v in variants}
        if 'in_stock' in stocks:
            product.in_stock = 'in_stock'
        elif 'on_order' in stocks:
            product.in_stock = 'on_order'
        else:
            product.in_stock = 'out_of_stock'
        product.allow_custom_size = any(v.allow_custom_size for v in variants)
        product.allow_custom_length = any(v.allow_custom_length for v in variants)
        product.save(update_fields=[
            'in_stock', 'allow_custom_size', 'allow_custom_length',
        ])

        m_nodes, g_nodes, f_nodes = {}, {}, {}
        params = {'size': [], 'length': [], 'height': []}
        for v in variants:
            m_node = m_nodes.get(v.material_id)
            if m_node is None:
                m_node = Node.objects.create(
                    product=product, node_type='material',
                    material_id=v.material_id, sort_order=len(m_nodes),
                )
                m_nodes[v.material_id] = m_node

            parent = m_node
            if v.steel_grade_id:
                g_key = (v.material_id, v.steel_grade_id)
                parent = g_nodes.get(g_key)
                if parent is None:
                    parent = Node.objects.create(
                        product=product, parent=m_node, node_type='steel_grade',
                        steel_grade_id=v.steel_grade_id, sort_order=len(g_nodes),
                    )
                    g_nodes[g_key] = parent

            if v.finish_id:
                f_key = (parent.pk, v.finish_id)
                f_node = f_nodes.get(f_key)
                if f_node is None:
                    f_node = Node.objects.create(
                        product=product, parent=parent, node_type='finish',
                        finish_id=v.finish_id, sort_order=len(f_nodes),
                    )
                    colors = (grade_colors.get(v.steel_grade_id)
                              or mat_colors.get(v.material_id) or [])
                    if colors:
                        f_node.colors.set(colors)
                    f_nodes[f_key] = f_node

            if v.size and v.size not in params['size']:
                params['size'].append(v.size)
            if v.length_m is not None:
                length = _trim(v.length_m)
                if length not in params['length']:
                    params['length'].append(length)
            if v.height_mm is not None:
                height = _trim(v.height_mm)
                if height not in params['height']:
                    params['height'].append(height)

        for kind, values in params.items():
            for order, value in enumerate(values):
                Param.objects.get_or_create(
                    product=product, kind=kind, value=value,
                    defaults={'sort_order': order},
                )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_productoptionnode_productparamvalue_and_more'),
        ('references', '0007_materialcolor'),
    ]
    run_before = [
        ('references', '0008_alter_steelgradecolor_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
