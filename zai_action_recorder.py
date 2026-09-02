import os, time, json, sys, signal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    WebDriverException, NoSuchFrameException,
    StaleElementReferenceException, InvalidSessionIdException,
)
from webdriver_manager.chrome import ChromeDriverManager

ACTIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zai_recorded_actions.json")

_actions_ref = []
_driver_ref = [None]
_stop_flag = [False]


def get_cached_chromedriver():
    import glob as _glob
    candidates = []
    for path in _glob.glob(os.path.expanduser("~/.wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver")):
        ver = path.split("/linux64/")[1].split("/")[0]
        parts = [int(x) for x in ver.split(".") if x.isdigit()]
        candidates.append((parts, path))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


def load_actions():
    if os.path.exists(ACTIONS_FILE):
        with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_actions(actions):
    with open(ACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(actions, f, ensure_ascii=False, indent=2)


def describe_element(driver, webelement):
    """Создаёт стабильный CSS-селектор: id > data-testid > aria-label > class > outerHTML."""
    try:
        el_id = webelement.get_attribute("id")
        if el_id:
            return f"#{el_id}"
    except Exception:
        pass
    for attr in ("data-testid", "data-cy", "aria-label", "name", "placeholder", "role"):
        try:
            val = webelement.get_attribute(attr)
            if val:
                short = val[:60].replace('"', '\\"')
                return f"[{attr}=\"{short}\"]"
        except Exception:
            pass
    try:
        tag = webelement.tag_name
        classes = webelement.get_attribute("class") or ""
        cls_list = [c for c in classes.split() if c and len(c) < 40]
        if cls_list:
            sel = f"{tag}.{'.'.join(cls_list[:3])}"
            found = driver.find_elements(By.CSS_SELECTOR, sel)
            if len(found) == 1:
                return sel
            if len(found) <= 3:
                idx = -1
                for i, el in enumerate(found):
                    try:
                        if el.location == webelement.location and el.size == webelement.size:
                            idx = i
                            break
                    except Exception:
                        pass
                if idx >= 0:
                    return f"{sel}:nth-of-type({idx + 1})"
    except Exception:
        pass
    try:
        outer = webelement.get_attribute("outerHTML")[:120].strip()
        return f"outerHTML={outer}"
    except Exception:
        pass
    return "unknown"


def safe_js(driver, script, *args):
    """Выполняет JS через execute_script, возвращает результат или None."""
    try:
        return driver.execute_script(script, *args)
    except Exception:
        return None


_CLICK_LISTENER_JS = r"""
(function() {
    if (window.__rec_installed) return;
    window.__rec_installed = true;
    window.__recorder_clicks = [];

    function buildSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        var parts = [];
        var node = el;
        while (node && node.nodeType === 1 && parts.length < 6) {
            var tag = node.tagName.toLowerCase();
            if (node.id) {
                parts.unshift(tag + '#' + node.id);
                break;
            }
            var cls = (node.className || '').toString()
                .split(/\s+/).filter(function(c){ return c && c.length < 40; })
                .slice(0, 3).join('.');
            var sel = tag + (cls ? '.' + cls : '');
            var sibs = node.parentNode ? Array.prototype.filter.call(
                node.parentNode.children, function(c){ return c.tagName === node.tagName; }
            ) : [];
            if (sibs.length > 1) {
                var idx = Array.prototype.indexOf.call(node.parentNode.children, node) + 1;
                sel += ':nth-child(' + idx + ')';
            }
            parts.unshift(sel);
            node = node.parentNode;
        }
        return parts.join(' > ');
    }

    function describe(el) {
        return {
            tag: el.tagName.toLowerCase(),
            id: el.id || '',
            cls: (el.className || '').toString().substring(0, 200),
            text: (el.textContent || '').trim().substring(0, 100),
            ariaLabel: el.getAttribute('aria-label') || '',
            name: el.getAttribute('name') || '',
            role: el.getAttribute('role') || '',
            value: (el.value || '').substring(0, 200),
            href: el.getAttribute('href') || '',
            placeholder: el.getAttribute('placeholder') || '',
            selector: buildSelector(el)
        };
    }

    function capture(ev) {
        var t = ev.target;
        while (t && t.nodeType !== 1) t = t.parentNode;
        var interactive = t ? t.closest(
            'a,button,input,select,textarea,[role="button"],[role="link"],'
            + '[contenteditable="true"],label,summary'
        ) : null;
        var el = interactive || t;
        if (!el) return;
        var info = describe(el);
        info.targetCls = (t.className || '').toString().substring(0, 200);
        info.targetTag = t ? t.tagName.toLowerCase() : '';
        info.ts = Date.now();
        window.__recorder_clicks.push(info);
    }

    document.addEventListener('click', capture, true);
})();
"""


def install_click_listener(driver):
    """Идемпотентно устанавливает перехватчик кликов (переживает SPA-навигацию)."""
    safe_js(driver, _CLICK_LISTENER_JS)


def read_clicks(driver):
    """Возвращает и очищает очередь кликов, собранную на странице."""
    res = safe_js(driver, """
        var c = window.__recorder_clicks || [];
        window.__recorder_clicks = [];
        return c;
    """)
    return res or []


def snapshot_page_elements(driver):
    """Снимок всех интерактивных элементов + сообщений чата. Возвращает dict."""
    snap = {}
    # Все textarea / input
    snap["inputs"] = safe_js(driver, """
        return [...document.querySelectorAll('textarea, input[type="text"], [contenteditable="true"]')]
            .map(e => ({
                tag: e.tagName,
                id: e.id || '',
                cls: (e.className || '').substring(0, 120),
                role: e.getAttribute('role') || '',
                placeholder: e.getAttribute('placeholder') || '',
                value: (e.value || e.textContent || '').substring(0, 500),
                ariaLabel: e.getAttribute('aria-label') || '',
            }));
    """) or []
    # Все кнопки
    snap["buttons"] = safe_js(driver, """
        return [...document.querySelectorAll('button, [role="button"], a[role="button"]')]
            .map(e => ({
                tag: e.tagName,
                id: e.id || '',
                cls: (e.className || '').substring(0, 120),
                text: (e.textContent || '').trim().substring(0, 80),
                ariaLabel: e.getAttribute('aria-label') || '',
                disabled: e.disabled || false,
                ariaExpanded: e.getAttribute('aria-expanded'),
            }));
    """) or []
    # Все div с role=listitem или с длинным текстом (сообщения чата)
    snap["messages"] = safe_js(driver, """
        const msgs = [];
        const seen = new Set();
        // Пробуем разные селекторы для сообщений чата
        const sels = [
            '[role="listitem"]',
            '[class*="message"]',
            '[data-message-id]',
            '.markdown-body',
            '[class*="chat"] [class*="text"]',
            '[class*="conversation"] [class*="text"]',
        ];
        for (const sel of sels) {
            document.querySelectorAll(sel).forEach(e => {
                const t = (e.textContent || '').trim();
                if (t && t.length > 10 && !seen.has(t.substring(0, 100))) {
                    seen.add(t.substring(0, 100));
                    msgs.push({
                        selector: sel,
                        id: e.id || '',
                        cls: (e.className || '').substring(0, 120),
                        text: t.substring(0, 500),
                    });
                }
            });
        }
        return msgs;
    """) or []
    # Спиннер / "generating" индикаторы
    snap["generating"] = safe_js(driver, """
        const indicators = document.querySelectorAll(
            '[class*="loading"], [class*="spinner"], [class*="generating"], '
            + '[class*="typing"], [class*="thinking"], [aria-busy="true"]'
        );
        return indicators.length;
    """) or 0
    # Текущий URL и title
    snap["url"] = driver.current_url
    snap["title"] = safe_js(driver, "return document.title;") or ""
    return snap


def _emergency_save(signum=None, frame=None):
    if _stop_flag[0]:
        return
    _stop_flag[0] = True
    try:
        save_actions(_actions_ref)
    except Exception:
        pass
    try:
        if _driver_ref[0]:
            _driver_ref[0].quit()
    except Exception:
        pass
    sys.exit(0)


def start_recording():
    signal.signal(signal.SIGTERM, _emergency_save)
    signal.signal(signal.SIGHUP, _emergency_save)

    option = webdriver.ChromeOptions()
    option.binary_location = '/usr/bin/google-chrome-stable'
    option.add_argument("--enable-features=WebRtcHideLocalIpsWithMdns")
    option.add_experimental_option("excludeSwitches", ['enable-automation'])
    option.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.118 Safari/537.36")
    option.add_argument("--use-fake-ui-for-media-stream")
    option.add_argument("--disable-popup-blocking")
    option.add_argument('--user-data-dir=/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/work')

    driver_path = get_cached_chromedriver()
    if not driver_path:
        driver_path = ChromeDriverManager().install()
    driver = webdriver.Chrome(service=Service(driver_path), options=option)
    _driver_ref[0] = driver

    driver.get("https://chat.z.ai/")
    time.sleep(5)
    install_click_listener(driver)
    print("[Recorder] Браузер открыт. Выполняйте действия на сайте.")
    print(f"[Recorder] Запись в: {ACTIONS_FILE}")
    print("[Recorder] Закройте браузер или нажмите Ctrl+C — действия сохранятся.\n")

    actions = load_actions()
    _actions_ref.clear()
    _actions_ref.extend(actions)
    step = len(actions)

    prev_snapshot = None
    prev_value = {}

    while not _stop_flag[0]:
        try:
            snap = snapshot_page_elements(driver)
            install_click_listener(driver)
        except (WebDriverException, InvalidSessionIdException, NoSuchFrameException):
            print("[Recorder] Браузер закрыт или сессия потеряна.")
            break
        except Exception:
            time.sleep(1)
            continue

        if prev_snapshot is None:
            prev_snapshot = snap
            prev_value = {i.get("id") or i.get("placeholder") or str(k): i.get("value", "")
                          for k, i in enumerate(snap.get("inputs", []))}
            print(f"[Recorder] Страница загружена: {snap['title']}")
            print(f"[Recorder] Найдено: {len(snap['inputs'])} полей ввода, {len(snap['buttons'])} кнопок, {len(snap['messages'])} сообщений\n")
            continue

        # --- Изменения в полях ввода (ввод текста) ---
        for inp in snap.get("inputs", []):
            key = inp.get("id") or inp.get("placeholder") or ""
            cur_val = inp.get("value", "")
            old_val = prev_value.get(key, "")
            if cur_val != old_val and len(cur_val.strip()) >= 1 and len(cur_val) >= len(old_val):
                sel_parts = []
                if inp.get("id"):
                    sel_parts.append(f"#{inp['id']}")
                elif inp.get("placeholder"):
                    sel_parts.append(f"[placeholder=\"{inp['placeholder'][:50]}\"]")
                elif inp.get("ariaLabel"):
                    sel_parts.append(f"[aria-label=\"{inp['ariaLabel'][:50]}\"]")
                elif inp.get("role"):
                    sel_parts.append(f"[role=\"{inp['role']}\"]")
                else:
                    sel_parts.append(inp.get("cls", "")[:80])
                selector_str = " ".join(sel_parts)
                new_action = {
                    "type": "input",
                    "selector": selector_str,
                    "value": cur_val[:1000],
                    "time": round(time.time(), 2),
                    "step": step,
                }
                if not _actions_ref or _actions_ref[-1].get("type") != "input" or _actions_ref[-1].get("selector") != selector_str or _actions_ref[-1].get("value") != cur_val[:1000]:
                    _actions_ref.append(new_action)
                    save_actions(_actions_ref)
                    step += 1
                    print(f"  [{step}] INPUT [{selector_str}] → {cur_val[:80]}")
            prev_value[key] = cur_val

        # --- Новые сообщения ---
        old_texts = {(m.get("id") or m.get("cls", "")[:40]): m.get("text", "")[:100]
                     for m in prev_snapshot.get("messages", [])}
        for msg in snap.get("messages", []):
            msg_id = msg.get("id") or msg.get("cls", "")[:40]
            msg_text = msg.get("text", "")[:500]
            if msg_id not in old_texts or old_texts[msg_id] != msg_text[:100]:
                if len(msg_text) > 10:
                    new_action = {
                        "type": "message",
                        "selector": msg.get("selector", ""),
                        "id": msg.get("id", ""),
                        "cls": msg.get("cls", "")[:120],
                        "text": msg_text,
                        "time": round(time.time(), 2),
                        "step": step,
                    }
                    if not _actions_ref or _actions_ref[-1].get("text", "")[:100] != msg_text[:100]:
                        _actions_ref.append(new_action)
                        save_actions(_actions_ref)
                        step += 1
                        preview = msg_text[:80].replace('\n', ' ')
                        print(f"  [{step}] MSG [{msg.get('selector', '')}] → {preview}")

        # --- Кнопки: какие появились / изменились (state) ---
        old_btns = {(b.get("id") or b.get("text", "")[:30] or b.get("ariaLabel", "")): b
                    for b in prev_snapshot.get("buttons", [])}
        for btn in snap.get("buttons", []):
            btn_key = btn.get("id") or btn.get("text", "")[:30] or btn.get("ariaLabel", "")
            old = old_btns.get(btn_key)
            if old and old.get("disabled") != btn.get("disabled"):
                new_action = {
                    "type": "button_state",
                    "id": btn.get("id", ""),
                    "text": btn.get("text", "")[:50],
                    "ariaLabel": btn.get("ariaLabel", ""),
                    "disabled": btn.get("disabled"),
                    "time": round(time.time(), 2),
                    "step": step,
                }
                _actions_ref.append(new_action)
                save_actions(_actions_ref)
                step += 1
                print(f"  [{step}] BTN [{btn.get('text', '')[:30]}] disabled={btn.get('disabled')}")

        # --- URL / страница сменились ---
        if snap.get("url") != prev_snapshot.get("url"):
            new_action = {
                "type": "navigate",
                "url": snap.get("url", ""),
                "time": round(time.time(), 2),
                "step": step,
            }
            _actions_ref.append(new_action)
            save_actions(_actions_ref)
            step += 1
            print(f"  [{step}] NAV → {snap.get('url', '')}")

        # --- Клики по элементам (id, классы, текст, селектор) ---
        for clk in read_clicks(driver):
            sel = clk.get("selector") or clk.get("id") or clk.get("cls", "")[:80] or clk.get("text", "")[:40]
            new_action = {
                "type": "click",
                "selector": sel,
                "id": clk.get("id", ""),
                "class": clk.get("cls", "")[:200],
                "text": clk.get("text", "")[:100],
                "ariaLabel": clk.get("ariaLabel", ""),
                "name": clk.get("name", ""),
                "role": clk.get("role", ""),
                "href": clk.get("href", ""),
                "placeholder": clk.get("placeholder", ""),
                "targetTag": clk.get("targetTag", ""),
                "targetClass": clk.get("targetCls", "")[:200],
                "time": round(time.time(), 2),
                "step": step,
            }
            last = _actions_ref[-1] if _actions_ref else None
            if not (last and last.get("type") == "click" and last.get("selector") == sel
                    and abs(last.get("time", 0) - new_action["time"]) < 1.0):
                _actions_ref.append(new_action)
                save_actions(_actions_ref)
                step += 1
                label = clk.get("text") or clk.get("ariaLabel") or clk.get("id") or clk.get("cls", "")[:40]
                print(f"  [{step}] CLICK [{sel}] → {label[:50]}")

        prev_snapshot = snap
        time.sleep(0.5)

    save_actions(_actions_ref)
    print(f"\n[Recorder] Сохранено {len(_actions_ref)} действий в {ACTIONS_FILE}")
    try:
        driver.quit()
    except Exception:
        pass


if __name__ == "__main__":
    start_recording()
