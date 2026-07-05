from django.db import models


class Material(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Slug', max_length=100, unique=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['name']

    def __str__(self):
        return self.name


class SteelGrade(models.Model):
    name = models.CharField('Марка', max_length=100)
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        related_name='steel_grades',
        verbose_name='Материал',
    )
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Марка стали'
        verbose_name_plural = 'Марки стали'
        ordering = ['material', 'name']

    def __str__(self):
        return f'{self.name} ({self.material})'


class Finish(models.Model):
    name = models.CharField('Название', max_length=100)
    slug = models.SlugField('Slug', max_length=100, unique=True)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Обработка'
        verbose_name_plural = 'Обработки'
        ordering = ['name']

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField('Название', max_length=100)
    hex_code = models.CharField('HEX-код', max_length=7, blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Цвет'
        verbose_name_plural = 'Цвета'
        ordering = ['name']

    def __str__(self):
        return self.name


class FinishColor(models.Model):
    finish = models.ForeignKey(
        Finish, on_delete=models.CASCADE,
        related_name='finish_colors',
        verbose_name='Обработка',
    )
    color = models.ForeignKey(
        Color, on_delete=models.CASCADE,
        related_name='finish_colors',
        verbose_name='Цвет',
    )

    class Meta:
        verbose_name = 'Цвет обработки'
        verbose_name_plural = 'Цвета обработок'
        unique_together = [('finish', 'color')]

    def __str__(self):
        return f'{self.finish} — {self.color}'
