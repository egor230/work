/*
##
##  Enhancer for YouTube™
##  =====================
##
##  Author: Max RF <https://www.mrfdev.com>
##
##  This file is protected by copyright laws and international copyright
##  treaties, as well as other intellectual property laws and treaties.
##
##  All rights not expressly granted to you are retained by the author.
##  Read the license.txt file for more details.
##
##  © MRFDEV.com - All Rights Reserved
##
*/
importScripts("config.js");

// === efyt-backup: auto-restore config-backup.json on install/update ===
// Reads config-backup.json from the extension folder (if present) and
// merges it into chrome.storage.local. In unpacked mode the file is
// directly readable via chrome.runtime.getURL().
(async function _efytAutoRestore(){
  try {
    const url = chrome.runtime.getURL("config-backup.json");
    const res = await fetch(url);
    if (!res.ok) return; // file not found — normal on first install
    const data = await res.json();
    const restore = {};
    for (const k in data) if (k !== "_meta") restore[k] = data[k];
    if (Object.keys(restore).length > 0) {
      await chrome.storage.local.set(restore);
      console.info(`[efyt-backup] auto-restored ${Object.keys(restore).length} keys from config-backup.json`);
    }
  } catch (e) {
    console.info("[efyt-backup] no config-backup.json found (first install) — skip:", e.message);
  }
})();

// efyt-backup: save/restore handlers
chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  if (msg && msg.request === "efyt-backup-save") {
    try {
      const data = await chrome.storage.local.get(null);
      const out = Object.assign({ _meta: { savedAt: new Date().toISOString(), version: chrome.runtime.getManifest().version } }, data);
      const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      chrome.downloads.download({ url, filename: "config-backup.json", conflictAction: "overwrite", saveAs: true },
        function () {
          if (chrome.runtime.lastError) sendResponse({ ok: false, error: chrome.runtime.lastError.message });
          else sendResponse({ ok: true, file: "config-backup.json (в Загрузки — скопируйте в папку расширения)" });
          URL.revokeObjectURL(url);
        });
    } catch (e) { sendResponse({ ok: false, error: e.message }); }
    return true; // async response
  }
  if (msg && msg.request === "efyt-backup-restore") {
    try {
      const res = await fetch(chrome.runtime.getURL("config-backup.json"));
      if (!res.ok) throw new Error("HTTP " + res.status + " — файл не найден в папке расширения");
      const data = await res.json();
      const restore = {};
      for (const k in data) if (k !== "_meta") restore[k] = data[k];
      if (Object.keys(restore).length === 0) throw new Error("файл пуст");
      await chrome.storage.local.set(restore);
      sendResponse({ ok: true, keys: Object.keys(restore) });
    } catch (e) { sendResponse({ ok: false, error: e.message }); }
    return true;
  }
});
(f=>{chrome.action.onClicked.addListener(()=>{chrome.runtime.openOptionsPage()});chrome.runtime.setUninstallURL("https://www.mrfdev.com/event?n=uninstall&b=chrome&e=enhancer-for-youtube&v="+chrome.runtime.getManifest().version);chrome.runtime.onInstalled.addListener(async c=>{if("install"===c.reason)c=(await chrome.tabs.query({url:"*://www.youtube.com/*"})).length,chrome.tabs.create({url:chrome.runtime.getURL("html/options.html"+(0<c?`?youtube_tabs_open=${c}`:""))}),chrome.tabs.create({url:"https://www.mrfdev.com/event?n=install&b=chrome&e=enhancer-for-youtube&v="+
chrome.runtime.getManifest().version,active:!0}),chrome.storage.local.set({date:Date.now(),update:Date.now()});else if("update"===c.reason){var a=await chrome.storage.local.get(),b={};/2\.0\.(10[3-9]|11[0-9]|12[0-1])/.test(c.previousVersion)&&(Array.isArray(a.controls)&&(b.controls=a.controls.filter(d=>"whitelist"!==d&&"not-interested"!==d)),await chrome.storage.local.remove(["blockads","blockadsexceptforsubs","whitelist"]));if(/^2\.0/.test(c.previousVersion)){b.reload=!0;b.videofilters=f.videofilters;
var e="blur brightness contrast grayscale huerotate invert saturate sepia".split(" ");e.forEach(d=>{a[d]&&("huerotate"===d?b.videofilters.rotation=a[d]:"invert"===d?b.videofilters.inversion=a[d]:"saturate"===d?b.videofilters.saturation=a[d]:b.videofilters[d]=a[d])});a.backgroundcolor&&(b.backdropcolor=a.backgroundcolor,e.push("backgroundcolor"));a.backgroundopacity&&(b.backdropopacity=a.backgroundopacity,e.push("backgroundopacity"));a.customcssrules&&(b.customcss=a.customcssrules,e.push("customcssrules"));
await chrome.storage.local.remove(e);a.miniplayersize&&(b.miniplayersize=a.miniplayersize.replace("_",""));a.miniplayerposition&&(b.miniplayerposition=a.miniplayerposition.replace("_",""));a.themevariant&&(b.vendorthemevariant=a.themevariant.replace("-youtube-light",""),b.themevariant=f.themevariant)}/3\.0\.1[0-4]/.test(c.previousVersion)&&Array.isArray(a.controls)&&0<a.controls.length&&(b.controls=[...a.controls,"experiments"]);c.previousVersion!==chrome.runtime.getManifest().version&&(b.reload=
!0,b.previousversion=c.previousVersion,b.update=Date.now(),/3\.0\.1[0-4]/.test(c.previousVersion)&&(b.whatsnew=!0));0<Object.keys(b).length&&chrome.storage.local.set(b)}});chrome.runtime.onMessage.addListener(async(c,a)=>{switch(c.request){case "pop-up-player":chrome.windows.create(c.options,b=>{chrome.windows.update(b.id,{drawAttention:!0})});break;case "options-page":chrome.runtime.openOptionsPage();break;case "whats-new":await chrome.storage.local.set({whatsnew:!1});chrome.tabs.create({url:"html/whats-new.html",
active:!0});break;case "dark-theme-off":chrome.storage.local.set({darktheme:!1});break;case "open-options":chrome.runtime.openOptionsPage();break;case "keyboard-shortcuts":chrome.tabs.create({url:"https://www.mrfdev.com/youtube-keyboard-shortcuts",active:!0});break;case "configure-keyboard-shortcuts":chrome.tabs.create({url:"chrome://extensions/shortcuts",active:!0})}});chrome.storage.onChanged.addListener(c=>{for(const a in c)void 0!==c[a].newValue&&"customscript"!==a&&"popuplayersize"!==a&&chrome.tabs.query({url:"*://www.youtube.com/*"},b=>{b.forEach(e=>
{chrome.tabs.sendMessage(e.id,{message:"preference-changed",name:a,value:c[a].newValue,oldvalue:c[a].oldValue}).catch(()=>{})})})});chrome.commands.onCommand.addListener(c=>{var a={"c070-toggle-loop":"loop","c080-stop-video":"stop","c090-reverse-playlist":"reverse-playlist","c100-toggle-volume-booster":"volume-booster","c130-toggle-annotations":"cards-end-screens","c140-toggle-cinema-mode":"cinema-mode","c150-toggle-player-size":"size","c160-center-video-player":"size","c170-pop-up-player":"pop-up-player","c180-decrease-speed":"speed-minus",
"c190-increase-speed":"speed-plus","c200-default-speed":"speed","c210-normal-speed":"speed","c220-toggle-video-filters":"video-filters","c230-flip-horizontally":"flip-horizontally","c240-flip-vertically":"flip-vertically","c250-take-screenshot":"screenshot","c260-keyboard-shortcuts":"keyboard-shortcuts","c270-custom-script":"custom-script"};switch(c){case "c000-options-page":chrome.runtime.openOptionsPage();break;case "c020-theme-youtube-dark":chrome.storage.local.set({darktheme:!0,theme:"default-dark"});
break;case "c025-theme-enhanced-dark":chrome.storage.local.set({darktheme:!0,theme:"enhanced-dark"});break;case "c030-theme-youtube-deep-dark":chrome.storage.local.set({darktheme:!0,theme:"youtube-deep-dark"});break;case "c040-theme-youtube-deep-dark-custom":chrome.storage.local.set({darktheme:!0,theme:"youtube-deep-dark-custom"});break;case "c050-theme-custom-theme":chrome.storage.local.get({customtheme:f.customtheme},b=>{chrome.storage.local.set({customtheme:!b.customtheme})});break;default:chrome.tabs.query({lastFocusedWindow:!0,
active:!0},b=>{b[0]&&chrome.tabs.sendMessage(b[0].id,{message:"command",command:c,control:a[c]?a[c]:""}).catch(()=>{})})}})})(config);
// === ytcs: контекстное меню «Поиск на YouTube» ===
// Выделить текст на любой странице → правый клик → «Поиск на YouTube»:
// открывается новая вкладка с результатами поиска YouTube.
// Пункт меню и иконка перенесены из расширения «Contextual Search for YouTube».
const YTCS_MENU_ID = "ytcs-search-youtube";

function ytcsCreateMenu() {
  // removeAll убирает дубли после переустановки/обновления расширения.
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: YTCS_MENU_ID,
      title: "Поиск на YouTube",
      contexts: ["selection"]
    });
  });
}

chrome.runtime.onInstalled.addListener(ytcsCreateMenu);
chrome.runtime.onStartup.addListener(ytcsCreateMenu);

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId !== YTCS_MENU_ID) return;

  // Схлопываем переносы строк и повторные пробелы — YouTube их не любит.
  const query = String(info.selectionText || "").replace(/\s+/g, " ").trim();
  if (!query) return;

  // encodeURIComponent сохраняет кириллицу и спецсимволы (в оригинале они терялись).
  chrome.tabs.create({
    url: "https://www.youtube.com/results?search_query=" + encodeURIComponent(query)
  });
});

// === efyt-speeds-json: зеркало скоростей по каналам в JSON-файл (§12) ===
//
// Таблица канальных скоростей (§2/§7/§9) хранится в
// chrome.storage.local.channelspeeds. Все писатели — channel-speed-set
// (колесо, кнопки, нативное меню YouTube, горячие клавиши) и панель
// скорости (channel-speed-bridge) — меняют этот один ключ, поэтому
// достаточно слушать chrome.storage.onChanged: фиксируется любой способ
// смены скорости.
//
// Зеркало на диск:
//   1) через native messaging host com.efyt.channelspeeds
//      (native-host/efyt-json-host.py, регистрация — install-native-host.sh)
//      — пишет точно в channelspeeds.json в папке расширения;
//   2) если хост не установлен — fallback через chrome.downloads:
//      «расширения/Enhancer for YouTube/channelspeeds.json» относительно
//      папки загрузок браузера. При стандартной папке загрузок это та же
//      папка расширения; при изменённой — подпапка внутри неё (README §12).
//
// Если файл на диске новее внутреннего хранилища — его правили вручную:
// содержимое импортируется обратно в chrome.storage (двусторонняя синхронизация).

const EFYT_SPEEDS_HOST = "com.efyt.channelspeeds";
const EFYT_SPEEDS_FALLBACK_REL = "расширения/Enhancer for YouTube/channelspeeds.json";
const EFYT_SPEEDS_DEBOUNCE_MS = 1500;

let efytSpdJsonTimer = 0, efytSpdJsonBusy = !1, efytSpdJsonDirty = !1, efytSpdJsonSig = "";

/** Сигнатура таблицы (без меток времени) — чтобы не перезаписывать файл без изменений. */
function efytSpdSignature(speeds) {
  const keys = Object.keys(speeds).sort();
  return JSON.stringify(keys.map(k => [k, speeds[k]]));
}

/** Собирает JSON-текст: speeds — каноническая таблица, channels — человекочитаемый вид. */
function efytSpdJsonBuild(speeds) {
  const now = new Date().toISOString();
  const namesBySpeed = {};
  for (const k in speeds) {
    const v = speeds[k];
    if (typeof v === "number" && Number.isFinite(v) && k.startsWith("name:")) {
      (namesBySpeed[v] || (namesBySpeed[v] = [])).push(k.slice(5));
    }
  }
  const channels = [];
  for (const k in speeds) {
    const v = speeds[k];
    if (typeof v !== "number" || !Number.isFinite(v) || k.startsWith("name:")) continue;
    const names = namesBySpeed[v] || [];
    // Имя однозначно восстанавливается, когда у скорости один «name:»-ключ.
    channels.push({ id: k, name: 1 === names.length ? names[0] : null, speed: v });
  }
  channels.sort((a, b) => String(a.name || a.id).localeCompare(String(b.name || b.id), "ru"));
  return JSON.stringify({
    _meta: {
      about: "Скорости воспроизведения по каналам — Enhancer for YouTube™ (кастом, §12)",
      note: "speeds — каноническая таблица: ключ = channelId либо name:<Имя канала>, значение = скорость. Файл перезаписывается расширением автоматически; если файл отредактирован вручную и стал новее внутреннего хранилища — правки импортируются в расширение.",
      updatedAt: now,
      channels: channels.length
    },
    updatedAt: now,
    speeds: speeds,
    channels: channels
  }, null, 2) + "\n";
}

/** Один запрос к native host: Promise с ответом или reject (хост недоступен/таймаут). */
function efytSpdHostRequest(msg) {
  return new Promise((resolve, reject) => {
    let settled = !1, port;
    try { port = chrome.runtime.connectNative(EFYT_SPEEDS_HOST); }
    catch (e) { reject(e); return; }
    const t = setTimeout(() => {
      if (settled) return;
      settled = !0;
      try { port.disconnect(); } catch (e) {}
      reject(new Error("host timeout"));
    }, 5000);
    port.onMessage.addListener(m => {
      if (settled) return;
      settled = !0;
      clearTimeout(t);
      try { port.disconnect(); } catch (e) {}
      resolve(m);
    });
    port.onDisconnect.addListener(() => {
      if (settled) return;
      settled = !0;
      clearTimeout(t);
      reject(new Error(chrome.runtime.lastError ? chrome.runtime.lastError.message : "host disconnected"));
    });
    port.postMessage(msg);
  });
}

/** Импорт отредактированного вручную JSON обратно в chrome.storage.local. */
async function efytSpdJsonImport(text, mtimeMs) {
  const doc = JSON.parse(text);
  const speeds = doc && doc.speeds;
  if (!speeds || typeof speeds !== "object" || Array.isArray(speeds)) {
    throw new Error("в JSON нет объекта speeds");
  }
  const clean = {};
  for (const k in speeds) {
    if (typeof speeds[k] === "number" && Number.isFinite(speeds[k])) clean[k] = speeds[k];
  }
  await chrome.storage.local.set({ channelspeeds: clean, channelspeedsUpdatedAt: mtimeMs || Date.now() });
  efytSpdJsonSig = efytSpdSignature(clean);
}

async function efytSpdJsonSync() {
  if (efytSpdJsonBusy) { efytSpdJsonDirty = !0; return; }
  efytSpdJsonBusy = !0;
  try {
    const st = await chrome.storage.local.get({ channelspeeds: {}, channelspeedsUpdatedAt: 0 });
    const speeds = st.channelspeeds && "object" === typeof st.channelspeeds && !Array.isArray(st.channelspeeds) ? st.channelspeeds : {};
    const sig = efytSpdSignature(speeds);
    try {
      // --- 1) native host ---
      const cur = await efytSpdHostRequest({ type: "read" });
      if (cur && cur.ok) {
        if (cur.data && cur.mtimeMs > st.channelspeedsUpdatedAt) {
          // Файл на диске новее хранилища → его правили вручную: импортируем.
          await efytSpdJsonImport(cur.data, cur.mtimeMs);
          return;
        }
        if (sig !== efytSpdJsonSig) {
          const res = await efytSpdHostRequest({ type: "write", data: efytSpdJsonBuild(speeds) });
          if (res && res.ok) {
            efytSpdJsonSig = sig;
            await chrome.storage.local.set({ channelspeedsUpdatedAt: res.mtimeMs || Date.now() });
          }
        }
        return;
      }
      // cur.ok === false (ошибка чтения) — падаем в fallback
    } catch (e) { /* хост не установлен или не отвечает — fallback */ }
    // --- 2) fallback: chrome.downloads, перезапись одного и того же файла ---
    if (sig !== efytSpdJsonSig) {
      efytSpdJsonSig = sig;
      const url = "data:application/json;charset=utf-8," + encodeURIComponent(efytSpdJsonBuild(speeds));
      chrome.downloads.download({ url, filename: EFYT_SPEEDS_FALLBACK_REL, conflictAction: "overwrite", saveAs: !1 },
        () => void chrome.runtime.lastError);
      await chrome.storage.local.set({ channelspeedsUpdatedAt: Date.now() });
    }
  } finally {
    efytSpdJsonBusy = !1;
    if (efytSpdJsonDirty) { efytSpdJsonDirty = !1; setTimeout(efytSpdJsonSync, 300); }
  }
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !changes.channelspeeds) return;
  // Первое изменение пишем сразу, серию слепляем дебаунсом.
  if (!efytSpdJsonTimer) efytSpdJsonSync();
  clearTimeout(efytSpdJsonTimer);
  efytSpdJsonTimer = setTimeout(() => { efytSpdJsonTimer = 0; efytSpdJsonSync(); }, EFYT_SPEEDS_DEBOUNCE_MS);
});

chrome.runtime.onStartup.addListener(() => { efytSpdJsonSig = ""; setTimeout(efytSpdJsonSync, 800); });
chrome.runtime.onInstalled.addListener(() => { efytSpdJsonSig = ""; setTimeout(efytSpdJsonSync, 800); });
