/**
 * channel-speed-panel.js — MAIN world (Enhancer for YouTube).
 *
 * Компактная панель скорости у шестерёнки. Не дублирует механизм
 * «скорость по каналам» Enhancer (§2/§7/§9), а работает поверх него:
 *  - читает/пишет ту же таблицу chrome.storage.local.channelspeeds;
 *  - применяет скорость через хук window.__efytChannelSpeed, который
 *    выставляет её так же, как кнопки/колесо Enhancer (efytApplySpeed),
 *    и сохраняет через efytSpdSave;
 *  - сама ничего не восстанавливает при переходе между видео — это
 *    по-прежнему делает Enhancer.
 */
(() => {
  'use strict';

  if (window.__ytcsPanel) return;
  window.__ytcsPanel = true;

  const NS = 'ytcs';
  const DEFAULT_RATE = 1;
  const MIN_RATE = 0.25;
  const MAX_RATE = 4;
  const PRESETS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5];
  const REQUEST_TIMEOUT = 4000;

  const state = {
    player: null,
    video: null,
    channel: null,
    channelKey: '',
    savedRate: null,
    lastHref: location.href,
    bridgeResolved: false,
    savedTimer: 0,
  };

  // --------------------------------------------------------------------------
  // Мост в ISOLATED world (channel-speed-bridge.js)
  // --------------------------------------------------------------------------

  let resolveReady;
  const readyPromise = new Promise((resolve) => { resolveReady = resolve; });

  function markBridgeReady(ok) {
    if (state.bridgeResolved) return;
    state.bridgeResolved = true;
    resolveReady(ok);
  }

  document.addEventListener(`${NS}-ready`, () => markBridgeReady(true));
  if (document.documentElement.hasAttribute('data-ytcs-bridge')) markBridgeReady(true);
  setTimeout(() => markBridgeReady(false), 1500);

  let requestSeq = 0;
  const pending = new Map();

  function bridge(op, payload) {
    return readyPromise.then(() => new Promise((resolve) => {
      const reqId = `${NS}:${++requestSeq}:${Date.now()}`;
      const timer = setTimeout(() => {
        pending.delete(reqId);
        resolve(null);
      }, REQUEST_TIMEOUT);

      pending.set(reqId, { resolve, timer });
      document.dispatchEvent(new CustomEvent(`${NS}-request`, {
        detail: { reqId, op, payload: payload || {} },
      }));
    }));
  }

  document.addEventListener(`${NS}-response`, (event) => {
    const detail = event.detail || {};
    const item = pending.get(detail.reqId);
    if (!item) return;
    clearTimeout(item.timer);
    pending.delete(detail.reqId);
    item.resolve(detail.ok ? detail.data : null);
  });

  document.addEventListener(`${NS}-saved-changed`, () => {
    scheduleSavedRefresh(150);
  });

  // --------------------------------------------------------------------------
  // Вспомогательные функции
  // --------------------------------------------------------------------------

  function clampRate(value) {
    const rate = Math.round(Number(value) * 100) / 100;
    if (!Number.isFinite(rate)) return DEFAULT_RATE;
    return Math.min(MAX_RATE, Math.max(MIN_RATE, rate));
  }

  function formatRate(rate) {
    return `${Math.round(rate * 100) / 100}×`;
  }

  function isSameRate(a, b) {
    return Math.abs(Number(a) - Number(b)) < 0.011;
  }

  function isWatchPage() {
    if (/^\/(watch|shorts|live)\b/.test(location.pathname)) return true;
    return new URLSearchParams(location.search).has('v');
  }

  function findPlayer() {
    return document.getElementById('movie_player')
      || document.getElementById('shorts-player')
      || document.querySelector('.html5-video-player');
  }

  function findVideo() {
    const player = state.player || findPlayer();
    return (player && player.querySelector('video.html5-main-video'))
      || (player && player.querySelector('video'))
      || document.querySelector('video.html5-main-video')
      || document.querySelector('video');
  }

  function normalizeChannelUrl(raw) {
    if (!raw) return '';
    try {
      const url = new URL(raw, location.origin);
      if (!/(^|\.)youtube\.com$/i.test(url.hostname)) return '';
      let path = url.pathname.replace(/\/+$/, '');
      path = path.replace(/\/(videos|shorts|streams|playlists|about|featured|community|store|membership|podcasts)$/i, '');
      return `https://www.youtube.com${path || '/'}`;
    } catch {
      return '';
    }
  }

  function readChannel() {
    let id = '';
    let name = '';

    // Основной источник — сам Enhancer (те же данные, что использует §2/§7/§9).
    const hook = window.__efytChannelSpeed;
    if (hook && typeof hook.get === 'function') {
      try {
        const info = hook.get();
        id = info.id || '';
        name = info.name || '';
      } catch { /* Enhancer ещё не готов */ }
    }

    const player = state.player || findPlayer();
    if (player && (!id || !name)) {
      try {
        const details = player.getPlayerResponse
          && player.getPlayerResponse().videoDetails;
        if (details) {
          id = id || details.channelId || '';
          name = name || details.author || '';
        }
      } catch { /* ignore */ }
    }

    let url = '';
    const selectors = [
      '#owner #channel-name a',
      'ytd-video-owner-renderer #channel-name a',
      '#owner a.yt-simple-endpoint[href*="/@"]',
      '#owner a.yt-simple-endpoint[href*="/channel/"]',
      'ytd-reel-video-renderer[is-active] #channel-name a',
    ];
    for (const selector of selectors) {
      const link = document.querySelector(selector);
      if (!link) continue;
      url = normalizeChannelUrl(link.getAttribute('href'));
      if (!name) name = (link.textContent || '').trim();
      if (url) break;
    }
    if (!url && id) url = `https://www.youtube.com/channel/${id}`;

    return { id, name: name.trim(), url };
  }

  function scheduleSavedRefresh(delay = 400) {
    clearTimeout(state.savedTimer);
    state.savedTimer = setTimeout(querySaved, delay);
  }

  async function querySaved() {
    const channel = state.channel;
    if (!channel || (!channel.id && !channel.name)) return;

    const stored = await bridge('get', { id: channel.id, name: channel.name });
    if (channel !== state.channel) return;

    state.savedRate = typeof stored === 'number' ? clampRate(stored) : null;
    updateUI();
  }

  function refreshChannel(force = false) {
    const channel = readChannel();
    if (!channel.id && !channel.name) return;

    // ID предпочтительнее: имя может совпасть у разных каналов.
    const key = channel.id || `name:${channel.name}`;
    if (!force && key === state.channelKey) return;

    state.channelKey = key;
    state.channel = channel;
    querySaved();
    updateUI();
  }

  // --------------------------------------------------------------------------
  // Изменение скорости
  // --------------------------------------------------------------------------

  /**
   * @param {number} rate
   * @param {boolean} save — записывать ли в channelspeeds
   */
  function setRate(rate, save) {
    const nextRate = clampRate(rate);
    const channel = state.channel;
    const hook = window.__efytChannelSpeed;

    if (hook && typeof hook.set === 'function') {
      try {
        hook.set(nextRate, save);
      } catch {
        applyDirect(nextRate, save);
      }
    } else {
      applyDirect(nextRate, save);
    }

    if (save) {
      state.savedRate = nextRate;
    } else {
      state.savedRate = null;
    }
    updateUI();
  }

  /** Запасной путь, если хук Enhancer недоступен. */
  function applyDirect(rate, save) {
    const video = state.video || findVideo();
    if (video) {
      try {
        video.playbackRate = rate;
        video.defaultPlaybackRate = rate;
      } catch { /* ignore */ }
    }
    const channel = state.channel;
    if (save && channel) {
      bridge('set', { id: channel.id, name: channel.name, rate });
    }
  }

  async function forgetChannel() {
    const channel = state.channel;

    // Сбрасываем и кеш Enhancer (efytSpd): иначе он применит старую скорость
    // на следующем видео этого канала, хотя в storage записи уже нет.
    const hook = window.__efytChannelSpeed;
    if (hook && typeof hook.forget === 'function') {
      try { hook.forget(); } catch { /* ignore */ }
    }

    if (channel) await bridge('remove', { id: channel.id, name: channel.name });
    state.savedRate = null;
    setRate(DEFAULT_RATE, false); // применить 1×, но не записывать
    hidePanel();
  }

  // --------------------------------------------------------------------------
  // Интерфейс
  // --------------------------------------------------------------------------

  function createButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ytp-button ytcs-btn';
    button.title = 'Скорость для этого канала';
    button.setAttribute('aria-label', 'Скорость для этого канала');

    const label = document.createElement('span');
    label.className = 'ytcs-btn-label';
    label.textContent = '1×';
    button.append(label);

    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      togglePanel();
    });
    return button;
  }

  function createPanel() {
    const panel = document.createElement('div');
    panel.className = 'ytcs-panel';
    panel.hidden = true;

    const head = document.createElement('div');
    head.className = 'ytcs-head';
    const title = document.createElement('span');
    title.className = 'ytcs-title';
    title.textContent = 'Скорость канала';
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'ytcs-close';
    close.title = 'Закрыть';
    close.textContent = '×';
    head.append(title, close);

    const channel = document.createElement('div');
    channel.className = 'ytcs-channel';
    channel.textContent = 'Канал не определён';

    const row = document.createElement('div');
    row.className = 'ytcs-row';
    const minus = document.createElement('button');
    minus.type = 'button';
    minus.className = 'ytcs-step';
    minus.dataset.step = '-0.05';
    minus.textContent = '−';
    const value = document.createElement('span');
    value.className = 'ytcs-value';
    value.textContent = '1×';
    const plus = document.createElement('button');
    plus.type = 'button';
    plus.className = 'ytcs-step';
    plus.dataset.step = '0.05';
    plus.textContent = '+';
    row.append(minus, value, plus);

    const presets = document.createElement('div');
    presets.className = 'ytcs-presets';
    PRESETS.forEach((rate) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'ytcs-preset';
      button.dataset.rate = String(rate);
      button.textContent = formatRate(rate);
      presets.append(button);
    });

    const foot = document.createElement('div');
    foot.className = 'ytcs-foot';
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.className = 'ytcs-reset';
    reset.textContent = 'Сбросить (1×)';
    const forget = document.createElement('button');
    forget.type = 'button';
    forget.className = 'ytcs-forget';
    forget.textContent = 'Забыть канал';
    foot.append(reset, forget);

    const hint = document.createElement('div');
    hint.className = 'ytcs-hint';
    hint.textContent = 'Общая база с Enhancer: скорость запоминается для канала';

    panel.append(head, channel, row, presets, foot, hint);

    panel.addEventListener('click', (event) => {
      event.stopPropagation();
      const button = event.target.closest('button');
      if (!button) return;

      if (button.classList.contains('ytcs-close')) {
        hidePanel();
      } else if (button.classList.contains('ytcs-step')) {
        setRate(getDisplayRate() + Number(button.dataset.step), true);
      } else if (button.dataset.rate) {
        setRate(Number(button.dataset.rate), true);
      } else if (button.classList.contains('ytcs-reset')) {
        setRate(DEFAULT_RATE, true);
      } else if (button.classList.contains('ytcs-forget')) {
        forgetChannel();
      }
    });

    ['mousedown', 'mouseup', 'dblclick'].forEach((type) => {
      panel.addEventListener(type, (event) => event.stopPropagation());
    });

    return panel;
  }

  function getDisplayRate() {
    const video = state.video || findVideo();
    if (video && Number.isFinite(video.playbackRate)) {
      return clampRate(video.playbackRate);
    }
    return state.savedRate !== null ? state.savedRate : DEFAULT_RATE;
  }

  function updateUI() {
    const player = state.player || findPlayer();
    if (!player) return;

    const rate = getDisplayRate();
    const button = player.querySelector('.ytcs-btn');
    if (button) {
      const label = button.querySelector('.ytcs-btn-label');
      if (label) label.textContent = formatRate(rate);
      button.classList.toggle('ytcs-saved', state.savedRate !== null);
      button.title = state.channel
        ? `Скорость для канала «${state.channel.name || state.channel.url}»`
        : 'Скорость для этого канала';
    }

    const panel = player.querySelector('.ytcs-panel');
    if (!panel) return;

    const channelLabel = panel.querySelector('.ytcs-channel');
    if (channelLabel) {
      channelLabel.textContent = state.channel
        ? (state.channel.name || state.channel.url)
        : 'Канал не определён';
      channelLabel.title = state.channel ? (state.channel.url || '') : '';
    }

    const value = panel.querySelector('.ytcs-value');
    if (value) value.textContent = formatRate(rate);

    panel.querySelectorAll('.ytcs-preset').forEach((preset) => {
      preset.classList.toggle('ytcs-active', isSameRate(preset.dataset.rate, rate));
    });

    const forget = panel.querySelector('.ytcs-forget');
    if (forget) forget.disabled = state.savedRate === null;
  }

  function ensureUI() {
    if (!isWatchPage()) {
      removeUI();
      return;
    }

    const player = state.player || findPlayer();
    if (!player) return;

    const controls = player.querySelector('.ytp-right-controls');
    if (!controls) return;

    if (!controls.querySelector('.ytcs-btn')) {
      const button = createButton();
      const settings = controls.querySelector('.ytp-settings-button');
      if (settings && settings.parentElement) {
        settings.parentElement.insertBefore(button, settings);
      } else {
        controls.append(button);
      }
    }

    if (!player.querySelector('.ytcs-panel')) {
      player.appendChild(createPanel());
    }

    updateUI();
  }

  function removeUI() {
    document.querySelectorAll('.ytcs-btn, .ytcs-panel').forEach((node) => node.remove());
  }

  function togglePanel() {
    const player = state.player || findPlayer();
    if (!player) return;
    const panel = player.querySelector('.ytcs-panel');
    if (!panel) return;

    if (panel.hidden) {
      panel.hidden = false;
      refreshChannel(true);
      updateUI();
    } else {
      panel.hidden = true;
    }
  }

  function hidePanel() {
    document.querySelectorAll('.ytcs-panel').forEach((panel) => {
      panel.hidden = true;
    });
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('.ytcs-panel, .ytcs-btn')) return;
    hidePanel();
  }, true);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hidePanel();
  });

  // --------------------------------------------------------------------------
  // События YouTube и медиаэлемента
  // --------------------------------------------------------------------------

  function onNavigateStart() {
    state.channelKey = '';
    hidePanel();
  }

  function onNavigateFinish() {
    state.channelKey = '';
    setTimeout(() => refreshChannel(true), 300);
    scheduleSavedRefresh(1200);
  }

  ['yt-navigate-start', 'yt-navigate-finish', 'yt-page-data-updated', 'yt-player-updated']
    .forEach((name) => {
      document.addEventListener(name, () => {
        if (name === 'yt-navigate-start') onNavigateStart();
        else if (name === 'yt-navigate-finish') onNavigateFinish();
        else {
          state.channelKey = '';
          setTimeout(() => refreshChannel(true), 250);
        }
      });
    });

  function onRateChange(event) {
    if (!isWatchPage()) return;
    const video = event.target;
    if (!(video instanceof HTMLVideoElement)) return;
    if (state.video && video !== state.video) return;

    state.video = video;
    updateUI();
    scheduleSavedRefresh(600);
  }

  document.addEventListener('ratechange', onRateChange, true);
  document.addEventListener('loadedmetadata', () => {
    state.video = findVideo();
    updateUI();
    scheduleSavedRefresh(1000);
  }, true);
  document.addEventListener('playing', () => updateUI(), true);

  // --------------------------------------------------------------------------
  // Watchdog: подмена плеера/видео и SPA-переходы без событий
  // --------------------------------------------------------------------------

  function watchdog() {
    if (!isWatchPage()) {
      removeUI();
      state.channelKey = '';
      return;
    }

    const player = findPlayer();
    if (player !== state.player) {
      state.player = player;
      ensureUI();
    }

    const video = findVideo();
    if (video !== state.video) {
      state.video = video;
      updateUI();
    }

    if (location.href !== state.lastHref) {
      state.lastHref = location.href;
      state.channelKey = '';
      hidePanel();
      setTimeout(() => refreshChannel(true), 400);
      scheduleSavedRefresh(1500);
    }

    if (!state.channelKey) refreshChannel();
    ensureUI();
  }

  setInterval(watchdog, 1000);
  watchdog();
})();
