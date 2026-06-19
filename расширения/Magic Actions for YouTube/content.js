'use strict';

(function () {
  var html = document.documentElement;
  var STORAGE_KEY = 'maTheme';
  var currentTheme = null;

  function applyTheme(theme) {
    currentTheme = theme;

    html.classList.remove('__ytnight', '__ytday');

    if (theme === 'dark') {
      html.classList.add('__ytnight');
      html.setAttribute('dark', 'true');
    } else {
      html.classList.add('__ytday');
      html.removeAttribute('dark');
    }

    syncCookie(theme);
  }

  function syncCookie(theme) {
    try {
      var match = document.cookie.match(/PREF=([^;]*)/);
      var params = new URLSearchParams(match ? match[1] : '');
      params.set('f6', theme === 'dark' ? '400' : '80000');
      document.cookie = 'PREF=' + params.toString() +
        ';max-age=22592000;path=/;domain=.youtube.com';
    } catch (e) {
      // Игнорируем ошибки cookie
    }
  }

  function getTheme(callback) {
    if (currentTheme) {
      callback(currentTheme);
      return;
    }
    chrome.storage.local.get([STORAGE_KEY], function (result) {
      var theme = result[STORAGE_KEY] || 'light';
      currentTheme = theme;
      callback(theme);
    });
  }

  function setTheme(theme, callback) {
    chrome.storage.local.set({ maTheme: theme }, callback || function () {});
  }

  function toggleTheme() {
    getTheme(function (current) {
      var next = current === 'dark' ? 'light' : 'dark';
      setTheme(next);
    });
  }

  function updateToggleIcon(theme) {
    var sw = document.getElementById('__magic-theme-switch');
    if (sw) {
      sw.classList.toggle('dark', theme === 'dark');
    }
  }

  chrome.storage.onChanged.addListener(function (changes, area) {
    if (area === 'local' && STORAGE_KEY in changes) {
      var theme = changes[STORAGE_KEY].newValue;
      applyTheme(theme);
      updateToggleIcon(theme);
    }
  });

  function createToggle() {
    if (document.getElementById('__magic-theme-switch')) return;

    var sw = document.createElement('div');
    sw.id = '__magic-theme-switch';
    sw.setAttribute('tabindex', '0');
    sw.setAttribute('role', 'button');
    sw.setAttribute('aria-label', 'Переключить тему YouTube');

    getTheme(function (theme) {
      if (theme === 'dark') sw.classList.add('dark');
    });

    sw.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleTheme();
    }, true);

    sw.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      e.stopPropagation();
    }, true);

    function appendToggle() {
      if (document.body && !document.getElementById('__magic-theme-switch')) {
        document.body.appendChild(sw);
      }
    }

    if (document.body) {
      appendToggle();
    } else {
      var observer = new MutationObserver(function () {
        if (document.body) {
          appendToggle();
          observer.disconnect();
        }
      });
      observer.observe(html, { childList: true });
    }
  }

  getTheme(function (theme) {
    applyTheme(theme);
    updateToggleIcon(theme);
  });
  createToggle();

  document.addEventListener('yt-navigate-finish', function () {
    getTheme(function (theme) {
      applyTheme(theme);
      updateToggleIcon(theme);
    });
    createToggle();
  });
})();
