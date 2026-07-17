import django_filters

from apps.references.models import Material, SteelGrade, Finish
from .models import Product


class ProductFilter(django_filters.FilterSet):
    material = django_filters.ModelMultipleChoiceFilter(
        queryset=Material.objects.filter(is_active=True),
        field_name='option_nodes__material',
        label='Материал',
    )
    steel_grade = django_filters.ModelMultipleChoiceFilter(
        queryset=SteelGrade.objects.filter(is_active=True),
        field_name='option_nodes__steel_grade',
        label='Марка стали',
    )
    finish = django_filters.ModelMultipleChoiceFilter(
        queryset=Finish.objects.filter(is_active=True),
        field_name='option_nodes__finish',
        label='Обработка',
    )
    size = django_filters.MultipleChoiceFilter(
        method='filter_param_value',
        label='Размер',
    )
    length = django_filters.MultipleChoiceFilter(
        method='filter_param_value',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Choices размер/длина — реальные значения параметров товаров выборки
        # (queryset уже сужен до раздела каталога)
        from .models import ProductParamValue
        for key in ('size', 'length'):
            values = (
                ProductParamValue.objects
                .filter(kind=key, product__in=self.queryset.values('pk'))
                .values_list('value', flat=True)
                .distinct()
            )
            self.filters[key].extra['choices'] = [(v, v) for v in values]

    def filter_param_value(self, queryset, name, value):
        if value:
            return queryset.filter(
                param_values__kind=name,
                param_values__value__in=value,
            )
        return queryset

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(in_stock='in_stock')
        return queryset
