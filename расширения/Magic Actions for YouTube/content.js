'use strict';

(function () {
  var STORAGE_KEY = 'maTheme';
  var currentTheme = null;
  var _maSearchRetry = null;

  // ФИЛОСОФИЯ РАСШИРЕНИЯ:
  //   dark  = расширение ВКЛЮЧЕНО: форсим пару атрибутов dark/light + кук f6,
  //           guards не дают YouTube сбить тему;
  //   light = расширение «ВЫКЛЮЧЕНО»: только ставим нативную пару атрибутов
  //           и кук, счищаем застрявшие тёмные классы — дальше YouTube сам
  //           рендерит и красит страницу (100% нативный вид). Никаких
  //           CSS-переменных и страховок. Если пользователь переключил тему
  //           родным тумблером YouTube — следуем за ним.

  function getCookieParams() {
    try {
      var match = document.cookie.match(/PREF=([^;]*)/);
      return new URLSearchParams(match ? match[1] : '');
    } catch (e) {
      return new URLSearchParams('');
    }
  }

  // f6 — битовая маска (бит 165 = 0x400 dark, бит 174 = 0x80000 light),
  // YouTube склеивает флаги (40080000 и т.п.) → читаем по первому символу.
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

  function updateToggleIcon(theme) {
    var sw = document.getElementById('__magic-theme-switch');
    if (sw) sw.classList.toggle('dark', theme === 'dark');
  }

  // Classы *Dark висят на РАЗНЫХ элементах (не на хосте!) — по реальному DOM
  // yt-searchbox=host, внутри него InputBox, рядом SearchButton,
  // SuggestionsContainer. Правильно: найти каждый элемент по базовому классу
  // и повесить тёмный вариант на НЕГО. Если базового класса нет — пропускаем.
  // requestUpdate() заставляет Lit-компонент перечитать живой
  // hasAttribute('dark') при следующем рендере — самокоррекция.
  //
  // ГЛАВНАЯ НАХОДКА (из оригинального расширения ImprovedTube=преемника
  // Magic Actions for YouTube, themes.js): при переключении он ставит/снимает
  // АТРИБУТ dark и на <html>, и на ytd-masthead: setAttribute('dark','') /
  // removeAttribute('dark'). В CSS сегодняшнего YouTube тёмные токены поиска
  // заданы селектором "[dark],html[dark]{" — то есть атрибут dark на любом
  // элементе (в т.ч. на masthead) включает тёмные токены в его поддереве.
  // Мы никогда не ставили атрибут на masthead (только класс) — поиск и
  // оставался светлым в тёмной теме. Ниже зеркалим поведение оригинала.
  var DARK_CLASS_MAP = [
    ['ytSearchboxComponentHost', 'ytSearchboxComponentHostDark'],
    ['ytSearchboxComponentInputBox', 'ytSearchboxComponentInputBoxDark'],
    ['ytSearchboxComponentInput', 'yt-searchbox-input-dark'],
    ['ytSearchboxComponentSearchButton', 'ytSearchboxComponentSearchButtonDark'],
    ['ytSearchboxComponentSuggestionsContainer', 'ytSearchboxComponentSuggestionsContainerDark'],
    ['ytSearchboxComponentClearButton', 'ytSearchboxComponentClearButtonDark'],
    ['ytSearchboxComponentVoiceButton', 'ytSearchboxComponentVoiceButtonDark'],
    ['ytSearchboxComponentDesktop', 'ytSearchboxComponentDesktopDark'],
    ['ytSearchboxComponentSuggestionsItem', 'ytSearchboxComponentSuggestionsItemDark']
  ];

  function syncSearchboxClasses(theme) {
    try {
      var isDark = theme === 'dark';
      for (var i = 0; i < DARK_CLASS_MAP.length; i++) {
        var base = DARK_CLASS_MAP[i][0];
        var dark = DARK_CLASS_MAP[i][1];
        var els = document.querySelectorAll('.' + base);
        for (var j = 0; j < els.length; j++) {
          els[j].classList.toggle(dark, isDark);
        }
      }
      var masthead = document.querySelector('ytd-masthead');
      if (masthead) {
        // как оригинал (ImprovedTube/themes.js): dark → атрибут dark="",
        // light → снять атрибут; класс 'dark' — страховка второго слоя
        masthead.classList.toggle('dark', isDark);
        if (isDark) {
          masthead.setAttribute('dark', '');
        } else {
          masthead.removeAttribute('dark');
        }
        try { masthead.requestUpdate && masthead.requestUpdate(); } catch (e) {}
      }
      var searchbox = document.querySelector('yt-searchbox');
      if (searchbox) {
        try { searchbox.requestUpdate && searchbox.requestUpdate(); } catch (e) {}
      }
    } catch (e) {}
  }

  function applyTheme(theme) {
    var html = document.documentElement;
    if (!html) return;
    currentTheme = theme === 'dark' ? 'dark' : 'light';

    // наших классов темы больше нет — только нативные атрибуты YouTube
    html.classList.remove('__ytnight', '__ytday');
    html.setAttribute('data-ma-theme', currentTheme);

    // Нативная пара атрибутов (как у родного тумблера YT):
    // dark-тема → dark=""; light-тема → light="".
    // ВАЖНО: ставить light обязательно — обфусцированные токены --t*
    // имеют ТЁМНЫЙ дефолт в :root, без [light] страница останется чёрной.
    if (currentTheme === 'dark') {
      html.setAttribute('dark', '');
      html.removeAttribute('light');
    } else {
      html.setAttribute('light', '');
      html.removeAttribute('dark');
    }
    syncSearchboxClasses(currentTheme);

    // Один короткий ретрай (~75мс): догоняет повторный рендер YouTube
    // (главный паттерн старых багов — компонент перерисовывался и
    // возвращал классы). Долгих ретраев (300/1200) — нет, они дрались.
    try {
      clearTimeout(_maSearchRetry);
      _maSearchRetry = setTimeout(function () {
        syncSearchboxClasses(currentTheme);
      }, 75);
    } catch (e) {}

    try { sessionStorage.setItem('maTheme', currentTheme); } catch (e) {}
    syncCookie(currentTheme);
    updateToggleIcon(currentTheme);
    notifyYouTubeThemeChanged(currentTheme);
  }

  // Родной тумблер YT уведомляет компоненты экшеном
  // yt-dark-mode-toggled-action через CustomEvent('yt-action') на body.
  // Из ISOLATED world объект detail не доходит в MAIN world (граница миров),
  // поэтому диспатчит main_world.js по метке data-ma-notify (см. там).
  function notifyYouTubeThemeChanged(theme) {
    try {
      document.documentElement.setAttribute('data-ma-notify', theme);
    } catch (e) {}
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
    // dark: держим пару атрибутов (YouTube может пытаться сбить).
    // light: режим «выключено» — не воюем; если пользователь переключил
    // тему РОДНЫМ тумблером YouTube (появился dark) — синхронизируемся.
    var attrGuard = new MutationObserver(function () {
      var html = document.documentElement;
      if (!html) return;
      if (currentTheme === 'dark') {
        if (!html.hasAttribute('dark') || html.hasAttribute('light')) {
          html.setAttribute('dark', '');
          html.removeAttribute('light');
        }
      } else if (currentTheme === 'light') {
        if (html.hasAttribute('dark')) {
          chrome.storage.local.set({ maTheme: 'dark' });
        }
      }
    });
    attrGuard.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['dark', 'light']
    });

    // тумблер мог быть удалён YouTube из DOM — пересоздаём
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

    // мгновенное применение (до ответа storage) — без тёмной вспышки
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
