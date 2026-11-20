/* ============================================================
   WebTube TV-mode JS — навигация с пульта как в SmartTube
   Загружается в WebView, работает с DOM m.youtube.com.
   ============================================================ */
(function () {
  'use strict';
  if (window.__webtubeTV) return;
  window.__webtubeTV = true;

  // ---------- Селекторы карточек видео (порядок = приоритет) ----------
  var CARD_SELECTORS = [
    'ytm-rich-item-renderer',
    'ytm-video-with-context-renderer',
    'ytm-search-video-renderer',
    'ytm-compact-video-renderer',
    'ytm-playlist-video-renderer',
    'ytm-media-item',
    'ytm-channel-renderer',
    'ytm-compact-playlist-renderer'
  ].join(',');

  var OSD_ID = 'tv-osd';
  var FOCUS_CLASS = 'tv-focused';
  var osdTimer = null;
  var currentFocus = null;

  // ---------- OSD ----------
  function showOsd(text, ms) {
    var osd = document.getElementById(OSD_ID);
    if (!osd) {
      osd = document.createElement('div');
      osd.id = OSD_ID;
      document.body.appendChild(osd);
    }
    osd.textContent = text;
    osd.style.opacity = '1';
    osd.style.display = 'block';
    clearTimeout(osdTimer);
    osdTimer = setTimeout(function () {
      osd.style.opacity = '0';
      setTimeout(function () { osd.style.display = 'none'; }, 300);
    }, ms || 1800);
  }
  window.__wtShowOsd = showOsd;

  // ---------- Получение всех карточек на странице ----------
  function getCards() {
    return Array.prototype.slice.call(document.querySelectorAll(CARD_SELECTORS))
      .filter(function (el) {
        // только видимые
        var r = el.getBoundingClientRect();
        return r.width > 10 && r.height > 10;
      });
  }

  // ---------- Видимый фокус ----------
  function setFocus(el) {
    if (currentFocus === el) return;
    if (currentFocus) currentFocus.classList.remove(FOCUS_CLASS);
    currentFocus = el || null;
    if (el) {
      el.classList.add(FOCUS_CLASS);
      el.focus({ preventScroll: true });
      scrollIntoViewSafe(el);
    }
  }

  function scrollIntoViewSafe(el) {
    try {
      var r = el.getBoundingClientRect();
      var vh = window.innerHeight || 1080;
      // прокрутить так, чтобы карточка была видна целиком
      if (r.top < 100 || r.bottom > vh - 60) {
        el.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    } catch (e) {}
  }

  function focusFirstCard() {
    var cards = getCards();
    if (cards.length) setFocus(cards[0]);
  }

  // ---------- Геометрия для D-pad навигации ----------
  // Возвращает ближайшую карточку в указанном направлении
  function findNearest(dx, dy) {
    var cards = getCards();
    if (!cards.length) return null;
    if (!currentFocus) return cards[0];

    var cur = currentFocus.getBoundingClientRect();
    var cx = cur.left + cur.width / 2;
    var cy = cur.top + cur.height / 2;
    var best = null;
    var bestScore = Infinity;

    cards.forEach(function (el) {
      if (el === currentFocus) return;
      var r = el.getBoundingClientRect();
      var x = r.left + r.width / 2;
      var y = r.top + r.height / 2;
      var ddx = x - cx;
      var ddy = y - cy;

      // фильтр: только элементы в нужном направлении
      if (dx > 0 && ddx <= 2) return;       // вправо
      if (dx < 0 && ddx >= -2) return;      // влево
      if (dy > 0 && ddy <= 2) return;       // вниз
      if (dy < 0 && ddy >= -2) return;      // вверх

      // взвешенное расстояние (вертикаль/горизонталь приоритетнее)
      var dist = Math.sqrt(ddx * ddx + ddy * ddy);
      var score = dist;
      if (dy !== 0) score = Math.abs(ddy) * 1.2 + Math.abs(ddx) * 0.4;
      if (dx !== 0) score = Math.abs(ddx) * 1.2 + Math.abs(ddy) * 0.4;

      if (score < bestScore) {
        bestScore = score;
        best = el;
      }
    });
    return best;
  }

  // ---------- D-pad ----------
  function moveFocus(dx, dy) {
    var target = findNearest(dx, dy);
    if (target) {
      setFocus(target);
      return true;
    }
    return false;
  }

  // ---------- Клик по элементу под фокусом ----------
  function clickFocused() {
    if (!currentFocus) return false;
    // ищем ссылку/кликабельный элемент внутри карточки
    var link = currentFocus.querySelector('a[href*="watch"], a[href*="/watch"], a[href*="channel"], a[href*="/c/"], a[href*="playlist"]')
      || currentFocus.querySelector('a[href]');
    if (link) {
      link.click();
      return true;
    }
    currentFocus.click();
    return true;
  }

  // ---------- Работа с <video> ----------
  function getVideo() {
    return document.querySelector('video');
  }

  // ---------- Обработка клавиш ----------
  document.addEventListener('keydown', function (e) {
    var code = e.keyCode;
    var handled = false;

    switch (code) {
      case 13:   // ENTER
      case 160:  // DPAD_CENTER
        handled = clickFocused();
        break;
      case 37:   // LEFT
        handled = moveFocus(-1, 0);
        break;
      case 39:   // RIGHT
        handled = moveFocus(1, 0);
        break;
      case 38:   // UP
        handled = moveFocus(0, -1);
        break;
      case 40:   // DOWN
        handled = moveFocus(0, 1);
        break;
      default:
        break;
    }

    if (handled) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // Цифры 0-9 → перемотка на 0-90% (как в SmartTube)
  document.addEventListener('keypress', function (e) {
    var code = e.keyCode;
    if (code >= 48 && code <= 57) {
      var v = getVideo();
      if (v && v.duration > 0) {
        var pct = (code - 48) / 10;
        var pos = v.duration * pct;
        v.currentTime = pos;
        showOsd('⏩ ' + formatTime(pos) + ' / ' + formatTime(v.duration), 1500);
        e.preventDefault();
        e.stopPropagation();
      }
    }
  }, true);

  function formatTime(s) {
    if (!isFinite(s)) return '0:00';
    s = Math.floor(s);
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    var mm = h > 0 ? String(m).padStart(2, '0') : String(m);
    return (h > 0 ? h + ':' : '') + mm + ':' + String(sec).padStart(2, '0');
  }
  window.__wtFormatTime = formatTime;

  // ---------- Применение скорости к видео ----------
  // Скорость передаётся с Android-стороны через __wtSpeed
  function applySpeed() {
    var v = getVideo();
    var speed = window.__wtSpeed || 1.0;
    if (v && Math.abs(v.playbackRate - speed) > 0.01) {
      try {
        v.playbackRate = speed;
        v.defaultPlaybackRate = speed;
      } catch (err) {}
    }
  }
  window.__wtApplySpeed = applySpeed;

  // Видео-элемент пересоздаётся при смене ролика — следим
  var lastVideo = null;
  setInterval(function () {
    var v = getVideo();
    if (v && v !== lastVideo) {
      lastVideo = v;
      applySpeed();
    } else if (v) {
      applySpeed();
    }
  }, 1000);

  // ---------- Авто-фокус на первой карточке ----------
  var focusTries = 0;
  var focusInterval = setInterval(function () {
    if (currentFocus) { clearInterval(focusInterval); return; }
    focusFirstCard();
    if (++focusTries > 20) clearInterval(focusInterval);
  }, 500);

  // Фокус при клике мышью/тачем (на случай тачскрина)
  document.addEventListener('focusin', function (e) {
    var t = e.target.closest ? e.target.closest(CARD_SELECTORS) : null;
    if (t) setFocus(t);
  }, true);

  console.log('[WebTube] TV-mode engine loaded');
})();
