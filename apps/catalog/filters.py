import re

import django_filters
from django.db.models import Q

from apps.references.models import Material, SteelGrade, Finish, Color, Parameter
from .models import Product

# GET-ключ фильтра по параметру справочника: p<id> (Parameter.filter_key)
PARAM_KEY = re.compile(r'^p(\d+)$')


class ProductFilter(django_filters.FilterSet):
    material = django_filters.ModelMultipleChoiceFilter(
        queryset=Material.objects.filter(is_active=True),
        field_name='option_nodes__material',
        label='Материал',
    )
    color = django_filters.ModelMultipleChoiceFilter(
        queryset=Color.objects.filter(is_active=True),
        method='filter_color',
        label='Цвет',
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
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='Только в наличии',
        widget=django_filters.widgets.BooleanWidget(),
    )

    class Meta:
        model = Product
        fields = []

    def filter_color(self, queryset, name, value):
        # Цвет доступен, если он в ручном наборе обработки ИЛИ в её палитре
        if value:
            return queryset.filter(
                Q(option_nodes__colors__in=value)
                | Q(option_nodes__palette__colors__in=value)
            )
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return self._filter_params(queryset)

    def _filter_params(self, queryset):
        """Фильтры по параметрам справочника: ?p3=20&p3=40&p5=3.

        Набор параметров заранее не известен, поэтому они не объявлены полями
        FilterSet, а разбираются из GET напрямую. Внутри параметра значения —
        «или», между параметрами — «и». Условия параметра и значения стоят в
        одном filter(): Django берёт для них один join, и «3» ширины не
        засчитывается за «3» длины. Выключенный параметр не фильтрует.
        """
        data = self.data or {}
        wanted = {}
        for key in data:
            m = PARAM_KEY.match(key)
            if not m:
                continue
            values = data.getlist(key) if hasattr(data, 'getlist') else [data[key]]
            values = [v for v in values if v]
            if values:
                wanted[int(m.group(1))] = values
        if not wanted:
            return queryset
        for parameter in Parameter.objects.filter(pk__in=wanted, is_active=True):
            queryset = queryset.filter(
                parameters__parameter=parameter,
                parameters__values__value__in=wanted[parameter.pk],
            )
        return queryset

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(in_stock='in_stock')
        return queryset
