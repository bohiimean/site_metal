# Слияние ProductColorImage в ProductImage, шаг 2: перенос строк
# «фото по цвету» в общую таблицу и удаление старой модели.

from django.db import migrations


def copy_color_images(apps, schema_editor):
    ProductImage = apps.get_model('catalog', 'ProductImage')
    ProductColorImage = apps.get_model('catalog', 'ProductColorImage')
    for ci in ProductColorImage.objects.all():
        ProductImage.objects.create(
            product_id=ci.product_id,
            image=ci.image.name,  # файл остаётся на месте (products/colors/)
            color_id=ci.color_id,
            color_group=ci.color_group,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_product_image_finish_color_fields'),
    ]

    operations = [
        migrations.RunPython(copy_color_images, migrations.RunPython.noop),
        migrations.DeleteModel(name='ProductColorImage'),
    ]
