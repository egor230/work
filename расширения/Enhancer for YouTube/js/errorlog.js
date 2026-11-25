'use strict';

/** Просмотр лога ошибок (html/errorlog.html). */
(() => {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmt(at) {
    try { return new Date(at).toLocaleString('ru-RU'); } catch (e) { return String(at); }
  }

  const list = document.getElementById('list');
  const status = document.getElementById('status');

  function setStatus(msg) { if (status) status.textContent = msg; }

  function render() {
    chrome.storage.local.get({ errorlog: [] }, function (res) {
      const entries = Array.isArray(res.errorlog) ? res.errorlog : [];
      if (!entries.length) {
        list.className = 'empty';
        list.textContent = 'Ошибок пока нет. Если видео не загрузится — запись появится здесь автоматически.';
        setStatus('записей: 0');
        return;
      }
      list.className = '';
      list.innerHTML = entries.map(function (e) {
        const head = [e.kind, e.code].filter(Boolean).join(' · ') || 'ошибка';
        const meta = [fmt(e.at), e.title, e.videoId ? 'id: ' + e.videoId : '',
                      e.source, e.url].filter(Boolean).join(' | ');
        return '<div class="entry">' +
          '<div class="head">' + esc(head) + '</div>' +
          '<div class="msg">' + esc(e.message || '(без сообщения)') + '</div>' +
          '<div class="meta">' + esc(meta) + '</div>' +
          (e.src ? '<div class="meta">src: <code>' + esc(e.src) + '</code></div>' : '') +
          '</div>';
      }).join('');
      setStatus('записей: ' + entries.length + ' (повторы не сохраняются)');
    });
  }

  document.getElementById('refresh').addEventListener('click', render);

  document.getElementById('export').addEventListener('click', function () {
    chrome.runtime.sendMessage({ request: 'efyt-error-sync' }, function () {
      setStatus('JSON записан в папку расширения / Загрузки');
    });
  });

  document.getElementById('clear').addEventListener('click', function () {
    if (!window.confirm('Очистить лог ошибок?')) return;
    chrome.storage.local.set({ errorlog: [] }, function () {
      chrome.runtime.sendMessage({ request: 'efyt-error-sync' });
      render();
    });
  });

  render();
})();
