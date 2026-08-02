'use strict';

(function () {
  var html = document.documentElement;
  var STORAGE_KEY = 'maTheme';
  var RELOAD_FLAG = 'maThemeReloaded';
  var currentTheme = null;

  function getThemeFromCookie() {
    try {
      var match = document.cookie.match(/PREF=([^;]*)/);
      var params = new URLSearchParams(match ? match[1] : '');
      if (params.get('f6') === '400') return 'dark';
    } catch (e) {}
    return 'light';
  }

  function syncCookie(theme) {
    try {
      var match = document.cookie.match(/PREF=([^;]*)/);
      var params = new URLSearchParams(match ? match[1] : '');
      params.set('f6', theme === 'dark' ? '400' : '8');
      document.cookie = 'PREF=' + params.toString() +
        ';max-age=22592000;path=/;domain=.youtube.com';
    } catch (e) {}
  }

  function setLock(theme) {
    html.setAttribute('data-ma-theme', theme === 'dark' ? 'dark' : 'light');
  }

  function updateToggleIcon(theme) {
    var sw = document.getElementById('__magic-theme-switch');
    if (sw) {
      sw.classList.toggle('dark', theme === 'dark');
    }
  }

  function applyTheme(theme, options) {
    options = options || {};
    currentTheme = theme;

    html.classList.remove('__ytnight', '__ytday');
    setLock(theme);

    if (theme === 'dark') {
      html.classList.add('__ytnight');
      html.setAttribute('dark', 'true');
    } else {
      html.classList.add('__ytday');
      html.removeAttribute('dark');
    }

    syncCookie(theme);
    updateToggleIcon(theme);

    if (options.reload) {
      location.reload();
    }
  }

  function toggleTheme() {
    var next = currentTheme === 'dark' ? 'light' : 'dark';
    chrome.storage.local.set({ maTheme: next });
  }

  function createToggle() {
    if (document.getElementById('__magic-theme-switch')) return;

    var sw = document.createElement('div');
    sw.id = '__magic-theme-switch';
    sw.setAttribute('tabindex', '0');
    sw.setAttribute('role', 'button');
    sw.setAttribute('aria-label', 'Переключить тему YouTube');
    if (currentTheme === 'dark') sw.classList.add('dark');

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

  var syncTheme = getThemeFromCookie();
  applyTheme(syncTheme, { reload: false });

  chrome.storage.local.get([STORAGE_KEY], function (result) {
    var stored = result[STORAGE_KEY];

    if (stored === undefined || stored === null || stored === '') {
      chrome.storage.local.set({ maTheme: syncTheme });
      return;
    }

    if (stored !== syncTheme) {
      if (sessionStorage.getItem(RELOAD_FLAG)) {
        applyTheme(stored, { reload: false });
      } else {
        sessionStorage.setItem(RELOAD_FLAG, '1');
        applyTheme(stored, { reload: true });
      }
    }
  });

  chrome.storage.onChanged.addListener(function (changes, area) {
    if (area !== 'local') return;
    if (!(STORAGE_KEY in changes)) return;
    var next = changes[STORAGE_KEY].newValue || 'light';
    applyTheme(next, { reload: true });
  });

  document.addEventListener('yt-navigate-finish', function () {
    chrome.storage.local.get([STORAGE_KEY], function (result) {
      applyTheme(result[STORAGE_KEY] || getThemeFromCookie(), { reload: false });
    });
  });

  createToggle();
})();
