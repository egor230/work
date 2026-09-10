'use strict';

(function () {
  function desiredTheme() {
    var d = document.documentElement;
    return d ? d.getAttribute('data-ma-theme') : null;
  }

  var origSetAttribute = Element.prototype.setAttribute;
  var origRemoveAttribute = Element.prototype.removeAttribute;

  // Философия: dark = «расширение включено» — фиксируем пару атрибутов
  // dark/light на <html> (токены --t* определены на html[dark]/html[light]
  // с ТЁМНЫМ дефолтом в :root, поэтому YouTube не должен их сбивать).
  // light = «расширение выключено» — НИЧЕГО не блокируем: YouTube ведёт
  // тему сам (в т.ч. родной тумблер пользователя), content.js следует за ним.

  Element.prototype.setAttribute = function (name, value) {
    if (this === document.documentElement && desiredTheme() === 'dark') {
      if (name === 'light') return; // в dark-режиме light не пускаем
    }
    return origSetAttribute.apply(this, arguments);
  };

  Element.prototype.removeAttribute = function (name) {
    if (this === document.documentElement && desiredTheme() === 'dark') {
      if (name === 'dark') return; // держим тёмную тему
    }
    return origRemoveAttribute.apply(this, arguments);
  };

  if (Element.prototype.toggleAttribute) {
    var origToggleAttribute = Element.prototype.toggleAttribute;
    Element.prototype.toggleAttribute = function (name, force) {
      if (this === document.documentElement && desiredTheme() === 'dark' &&
          (name === 'dark' || name === 'light')) {
        var has = this.hasAttribute(name);
        if (force === undefined) force = !has;
        // в dark держим dark на месте, light не пускаем
        if (name === 'dark' && !force) return has;
        if (name === 'light' && force) return has;
      }
      return origToggleAttribute.apply(this, arguments);
    };
  }

  // В dark-режиме YouTube может перезаписывать кук PREF (f6) под своё
  // состояние — держим f6=400. В light-режиме не вмешиваемся (натив).
  var cookieDesc;
  try {
    cookieDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie');
  } catch (e) {}
  if (cookieDesc && cookieDesc.configurable) {
    var origSetCookie = cookieDesc.set;
    Object.defineProperty(Document.prototype, 'cookie', {
      configurable: true,
      enumerable: true,
      get: function () {
        return cookieDesc.get.call(this);
      },
      set: function (value) {
        var theme = desiredTheme();
        if (theme === 'dark' && typeof value === 'string' &&
            /(^|;\s*)PREF=/i.test(value) && this === document) {
          try {
            var m = value.match(/PREF=([^;]*)/);
            if (m) {
              var p = new URLSearchParams(m[1]);
              p.set('f6', '400');
              var rest = value.slice(0, m.index) + 'PREF=' + p.toString() +
                value.slice((m.index + m[0].length));
              return origSetCookie.call(this, rest);
            }
          } catch (e) {}
        }
        return origSetCookie.call(this, value);
      }
    });
  }

  // content.js (ISOLATED) не может передать объект через CustomEvent.detail
  // в MAIN world (объекты не пересекают границу миров). Поэтому он ставит
  // метку data-ma-notify на <html>, а мы здесь диспатчим настоящий
  // yt-action — так же, как родной тумблер YouTube. Слушает ytd-app
  // → роутер -> actionMap компонентов -> перерисовка (в т.ч. yt-searchbox
  // и ytd-masthead: они слушают именно это событие, не атрибуты).
  // Dispatch сразу (без debounce) — как у нативного тумблера YouTube.
  var lastNotify = null;
  var notifyObserver = new MutationObserver(function () {
    var v = document.documentElement.getAttribute('data-ma-notify');
    if (v && v !== lastNotify) {
      lastNotify = v;
      var isDark = v === 'dark';
      try {
        document.documentElement.dispatchEvent(new CustomEvent('yt-action', {
          bubbles: true,
          composed: true,
          detail: {
            actionName: 'yt-dark-mode-toggled-action',
            args: [isDark]
          }
        }));
      } catch (e) {}
    }
  });
  function startNotifyObserver() {
    if (!document.documentElement) {
      setTimeout(startNotifyObserver, 10);
      return;
    }
    notifyObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-ma-notify']
    });
  }
  startNotifyObserver();
})();
