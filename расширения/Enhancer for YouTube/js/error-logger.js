/**
 * error-logger.js — MAIN world (Enhancer for YouTube, кастом §15).
 *
 * Ловит ошибки воспроизведения YouTube и шлёт их в изолированный мир
 * событием `efyt-error-record`. Дедупликацией и записью занимается
 * js/error-logger-bridge.js — сюда попадают только «сырые» события.
 *
 * Источники ошибок:
 *   - player.onError            — код ошибки плеера YouTube (100/150/2/5 …)
 *   - <video>.error             — MediaError браузера (код + сообщение)
 *   - error screen              — «Video unavailable», «Playability on …» и т.п.
 */
(() => {
  'use strict';

  const SIGNAL = 'efyt-error-record';
  let lastScreen = '';

  function playerData() {
    const p = document.querySelector('#movie_player.html5-video-player');
    if (!p || typeof p.getVideoData !== 'function') return null;
    try { return p.getVideoData(); } catch (e) { return null; }
  }

  function videoId() {
    const v = playerData();
    if (v && v.video_id) return String(v.video_id).slice(0, 64);
    try {
      const m = location.search.match(/[?&]v=([^&#]+)/);
      if (m) return decodeURIComponent(m[1]).slice(0, 64);
    } catch (e) {}
    return '';
  }

  function title() {
    const v = playerData();
    if (v && v.title) return String(v.title).slice(0, 200);
    return String(document.title || '').slice(0, 200);
  }

  function emit(kind, code, message, extra) {
    try {
      document.dispatchEvent(new CustomEvent(SIGNAL, {
        detail: {
          kind: String(kind || 'unknown').slice(0, 40),
          code: code == null ? '' : String(code).slice(0, 80),
          message: String(message || '').slice(0, 500),
          videoId: videoId(),
          title: title(),
          at: Date.now(),
          url: String(location.href || '').split('?')[0].slice(0, 300),
          extra: extra || {}
        }
      }));
    } catch (e) {}
  }

  /** YouTube присылает код то в detail, то в data, то объектом — нормализуем. */
  function readEventData(e) {
    let d = e && e.detail !== undefined ? e.detail : (e && e.data);
    if (Array.isArray(d)) d = d[0];
    if (d && typeof d === 'object') {
      return {
        code: d.code != null ? d.code : (d.errorCode != null ? d.errorCode : (d.data != null ? d.data : '')),
        message: d.message != null ? d.message : (d.reason != null ? d.reason : (d.error != null ? d.error : ''))
      };
    }
    return { code: d == null ? '' : d, message: '' };
  }

  function hookPlayer() {
    const p = document.querySelector('#movie_player.html5-video-player');
    if (!p || p.__efytErrorHooked) return;
    p.__efytErrorHooked = true;

    p.addEventListener('onError', function (e) {
      const x = readEventData(e);
      emit('player', x.code, x.message, { source: 'player.onError' });
    });
    checkErrorScreen();
  }

  function hookVideo() {
    const v = document.querySelector('video.html5-main-video');
    if (!v || v.__efytErrorHooked) return;
    v.__efytErrorHooked = true;

    v.addEventListener('error', function () {
      const me = v.error;
      // Подпись URL из googlevideo не нужна — она быстро меняется и мешает дедупу.
      const src = String(v.currentSrc || '').split('?')[0].slice(0, 300);
      emit('media', me ? me.code : 'unknown', me ? me.message : '', {
        source: 'video.error',
        networkState: v.networkState,
        readyState: v.readyState,
        src: src
      });
    });
  }

  function checkErrorScreen() {
    const screen = document.querySelector(
      'yt-playability-error-supported-renderers#error-screen, #error-screen, yt-playability-error-supported-renderers'
    );
    if (!screen) { lastScreen = ''; return; }
    const text = String(screen.innerText || screen.textContent || '')
      .replace(/\s+/g, ' ').trim().slice(0, 400);
    if (!text || text === lastScreen) return;
    lastScreen = text;
    emit('playability', '', text, { source: 'error-screen' });
  }

  function start() { hookPlayer(); hookVideo(); checkErrorScreen(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }

  // YouTube — SPA: плеер и <video> пересоздаются при каждом переходе.
  const mo = new MutationObserver(function () {
    hookPlayer();
    hookVideo();
    checkErrorScreen();
  });
  mo.observe(document.documentElement || document, { childList: true, subtree: true });
  setInterval(checkErrorScreen, 5000);
})();
