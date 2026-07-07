(function ($) {
    'use strict';

    var API = '/admin/catalog/product/api/';

    function buildOptions(items, currentVal, emptyLabel) {
        var html = '<option value="">' + emptyLabel + '</option>';
        items.forEach(function (item) {
            var sel = String(item.id) === String(currentVal) ? ' selected' : '';
            html += '<option value="' + item.id + '"' + sel + '>' + item.name + '</option>';
        });
        return html;
    }

    // Обновляем список опций select и, если он обёрнут в Select2, дёргаем change,
    // чтобы Select2 перечитал варианты и текущее значение
    function updateSelect($sel, html) {
        $sel.html(html);
        if ($sel.hasClass('admin-autocomplete') || $sel.next('.select2').length) {
            $sel.trigger('change.select2');
        }
    }

    $(document).on('change', 'select[name="material"]', function () {
        var $sel = $(this);
        var $grade = $('select[name="steel_grade"]');
        if (!$grade.length) return;
        var cur = $grade.val();
        var matId = $sel.val();
        if (!matId) { updateSelect($grade, buildOptions([], null, '---------')); return; }
        $.getJSON(API + 'steel-grades/', { material: matId }, function (data) {
            updateSelect($grade, buildOptions(data, cur, '---------'));
        });
    });

    $(document).on('change', 'select[name="finish"]', function () {
        var $sel = $(this);
        var $color = $('select[name="color"]');
        if (!$color.length) return;
        var cur = $color.val();
        var finId = $sel.val();
        if (!finId) { updateSelect($color, buildOptions([], null, '---------')); return; }
        $.getJSON(API + 'colors/', { finish: finId }, function (data) {
            updateSelect($color, buildOptions(data, cur, '---------'));
        });
    });

}(django.jQuery));
