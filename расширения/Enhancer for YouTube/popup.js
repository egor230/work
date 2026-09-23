'use strict';

document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;

  function render(theme) {
    btn.classList.toggle('dark', theme === 'dark');
  }

  chrome.storage.local.get(['maTheme'], function (result) {
    render(result.maTheme || 'light');
  });

  btn.addEventListener('click', function () {
    chrome.storage.local.get(['maTheme'], function (result) {
      var next = result.maTheme === 'dark' ? 'light' : 'dark';
      chrome.storage.local.set({ maTheme: next });
      render(next);
    });
  });

  var opts = document.getElementById('open-options');
  if (opts) {
    opts.addEventListener('click', function () {
      chrome.runtime.sendMessage({ request: 'open-options' });
      window.close();
    });
  }

  // === efyt-backup: save/restore ===
  var status = document.getElementById('backup-status');
  function setStatus(msg) {
    if (status) status.textContent = msg;
  }

  var saveBtn = document.getElementById('save-backup');
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      chrome.runtime.sendMessage({ request: 'efyt-backup-save' }, function (res) {
        if (res && res.ok) setStatus('Сохранено: ' + res.file);
        else setStatus('Ошибка: ' + (res ? res.error : 'нет ответа'));
      });
    });
  }

  var restoreBtn = document.getElementById('restore-backup');
  if (restoreBtn) {
    restoreBtn.addEventListener('click', function () {
      chrome.runtime.sendMessage({ request: 'efyt-backup-restore' }, function (res) {
        if (res && res.ok) {
          setStatus('Восстановлено: ' + res.keys.length + ' ключей. Перезагрузите вкладки YouTube.');
          setTimeout(function () { setStatus('тема + скорость по каналам'); }, 4000);
        } else {
          setStatus('Ошибка: ' + (res ? res.error : 'нет ответа'));
        }
      });
    });
  }
});
