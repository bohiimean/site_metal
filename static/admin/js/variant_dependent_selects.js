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

    // "variants-0-material" → "variants-0", "material" → ""
    function getPrefix(name) {
        var parts = name.split('-');
        return parts.length >= 3 ? parts.slice(0, -1).join('-') : '';
    }

    function sibling(prefix, field) {
        var name = prefix ? (prefix + '-' + field) : field;
        return $('select[name="' + name + '"]');
    }

    $(document).on('change', 'select[name$="-material"], select[name="material"]', function () {
        var $sel = $(this);
        var prefix = getPrefix($sel.attr('name'));
        var $grade = sibling(prefix, 'steel_grade');
        var cur = $grade.val();
        var matId = $sel.val();
        if (!matId) { $grade.html(buildOptions([], null, '---------')); return; }
        $.getJSON(API + 'steel-grades/', { material: matId }, function (data) {
            $grade.html(buildOptions(data, cur, '---------'));
        });
    });

    $(document).on('change', 'select[name$="-finish"], select[name="finish"]', function () {
        var $sel = $(this);
        var prefix = getPrefix($sel.attr('name'));
        var $color = sibling(prefix, 'color');
        var cur = $color.val();
        var finId = $sel.val();
        if (!finId) { $color.html(buildOptions([], null, '---------')); return; }
        $.getJSON(API + 'colors/', { finish: finId }, function (data) {
            $color.html(buildOptions(data, cur, '---------'));
        });
    });

}(django.jQuery));
