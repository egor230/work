// popup.js — живое окно с текстом реплики (эквивалент PyQt-облачка)
// Открывается ПО КЛИКУ значка и живёт, пока открыто: показывает
// текущий распознаваемый текст и историю последних фраз.

const el = document.getElementById("text");
const st = document.getElementById("state");

let lastLen = 0;

function render(msg) {
  if (msg.type === "LIVE_TEXT" || msg.type === "PHRASE_READY") {
    // растущий текст — «живой ввод»; новая короткая строка — новая фраза
    const isNewPhrase = msg.text.length < lastLen;
    if (msg.type === "PHRASE_READY") {
      el.textContent += "\n";
    }
    el.textContent = msg.text;
    el.scrollTop = el.scrollHeight;      // автопрокрутка текста
    lastLen = msg.text.length;
  }
  if (msg.type === "STATE") {
    st.textContent = msg.state === "on"
      ? `слушаю (${msg.mode === "record" ? "запись" : "авто"})…`
      : "остановлено";
  }
}

chrome.runtime.onMessage.addListener(render);

// старт/стоп из окна
document.getElementById("toggle").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "POPUP_TOGGLE" }, () => {
    setTimeout(() => chrome.runtime.sendMessage({ type: "POPUP_OPEN" }, (s) => {
      if (!chrome.runtime.lastError && s) {
        st.textContent = s.on
          ? `слушаю (${s.mode === "record" ? "запись" : "авто"})…`
          : "остановлено";
      }
    }), 400);
  });
});

// первичное состояние
chrome.runtime.sendMessage({ type: "POPUP_OPEN" }, (s) => {
  if (chrome.runtime.lastError || !s) return;
  st.textContent = s.on
    ? `слушаю (${s.mode === "record" ? "запись" : "авто"})…`
    : "остановлено";
  if (s.text) { el.textContent = s.text; el.scrollTop = el.scrollHeight; }
  lastLen = s.text ? s.text.length : 0;
});
