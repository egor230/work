// ============================================================
// background.js — service worker (диспетчер)
//   ЛКМ по значку     = старт/стоп текущего режима (как трей-клик в Python)
//   ПКМ по значку     = меню (как трей-меню в Python): Авто / Запись / Выход
//   подсказки живого текста = облачко (как show_message в PyQt)
// ============================================================

let on = false;
let mode = "auto";          // "auto" | "record" — как self.mode
let seq = 0;
let aliceTabId = null;
let port = null;
let lastLiveText = "";      // что показываем в облачке/popup сейчас
let lastPhrase = "";        // последняя напечатанная фраза (для popup)
let alwaysHear = true;      // держать окно Алисы видимым (анти-троттлинг Chrome)

// ---------- контекстное меню (аналог трей-меню PyQt) ----------
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "mode_auto",   title: "Режим: Авто",    type: "radio", checked: true,  contexts: ["action"] });
    chrome.contextMenus.create({ id: "mode_record", title: "Режим: Запись",  type: "radio", checked: false, contexts: ["action"] });
    chrome.contextMenus.create({ id: "sep1", type: "separator", contexts: ["action"] });
    chrome.contextMenus.create({ id: "stop_now", title: "Остановить ввод", contexts: ["action"], enabled: false });
  });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId === "mode_auto" || info.menuItemId === "mode_record") {
    const newMode = info.menuItemId === "mode_record" ? "record" : "auto";
    const wasOn = on;
    if (on) await stopListening();          // сменить режим можно только «на ходу» остановив
    mode = newMode;
    chrome.contextMenus.update("mode_auto",   { checked: newMode === "auto" });
    chrome.contextMenus.update("mode_record", { checked: newMode === "record" });
    chrome.storage.local.set({ mode });
    if (wasOn) setTimeout(() => toggleListening(), 300); // сразу в новом режиме
  }
  if (info.menuItemId === "stop_now") {
    await stopListening();
  }
});

// восстановить режим после перезапуска браузера
chrome.storage.local.get("mode").then((s) => {
  if (s.mode === "record" || s.mode === "auto") mode = s.mode;
});

// ---------- keepalive: не давать SW уснуть, пока слушаем ----------
// ---------- keepalive: будильник только ПРОДЛЕВАЕТ жизнь service worker ----------
// Никаких ping-проверок и disconnect-тестов: порт живёт сам. Будильник лишь
// не даёт SW уснуть и ПОДНИМАЕТ порт, если его не стало (без разрыва самим).
function startKeepalive() {
  chrome.alarms.create("keepalive", { periodInMinutes: 0.35 });
}
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === "keepalive" && on) {
    if (!port) connectNative();          // порт исчез — тихо поднять (не отключая)
    // обновить пункт меню «Остановить»
    chrome.contextMenus.update("stop_now", { enabled: on });
    // АНТИ-ТРОТТЛИНГ: если окно Алисы свернули/закрыли — вернуть видимость
    if (alwaysHear) await ensureAliceVisible();
  }
});

// ---------- native host ----------
function connectNative() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative("voice_input_yandex");
    // Разрыв (браузер закрыл хост и т.п.): тихо переподключиться — бесконечно,
    // без счётчиков и отказов. Слушание НЕ останавливаем никогда.
    port.onDisconnect.addListener(() => {
      port = null;
      if (on) setTimeout(() => { if (on && !port) connectNative(); }, 1000);
    });
    // СРАЗУ НЕ посылаем ничего: каждое соединение стартует Python-хост —
    // пусть ждёт первую фразу. Никаких ping.
  } catch (e) {
    port = null;
    // и здесь не сдаёмся: повтор через 1 с, если слушаем
    if (on) setTimeout(() => { if (on && !port) connectNative(); }, 1000);
  }
}

function badge(text, color = "#d32f2f", ms = 4000) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  if (ms) setTimeout(() => chrome.action.setBadgeText({ text: "" }), ms);
}

// ---------- вкладка Алисы ----------
async function findAliceTab() {
  const tabs = await chrome.tabs.query({ url: "https://alice.yandex.ru/*" });
  return tabs.length ? tabs[0] : null;
}

// ---------- АНТИ-ТРОТТЛИНГ: фоновая вкладка в Chrome зажата (таймеры до 1 c,
// потом до 1/мин). Как в Python-скрипте (маленькое окно 532×467) — держим
// Алису в ВИДИМОМ отдельном окошке поверх всего: видимая вкладка не
// троттлится даже без фокуса. Вкладка ПЕРЕНОСИТСЯ (не перезагружается,
// вход сохраняется). Активная вкладка пользователя не крадём.
async function ensureAliceVisible() {
  const tab = await findAliceTab();
  if (!tab) return;
  aliceTabId = tab.id;
  const isHidden = !tab.active || (tab.windowId && !await isVisibleWindow(tab.windowId));
  if (!isHidden) return;
  try {
    // перенести вкладку в маленькое always-on-top окно (как 532×467 у Python)
    const win = await chrome.windows.create({
      tabId: tab.id,
      type: "popup",
      width: 532,
      height: 467,
      left: 0,
      top: 378,
      focused: false          // НЕ красть фокус у текущего окна
    });
    console.log("Алиса перенесена в видимое мини-окно (анти-троттлинг)");
  } catch (e) {
    console.warn("не удалось перенести:", e);
  }
}

async function isVisibleWindow(winId) {
  try {
    const w = await chrome.windows.get(winId);
    return w.state !== "minimized";
  } catch (e) { return false; }
}

async function ensureContentScript(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "PING" });
    return true;
  } catch (e) {
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ["content-alice.js"] });
      return true;
    } catch (e2) {
      return false;
    }
  }
}

async function sendAlice(type) {
  const tab = await findAliceTab();
  if (!tab) return null;
  aliceTabId = tab.id;
  if (!(await ensureContentScript(tab.id))) return null;
  await chrome.tabs.sendMessage(tab.id, { type, seq, mode });
  return tab;
}

// ---------- значок: ЛКМ старт/стоп ----------
async function toggleListening() {
  on ? await stopListening() : await startListening();
}

async function startListening() {
  const tab = await findAliceTab();
  if (!tab) {
    badge("!");
    chrome.action.setTitle({ title: "Откройте вкладку alice.yandex.ru" });
    return;
  }
  seq++;
  on = true;
  connectNative();
  startKeepalive();
  // Алиса обязана быть ВИДИМОЙ, иначе Chrome затроттлит вкладку и «не услышит»
  if (alwaysHear) await ensureAliceVisible();
  chrome.action.setIcon({ path: { 16: "icons/record16.png", 48: "icons/record48.png", 128: "icons/record128.png" } });
  chrome.action.setTitle({ title: `Слушаю (${mode === "record" ? "Запись" : "Авто"}) — клик: стоп` });
  chrome.contextMenus.update("stop_now", { enabled: true });
  const sent = await sendAlice("START_LISTENING");
  if (!sent) {
    on = false;
    chrome.action.setIcon({ path: { 16: "icons/voice16.png", 48: "icons/voice48.png", 128: "icons/voice128.png" } });
    badge("!");
  }
}

async function stopListening() {
  on = false;
  chrome.action.setIcon({ path: { 16: "icons/voice16.png", 48: "icons/voice48.png", 128: "icons/voice128.png" } });
  chrome.action.setTitle({ title: "Голосовой ввод (клик — старт)" });
  chrome.contextMenus.update("stop_now", { enabled: false });
  hideBubble();
  await sendAlice("STOP_LISTENING");
  if (port) { try { port.disconnect(); } catch (e) {} port = null; }
  chrome.alarms.clear("keepalive");
  // вернуть Алису на место? НЕТ: оставляем мини-окно — пользователь сам
  // решит (перетащит вкладку обратно). Слушание выключено — троттлинг не важен.
}

chrome.action.onClicked.addListener(toggleListening);

// ---------- сообщения от content-alice + popup ----------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "PING") { sendResponse({ pong: true }); return; }

  // popup открылся — отдать состояние (popup сам слушает broadcast ниже)
  if (msg.type === "POPUP_OPEN") {
    sendResponse({ on, mode, text: lastLiveText || lastPhrase });
    return;
  }
  if (msg.type === "POPUP_TOGGLE") {
    toggleListening();
    sendResponse({ ok: true });
    return;
  }

  if (msg.type === "PHRASE_READY") {
    lastPhrase = msg.text;
    lastLiveText = msg.text;
    const send = () => {
      if (port) { port.postMessage({ cmd: "print", text: msg.text }); return true; }
      return false;
    };
    if (!send()) {
      badge("P");
      connectNative();
      setTimeout(() => { if (!send()) badge("P"); }, 500);
      setTimeout(() => { if (!send()) badge("P"); }, 1500);
    }
    return;
  }

  if (msg.type === "LIVE_TEXT") {
    lastLiveText = msg.text;
    showBubble(msg.text);   // подсказка живого текста (как show_message)
    return;                 // popup получает то же через broadcast выше
  }

  if (msg.type === "STATE" && msg.state === "on") {
    badge("mic", "#1e8e3e", 1500);
    return;
  }
});

// ---------- облачко-подсказка (аналог PyQt label) ----------
// Рисуем в ПЕРВОМ ОКНЕ браузера, АКТИВНУЮ вкладку НЕ трогаем:
// host_permissions: <all_urls> + scripting — теперь доступ есть всегда.
async function showBubble(text) {
  if (!text) return;
  lastLiveText = text;
  try {
    const [win] = await chrome.windows.getAll({ windowTypes: ["normal"], populate: false });
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab || tab.id === aliceTabId) return; // не рисовать в самой Алисе
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (t) => {
        let el = document.getElementById("__voice_bubble__");
        if (!el) {
          el = document.createElement("div");
          el.id = "__voice_bubble__";
          el.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);" +
            "background:rgba(20,20,20,.85);color:#fff;padding:10px 18px;border-radius:12px;" +
            "font:14px sans-serif;z-index:2147483647;max-width:70vw;white-space:nowrap;" +
            "overflow:hidden;text-overflow:ellipsis;box-shadow:0 4px 16px rgba(0,0,0,.4)";
          document.documentElement.appendChild(el);
        }
        el.textContent = t;
        clearTimeout(el.__t);
        el.__t = setTimeout(() => el.remove(), 4000);
      },
      args: [text]
    });
  } catch (e) {
    // вкладка недоступна (chrome:// и т.п.) — тихо пропускаем
  }
}

async function hideBubble() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab) return;
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.getElementById("__voice_bubble__")?.remove()
    });
  } catch (e) {}
}
