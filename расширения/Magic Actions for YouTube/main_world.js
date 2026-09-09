'use strict';

(function () {
  function desiredTheme() {
    var d = document.documentElement;
    return d ? d.getAttribute('data-ma-theme') : null;
  }

  var origSetAttribute = Element.prototype.setAttribute;
  var origRemoveAttribute = Element.prototype.removeAttribute;

  // Тема YouTube определяется парой атрибутов <html>: dark / light.
  // Современный CSS YouTube держит цвета в обфусцированных токенах (--t*),
  // которые определены на html[dark] / html[light] с тёмным дефолтом в :root.
  // Поэтому фиксируем ОБА атрибута, не давая странице перебить тему.

  Element.prototype.setAttribute = function (name, value) {
    if (this === document.documentElement && desiredTheme()) {
      if (name === 'dark' && desiredTheme() === 'light') return;
      if (name === 'light' && desiredTheme() === 'dark') return;
    }
    return origSetAttribute.apply(this, arguments);
  };

  Element.prototype.removeAttribute = function (name) {
    if (this === document.documentElement && desiredTheme()) {
      if (name === 'dark' && desiredTheme() === 'dark') return;
      if (name === 'light' && desiredTheme() === 'light') return;
    }
    return origRemoveAttribute.apply(this, arguments);
  };

  if (Element.prototype.toggleAttribute) {
    var origToggleAttribute = Element.prototype.toggleAttribute;
    Element.prototype.toggleAttribute = function (name, force) {
      if (this === document.documentElement && desiredTheme() &&
          (name === 'dark' || name === 'light')) {
        var want = desiredTheme();
        var has = this.hasAttribute(name);
        if (force === undefined) force = !has;
        // разрешаем только приведение к желаемой теме
        if (name !== want || !!force === has) return has;
      }
      return origToggleAttribute.apply(this, arguments);
    };
  }

  // YouTube сам перезаписывает кук PREF (в т.ч. f6) под своё внутреннее
  // состояние — после перезагрузки сервер рендерил старую тему.
  // Перехватываем запись document.cookie и держим f6 в согласии с темой.
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
        if (theme && typeof value === 'string' && /(^|;\s*)PREF=/i.test(value) && this === document) {
          var wantF6 = theme === 'dark' ? '400' : '80000';
          try {
            var m = value.match(/PREF=([^;]*)/);
            if (m) {
              var p = new URLSearchParams(m[1]);
              p.set('f6', wantF6);
              var rest = value.slice(0, m.index) + 'PREF=' + p.toString() + value.slice((m.index + m[0].length));
              return origSetCookie.call(this, rest);
            }
          } catch (e) {}
        }
        return origSetCookie.call(this, value);
      }
    });
  }
})();
