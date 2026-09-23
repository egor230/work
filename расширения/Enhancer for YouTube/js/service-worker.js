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