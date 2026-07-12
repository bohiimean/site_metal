from django.forms.widgets import CheckboxSelectMultiple
from django.utils.html import mark_safe


GROUP_LABELS = {
    'white':    'Белые',
    'gray':     'Серые',
    'black':    'Чёрные',
    'brown':    'Коричневые',
    'blue':     'Синие',
    'green':    'Зелёные',
    'metallic': 'Металлик',
    'other':    'Другие',
    '':         'Без группы',
}

GROUP_ORDER = ['white', 'gray', 'black', 'brown', 'blue', 'green', 'metallic', 'other', '']


class GroupedColorCheckboxWidget(CheckboxSelectMultiple):
    """
    Чекбоксы цветов, сгруппированные по color_group, со свотчами.
    Совместим со стандартным Django admin и кастомными темами (Unfold, Jazzmmin):
    рендерит чистый HTML без внешних зависимостей.
    """

    def render(self, name, value, attrs=None, renderer=None):
        from .models import Color

        selected_ids = set()
        for v in (value or []):
            try:
                selected_ids.add(int(v))
            except (TypeError, ValueError):
                pass

        colors = Color.objects.filter(is_active=True).order_by('color_group', 'name')

        groups: dict[str, list] = {}
        for color in colors:
            key = color.color_group or ''
            groups.setdefault(key, []).append(color)

        picker_id = f'grouped-colors-{name}'
        btn_style = (
            'font-size:11px;padding:3px 10px;border:1px solid #d1d5db;'
            'border-radius:6px;background:transparent;color:#888;cursor:pointer;'
        )
        lines = [
            f'<div id="{picker_id}">',
            f'<div style="display:flex;gap:8px;margin-top:6px;">'
            f'<button type="button" data-check-all style="{btn_style}">Выбрать все</button>'
            f'<button type="button" data-uncheck-all style="{btn_style}">Снять все</button>'
            f'</div>',
            '<div style="display:flex;flex-wrap:wrap;gap:20px 28px;margin-top:12px;">',
        ]

        for key in GROUP_ORDER:
            if key not in groups:
                continue
            label = GROUP_LABELS.get(key, key)
            lines.append(
                f'<div style="min-width:160px;" data-color-group>'
                f'<p style="font-size:11px;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:.06em;color:#888;margin:0 0 6px;">{label} '
                f'<button type="button" data-group-toggle '
                f'style="border:0;padding:0;background:none;color:#4f8ef7;'
                f'font-size:10px;text-transform:none;letter-spacing:0;cursor:pointer;">все</button></p>'
                f'<div style="display:flex;flex-direction:column;gap:5px;">'
            )
            for color in groups[key]:
                checked = 'checked' if color.pk in selected_ids else ''
                bg = color.hex_code if color.hex_code else '#cccccc'
                ral = f' <span style="color:#aaa;font-size:10px;">({color.ral_code})</span>' if color.ral_code else ''
                lines.append(
                    f'<label style="display:flex;align-items:center;gap:7px;cursor:pointer;">'
                    f'<input type="checkbox" name="{name}" value="{color.pk}" {checked} '
                    f'style="margin:0;cursor:pointer;">'
                    f'<span style="width:14px;height:14px;border-radius:50%;flex-shrink:0;'
                    f'background:{bg};border:1px solid rgba(0,0,0,.15);display:inline-block;"></span>'
                    f'<span style="font-size:12px;">{color.name}{ral}</span>'
                    f'</label>'
                )
            lines.append('</div></div>')

        lines.append('</div></div>')
        lines.append(
            f'''<script>
(function() {{
  var root = document.getElementById('{picker_id}');
  if (!root) return;
  function setAll(scope, state) {{
    scope.querySelectorAll('input[type=checkbox]').forEach(function(cb) {{ cb.checked = state; }});
  }}
  root.querySelector('[data-check-all]').addEventListener('click', function() {{ setAll(root, true); }});
  root.querySelector('[data-uncheck-all]').addEventListener('click', function() {{ setAll(root, false); }});
  root.querySelectorAll('[data-group-toggle]').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var grp = btn.closest('[data-color-group]');
      var cbs = grp.querySelectorAll('input[type=checkbox]');
      var anyUnchecked = Array.prototype.some.call(cbs, function(cb) {{ return !cb.checked; }});
      setAll(grp, anyUnchecked);
    }});
  }});
}})();
</script>'''
        )
        return mark_safe(''.join(lines))

    def value_from_datadict(self, data, files, name):
        return data.getlist(name)
