// Окно заметок по заявке поверх страницы админки: колонка «Заметки» в списке
// заявок и кнопка в карточке (ссылки с data-lead-notes). Содержимое окна
// отдаёт LeadAdmin.notes_view — HTML-фрагмент; добавление заметки шлётся
// туда же POST-ом, в ответ приходит обновлённое окно.
(function () {
  var overlay, box, currentUrl;

  function ensureOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.className = 'lead-notes-overlay';
    overlay.hidden = true;
    box = document.createElement('div');
    box.className = 'lead-notes-box';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target.closest('[data-lead-notes-close]')) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !overlay.hidden) close();
    });
  }

  function close() {
    overlay.hidden = true;
    box.innerHTML = '';
    currentUrl = null;
  }

  function show(html) {
    box.innerHTML = html;
    updateButtons();
    var form = box.querySelector('form');
    if (!form) return;
    var textarea = form.querySelector('textarea');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submit(form);
    });
    textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        submit(form);
      }
    });
    textarea.focus();
    var scroll = box.querySelector('.lead-notes__scroll');
    if (scroll) scroll.scrollTop = scroll.scrollHeight;
  }

  function updateButtons() {
    var root = box.querySelector('[data-summary]');
    if (!root || !currentUrl) return;
    document.querySelectorAll('[data-lead-notes="' + currentUrl + '"]').forEach(function (a) {
      if (a.dataset.notesLabel === 'card') {
        a.textContent = '💬 Открыть заметки (' + root.dataset.count + ')';
      } else {
        a.textContent = root.dataset.summary;
        a.title = root.dataset.lastText || '';
      }
    });
  }

  function load(url, options) {
    return fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}))
      .then(function (r) { return r.text(); })
      .then(show)
      .catch(function () {
        box.innerHTML = '<div class="lead-notes"><p class="lead-notes__error">' +
          'Не удалось загрузить заметки. Обновите страницу.</p></div>';
      });
  }

  function submit(form) {
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    load(currentUrl, { method: 'POST', body: new FormData(form) });
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('[data-lead-notes]');
    if (!link) return;
    e.preventDefault();
    ensureOverlay();
    currentUrl = link.dataset.leadNotes;
    box.innerHTML = '<div class="lead-notes"><p class="lead-notes__empty">Загрузка…</p></div>';
    overlay.hidden = false;
    load(currentUrl);
  });
})();
