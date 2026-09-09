'use strict';

(function () {
  var STORAGE_KEY = 'maTheme';
  var currentTheme = null;

  function getCookieParams() {
    try {
      var match = document.cookie.match(/PREF=([^;]*)/);
      return new URLSearchParams(match ? match[1] : '');
    } catch (e) {
      return new URLSearchParams('');
    }
  }

  function getThemeFromCookie() {
    var html = document.documentElement;
    var f6 = getCookieParams().get('f6');
    if (f6 !== null && f6 !== '') {
      return f6.charAt(0) === '4' ? 'dark' : 'light';
    }
    return html && html.hasAttribute('dark') ? 'dark' : 'light';
  }

  function syncCookie(theme) {
    try {
      var params = getCookieParams();
      params.set('f6', theme === 'dark' ? '400' : '80000');
      document.cookie = 'PREF=' + params.toString() +
        ';max-age=22592000;path=/;domain=.youtube.com';
    } catch (e) {}
  }

  function setLock(theme) {
    document.documentElement.setAttribute('data-ma-theme', theme);
  }

  function updateToggleIcon(theme) {
    var sw = document.getElementById('__magic-theme-switch');
    if (sw) sw.classList.toggle('dark', theme === 'dark');
  }

  function applyTheme(theme) {
    var html = document.documentElement;
    if (!html) return;
    currentTheme = theme === 'dark' ? 'dark' : 'light';

    html.classList.remove('__ytnight', '__ytday');
    setLock(currentTheme);

    if (currentTheme === 'dark') {
      html.classList.add('__ytnight');
      html.setAttribute('dark', '');
      html.removeAttribute('light');
    } else {
      html.classList.add('__ytday');
      html.setAttribute('light', '');
      html.removeAttribute('dark');
    }

    try { sessionStorage.setItem('maTheme', currentTheme); } catch (e) {}
    syncCookie(currentTheme);
    updateToggleIcon(currentTheme);
  }

  function normalize(stored) {
    if (stored === 'dark') return 'dark';
    if (stored === 'light') return 'light';
    return null;
  }

  function toggleTheme() {
    chrome.storage.local.set({ maTheme: currentTheme === 'dark' ? 'light' : 'dark' });
  }

  function onToggleActivate(e) {
    e.preventDefault();
    e.stopPropagation();
    toggleTheme();
  }

  function createToggle() {
    if (document.getElementById('__magic-theme-switch')) return;

    var sw = document.createElement('div');
    sw.id = '__magic-theme-switch';
    sw.setAttribute('tabindex', '0');
    sw.setAttribute('role', 'button');
    sw.setAttribute('aria-label', 'Переключить тему YouTube');
    if (currentTheme === 'dark') sw.classList.add('dark');

    sw.addEventListener('click', onToggleActivate, true);
    sw.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') onToggleActivate(e);
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
      observer.observe(document.documentElement, { childList: true });
    }
  }

  chrome.storage.onChanged.addListener(function (changes, area) {
    if (area !== 'local') return;
    if (!(STORAGE_KEY in changes)) return;
    var next = normalize(changes[STORAGE_KEY].newValue);
    if (next) applyTheme(next);
  });

  document.addEventListener('yt-navigate-finish', function () {
    chrome.storage.local.get([STORAGE_KEY], function (result) {
      var stored = normalize(result[STORAGE_KEY]);
      if (stored) applyTheme(stored);
    });
    createToggle();
  });

  function startGuards() {
    var classGuard = new MutationObserver(function () {
      var html = document.documentElement;
      if (!html) return;
      var cls = html.className || '';
      var wanted = currentTheme === 'dark' ? '__ytnight' : '__ytday';
      var unwanted = currentTheme === 'dark' ? '__ytday' : '__ytnight';
      var attrOk = currentTheme === 'dark' ? html.hasAttribute('dark') : html.hasAttribute('light');
      if (cls.indexOf(wanted) === -1 || cls.indexOf(unwanted) !== -1 || !attrOk) {
        applyTheme(currentTheme);
      }
    });
    classGuard.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'dark', 'light']
    });

    var bodyGuard = new MutationObserver(function () {
      if (document.body && !document.getElementById('__magic-theme-switch')) {
        createToggle();
      }
    });
    bodyGuard.observe(document.documentElement, { childList: true });
  }

  function boot() {
    if (!document.documentElement) {
      setTimeout(boot, 4);
      return;
    }

    var quick = null;
    try { quick = normalize(sessionStorage.getItem('maTheme')); } catch (e) {}
    applyTheme(quick || getThemeFromCookie());

    chrome.storage.local.get([STORAGE_KEY], function (result) {
      var stored = normalize(result[STORAGE_KEY]);
      if (stored === null) {
        chrome.storage.local.set({ maTheme: currentTheme });
      } else if (stored !== currentTheme) {
        applyTheme(stored);
      }
      startGuards();
    });

    createToggle();
  }

  boot();
})();
