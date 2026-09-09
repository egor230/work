# Голосовой ввод от Яндекса — расширение Chrome / Яндекс Браузера

Перенос логики скрипта `Голосовой_ввод_текста_яндекс_pytq.py` в расширение (Manifest V3).
Говорите — Алиса распознаёт — текст печатается **там, где курсор/фокус** (в любом окне системы, не только в браузере).

Статус: **рабочая версия 1.3.0** (проверено 2026-09-09; печать через evdev, оба режима).

## Состав

| Файл | Роль |
|------|------|
| `manifest.json` | Manifest V3: права, вкладка Алисы, native messaging, popup, контекстное меню |
| `background.js` | service worker: значок/меню старт-стоп, поиск вкладки Алисы, мост в native host, мини-окно Алисы (анти-троттлинг), облачко живого текста, keepalive |
| `content-alice.js` | работает на alice.yandex.ru: MutationObserver + **все условия скрипта 1:1**; режим Записи = перенос `toggle()`/`talk()` с VAD на AudioWorkletNode |
| `popup.html` / `popup.js` | живое окно текста реплики под значком (аналог PyQt-облачка) + кнопка старт/стоп |
| `native-host/native_host.py` | печатает через `write_text_fast.process_text` (evdev) — как `press_keys`; восстанавливает DISPLAY |
| `native-host/native_host.sh` | shim: venv-python + `export DISPLAY=:0` + `XAUTHORITY` |
| `native-host/com.voice_input_yandex.json` | эталонный манифест native messaging host |
| `install.sh` | установка: копирует host в `~/.local/share/voice-input-yandex/` (права!), манифесты 3 браузеров, самопроверка |
| `icons/` | voice / record / stop (16/48/128) |

## Управление

| Действие | Как в Python |
|----------|--------------|
| Клик по значку | открывает окно живого текста (кнопка старт/стоп внутри) |
| ПКМ по значку | меню: «Режим: Авто» / «Режим: Запись» / «Остановить ввод» (аналог трей-меню) |
| Режим сохраняется между перезапусками (chrome.storage) | как self.mode |

## Соответствие Python → расширение

| Python-скрипт | Расширение |
|---------------|------------|
| цикл `while True` + опрос каждые 10 мс | `MutationObserver` (событие смены class/data-testid/aria) |
| `self.button = find_element(...)` | `document.querySelector` внутри observer |
| `"col" in classes`, `"сл" in aria`, `"th" in filter_elem`, `white.display=="none"` | `isPhraseReady()` — подстроки 1:1 |
| `counts1 > self.counts` (новый пузырёк) | `bubbles.count > bubbleCount` |
| `"lis" in classes and "стоп" in aria` — живой текст | `isLive()` → popup-окно + облачко |
| `"spe"+"th"+круги` — залипание | `isStuck()` (круги через `getComputedStyle`) |
| `"su" in filter_elem` — покой → клик | `isIdle()` |
| двойной клик стоп→слушать после печати | `clickButton` + `setTimeout(..., 2400)` (+20% анти-бан) |
| `window.scrollTo(0, scrollHeight)` | там же — автопрокрутка чата Алисы |
| `process_text` → `press_keys` (evdev) | native host: `process_text` без изменений |
| `toggle()` → клик окникс | `startRecord()`: клик окникс безусловно |
| `_ON()` → `find_mic_button()` | клик `button[data-testid='button-dictation-button']` |
| `talk()`: sounddevice VAD `mean_amp>4`, тишина 3.3 с | `getUserMedia` + **AudioWorkletNode** `vad-processor` (blob-строка, без deprecated ScriptProcessor), те же порог 4 и 3.3 с |
| `find_stop_button()` | те же селекторы `.StandaloneRichInput-ControlsPlayer button...` / `AliceButton_view_secondary.AliceButton_square` |
| `get_recognized_text()` | текст из `textarea[data-testid='inputbase-textarea']` |
| `clear_input_field()` | очистка value + событие input |
| сессия = один старт (`_stop_recording_flag`) | после печати `listening=false`, `record_done`; новый старт по значку |
| задержки ×1.2 (анти-бан) | `CLICK_MIN_INTERVAL=1800`, `DOUBLE_CLICK_MS=2400`, `ON_PAUSE=1000`, `STOP_PAUSE=360`, дебаунс observer 60 мс |

## Решённые грабли (история багов — читать при странном поведении)

### 0. ГЛАВНАЯ ГРАБЛЯ: host на ntfs = root:root 777 → браузер его НЕ запускает
**Симптом:** «расширение постоянно отключается из-за проверок безопасности»,
текст не печатается, `pgrep -af native_host` пустой — браузер ни разу не поднял хост.
**Причина:** native host лежал в папке расширения на ntfs-разделе `/mnt/...`,
где все файлы `root:root` c правами `777` (world-writable). Chromium-безопасность
считает такой исполняемый файл недоверенным и **молча** отказывается его стартовать.
**Фикс:** хост копируется в домашнюю папку `~/.local/share/voice-input-yandex/`
(ext4, `egor:egor`, права `700` на `.sh` / `644` на `.py`), манифесты
NativeMessagingHosts трёх браузеров указывают туда. `install.sh` делает
копирование + манифесты + самопроверку запуска автоматически.

### 1. Текст в диалоге есть, но не печатается — DISPLAY у native host
**Симптом:** режим Авто работал, пузырёк появлялся, но текст не печатался.
**Причина:** браузер запускает native messaging host в **стерильном окружении
без `DISPLAY`**. `write_text_fast` печатает через X11-инструменты (`xte`/`xset`
в `set_layout`), а `pynput` (импортируется модулем) при отсутствии DISPLAY
падает с `ImportError: failed to acquire X connection` — **хост умирал на
импорте**, до evdev дело не доходило.
**Фикс (двойной):**
- `native_host.sh`: `export DISPLAY=":0"` + `XAUTHORITY="$HOME/.Xauthority"`
- `native_host.py`: если `DISPLAY` пуст — ставит `:0`, ищет `.Xauthority`
  (`~/.Xauthority`, `/run/user/<uid>/gdm/Xauthority`)

### 2. Фоновая вкладка «не слышит» — троттлинг Chrome
Chrome зажимает таймеры скрытых вкладок (до 1 с, через 5 мин — до 1/мин).
**Фикс:** при старте слушания вкладка Алисы переносится в видимое мини-окно
532×467 (как окно Selenium в Python), `focused:false` — фокус не крадётся.
Будильник (~21 c) вернёт окно, если его свернули/закрыли.

### 3. Отключения «из-за проверок»
Убраны ВСЕ ping-тесты native-порта; при разрыве — тихий бесконечный реконнект
через 1 с (без счётчиков и отказов), слушание никогда не останавливается.
Будильник лишь продлевает жизнь service worker (активный порт сам держит
SW живым в Chrome 116+) и поднимает порт, если его не стало.

### 4. Обрыв реплик посреди фразы
Печать строго по условию готовности (как в Python: `self.counts` растёт
только после печати). Убран «принудительный» ретрай через 3 тика и
`whiteHidden:true` при отсутствии белого круга в DOM.

### 5. Deprecated ScriptProcessorNode в режиме Записи
Браузер ругался «The ScriptProcessorNode is deprecated» (выглядело как
«проверка безопасности»). **Фикс:** VAD переписан на `AudioWorkletNode`
(процессор `vad-processor` из blob-строки): сам считает `mean(abs)*100`,
сам следит за тишиной 3.3 с по `currentTime`, сигнал — `port.postMessage`.
Дополнительно: `sessionBusy` (один `finishPhrase` на сессию) и
`keepAudioAlive()` (будит приостановленный AudioContext каждые 2 c).

### 6. Content script не попадал в старые вкладки
Вкладка Алисы, открытая ДО установки расширения, не имеет content script.
**Фикс:** перед командой — `PING`; нет ответа → `chrome.scripting.executeScript`
принудительно инжектит. При неудаче — откат значка + бейдж.

## Установка

1. Браузер → страница расширений → «Загрузить распакованное расширение» → выбрать эту папку.
2. Скопировать ID расширения.
3. В терминале:
   ```bash
   cd ".../расширения/голосовой ввод от Яндекса"
   bash install.sh <ID_РАСШИРЕНИЯ>
   ```
   (скопирует host в `~/.local/share/voice-input-yandex/` с правильными правами,
   поставит манифесты в Яндекс Браузер / Chrome / Chromium, проверит запуск)
4. **Полностью перезапустить браузер** (закрыть все окна — манифесты host читаются при старте).
5. Открыть `https://alice.yandex.ru` (обычная вкладка).
6. Клик по значку → окно живого текста → кнопка «старт/стоп».
7. ПКМ по значку — переключение режима Авто/Запись.

## Как это работает

```
значок (клик) ─▶ popup (живой текст) / background.js
                  ├─ найти вкладку alice.yandex.ru (нет → бейдж «!»)
                  ├─ перенести Алису в мини-окно 532×467 (анти-троттлинг)
                  ├─ connectNative("voice_input_yandex") — держит SW живым
                  └─ → content-alice.js: START_LISTENING
                       ├─ АВТО:   observer состояний; НОВЫЙ ПУЗЫРЁК +
                       │   ("col"|"сл"|"th"|белый круг скрыт) → печать
                       │   + двойной клик «стоп→слушать» (2400 мс)
                       └─ ЗАПИСЬ: клик окникс → клик диктовки → VAD
                           (AudioWorklet, порог 4, тишина 3.3 c) →
                           кнопка-стоп → текст из поля → печать → clear
                  печать: background → native host → process_text →
                  press_keys (evdev, раскладки) → ФОКУС СИСТЕМЫ
                  + дубль фразы в буфер обмена (страховка)
```

Печать идёт через native host в **фокус системы** (как у скрипта) — работает и в редакторах вне браузера.

## Диагностика (если вдруг перестало)

```bash
# 1) Браузер поднял хост? (во время слушания)
pgrep -af native_host
# пусто → грабля №0 (ntfs/root) или манифест: проверь
cat ~/.config/yandex-browser/NativeMessagingHosts/voice_input_yandex.json

# 2) Хост жив, но печать не идёт → грабля №1 (DISPLAY):
env -u DISPLAY -u XAUTHORITY ~/.local/share/voice-input-yandex/native_host.sh </dev/null
# падение pynput видно мгновенно в stderr

# 3) Консоль расширения: страница расширений → «service worker» → Console.
#    Бейджи значка: «!» — нет вкладки Алисы, «P» — фраза готова, но порт
#    в native host не поднялся (см. пункты выше).
```

## Отчёт о диагностике проблем клавиатуры

Подробная история проблем с печатью и X11/pynput — в
`/mnt/.../python_linux/Project/Отчет_проблемы_с_клавиатурой.md`
(почему печать идёт через evdev, а не pynput; почему Listener — нельзя).

## Заметки

- `white.display` и круги читаются через `getComputedStyle` — как `value_of_css_property` в Selenium.
- Проблема F5 отсутствует: content script ищет кнопку заново каждый раз, observer сам подключается.
- `myvenv` из Project используется в shim — там все зависимости evdev.
- **Хост живёт в `~/.local/share/voice-input-yandex/`**, НЕ в папке расширения
  (ntfs даёт root:root 777 → браузер блокирует запуск — грабля №0).
  После правок `native-host/native_host.py` — перезапусти `install.sh <ID>`
  (он скопирует свежую версию в домашнюю папку).
- Каждая фраза дублируется в буфер обмена (xclip) — страховка для окон,
  где evdev-печать заблокирована: вставь Ctrl+V.
