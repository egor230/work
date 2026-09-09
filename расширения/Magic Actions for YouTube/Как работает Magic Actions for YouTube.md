# Magic Actions for YouTube — Custom (v2.0.0)

Кастомная урезанная версия расширения «Magic Actions for YouTube»: единственная
функция — переключение светлой/тёмной темы YouTube. Рабочая копия файлов
`content.js`, `main_world.js`, `styles.css` — в этой папке. Остальные файлы
оригинала (`esw30.js`, `gjs30/`, `gcss30/`, `e*.html`) не подключены в
manifest.json и ни на что не влияют.

## Архитектура

| Файл | Роль |
|---|---|
| `manifest.json` | MV3, только `storage`. Два content-скрипта на `youtube.com`, оба `document_start`, `main_world.js` — в MAIN world, `content.js` + `styles.css` — в ISOLATED |
| `content.js` | Ядро: чтение темы, применение, тумблер `#__magic-theme-switch`, синхронизация между вкладками |
| `main_world.js` | Патчи в контексте страницы: блокировка `dark`/`light` атрибутов + защита куки `PREF` |
| `styles.css` | Темы через CSS-переменные YouTube (`--yt-spec-*`, `--yt-sys-*`) + `scrollbar-color`, z-index тумблера |
| `popup.html`/`popup.js` | Кнопка в popup → та же запись в `chrome.storage.local` |

## Как YouTube хранит тему (важно!)

1. **Кук `PREF` параметр `f6`**: `400`/`400…` — тёмная, `80000`/`8…` — светлая.
   Чтение — по первому символу (`4`→dark, `8`→light), не по точному сравнению
   (YouTube склеивает флаги: реально встречаются `40080000`, `40000400` и т.п.).
2. **Атрибуты `<html>`**: `dark` и `light`. Критично: современный CSS YouTube
   (2025+) держит цвета в обфусцированных токенах `--t3e41d7b17b187f69` (и ~117
   других `--t*`), определённых на `html[dark] {#0f0f0f}` / `html[light] {#fff}`,
   причём **в `:root` дефолт — тёмный `#0f0f0f`**. Итог: просто снять `dark`
   недостаточно — `ytd-app {background: var(--t3…)}` останется чёрным. Нужно
   обязательно ставить атрибут `light`.

## content.js — логика

- `applyTheme(theme)`: классы `__ytnight`/`__ytday` + **пара атрибутов** —
  dark: `dark=""`, снять `light`; light: `light=""`, снять `dark`. Кук `PREF.f6`
  (`400`/`80000`), `max-age=22592000`, `domain=.youtube.com`. Плюс дубль темы в
  `sessionStorage.maTheme` для мгновенного применения до ответа `chrome.storage`.
- `normalize()`: валидирует и `dark`, И `light` (багfixed-версии, где light
  превращался в null, перезаписывали выбор пользователя кукой).
- boot: мгновенный `applyTheme(sessionStorage || кука)`, затем асинхронный
  `chrome.storage` — расхождение корректируется. Если storage пуст —
  инициализируется текущей темой (создаётся запись).
- Переключение: тумблер/popup → `chrome.storage.local.set({maTheme})` →
  `onChanged` в каждой вкладке YouTube → `applyTheme` **на лету, без reload**.
- `yt-navigate-finish` (SPA-навигация): повторное применение темы из storage.
- MutationObserver-guard на `<html>` (attributes: class, dark, light): если
  YouTube снёс классы/атрибуты темы — немедленно восстановить.
- bodyGuard: если YouTube удалил тумблер из DOM — пересоздать.
- Тумблер: `click` capture + `keydown` (Enter/Space), `contextmenu` заблокирован.

## main_world.js — патчи страницы

- `Element.prototype.setAttribute/removeAttribute/toggleAttribute`: на
  `<html>` запрещено ставить/снимать `dark`/`light` вопреки `data-ma-theme`
  (симметричная блокировка обоих атрибутов).
- **Перехват `document.cookie` setter**: YouTube сам перезаписывает `PREF`
  (включая `f6`) под своё внутреннее состояние, из-за чего после перезагрузки
  сервер рендерил старую тему. Патч переписывает `f6` в любой записываемый
  `PREF=…` в согласии с текущей темой (`400`/`80000`), остальной кук проходит
  насквозь. Геттер не тронут.

## styles.css

- Тумблер `#__magic-theme-switch`: `z-index: 2147483647` (максимальный; раньше
  был 3646 и баннер-диалог YouTube с таким же z-index перекрывал кнопку —
  клики «не работали»), `position:fixed`, `top:7px`, `left:5px`, спрайт
  солнце/луна 28×34, правая половина показывается при `.dark`.
- Тёмная (`html.__ytnight`) и светлая (`html.__ytday`) темы: переопределение
  `--yt-spec-*` и `--yt-sys-color-baseline--*` (важно и то и то: obf-токены
  YT часто `var()`-ссылается на sys-color), плюс `scrollbar-color` — это
  единственное прямое правило, поэтому при сломанных темах «переключалась
  только прокрутка».

## Диагностика (как проверять)

Тестовый стенд: Chromium + CDP (`--load-extension` в Chrome stable ≥136
заблокирован, нужен именно chromium; google-chrome не подходит).

```bash
# запуск (ВАЖНО: в pkill-паттерне брекет, иначе pkill убивает сам bash!)
/tmp/launch_test_chrome.sh   # создаёт скрипт по образцу:
#   for p in $(pgrep -f "user-data-dir=/tmp/ma_test_pr[o]f"); do kill -9 $p; done
#   rm -rf /tmp/ma_test_profile; mkdir -p /tmp/ma_test_profile
#   setsid nohup chromium --user-data-dir=/tmp/ma_test_profile \
#     --remote-debugging-port=9222 --remote-allow-origins=http://127.0.0.1:9222 \
#     --no-first-run --no-default-browser-check --load-extension=/tmp/ma_test_ext \
#     --window-size=1400,900 --no-sandbox "https://www.youtube.com/" & disown
# Хром запускать ТОЛЬКО setsid nohup ... & disown — иначе гибнет при килле
# процессной группы bash-инструмента.
```

Грабли, найденные при диагностике:
- CDP-эвал в изолированном world: Runtime.evaluate с `contextId` контекста
  расширения; контексты перечисляются после `Runtime.enable` (нужен и
  `DOM.enable`+`CSS.enable` перед CSS-доменами).
- На youtube-вкладке ДВА+ MAIN-контекста (один — about:blank iframe): перед
  eval проверять `window.top===window`.
- `getMatchedStylesForNode` — единственный способ найти, что реально красит
  элемент (инлайн-стилей нет, а токены обфусцированы).
- Trusted-клик по тумблеру — `Input.dispatchMouseEvent` по координатам
  `getBoundingClientRect()`.

E2E-сценарий проверки (снимки `html/ytd-app/#guide-content/заголовок` цветов
до/после): старт → тумблер → главная light/dark → watch-страница → тумблер →
reload → тема должна сохраниться. Признак здоровья: `--t3e41d7b17b187f69`
= `#fff` в светлой, `#0f0f0f` в тёмной; `ytd-app` следует за `html`.

## История фиксов (2026-09-09)

1. Кук светлой темы писал `f6=8` вместо `80000` (YouTube не распознавал).
2. Точное сравнение `f6==='400'` ломалось на склеенных флагах; нет `PREF` →
   слепо «светлая». Теперь: чтение по первому символу + фолбэк на атрибут
   `dark` у `<html>`.
3. `location.reload()` на каждый toggle → убран, тема применяется живьём.
4. **Снятие `dark` без установки `light`** — главный баг «переключается только
   прокрутка»: obf-токены `--t*` дефолтятся в тёмный `:root`. Фикс: ставить
   `light`-атрибут при светлой теме.
5. Не блокировался `toggleAttribute('dark')` → YouTube обходил патч.
   Заблокирован, и для обоих атрибутов.
6. `normalize()` терял `'light'` → после reload выбор перезаписывался кукой.
7. YouTube перезаписывал кук `PREF` после переключения → после reload тема
   откатывалась. Фикс: перехват cookie-setter в main_world.
8. Классы `__ytnight/__ytday` стирались при SPA-миграциях → MutationObserver-guard.
9. Z-index тумблера (3646) равен z-index диалогов YouTube → кнопка некликабельна
   на главной. Фикс: 2147483647 + capture-обработчики + bodyGuard.

## Для пользователя

Пересоздать расширение в `chrome://extensions` (Reload) и обновить вкладки
YouTube. Переключение — плавающая кнопка слева вверху (солнце/луна) или кнопка
в popup расширения; работает на главной и на watch-страницах, переживает
перезагрузку страницы и SPA-навигацию, синхронно во всех вкладках YouTube.
