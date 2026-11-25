/**
 * error-logger-bridge.js — ISOLATED world (Enhancer for YouTube, кастом §15).
 *
 * Принимает события `efyt-error-record` от js/error-logger.js, проверяет
 * дедупликацию и пишет результат в chrome.storage.local.errorlog.
 *
 * Повтор НЕ записывается вообще: если запись с таким же сигнатурным ключом
 * уже есть в логе, функция возвращается до какого-либо вызова storage.set.
 *
 * Ключ дедупликации: тип ошибки + код + нормализованное сообщение + videoId.
 * То есть одна и та же ошибка на том же видео попадает в лог один раз;
 * разные видео с одной ошибкой остаются разными записями.
 */
(() => {
  'use strict';

  const KEY = 'errorlog';
  const MAX = 200;
  let chain = Promise.resolve();

  /** Нормализация сообщения: ссылки/пробелы/регистр не должны мешать дедупу. */
  function normalizeMessage(s) {
    return String(s == null ? '' : s)
      .replace(/https?:\/\/\S+/g, 'URL')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase()
      .slice(0, 200);
  }

  function signature(r) {
    return [r.kind || '', String(r.code || ''), normalizeMessage(r.message), r.videoId || ''].join('|');
  }

  async function record(d) {
    if (!d || typeof d !== 'object') return;

    const extra = (d.extra && typeof d.extra === 'object') ? d.extra : {};
    const rec = {
      kind: String(d.kind || 'unknown').slice(0, 40),
      code: String(d.code || '').slice(0, 80),
      message: String(d.message || '').slice(0, 500),
      videoId: String(d.videoId || '').slice(0, 64),
      title: String(d.title || '').slice(0, 200),
      source: String(extra.source || '').slice(0, 60),
      src: String(extra.src || '').slice(0, 300),
      networkState: extra.networkState == null ? null : extra.networkState,
      readyState: extra.readyState == null ? null : extra.readyState,
      at: Number(d.at) || Date.now(),
      url: String(d.url || '').split('?')[0].slice(0, 300)
    };
    rec.sig = signature(rec);

    try {
      const st = await chrome.storage.local.get({ [KEY]: [] });
      const list = Array.isArray(st[KEY]) ? st[KEY] : [];

      // === ДЕДУП: повторная ошибка не записывается и не обновляется ===
      if (list.some(function (x) { return x && x.sig === rec.sig; })) return;

      list.unshift(rec);
      await chrome.storage.local.set({ [KEY]: list.slice(0, MAX) });

      // Сервис-воркер выпишет JSON-файл (native host / downloads fallback).
      try { chrome.runtime.sendMessage({ request: 'efyt-error-sync' }); } catch (e) {}
    } catch (e) {}
  }

  document.addEventListener('efyt-error-record', function (e) {
    chain = chain.then(function () { return record(e.detail); }).catch(function () {});
  });
})();
