// Полоса цвета у селекта статуса заявки: перекрашивается сразу при выборе,
// не дожидаясь сохранения. Цвета — из data-status-colors (LeadStatusFieldMixin).
(function () {
  function paint(select) {
    var colors;
    try { colors = JSON.parse(select.dataset.statusColors || '{}'); } catch (e) { return; }
    var color = colors[select.value];
    select.style.borderLeft = color ? '6px solid ' + color : '';
  }

  document.addEventListener('change', function (e) {
    if (e.target.matches && e.target.matches('select[data-status-colors]')) paint(e.target);
  });
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('select[data-status-colors]').forEach(paint);
  });
})();
