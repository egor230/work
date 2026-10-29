# Enhancer for YouTube™ — кастомная копия

Распакованная копия Chrome-расширения Enhancer for YouTube (MV3, store 3.1.0)
с локальными правками. Общее руководство — в `README.md`, полная документация
по Magic Actions — в `../Magic Actions for YouTube — исследование переключения
темы (сводный документ).md` (в папке `../`).

В этой копии несколько сессий локальных правок:

| # | Дата | Что | Раздел |
|---|---|---|---|
| 1–2 | 2026-09-17 | Колесо=громкость, скорость по каналам | §1–§2 |
| 3 | 2026-09-24 | Объединение Magic Actions (тема) | §3 |
| 4 | 2026-09-24 | Сохранение/восстановление настроек | §4 |
| 6 | 2026-09-25 | Починка «число видео в ряду» (атрибуты → классы) | §6 |
| 7 | 2026-09-28 | Починка скорости по каналам: дробные скорости (1.6 и т.п.) не сохранялись | §7 |
| 8 | 2026-09-30 | Починка отключения звука на первых секундах нового видео | §8 |
| 9 | 2026-10-05 | Починка обоих симптомов разом: звук гаснет на старте, скорость падает на 1 при переходе на эпизод | §9 |
| 10 | 2026-10-28 | Панель скорости у шестерёнки + контекстное меню «Поиск на YouTube» | §10 |

Собирается в .crx скриптом `package-crx.sh` (§5).

---

## §1 Прокрутка громкости колёсиком мыши — по всему плееру

**Файл:** `js/youtube-main.js`, функция `gd(a)` (обработчик `wheel` на
`#player-container`).

До: чтобы колесо меняло громкость, нужно было включить опцию
`controlvolume` + курсор быть над контролами / удерживать кнопку мыши
(`controlvolumemousebutton`). В остальном колесо над видео просто
скроллило страницу.

После: колесо над видео (watch-страница) сразу меняет громкость — как в
Magic Actions. В центре видео появляется бейдж-цифра (`efyt-bezel`,
элемент `S`) с текущей громкостью, и через **1 секунду** гаснет
(`kb()` → `Jc=setTimeout(...,1E3)`). При мьюте показывается `0`.

```js
// gd() — новая ветка (вместо старого: ctrl+controlspeed / controlvolume+controlbar)
else{a.preventDefault();a.stopPropagation();var b=f.getVolume();
(!d.reversemousewheeldirection&&0<a.deltaY||d.reversemousewheeldirection&&0>a.deltaY)
  ?(b-=d.volumevariation,0>b&&(b=0))
  :(b+=d.volumevariation,100<b&&(b=100),f.isMuted()&&f.unMute());
Ub=f.classList.contains("unstarted-mode");za=!0;f.setVolume(b);f.efytVolume=b;
S.textContent=f.isMuted()?0:b;kb();Ba(b)}
```

`js/config.js`: `controlvolume:!0` (по умолчанию вкл., ранее `!1`).
Опции `controlvolume` / `controlvolumemousebutton` / `volumevariation`
в `options.html` остались, но больше не блокируют колесо по всему плееру.

## §2 Скорость воспроизведения — таблица по каналам (ID + название)

**Файлы:** `js/youtube-main.js` (маин-ворлд) + `js/youtube-isolated.js`
(изолированный, обращение к `chrome.storage.local`).

Механика:
- В маин-ворлде есть кеш `efytSpd{}` — вкладки текущего сайта.
- `chrome.storage.local.channelspeeds{}` — долговременная таблица
  (канал → скорость), читает/пишет только изолированный скрипт.

Добавлено:
- `efytChannelName()` — берёт `videoDetails.author` из
  `f.getPlayerResponse()` (fallback `f.getVideoData().author`), т.е.
  **название канала**, а не только `channelId` (`efytChannelId()`).
- Таблица теперь хранит **два ключа** на один канал:
  - `channelId` (как было; `channel-speed-set` с `channel=<id>`)
  - `name:<Имя>` (новое; при записи `name:<Имя>` в
    `chrome.storage.local.channelspeeds`).
- `efytSpdSave(a)` — при смене скорости колёсиком/мышью/кнопками
  вызывает `channel-speed-set` с `channel` (id) и `name` (название).
  Изолированный скрипт пишет оба ключа в `channelspeeds`.
- `efytAskChannelSpeed()` — при начале видео (вызывается из `sb()` и из
  `Wc` на `onStateChange`) запрашивает `channel-speed-get`. Сначала
  проверяет кеш `efytSpd[id]` и `efytSpd["name:"+имя]`; если нет —
  шлёт запрос в storage. Получив ответ, применяет скорость
  (`efytApplySpeed`) и кэширует по обоим ключам.

Итог: зашли на **другое видео того же канала** → автоматически
восстанавливается скорость, которую вы ставили на предыдущем видео этого
канала. Работает и по ID канала, и по его названию (на случай, когда
`channelId` вдруг не читается — например, на некоторых вкладках).

```js
// efytSpdSave — оба ключа
function efytSpdSave(a){if(a&&a!==efytSavedVal){efytSavedVal=a;
  var b=efytChannelId(),g=efytChannelName();
  (b||g)&&c.dispatchEvent(new CustomEvent("efyt-message",{detail:{
    request:"channel-speed-set",channel:b||g,name:g&&b?g:void 0,speed:a}}))}}

// efytAskChannelSpeed — кеш id + имя, иначе storage
function efytAskChannelSpeed(){try{var a=efytChannelId(),b=efytChannelName();
  if(a||b){efytSpdReq=a||b;
    var g=efytSpd[efytSpdReq]||efytSpd[a]||efytSpd[b];
    if(g)efytApplySpeed(g);
    else c.dispatchEvent(new CustomEvent("efyt-message",{detail:{
      request:"channel-speed-get",channel:efytSpdReq,name:b&&a?b:void 0}}))}}catch(e){}}
```

## §5 Скрипт упаковки в .crx (CRX3, канонический формат Chromium)

**Файлы:** `package-crx.sh` (в корне), `efyt_private.pem` (приватный ключ
RSA-2048, PKCS#8; генерируется при первом запуске и определяет ID).

В Chrome/Chromium ≥ 136 на Linux штатный `--pack-extension` заблокирован,
поэтому скрипт генерирует CRX3 напрямую. Формат воспроизводит исходники
Chromium (`components/crx_file/crx3.proto`, `crx_creator.cc`,
`crx_verifier.cc`) и побайтово сверен с настоящими store-файлами .crx.

#### Формат

```
u32  magic "Cr24"; u32 version = 3; u32 header_size;
protobuf CrxFileHeader header;  zip archive

message AsymmetricKeyProof { bytes public_key = 1;   // X.509 SPKI!
                             bytes signature  = 2; }
message CrxFileHeader { repeated AsymmetricKeyProof sha256_with_rsa = 2;
                        bytes signed_header_data = 10000; }  // SignedData
message SignedData { bytes crx_id = 1; }   // ровно 16 байт
```

Ключевые правила (каждое из них в прошлых версиях нарушалось — отсюда
`CRX_HEADER_INVALID` и `CRX_SIGNATURE_VERIFICATION_INITIALIZATION_FAILED`):

1. **Подписывается не zip и не SignedData**, а конкатенация
   `"CRX3 SignedData\0" + LE32(len(SignedData)) + SignedData + zip`
   (RSA-SHA256 PKCS1v15).
2. **Публичный ключ в proof — только X.509 SPKI** (294 байта для RSA-2048),
   в поле **1** (`public_key`), подпись — в поле 2. Chrome парсит ключ
   строго как SPKI; PKCS#1 или перепутанные поля дают
   `CRX_SIGNATURE_VERIFICATION_INITIALIZATION_FAILED`.
3. `crx_id` в SignedData = `SHA-256(SPKI)[:16]`. ID расширения — эти же 16
   байт, где каждый ниббл переводится в букву a–p.
4. Внутри заголовка не должно быть zip-токенов EOCD (`PK\x05\x06` и др.) —
   Chrome отвергает такой header.
5. Поле `key` манифеста заменяется на base64(SPKI) — **ровно это Chrome сам
   делает при установке .crx** (`RewriteManifestFile` в
   `sandboxed_unpacker.cc`). Тогда ID одинаков и при установке CRX, и при
   «Load unpacked».

#### Самопроверка

Скрипт после сборки сам верифицирует .crx по алгоритму `crx_verifier.cc`
(парсинг protobuf, SPKI, каноническое сообщение, совпадение crx_id,
целостность zip, `key` в манифесте) и **не запишет битый файл** — при любой
ошибке выход с кодом 1. Встроенная проверка также ловит EOCD-токены в
заголовке и отсутствие manifest.json в архиве.

#### Приватный ключ и ID

Приватный ключ `efyt_private.pem` менять нельзя: он определяет ID расширения
и подпись. Потеря = новый ID у всех последующих сборок.

**ID этой сборки:** `ifojmbdceojdnhhagpmfnmjndpplcndi`
(header 581 байт — ровно как у store-файлов; ~230 КБ, после объединения
с Magic Actions).

Результат: `../Enhancer_for_YouTube.crx` (имя — из поля `name` манифеста).

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh                # пакует текущий каталог
                                # сам проверяет результат; битый .crx не запишет
```

---

## §4 Сохранение/восстановление настроек (config-backup.json)

Настройки расширения хранятся в `chrome.storage.local` (встроенный хранилище
Chrome). Для архива и переноса на другой ПК:

### Сохранение
- Кнопка «Сохранить настройки» в popup (`popup.html`) → создаёт
  `config-backup.json` в папке Загрузок (Chrome не даёт писать в папку
  расширения напрямую из-за readonly-ограничений CRX). Скопируйте файл
  в папку расширения.
- Скрипт `save-config.sh` (в папке расширения) — читает LevelDB-хранилище
  Chrome и выгружает `config-backup.json` прямо в папку расширения.
  Работает с установленным расширением (CRX или unpacked).

### Восстановление
- Кнопка «Восстановить» в popup — читает `config-backup.json` из папки
  расширения (в unpacked-режиме) и записывает все ключи в
  `chrome.storage.local`.
- При установке/обновлении расширения сервис-воркер автоматически ищет
  `config-backup.json` в папке и восстанавливает настройки (только в
  unpacked-режиме; в CRX-режиме папка readonly и файл недоступен).
- Скрипт `restore-config.sh` — восстанавливает через CDP (Chrome должен быть
  запущен с `--remote-debugging-port=9223`).

### Какие данные сохраняются
Все ключи `chrome.storage.local`: `maTheme`, `channelspeeds` (скорость по
каналам — ID + название), `darktheme`, `theme`, `volume`, `speed`,
`selectquality`, `cinemamode`, `miniplayer`, `hidecomments`, `controls`,
`localecode`, `backdropcolor`, `filter`, `videofilters`, `customcss` и др.

---

## Файлы, изменённые в этой сессии

| Файл | § | Что |
|---|---|---|
| `js/youtube-main.js` | 1,3 | `gd` (колесо=громкость), `efytChannelName`, `efytSpdSave`, `efytAskChannelSpeed`, `sb` (вызов `efytAskChannelSpeed`), `efytApplySpeed` (защита на `S.style`), `gc`/`hc` (пропуск при `data-ma-theme="light"`) |
| `js/youtube-isolated.js` | 2 | `channel-speed-get`/`set` — два ключа (id + `name:`) |
| `js/config.js` | 1 | `controlvolume:!0` |
| `manifest.json` | 3 | `key` → публичный ключ `efyt_private.pem` (ID `ifojmbdceojdnhhagpmfnmjndpplcndi`), новые `content_scripts` (ma-main-world.js, ma-content.js, css/ma.css), `default_popup` → `popup.html` |
| `popup.html`/`popup.js`/`popup.css` | 3,4 | Popup: переключатель темы + «Настройки Enhancer» + «Сохранить/Восстановить настройки» |
| `js/service-worker.js` | 3,4 | case `"open-options"`, auto-restore `config-backup.json` на install/update, `efyt-backup-save`/`efyt-backup-restore` через `chrome.runtime.onMessage` |
| `html/options.html` | 4 | Панель «Сохранить/Восстановить» внизу страницы + JS-обработчик |
| `save-config.sh` | 4 | Dump `chrome.storage.local` → `config-backup.json` в папке расширения (через LevelDB) |
| `restore-config.sh` | 4 | Восстановление `config-backup.json` → `chrome.storage.local` (через CDP) |
| `css/ma.css` | 3 | CSS для темы Magic Actions (только тёмная тема `html[dark]` + тумблер) |
| `js/ma-content.js` | 3 | ISOLATED: применение темы, кукка PREF f6, чистка классов `*Dark`, тумблер |
| `js/ma-main-world.js` | 3 | MAIN: блокировка атрибутов dark/light, перехват cookie, диспатч `yt-action` |
| `package-crx.sh` | 5 | Скрипт упаковки в CRX3: канонический формат Chromium + встроенная верификация; SKIP: `config-backup.json`, `save-config.sh`, `restore-config.sh` |
| `efyt_private.pem` | 5 | Приватный ключ подписи CRX (PKCS#8, RSA-2048) — определяет ID |

Оригинальные `key`, `version`, `_locales`, `vendor`, `css` не тронуты.


---

## §3 Объединение с «Magic Actions for YouTube» (2026-09-24)

**Файлы добавлены в §3:**

| Файл | Что |
|---|---|
| `js/ma-content.js` | ISOLATED world: применение темы (dark/light), кукка PREF f6, чистка классов `*Dark`, тумблер `#__magic-theme-switch` |
| `js/ma-main-world.js` | MAIN world: блокировка атрибутов dark/light, перехват cookie PREF, диспатч `yt-action` по метке `data-ma-notify` |
| `css/ma.css` | CSS для темы (только тёмная тема `html[dark]` + тумблер) |
| `popup.html`, `popup.css`, `popup.js` | Popup-окно: переключатель темы + кнопка «Настройки Enhancer» |
| `manifest.json` | Новые `content_scripts` (MAIN + ISOLATED для магии), `action.default_popup` → `popup.html` |
| `js/service-worker.js` | Новый case `"open-options"` → `chrome.runtime.openOptionsPage()` |

**Изменения в `js/youtube-main.js` (§3):**
- `gc()` — пропускается, если `data-ma-theme="light"` (чтобы Enhancer не ставил тёмный `dark=""` при выборе светлой темы)
- `hc()` — пропускается, если `data-ma-theme="light"` (стили не вставляются)

**Философия темы (перенесена из Magic Actions §3):**
- `maTheme="dark"` = форсаж: атрибуты + куки + блокировки в MAIN world + CSS-токены
- `maTheme="light"` = расширение «выключено»: только нативные атрибуты, никаких CSS-правил

> **Папка `../Magic Actions for YouTube/` удалена.** Весь функционал темы
> влит сюда (§3). Исходники и документация сохранены в
> `../Magic Actions for YouTube — исследование переключения темы (сводный
> документ).md` и `../Magic Actions for YouTube — проблемы и ошибки.md`
> (в родительской папке `../расширения/`).

---

## §6 Починка «Число видео в ряду» (2026-09-25)

**Симптом:** опции «Видео в ряду» / «Shorts в ряду» / «Постов в ряду» (раздел
«Разное» настроек) не оказывают никакого эффекта — сетка всегда остаётся
нативной (3–4 в ряд).

**Первопричина:** расширение задавало число через CSS-переменную
`--ytd-rich-grid-items-per-row` (YouTube сам считает ширину карточки как
`calc(100%/var(--ytd-rich-grid-items-per-row) - var(--ytd-rich-grid-item-margin))`
— это работает и сейчас, проверено через `CSS.getMatchedStylesForNode`).
Селекторы, навешивающие эту переменную на элементы, были написаны под
**булевы атрибуты** (`is-shorts-grid`, `is-slim-media`, `rendered-from-rich-grid`,
`is-in-first-column`, `is-shelf-item`, `is-post`). Текущий билд YouTube
(clientVersion `2.20260922`, player `02b72088`) эти атрибуты больше не
выставляет — вместо них на элементах классы:

| старый атрибут | новый класс |
|---|---|
| `is-shorts-grid` | `.ytdRichItemRendererIsShortsGrid` |
| `is-slim-media` | `.ytdRichItemRendererIsSlimMedia` |
| `is-shorts-grid` + `is-slim-media` | `.ytdRichItemRendererIsShortsGridSlimMedia` |
| `is-in-first-column` | `.ytdRichItemRendererNoFirstColumnMargin` |
| `rendered-from-rich-grid` | удалён — больше не нужен |
| `is-shelf-item` | удалён — область видимости и так внутри shelf |

В коде YouTube (`ytmainappweb` бандл) `rendered-from-rich-grid` / `is-shelf-item`
/ `is-slim-media` / `is-shorts-grid` / `is-in-first-column` — **0 вхождений**,
а на живой странице у элементов только классы. Поэтому старые селекторы
никогда не матчились и переменная не применялась.

**Исправлено:**
- `css/youtube.css` (правила `html.efyt-videos-per-row` / `efyt-shorts-per-row`
  / `efyt-posts-per-row` / `efyt-channel-*-per-row` и правила отступов для
  первого столбца): атрибутные селекторы заменены на классовые.
- `js/youtube-main.js`, функция `Db()` (шаблонный литерал, что вставляет
  `<style id="efyt-grid-items-per-row">`): селекторы `:nth-child(-n + N)`
  для shelf-элементов переведены на классы.

**Проверка (chromium headless, CDP, 1920×1080, все опции = 6):**

| Страница | До | После |
|---|---|---|
| `/@MrBeast/videos` | 3 в ряд, ширина 419.98px | **6 в ряд**, 30 элементов, ширина 201.98px, `--ytd-rich-grid-items-per-row: 6` |
| `/@MrBeast/shorts` | 3 в ряд | **6 в ряд**, 48 элементов |

Главная страница (`page-subtype="home"`) анониму пустая, поэтому прямо
проверена только страница канала; механизм там тот же (та же переменная и
тот же `ytd-rich-item-renderer`), плюс к главной теперь применяются
исправленные селекторы и для shelf-элементов.

**Грабли:** `ytd-rich-shelf-renderer[is-shorts]` в старом CSS было частью
селектора для shorts; атрибут `is-shorts` тоже исчез — shorts теперь
различаются по классу самого элемента (`IsShortsGrid`/`IsSlimMedia`), а не
по атрибуту shelf'а.

---

## §7 Починка скорости по каналам: дробные скорости не сохранялись (2026-09-28)

**Симптом:** пользователь ставил скорость 1.6 на видео канала — и на следующем
видео **того же канала** скорость не восстанавливалась (возвращалась к
глобальному значению).

**Причина:** `Yc` (обработчик `onPlaybackRateChange` в `js/youtube-main.js`)
проверял `Number.isInteger(a)` перед вызовом `efytSpdSave(a)`. Дробные
скорости (1.25, 1.5, 1.6, 1.75, 2.5 и т.д.) — не целые числа, поэтому
`efytSpdSave` **никогда не вызывался** для них. В результат:
1. `efytSpdSave` не сохранял дробную скорость в `channelspeeds` (ни по
   `channelId`, ни по `name:<Имя>`).
2. Глобальная переменная `z` (текущая скорость) не обновлялась для дробных
   значений → все последующие сбросы (`sb()`, `Wc`, `Hc`) использовали
   устаревшее `z`.

**Исправлено** (все в `js/youtube-main.js`):
- `Yc`: `Number.isInteger(a)` → `Number.isFinite(a)` (в двух местах:
  перед `efytSpdSave` и перед обновлением `z`). Теперь `z` корректно
  обновляется и для дробных скоростей.
- `efytChannelId`: убран fallback на `getVideoData().author` (это **имя**,
  не ID) — он засорал `channelspeeds` лишними ключами. Теперь возвращает
  только `videoDetails.channelId` или `""`.
- `efytChannelName`: переписан на понятную последовательность
  (сначала `getPlayerResponse().videoDetails.author`, затем
  `getVideoData().author`).

После фикса: ставишь 1.6 на видео канала X → `Yc` → `efytSpdSave(1.6)` →
`channel-speed-set` (id + name) → изолированный скрипт пишет оба ключа в
`chrome.storage.local.channelspeeds`. Заходишь на другое видео X →
`Wc` (state 1) → `efytAskChannelSpeed()` → `channel-speed-get` → находит
в storage → `efytApplySpeed(1.6)` → скорость применяется.

---

## §8 Починка отключения звука на первых секундах нового видео (2026-09-30)

**Симптом:** при переходе на новое видео (или автопереходе к следующему)
звук на первых секундах был отключён — громкость не применялась.

**Причина:** в `js/youtube-main.js` функция `sb()` применяет сохранённую
громкость только при условии `d.defaultvolume&&!Ub`, где `Ub` — флаг
`unstarted-mode`, устанавливаемый в обработчике колеса мыши `gd()`:
`Ub=f.classList.contains("unstarted-mode")`. Если пользователь прокручивал
колесо над плеером, когда видео ещё не началось (unstarted-mode), `Ub`
оставался `true` и после загрузки нового видео — и `sb()` пропускал вызов
`f.setVolume(f.efytVolume)`. В результате видео стартовало с нулевой
громкостью (или с той, что было до вызова), т.е. звук был «отключён».

**Исправлено:** в обработчике `yt-navigate-finish` (строка 296) добавлен
сброс флага: `Ub=!1;`. Теперь при каждой навигации на новое видео `Sb()`
гарантированно применяет сохранённую громкость (`f.efytVolume` или
`d.volume`).

```js
// yt-navigate-finish — добавлен Ub=!1
f&&(f.enhance=!0,/&list=/.test(a.detail.url)||(f.efytVolume=void 0));Ub=!1;
```

---

## Файлы, изменённые в этой сессии

| Файл | § | Что |
|---|---|---|
| `js/youtube-main.js` | 8 | `yt-navigate-finish`: сброс `Ub=!1` — громкость применяется на новом видео |
| `package-crx.sh` | — | без изменений; собран `../Enhancer_for_YouTube.crx` (3.1.0, ID `ifojmbdceojdnhhagpmfnmjndpplcndi`) |

---

## §9 «Гаснет звук на старте» + «скорость падает на 1 при переходе на эпизод» (2026-10-05)

Два симптома, о которых сообщил пользователь:

1. **Включаю видео — выключается звук.**
2. **Перехожу на другой эпизод / на другую часть видео — скорость сбрасывается на 1**
   (должна оставаться той, что установлена).

### Проверено живьём (CDP, chromium)

Прогон `bash`-+python сценария: `chromium --headless=new --load-extension=…` +
CDP. Факты, которые подтвердились на живой странице:

| Что проверено | Результат |
|---|---|
| `#movie_player` и `<video class="html5-main-video">` при навигации | пересоздаются (новые узлы), у нового `<video>` `playbackRate=1`, `defaultPlaybackRate=1` |
| кеш расширения `n` / `f` | **остаётся актуальным** — `n === document.querySelector('video.html5-main-video')`, `f === #movie_player` (гипотеза «протухший узел» **не подтвердилась**) |
| `defaultvolume` в настройках по умолчанию | `false` — значит `sb()` громкость не трогает, и «выключает звук» не через неё |
| порядок в `sb()` | сначала применяется `z`, потом `efytAskChannelSpeed()` |
| `onPlaybackRateChange` при смене видео | плеер рапортует **1** на новом `<video>` |

### Корневая причина скорости

`Yc()` (обработчик `onPlaybackRateChange`) стоял так:

```js
function Yc(a){if(Number.isFinite(a)){if(a!==efytEcho)efytSpdSave(a);…
  else z=a}}
```

То есть **любое** событие изменения скорости, кроме собственного эха `efytEcho`,
считалось «выбором пользователя»:

* затирало глобальную скорость `z` значением `1`;
* вызывало `efytSpdSave(1)` → писало `channelspeeds[<канал>]=1` в
  `chrome.storage.local`.

А при смене видео YouTube создаёт новый `<video>` со скоростью 1 и честно
сообщает об этом `onPlaybackRateChange(1)`. Итог: стоило поставить 1.6 на
эпизоде — при переходе на следующий `z` становился 1 **и сохранённая скорость
канала переписывалась на 1**. Скорость «по каналам» (§2, §7) при этом
теряла смысл: сохранялось ровно то, что и так 1.

Воспроизведено прямым вызовом обработчиков расширения (headless-chromium не
декодирует H.264, поэтому реальные события плеера не приходят — вызываем
`Yc`/`jb` теми же числами, что шлёт YouTube):

```
                              ДО (исходный код)          ПОСЛЕ (этот фикс)
B: z не сброшен в 1 при навигации      FAIL (z=1)                  OK
B: 1 НЕ записан в channelspeeds        FAIL (SAVE 1)               OK
E: 1 не сохранён при новом видео       FAIL (SAVE 1)               OK
C/D: скорость пользователя сохраняется  OK                         OK
```

Кеш до: `Rick Astley: 1` (сохранённая скорость уничтожена сбросом).

### Исправление

1. **Флаг «это смена видео» `efytNav`.** Ставится в `yt-navigate-start` и
   `yt-player-updated`, снимается в `sb()` (когда наша скорость уже
   применена) и страховочным таймером 10 с:

```js
Ub=!1;efytUser=!1;efytNav=!0,clearTimeout(efytNavT),
  efytNavT=setTimeout(()=>{efytNav=!1},1E4);
```

2. **Флаг «это сделал пользователь» `efytUser`.** Ставится в обработчиках,
   которые меняют скорость по действию пользователя: `jb` (колесо и кнопки
   ± скорости), `Gb` (сброс на 1x), `Hc` (Ctrl+клик / клавиатура), и в
   `case "speed"` настроек. В `Yc` флаг сбрасывается после первого события.

3. **`Yc` различает сброс плеера и выбор пользователя:**

```js
function Yc(a){if(Number.isFinite(a)){var efytWasUser=efytUser;efytUser=!1;
if(a!==efytEcho){if(efytWasUser||!efytNav)efytSpdSave(a);else efytReapplySpeed()}
if(a===efytEcho)efytEcho=0;var b=f.querySelector(".ytp-speedmaster-overlay");
if(2===a&&0<(null==b?void 0:b.clientWidth))f.efytRestorePlaybackRate=!0;
else if(2!==a&&f.efytRestorePlaybackRate)if(delete f.efytRestorePlaybackRate,
  d.overridespeeds)n.playbackRate=z,n.defaultPlaybackRate=z;
  else{let e,g;null==(g=(e=f).setPlaybackRate)||g.call(e,z)}
else if(efytWasUser||!efytNav)z=a}}
```

Сброс от нового `<video>` → `efytReapplySpeed()` возвращает `z` (и
`defaultPlaybackRate`), **не** сохраняя и **не** затирая. Выбор пользователя
и нативное меню YouTube (когда `efytNav` уже снят) по-прежнему сохраняются.

4. **`efytReapplySpeed()`** — новый помощник, дубль `sb()` без побочных
   эффектов.

5. **Корневая причина «гаснет звук» — гейт `!Ub` в `sb()`.** `Ub`
   выставлялся в обработчике колеса `gd()`, когда видео ещё в
   `unstarted-mode`. С §1 колесо над всем плеером крутит громкость, поэтому
   достаточно одного прокручивания мыши над ещё не начавшимся видео, чтобы
   `Ub` стал `true` — и `sb()` пропускал `f.setVolume(f.efytVolume)`.
   §8 лечил это сбросом `Ub=!1` в `yt-navigate-start`, но флаг успевал
   снова встать в `true` при прокрутке **после** навигации. Гейт убран:

```js
// было:  d.defaultvolume&&!Ub&&(f.efytVolume||…
// стало: d.defaultvolume&&(f.efytVolume||…
```

6. **`efytAskChannelSpeed()` переспрашивает**, если `channelId` ещё не
   прочитан (сразу после навигации `getPlayerResponse()` может быть пустым) —
   до 10 попыток по 400 мс.

7. **Кеш скоростей больше не засоряется нулями:** изолированный скрипт
   возвращает `speed:0`, когда у канала нет сохранённой скорости; в
   `efyt-channel-speed` добавлена проверка `if(b.speed)`, иначе в
   `efytSpd` попадали нули.

### Требуемая настройка

Громкость восстанавливается только при включённой опции
**«Громкость по умолчанию» (`defaultvolume`)** — с выключенной опцией
`sb()` не трогает громкость вовсе, и «выключает звук» не может. Поскольку
§1 сделал колесо над плеером регулятором громкости, стоит держать эту опцию
включённой.

### Файлы, изменённые в этой сессии

| Файл | § | Что |
|---|---|---|
| `js/youtube-main.js` | 9 | `Yc` (различает сброс/пользователя), `sb` (снят гейт `!Ub`, сброс `efytNav`), новый `efytReapplySpeed`, флаги `efytNav`/`efytUser`/`efytNavT`/`efytAskT`/`efytAskN`, `efytAskChannelSpeed` (повтор), `efyt-channel-speed` (не кешировать 0), `jb`/`Gb`/`Hc`/`case "speed"` (ставят `efytUser`), `yt-navigate-start`/`yt-player-updated` (армят `efytNav`) |
| `package-crx.sh` | — | без изменений; собран и верифицирован `../Enhancer_for_YouTube.crx` (ID `ifojmbdceojdnhhagpmfnmjndpplcndi`) |

---

## §10 Панель скорости у шестерёнки + контекстное меню «Поиск на YouTube» (2026-10-28)

**Файлы:**

| Файл | Мир | Что |
|---|---|---|
| `js/channel-speed-panel.js` | MAIN | кнопка `1×` в плеере, панель пресетов, чтение канала |
| `js/channel-speed-bridge.js` | ISOLATED | доступ к `chrome.storage.local.channelspeeds` |
| `css/channel-speed-panel.css` | — | стили панели (префикс `ytcs-`) |
| `js/youtube-main.js` | MAIN | хук `window.__efytChannelSpeed` |
| `manifest.json` | — | право `contextMenus`, три новых файла в первых content-script записях |
| `js/service-worker.js` | SW | создание пункта меню и обработчик выбора |

### Почему не второй движок скорости

Enhancer уже умеет хранить и автоматически применять скорость по каналам
(§2, §7, §9). Поэтому панель **не** заводит своё хранилище и не повторяет
автоприменение: она работает поверх штатного механизма.

- Читает и пишет ту же таблицу `chrome.storage.local.channelspeeds`
  (`"<channelId>"` и `"name:<Имя>"`).
- Меняет скорость через `efytApplySpeed()` — тот же путь, что у кнопок `±`
  и колеса Enhancer.
- Сохраняет через `efytSpdSave()` — обновляется и `channelspeeds`, и
  внутристраничный кеш `efytSpd`.
- Восстанавливает скорость при переходе между видео по-прежнему Enhancer
  (`efytAskChannelSpeed()` / §9), а не панель.

Так исключён конфликт двух автоприменений: панель только показывает
состояние и по действию пользователя зовёт штатные функции.

### Хук в `js/youtube-main.js`

Добавлен в самый конец IIFE, перед `})(window,document);`:

```js
m.__efytChannelSpeed = {
  get: function () {
    return { id: efytChannelId(), name: efytChannelName(),
             rate: "number" == typeof z ? z : 1 };
  },
  set: function (a, b) {
    var r = Math.round(100 * Number(a)) / 100;
    Number.isFinite(r) || (r = 1);
    r = Math.min(4, Math.max(.25, r));
    efytApplySpeed(r);            // применить как Enhancer
    !1 !== b && efytSpdSave(r);   // сохранить (b === false — не сохранять)
    return r;
  },
  forget: function () {           // сброс кеша Enhancer
    try {
      var a = efytChannelId(), b = efytChannelName();
      a && delete efytSpd[a];
      b && (delete efytSpd[b], delete efytSpd["name:" + b]);
      efytSavedVal = 0;
    } catch (e) {}
  }
};
```

`forget` важен: без него «Забыть канал» удалял запись только из
`chrome.storage`, а Enhancer продолжал держать скорость в кеше `efytSpd` и
применял её на следующем видео этого канала. Заодно сбрасывается
`efytSavedVal`, иначе повторное сохранение той же скорости после «забыть»
молча пропускалось бы (`efytSpdSave` сравнивает с последним сохранённым
значением).

### Панель

- Кнопка `1×` вставляется **непосредственно перед шестерёнкой** — в
  актуальной вёрстке YouTube она лежит в `.ytp-right-controls-left`, поэтому
  `insertBefore` делается в родителя шестерёнки, а не в `.ytp-right-controls`.
- В панели: пресеты `0.5×…2.5×`, точная подстройка `−/+` по `0.05`,
  «Сбросить (1×)», «Забыть канал».
- Синий цвет кнопки — для канала есть сохранённая скорость.
- Канал берётся из `__efytChannelSpeed.get()`, запасной путь — DOM
  (`#owner #channel-name a`, `ytd-video-owner-renderer`, ссылки `/@handle`
  и `/channel/UC…`).
- Клики внутри панели не ставят видео на паузу (`stopPropagation` на
  `mousedown`/`mouseup`/`dblclick`).
- SPA: `yt-navigate-start/finish`, `yt-page-data-updated`, `yt-player-updated`,
  `ratechange`, `loadedmetadata`, `playing` + watchdog раз в 1 с. Панель не
  применяет скорость сама — только перечитывает канал и сохранённое значение,
  чтобы не спорить с §9.

### Контекстное меню

В `js/service-worker.js`:

```js
const YTCS_MENU_ID = "ytcs-search-youtube";

function ytcsCreateMenu() {
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
  const query = String(info.selectionText || "").replace(/\s+/g, " ").trim();
  if (!query) return;
  chrome.tabs.create({
    url: "https://www.youtube.com/results?search_query=" + encodeURIComponent(query)
  });
});
```

- `removeAll` перед `create` защищает от дублей при обновлении расширения.
- Пункт появляется только при выделенном тексте (`contexts: ["selection"]`),
  на любой странице, а не только на YouTube.
- В отличие от исходного расширения «Contextual Search for YouTube», запрос
  кодируется через `encodeURIComponent`, поэтому кириллица, `#`, `+`, `&`
  не теряются и не ломают URL.
- В `manifest.json` добавлено право `contextMenus`.

**Про иконку.** Chrome не поддерживает отдельные иконки для пунктов
контекстного меню (`contextMenus.create` не имеет поля `icons`). Рядом с
пунктом браузер показывает иконку самого расширения — то есть логотип
Enhancer. Иконку из «Contextual Search for YouTube» нельзя повесить только на
этот пункт, не заменив иконку всего расширения; поэтому branding Enhancer
оставлен как есть. Сам пункт и его работу это не затрагивает.

### Проверено

Chromium 149 (headless + headful в Xvfb):

- `chrome.developerPrivate`: `manifestErrors`, `runtimeErrors`,
  `installWarnings` — пустые; расширение `ENABLED`.
- Панель появляется слева от шестерёнки, канал определяется
  (`Rick Astley`), кнопка показывает текущую скорость.
- Пресет `1.5×` → `video.playbackRate = 1.5`, в `channelspeeds` появляются
  оба ключа (`UCuAXFkgsw1L7xaCfnd5JJOw` и `name:Rick Astley`).
- Перезагрузка видео → Enhancer сам возвращает `1.5×`, панель показывает
  `1.5×` и синюю кнопку.
- «Забыть канал» → скорость `1×`, `channelspeeds` пуст, кеш Enhancer сброшен;
  повторная установка `1.75×` снова сохраняется (проверка сброса
  `efytSavedVal`).
- Штатная кнопка Enhancer `#efyt-speed-plus` продолжает работать
  (два клика: `1× → 1.4×`), панель синхронно обновляет подпись.
- Правый клик по выделенному тексту → пункт **«Поиск на YouTube»** →
  открывается `youtube.com/results?search_query=…` с выделенной фразой
  (проверено на кириллице).

### Сборка

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh
```

Результат: `../Enhancer_for_YouTube.crx`, ID
`ifojmbdceojdnhhagpmfnmjndpplcndi` (ключ `efyt_private.pem` не менялся).
