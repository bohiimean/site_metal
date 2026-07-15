import django_filters

from apps.references.models import Material, SteelGrade, Finish
from .models import Product


class ProductFilter(django_filters.FilterSet):
    material = django_filters.ModelMultipleChoiceFilter(
        queryset=Material.objects.filter(is_active=True),
        field_name='variants__material',
        label='Материал',
    )
    steel_grade = django_filters.ModelMultipleChoiceFilter(
        queryset=SteelGrade.objects.filter(is_active=True),
        field_name='variants__steel_grade',
        label='Марка стали',
    )
    finish = django_filters.ModelMultipleChoiceFilter(
        queryset=Finish.objects.filter(is_active=True),
        field_name='variants__finish',
        label='Обработка',
    )
    size = django_filters.AllValuesMultipleFilter(
        field_name='variants__size',
        label='Размер',
    )
    length = django_filters.AllValuesMultipleFilter(
        field_name='variants__length_m',
        label='Длина',
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='Только в наличии',
        widget=django_filters.widgets.BooleanWidget(),
    )

    class Meta:
        model = Product
        fields = []

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(
                variants__in_stock='in_stock',
                variants__is_active=True,
            )
        return queryset
