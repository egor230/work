/**
 * channel-speed-bridge.js — ISOLATED world (Enhancer for YouTube).
 *
 * Доступ к chrome.storage.local для панели скорости. Используется та же
 * таблица, что и в §2/§7/§9 Enhancer:
 *
 *   channelspeeds: {
 *     "<channelId>": 1.6,
 *     "name:<Название канала>": 1.6
 *   }
 *
 * Никакого второго хранилища нет — панель и Enhancer видят одни и те же данные.
 */
(() => {
  'use strict';

  if (window.__ytcsBridge) return;
  window.__ytcsBridge = true;

  const NS = 'ytcs';
  const STORAGE_KEY = 'channelspeeds';
  const MIN_RATE = 0.25;
  const MAX_RATE = 4;

  document.documentElement.setAttribute('data-ytcs-bridge', '1');

  function clampRate(value) {
    const rate = Math.round(Number(value) * 100) / 100;
    if (!Number.isFinite(rate)) return 1;
    return Math.min(MAX_RATE, Math.max(MIN_RATE, rate));
  }

  function cleanName(value) {
    return String(value || '').trim();
  }

  async function readMap() {
    const data = await chrome.storage.local.get({ [STORAGE_KEY]: {} });
    const map = data[STORAGE_KEY];
    return (map && typeof map === 'object' && !Array.isArray(map)) ? map : {};
  }

  /** Ищет сохранённую скорость: сначала по channelId, затем по имени. */
  function pickRate(map, id, name) {
    if (id && typeof map[id] === 'number' && Number.isFinite(map[id])) {
      return clampRate(map[id]);
    }
    if (name) {
      const byName = map[`name:${name}`];
      if (typeof byName === 'number' && Number.isFinite(byName)) {
        return clampRate(byName);
      }
    }
    return null;
  }

  async function handle(op, payload) {
    const map = await readMap();
    const id = String(payload.id || '').trim();
    const name = cleanName(payload.name);

    switch (op) {
      case 'get':
        return pickRate(map, id, name);

      case 'set': {
        if (!id && !name) return false;
        const rate = clampRate(payload.rate);
        if (id) map[id] = rate;
        if (name) map[`name:${name}`] = rate;
        await chrome.storage.local.set({ [STORAGE_KEY]: map });
        return true;
      }

      case 'remove': {
        if (id) delete map[id];
        if (name) delete map[`name:${name}`];
        await chrome.storage.local.set({ [STORAGE_KEY]: map });
        return true;
      }

      case 'getAll':
        return map;

      default:
        return null;
    }
  }

  document.addEventListener(`${NS}-request`, async (event) => {
    const detail = event.detail || {};
    let ok = true;
    let data = null;

    try {
      data = await handle(detail.op, detail.payload || {});
    } catch (error) {
      ok = false;
      console.warn('[ytcs] channelspeeds:', error);
    }

    document.dispatchEvent(new CustomEvent(`${NS}-response`, {
      detail: { reqId: detail.reqId, ok, data },
    }));
  });

  // Enhancer сохранил скорость (колесо, кнопки, нативное меню) — обновить панель.
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes[STORAGE_KEY]) return;
    document.dispatchEvent(new CustomEvent(`${NS}-saved-changed`, {
      detail: { map: changes[STORAGE_KEY].newValue || {} },
    }));
  });

  document.dispatchEvent(new CustomEvent(`${NS}-ready`));
})();
