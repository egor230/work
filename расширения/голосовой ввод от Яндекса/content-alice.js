// ============================================================
// content-alice.js — вкладка alice.yandex.ru
// Режим АВТО:   пузырьки + col|сл|th|белый круг + двойной клик
// Режим ЗАПИСЬ: перенос toggle()/talk() из Python:
//   клик окникс -> пауза -> клик кнопки диктовки ->
//   VAD через AudioWorkletNode (БЕЗ deprecated ScriptProcessor):
//     mean(abs)*100 > 4 = речь; тишина 3.3 c -> СТОП ->
//   кнопка-стоп (find_stop_button) -> текст из поля ввода -> печать
// ============================================================

(() => {
  "use strict";
  if (window.__voiceInputInstalled) return;
  window.__voiceInputInstalled = true;

  let listening = false;
  let mode = "auto";
  let bubbleCount = 0;
  let printedText = "";
  let mo = null;
  let debounceT = null;
  let lastClickAt = 0;
  const CLICK_MIN_INTERVAL = 1800;
  const DOUBLE_CLICK_MS = 2400;
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // ---- константы talk() из Python ----
  const SILENCE_MS = 3300;
  const AMP_THRESHOLD = 4;
  const ON_PAUSE = 1000;
  const STOP_PAUSE = 360;

  const SEL = {
    button:  "button[data-testid='oknyx']",
    core:    ".StandaloneOknyxCore",
    white:   ".StandaloneOknyxCore-WhiteCircleWrapper",
    circles: ".StandaloneOknyxCore-ListeningCircle",
    bubbles: "[data-testid='message-bubble-container-from-user']",
    bubbleText: ".MessageBubble-Text",
    dictBtn: "button[data-testid='button-dictation-button']",
    stopBtn1: ".StandaloneRichInput-ControlsPlayer button.AliceButton_view_secondary",
    stopBtn2: "button.AliceButton_view_secondary.AliceButton_square",
    inputField: "textarea[data-testid='inputbase-textarea'], input[role='textbox'], textarea[role='textbox']"
  };

  function send(msg) {
    try { chrome.runtime.sendMessage(msg, () => void chrome.runtime.lastError); }
    catch (e) {}
  }

  function readButton() {
    const btn = document.querySelector(SEL.button);
    if (!btn) return null;
    const core = btn.querySelector(SEL.core);
    if (!core) return null;
    const b = {
      btn, core,
      aria: btn.getAttribute("aria-label") || "",
      testid: core.getAttribute("data-testid") || "",
      classes: core.getAttribute("class") || "",
      circlesVisible: [...core.querySelectorAll(SEL.circles)]
        .some(c => getComputedStyle(c).display !== "none"),
      whiteHidden: false
    };
    const w = core.querySelector(SEL.white);
    b.whiteHidden = w ? getComputedStyle(w).display === "none" : false;
    return b;
  }

  function clickButton(btn) {
    if (!btn) return;
    const now = Date.now();
    if (now - lastClickAt < CLICK_MIN_INTERVAL) return;
    lastClickAt = now;
    btn.click();
  }
  function forceClickButton(btn) { if (btn) btn.click(); }

  function readBubbles() {
    const els = document.querySelectorAll(SEL.bubbles);
    let text = "";
    if (els.length) {
      const last = els[els.length - 1];
      const t = last.querySelector(SEL.bubbleText);
      text = (t && t.textContent.trim()) || last.textContent.trim();
    }
    return { count: els.length, text: text.trim() };
  }

  function readInputText() {
    const f = document.querySelector(SEL.inputField);
    if (!f) return "";
    return (f.value || f.textContent || "").trim();
  }

  // ---------- условия Python 1:1 ----------
  function isPhraseReady(b) {
    const aria = b.aria.toLowerCase();
    return (
      b.classes.includes("out") ||
      b.classes.includes("col") ||
      aria.includes("сл") ||
      b.testid.includes("th") ||
      b.whiteHidden
    );
  }
  function isLive(b) {
    return b.classes.includes("lis") && b.aria.toLowerCase().includes("стоп");
  }
  function isStuck(b) {
    return b.testid.includes("spe") && b.classes.includes("th") && b.circlesVisible;
  }
  function isIdle(b) {
    return b.testid.includes("su");
  }

  // ============================================================
  //  РЕЖИМ АВТО
  // ============================================================
  function onMutations() {
    if (!listening || mode !== "auto") return;
    const b = readButton();
    if (!b) return;
    const bubbles = readBubbles();

    if (isStuck(b)) { clickButton(b.btn); return; }
    if (isIdle(b))  { clickButton(b.btn); return; }

    if (isLive(b) && bubbles.text) {
      send({ type: "LIVE_TEXT", text: bubbles.text });
    }

    if (bubbles.count > bubbleCount && bubbles.text && bubbles.text !== printedText) {
      if (isPhraseReady(b)) {
        printedText = bubbles.text;
        bubbleCount = bubbles.count;
        send({ type: "PHRASE_READY", text: bubbles.text });
        window.scrollTo(0, document.body.scrollHeight);
        clickButton(b.btn);
        setTimeout(() => { forceClickButton(readButton()?.btn); }, DOUBLE_CLICK_MS);
      }
    }
  }

  function startObserver() {
    if (mo) return;
    mo = new MutationObserver(() => {
      clearTimeout(debounceT);
      debounceT = setTimeout(onMutations, 60);
    });
    mo.observe(document.body, {
      childList: true, subtree: true,
      attributes: true, attributeFilter: ["class", "data-testid", "aria-label"]
    });
  }

  // ============================================================
  //  РЕЖИМ ЗАПИСИ — talk() из Python на AudioWorkletNode
  // ============================================================
  let audioCtx = null, micStream = null, workletNode = null;
  let vadActive = false, lastSpeechAt = 0, vadFired = false;
  let livePollIv = null;
  let sessionBusy = false;   // защита от повторного входа в finishPhrase

  // Worklet-процессор: считает среднюю амплитуду и сам решает «речь/тишина».
  // Код передаётся строкой (blob) — отдельный файл не нужен.
  const WORKLET_SRC = `
    class VADProcessor extends AudioWorkletProcessor {
      constructor() {
        super();
        this.lastSpeechAt = currentTime;
        this.fired = false;
        this.threshold = ${AMP_THRESHOLD};
        this.silence = ${SILENCE_MS / 1000};
      }
      process(inputs) {
        const d = inputs[0] && inputs[0][0];
        if (d) {
          let s = 0;
          for (let i = 0; i < d.length; i++) s += Math.abs(d[i]);
          const meanAmp = (s / d.length) * 100;      // как mean_amp в Python
          if (meanAmp > this.threshold) {
            this.lastSpeechAt = currentTime;
          } else if (!this.fired && currentTime - this.lastSpeechAt >= this.silence) {
            this.fired = true;
            this.port.postMessage({ type: "SILENCE" });  // тишина 3.3 c
          }
        }
        return true;   // держать процессор живым
      }
    }
    registerProcessor("vad-processor", VADProcessor);
  `;

  // toggle() из Python: клик окникс -> _ON(): клик микрофона -> talk()
  async function startRecord() {
    sessionBusy = false;
    const b = readButton();
    if (b) forceClickButton(b.btn);
    await sleep(ON_PAUSE);
    const dict = document.querySelector(SEL.dictBtn);
    if (dict) forceClickButton(dict);
    await sleep(ON_PAUSE);
    startLiveTextPoll();
    await startVAD();
  }

  async function startVAD() {
    vadActive = true;
    vadFired = false;
    lastSpeechAt = Date.now();
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      send({ type: "STATE", state: "no_mic" });   // микрофон не дали — сообщить
      finishPhrase();                             // забрать что есть и закончить
      return;
    }
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      if (audioCtx.state === "suspended") await audioCtx.resume();
      const blob = new Blob([WORKLET_SRC], { type: "application/javascript" });
      const url = URL.createObjectURL(blob);
      await audioCtx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      const source = audioCtx.createMediaStreamSource(micStream);
      workletNode = new AudioWorkletNode(audioCtx, "vad-processor");
      workletNode.port.onmessage = (e) => {
        if (e.data && e.data.type === "SILENCE" && vadActive && !vadFired) {
          vadFired = true;
          finishPhrase();
        }
      };
      source.connect(workletNode);       // НЕ подключаем к destination:
      //                                    микрофон не идёт в динамики
      // AudioContext в фоне может быть приостановлен — держим живым
      keepAudioAlive();
    } catch (e) {
      send({ type: "STATE", state: "vad_error" });
      finishPhrase();
    }
  }

  // КРИТИЧНО: у фоновой вкладки AudioContext suspend-ится браузером.
  // Но вкладка Алисы всегда ВИДИМА (мини-окно, анти-троттлинг) — контекст
  // живёт. На всякий случай проверяем раз в 2 c и будим.
  function keepAudioAlive() {
    if (!vadActive || !audioCtx) return;
    if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
    setTimeout(keepAudioAlive, 2000);
  }

  function stopVAD() {
    vadActive = false;
    try { if (workletNode) { workletNode.port.onmessage = null; workletNode.disconnect(); } } catch (e) {}
    try { if (audioCtx) audioCtx.close(); } catch (e) {}
    try { if (micStream) micStream.getTracks().forEach(t => t.stop()); } catch (e) {}
    audioCtx = null; micStream = null; workletNode = null;
  }

  // живой текст из поля ввода -> popup (каждые 400 мс; вкладка видима)
  function startLiveTextPoll() {
    let lastSent = "";
    livePollIv = setInterval(() => {
      if (!listening || mode !== "record") { clearInterval(livePollIv); livePollIv = null; return; }
      const t = readInputText();
      if (t && t !== lastSent) { lastSent = t; send({ type: "LIVE_TEXT", text: t }); }
    }, 400);
  }

  // конец фразы: find_stop_button -> клик -> текст -> печать -> clear
  async function finishPhrase() {
    if (sessionBusy) return;      // один вызов на сессию
    sessionBusy = true;
    stopVAD();
    if (livePollIv) { clearInterval(livePollIv); livePollIv = null; }

    const stopBtn = document.querySelector(SEL.stopBtn1) || document.querySelector(SEL.stopBtn2);
    if (stopBtn) {
      forceClickButton(stopBtn);
      await sleep(STOP_PAUSE);
    }

    const text = readInputText();
    if (text) {
      send({ type: "PHRASE_READY", text });
      clearInputField();
    }

    listening = false;            // как _stop_recording_flag = True
    send({ type: "STATE", state: "record_done" });
  }

  function clearInputField() {
    const f = document.querySelector(SEL.inputField);
    if (!f) return;
    f.value = "";
    f.textContent = "";
    f.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // ---------- команды от background ----------
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "PING") { sendResponse({ pong: true }); return; }

    if (msg.type === "START_LISTENING") {
      listening = true;
      mode = msg.mode || "auto";
      const bubbles = readBubbles();
      bubbleCount = bubbles.count;
      printedText = bubbles.text;

      if (mode === "record") {
        startRecord();
      } else {
        const b = readButton();
        if (!b) { send({ type: "STATE", state: "no_button" }); return; }
        if (isIdle(b)) clickButton(b.btn);
        startObserver();
        onMutations();
      }
      send({ type: "STATE", state: "on", mode });
    }

    if (msg.type === "STOP_LISTENING") {
      listening = false;
      if (mode === "record") {
        if (sessionBusy === false) {
          // ручной стоп: погасить VAD, остановить диктовку
          sessionBusy = true;
          stopVAD();
          if (livePollIv) { clearInterval(livePollIv); livePollIv = null; }
          const stopBtn = document.querySelector(SEL.stopBtn1) || document.querySelector(SEL.stopBtn2);
          if (stopBtn) forceClickButton(stopBtn);
        }
      } else {
        if (mo) { mo.disconnect(); mo = null; }
        const b = readButton();
        if (b && !isIdle(b)) clickButton(b.btn);
      }
      send({ type: "STATE", state: "off" });
    }
  });

  send({ type: "CONTENT_ALIVE" });
})();
