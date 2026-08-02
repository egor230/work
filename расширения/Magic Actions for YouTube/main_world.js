'use strict';

(function () {
  function desiredTheme() {
    var d = document.documentElement;
    return d ? d.getAttribute('data-ma-theme') : null;
  }

  var origSetAttribute = Element.prototype.setAttribute;
  var origRemoveAttribute = Element.prototype.removeAttribute;

  Element.prototype.setAttribute = function (name, value) {
    if (this === document.documentElement && name === 'dark' && desiredTheme() === 'light') {
      return;
    }
    return origSetAttribute.apply(this, arguments);
  };

  Element.prototype.removeAttribute = function (name) {
    if (this === document.documentElement && name === 'dark' && desiredTheme() === 'dark') {
      return;
    }
    return origRemoveAttribute.apply(this, arguments);
  };
})();
