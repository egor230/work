# Enhancer for YouTube™ — кастомная копия

Само видео: dtDWcBdrwVk — «Serious Sam: Next Encounter — Консольный аркадный Сэм», 45:12, playabilityStatus: OK, публичное, без возрастного restricting. С ссылкой t=2127s (35:27) всё в порядке, блокировки видео нет.

Потоки googlevideo.com с вашей машины (два замера с интервалом ~10 минут):

Замер	Результат
1-й	206 только у itag 251, 394, 244, 398, 299, 399. У остальных — 302 (редирект на удалённый узел) или 000 (нет ответа), в т.ч. 308 = 000
2-й	Все проверенные itag, включая 135, 303, 140, отдают 206
То есть жёсткой блокировки нет — есть нестабильность. CDN-узел сегодня 188.254.91.173 (в README от 16 ноября был 46.61.168.108 — кэш провайдера сменился, поэтому «хорошие» itag'и тоже поменялись).

Ключевые находки
1. Расширение уже патчили под это видео. В README-CUSTOM.md, §13 прямо написано: это видео крутилось в Яндекс.Браузере, и 16 ноября добавили параметр forcevp9 — запрет H.264 через переопределение MediaSource.isTypeSupported. Патч реально стоит в установленной копии (forcevp9&&/(avc1|avc3)/i.test(b)?!1:a(b)).

2. Но сейчас патч выключен. В живой БД настроек расширения история valores: false → true → false → true → false. Последняя запись — forcevp9 = false (записано сегодня ~15:41, прямо перед вашим вопросом). Вы сами его выключали — видимо, потому что перестановка не помогла.

3. При этом качество принудительно выставлено hd1440 (qualityvideos, qualityplaylists). Комбинация, которую просит плеер: VP9 + 1440p = itag 308 — а в первом замере он дал 000, худший результат. AV1 + 1440p = itag 400 дал 302. То есть даже включённый патч сегодня выбирал бы как раз нерабочие потоки.

4. Кодек-ловушка. Форматы 394–400 в таблице yt-dlp помечены как mp4, но на самом деле это AV1 (av01.0.xxM.08), а не H.264:

Кодек	itag'и
H.264 avc1	18, 133, 134, 135, 160, 298, 299
VP9	242, 243, 244, 278, 302, 303, 308
AV1	394–400
AAC / Opus	139/140 / 249/251
Поэтому «выбрать mp4» не значит «выбрать H.264» — плеер спокойно возьмёт AV1, и если в Яндекс.Браузере сломан аппаратный декодер AV1/VP9, получится ошибка кодека 4 или вечный буферинг. Это ваша «проблема с кодиками».

5. Перемотка на 35:27. Диапазонные запросы до ~5 МБ отдают 206, но запросы с lớn-оффсетом (20 МБ+) вернули 403. Скорее всего, это побочный эффект повторного использования подписанного URL (или смены IP — см. ниже), но именно такой запрос и делает плеер при перемотке в середину ролика.

6. DNS/прокси — вы были правы. В профиле Яндекс.Браузера три VPN-расширения: Browsec (PAC-скрипт с десятками зарубежных узлов cachequick.live, rapidcdn.click и т.п.), Windscribe, Cloud VPN. Подписанные URL googlevideo привязаны к IP: если трафик идёт то через прокси, то напрямую, подпись перестаёт совпадать → 403/302. Плюс браузер может резOLвить через свой DoH, минуя systemd-resolved (127.0.0.53), а правила nfqws завязаны на hostlist/ipset — из-за этого обход DPI применяется не ко всем запросам.

7. zapret в беспорядке. Активен ровно один nfqws, но вокруг него 24 осиротевших процесса service.sh run, запущенных с интервалом ~2 минуты за последние ~17 минут — следы множественных попыток перебрать стратегии, которые никто не остановил. Системный сервис zapret при этом inactive. Это тоже источник нестабильности.

Вердикт
Видео не заблокировано, кодеки как таковые не отсутствуют, соединение в среднем работает. «Иногда не могу» = плеер под ваши настройки (1440p + переключаемый codec-патч) выбирает конкретный itag, который в данный момент не отдаётся локальным кэшем, а перемотка требует нового range-запроса, который может быть отклонён из-за смены IP/подписи.

Что сделать (по порядку)
Убрать принудительное 1440p — поставить «Авто» или 720p. Это сразу убирает из уравнения itag 308/400.
Оставить forcevp9 выключенным на сегодня (сейчас так и есть) или включить обратно только после проверки — сегодня он не помогает.
Отключить VPN-расширения для YouTube (хотя бы Browsec) — это ваш «перехват DNS».
Почистить 24 зависших service.sh run, оставив одну рабочую стратегию zapret.
Если ошибка именно «кодек не поддерживается» — в Яндекс.Браузере отключить аппаратное ускорение (chrome://settings/system) и перезапустить.
Гарантированный просмотр: yt-dlp -f '299+140' (H.264+AAC, оба работали) или 398+251 (AV1+Opus) — скачать и открыть локально.
Чтобы поймать момент сбоя точно: F12 → Network → фильтр googlevideo, посмотреть статус (206/302/403) и itag выбранного потока, плюс chrome://media-internals для декодера.

Хотите — могу применить пункты 1, 4 и 5 (настройки расширения, чистка процессов, проверка конфигурации браузера), но я пока ничего не меняла, только анализировала.

можешь мне покороче объяснить, в чём проблема? 
Коротко:

Само видео нормальное и не заблокировано. Проблема в том, какой поток (itag) выбирает плеер — он меняется от кэша провайдера и настроек.

Причины по важности:

Расширение гонит качество 1440p. Для этого видео нужный поток (VP9 1440p, itag 308) сегодня не отдаётся (000), а AV1 1440p уводит на удалённый узел (302). Ролик и крутится.
Патч «forcevp9» вы включили, а потом выключили (последнее значение в настройках — false). Плюс прошлый workaround был рассчитан на старый кэш провайдера — сейчас узел сменился, и «хорошие» потоки другие.
Кодеки: то, что помечено как «mp4», на самом деле AV1 (394–400), а не H.264. Если декодер AV1/VP9 в браузере сбоит — ошибка кодека.
VPN-расширения (Browsec, Windscribe, Cloud VPN) и свой DNS браузера меняют IP — подписанные ссылки перестают работать → 403/302.
zapret размножен: 24 зависших процесса вместо одного — нестабильность.
Итог: не «видео заблокировано», а «плеер выбрал не тот поток + кэш и IP меняются».

Быстрое лечение: поставить качество Авто/720p, выключить VPN для YouTube, убрать лишние procesos zapret; для гарантии — скачать yt-dlp -f '299+140'.
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
| 11 | 2026-11-02 | Скриншот: копия в буфер обмена + имя «Screenshot ЧЧ-ММ-СС дата», убран битый путь в downloads | §11 |
| 12 | 2026-11-06 | Зеркало скоростей по каналам в JSON-файл `channelspeeds.json` в папке расширения | §12 |
| 13 | 2026-11-16 | Принудительный VP9/AV1 вместо H.264 (`forcevp9`) | §13 |
| 14 | 2026-11-22 | Настройки Яндекс.Браузера как значения по умолчанию | §14 |
| 15 | 2026-11-22 | Лог ошибок воспроизведения без повторов | §15 |
| 16 | 2026-11-24 | Скриншот → точная папка Screenshots, имя «Screenshot YouTube <дата>» | §16 |
| 17 | 2026-11-25 | Диагностика: почему скриншот всё равно не сохранялся; обновление в Яндекс.Браузере | §17 |

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

---

## §11 Скриншот: копия в буфер обмена + имя «Screenshot ЧЧ-ММ-СС дата» (2026-11-02)

**Файлы:** `js/youtube-main.js`, `js/youtube-isolated.js`.

### Что изменилось

1. **Буфер обмена.** В `youtube-main.js` в колбэке `toBlob` (функция `sc`,
   захват кадра) кадр одновременно копируется в системный буфер:
   `navigator.clipboard.write([new ClipboardItem({"image/png":k})])`.
   Вызов в try/catch с `.catch(()=>{})` — если страница/вкладка не даёт
   доступ к буферу (например, без user-activation), скриншот всё равно
   сохраняется в файл, ничего не ломается.
2. **Имя файла.** Было: `<автор> - <название> [id - WxH - время].png`
   ` DD MM YYYY HH MM SS` (через пробелы). Стало:
   `Screenshot ЧЧ-ММ-СС ГГГГ-ММ-ДД.png` — как у остальных файлов в папке
   `Screenshots` (пример: `Screenshot 05-18-55 2026-09-19.png`).
   Конфликты имён разбираются `conflictAction:"uniquify"`.
3. **Убран битый путь.** В предыдущей редакции в `filename`
   `chrome.downloads.download` прописывался `"../../../mnt/807EB5FA7EB5E954/...
   /Screenshots/"` — Chrome отбрасывает компоненты пути в `filename`
   (путь можно только **относительный от папки загрузки**, `".."`
   запрещён), поэтому файл падал в каталог загрузки браузера, а не в
   нужную папку. Теперь имя — чистый `Screenshot …png` без пути.

### Куда реально кладётся файл

Расширение (MV3) не имеет API записи в произвольную директорию
файловой системы — `chrome.downloads` пишет только в папку загрузки
браузера. Чтобы файл появлялся в
`/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Screenshots`:

- **Один раз** в браузере: `chrome://settings/downloads` →
  «Место назначения» → выбрать эту папку Screenshots.
- Дальше каждый скриншот кнопкой/горячей клавишей (c250)
  сохраняется туда автоматически с именем `Screenshot ЧЧ-ММ-СС ГГГГ-ММ-ДД.png`
  и копией в буфере обмена.

### Сборка

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh
```

---

## §12 Зеркало скоростей по каналам в JSON-файл (2026-11-06)

**Симптом/требование:** при смене скорости любым способом (колесо, кнопки
Enhancer, нативное меню YouTube, панель `1×`, горячие клавиши) значение
должно записываться в **настоящий JSON-файл в папке расширения**;
каждый канал хранит свою скорость и возвращает её на следующих видео
этого канала.

**Файлы:**

| Файл | Что |
|---|---|
| `js/service-worker.js` | зеркало `channelspeeds` → JSON: слушает `chrome.storage.onChanged`, пишет файл через native host (fallback — `chrome.downloads`) |
| `native-host/efyt-json-host.py` | native messaging host `com.efyt.channelspeeds`: пишет/читает `channelspeeds.json` |
| `install-native-host.sh` | регистрация хоста в NativeMessagingHosts всех установленных браузеров; `--uninstall` — убрать |
| `manifest.json` | право `nativeMessaging` |
| `package-crx.sh` | SKIP: `native-host/`, `install-native-host.sh`, `channelspeeds.json` |

### Хранение — двухуровневое

1. **`chrome.storage.local.channelspeeds`** — как и было (§2/§7/§9/§10):
   `{ "<channelId>": 1.5, "name:<Имя>": 1.5 }`. Источник правды для
   автоприменения скорости при переходах между видео. Работает в CRX.
2. **`channelspeeds.json` в папке расширения** — зеркало на диск,
   видимое и редактируемое вручную. **Формат:**

```json
{
  "_meta": { "about": "…", "updatedAt": "2026-11-06T…", "channels": 1 },
  "updatedAt": "2026-11-06T…",
  "speeds": { "UCuAXFkgsw1L7xaCfnd5JJOw": 1.5, "name:Rick Astley": 1.5 },
  "channels": [ { "id": "UC…", "name": "Rick Astley", "speed": 1.5 } ]
}
```

   `speeds` — каноническая таблица (по ней импорт), `channels` —
   человекочитаемый вид (имя восстанавливается, когда у скорости ровно
   один `name:`-ключ).

### Почему нужен native host

MV3-расширение не имеет API записи в произвольную директорию
(`chrome.downloads` пишет только относительно папки загрузок), а папка
установленного CRX вообще не та, что рабочая копия. Поэтому пишущий
процесс живёт вне расширения: `chrome.runtime.connectNative` запускает
`efyt-json-host.py`, который атомарно перезаписывает
`<папка расширения>/channelspeeds.json`. Расширение связано с хостом
через `allowed_origins` с ID `ifojmbdceojdnhhagpmfnmjndpplcndi`
(вычисляется из `efyt_private.pem`).

**Где регистрируется** (`install-native-host.sh` находит установленные):
`~/.config/google-chrome/NativeMessagingHosts/`,
`~/.config/chromium/NativeMessagingHosts/`,
`~/.config/yandex-browser/NativeMessagingHosts/`.

**Нюанс Chromium:** non-branded Chromium ищет манифесты хостов в
`<user-data-dir>/NativeMessagingHosts` — при обычном запуске это тот же
`~/.config/chromium/NativeMessagingHosts`; если запускать chromium с
другим `--user-data-dir`, манифест надо положить и в этот каталог.
Google Chrome читает `~/.config/google-chrome/NativeMessagingHosts`.

**Куда хост пишет файл:** `native-host/path.txt` (первая строка —
абсолютный путь; записывается установщиком). Файл конфигурации читается
при каждом запросе — путь можно поменять без перерегистрации.

### Механика зеркала (`js/service-worker.js`)

- Все писатели скорости (колесо/кнопки/нативное меню через
  `channel-speed-set`, панель через `channel-speed-bridge`) меняют один
  ключ `channelspeeds`, поэтому слушается `chrome.storage.onChanged` —
  фиксируется **любой** способ смены скорости.
- Дебаунс: первое изменение — сразу, серия — слепляется (1,5 с).
  Перезапись без изменения содержимого не происходит (сигнатура таблицы
  без меток времени).
- **Двусторонняя синхронизация:** перед записью хост отдаёт `mtimeMs`
  файла; если файл **новее** внутреннего хранилища
  (`chrome.storage.local.channelspeedsUpdatedAt`), его правили вручную —
  содержимое импортируется обратно в расширение (`speeds` →
  `channelspeeds`). После записи хранилище помечается тем же `mtimeMs`,
  поэтому собственные записи никогда не выглядят «чужими правками».
  Правка файла применяется при следующей смене скорости, при старте
  браузера (`onStartup`) или обновлении расширения (`onInstalled`).
- **Fallback без хоста:** если `connectNative` не находит хост — тот же
  JSON пишется через `chrome.downloads.download` с
  `conflictAction:"overwrite"` в
  `расширения/Enhancer for YouTube/channelspeeds.json` **относительно
  папки загрузок браузера**. При стандартной папке загрузок `~/Downloads`
  это ровно папка расширения; если назначение загрузок менялось в
  `chrome://settings/downloads`, файл окажется в подпапке внутри неё.
  Импорт ручных правок в fallback-режиме не работает (файл недоступен
  для чтения из CRX) — только запись.

### Установка и проверка

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./install-native-host.sh     # зарегистрировать (перезапустить браузер после)
./install-native-host.sh --uninstall   # убрать манифесты
```

Проверка: сменить скорость на видео → рядом с рабочей копией появляется/
обновляется `channelspeeds.json`. Панель скорости и таблица по каналам
работают как раньше (§10, §2/§7/§9) — зеркало ничего у них не отбирает.

### Проверено (E2E, chromium 149 headless + CDP)

| Сценарий | Результат |
|---|---|
| `channelspeeds` → JSON через хост | файл записан, `channels` содержит имя канала |
| повторный sync без изменений | файл не тронут (mtime совпадает) |
| хост жив, fallback не должен работать | скачиваний через `chrome.downloads` нет |
| файл правится вручную (новее хранилища) | правки импортированы в `chrome.storage` (1.5 из файла, а не 1.1 из хранилища) |
| хост удалён | тот же JSON через `chrome.downloads` → `загрузки/расширения/Enhancer for YouTube/channelspeeds.json` |

Протокол хоста проверен отдельно (пайп-тест: ping/read/write/rewrite).
`node --check`, `py_compile`, `bash -n` — без ошибок.

### Сборка

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh
```

Результат: `../Enhancer_for_YouTube.crx`, ID `ifojmbdceojdnhhagpmfnmjndpplcndi`.

---

## §13 Принудительный VP9/AV1 вместо H.264 (2026-11-16) — «как у helix»

**Проблема.** Видео `dtDWcBdrwVk` («Serious Sam: Next Encounter») крутилось в
Яндекс.Браузере, хотя остальные ролики шли нормально. Замер потоков с машины
показал: локальный Google Global Cache провайдера (`46.61.168.108`) отдаёт
`206` только для VP9/AV1-итагов (242/243/244/302/308/394/396–400) и аудио 251,
а H.264-итаги (18/133/134/135/160 и аудио 139/140) отвечают `302` и уводят на
удалённые узлы `173.194.x`, которые висят. Дело не в zapret и не в стратегии —
плеер выбирает «плохой» кодек.

**Решение.** НовыйCLUDE параметр `forcevp9` (по умолчанию **включён**) запрещает
H.264 через тот же механизм, что штатный `blockwebmformats` запрещает WebM:

| Файл | Изменение |
|---|---|
| `js/config.js` | `forcevp9:!0` в defaults + в `configEmbed` |
| `js/youtube-main.js` | в `MediaSource.isTypeSupported` добавлено `d&&d.forcevp9&&/(avc1\|avc3)/i.test(b)` |
| `js/embed-main.js` | то же для встроенного плеера |
| `html/options.html` | чекбокс «Принудительно VP9/AV1» в разделе кодеков |
| `js/options.js` | `#forcevp9` в списке биндингов чекбоксов |
| `_locales/ru,en_US` | сообщение `force_vp9` |

H.264 (`avc1`/`avc3`) блокируется, VP9/AV1 — остаются. Это заставляет YouTube
брать рабочие итаги из локального кэша. Чекбокс можно выключить, если
понадобится старое поведение.

**Настройки пользователя сохранены ДО патча:**

- `config-backup.json` в папке расширения
- `../config-backup-Yandex-20261116-225019.json`
- `/tmp/efyt-yandex-settings-20261116-225019.json`

Источник — `~/.config/yandex-browser/Default/Local Extension Settings/ifojmbdceojdnhhagpmfnmjndpplcndi`
(14 ключей, в т.ч. 42 скорости по каналам, тема `dark`, качество `hd1440`).
ID расширения не менялся: `ifojmbdceojdnhhagpmfnmjndpplcndi`.

**Сборка/установка:**

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh
# CRX: ../Enhancer_for_YouTube.crx
```

После сборки CRX распакован в установленную папку расширения Яндекс.Браузера
`~/.config/yandex-browser/Default/Extensions/ifojmbdceojdnhhagpmfnmjndpplcndi/3.1.0_1/`
(браузер был выключен, прежние файлы скопированы в бэкап).

---

## §14 Настройки Яндекс.Браузера — значения по умолчанию (2026-11-22)

**Требование:** настройки, которые были установлены в Яндекс.Браузере, должны
быть настройками по умолчанию для этого расширения (в т.ч. в CRX-сборке,
где `config-backup.json` из архива исключён).

**Источник:** `config-backup.json` / `../config-backup-Yandex-20261116-225019.json`
— 14 ключей, снятых с профиля Яндекс.Браузера
`~/.config/yandex-browser/Default/Local Extension Settings/ifojmbdceojdnhhagpmfnmjndpplcndi`.

### Проблема

`config-backup.json` лежит только в рабочей папке и в CRX **не попадает**
(`package-crx.sh`, `SKIP_FILES`). Механизм авто-восстановления из §4 читал
именно этот файл через `chrome.runtime.getURL()`, поэтому в установленном
CRX-расширении настройки Яндекс.Браузера не применялись — действовали
заводские значения из `js/config.js`.

### Решение

| Файл | Изменение |
|---|---|
| `js/config.js` | Заводские значения `config` приведены к значениям из бэкапа: `controlbar.active:!1`, `controls:"speed-minus speed speed-plus screenshot options"`, `controlsvisible:!0`, `griditemsperrow` (каналы 8/8, videos 6), `hideshorts:!0`, `qualityplaylists/qualityvideos:"hd1440"`, `selectquality:!0`, `speed:1.2` (`forcevp9:!0` уже был). Добавлены `defaultChannelSpeeds` (42 записи) и `defaultSettings` — полный набор из бэкапа, включая `maTheme:"dark"` и `channelspeeds`. |
| `js/service-worker.js` | Новый `_efytSeedDefaults()` досыпает ключи из `defaultSettings` в `chrome.storage.local` **только если их ещё нет** — пользовательские правки при обновлении не перетираются. При первичном посеве `channelspeeds` также ставится `channelspeedsUpdatedAt`, чтобы зеркало §12 не приняло свежую таблицу за «ручную правку файла». Прежний `_efytAutoRestore()` из `config-backup.json` оставлен как есть (unpacked-режим, поверх значений по умолчанию). |

### Итоговые значения по умолчанию

| Ключ | Значение |
|---|---|
| `channelspeeds` | 42 скорости по каналам (ID + `name:`) |
| `controlbar` | `{active:false, autohide:false, centered:true, position:"absolute"}` |
| `controls` | `speed-minus, speed, speed-plus, screenshot, options` |
| `controlsvisible` | `true` |
| `forcevp9` | `true` |
| `griditemsperrow` | channel.videos `true/8`, channel.shorts `false/5`, videos `true/6`, shorts `false/8`, posts `false/4` |
| `hideshorts` | `true` |
| `maTheme` | `dark` |
| `qualityplaylists`, `qualityvideos` | `hd1440` |
| `selectquality` | `true` |
| `speed` | `1.2` |

Мета-ключи `date` / `update` в значения по умолчанию не включены: их в любом
случае перезаписывает `onInstalled` сервис-воркера (`Date.now()`).

**Важно:** досыпание происходит только для отсутствующих ключей. Если
расширение уже установлено и у вас есть сохранённые настройки, они останутся
как есть; чтобы применить новые значения по умолчанию, нужно очистить
`chrome.storage.local` расширения (например, «Восстановить настройки» из
бэкапа или удаление/повторная установка расширения).

### Проверка

`node --check` — без ошибок. Сравнение всех 12 ключей `defaultSettings` и 8
совпадающих ключей `config` со значениями из `config-backup.json` — 22/22,
расхождений нет.

**Сборка:** `./package-crx.sh` → `../Enhancer_for_YouTube.crx`, ID
`ifojmbdceojdnhhagpmfnmjndpplcndi` (ключ не менялся).

---

## §15 Лог ошибок воспроизведения без повторов (2026-11-22)

**Требование:** если YouTube-видео не идёт / вылетает ошибка — записать её в
лог. Лог не должен содержать повторяющихся ошибок: если такая ошибка уже
была, новую запись не добавляем. Собрать один CRX и установить в Яндекс.Браузер.

### Файлы

| Файл | Мир | Что |
|---|---|---|
| `js/error-logger.js` | MAIN | Ловит `player.onError`, `<video>.error` (MediaError), появление error screen «Video unavailable». Шлёт событие `efyt-error-record` с videoId, названием, кодом/сообщением, состоянием сети. Подписывает новые узлы плеера/`video` MutationObserver'ом (YouTube — SPA). |
| `js/error-logger-bridge.js` | ISOLATED | Принимает событие, **дедуплицирует** и пишет `chrome.storage.local.errorlog`. Повтор прерывается до вызова `storage.set` — в лог не попадает ничего и не обновляется даже время. Лимит 200 записей. |
| `js/service-worker.js` | SW | `efytErrorLogSync()` экспортирует лог в JSON через уже установленный native host `com.efyt.channelspeeds` (путь берётся из `ping`, заменяется только имя файла на `errorlog.json`); fallback — `chrome.downloads` в `расширения/Enhancer for YouTube/errorlog.json`. Обработчик `efyt-error-sync`, debounce 1,5 с, синхронизация на старте и по `storage.onChanged`. |
| `html/errorlog.html`, `js/errorlog.js` | — | Просмотр лога: кнопки «Обновить», «Записать в файл», «Очистить». Открывается из popup кнопкой «⚠ Лог ошибок». |
| `popup.html`, `popup.js`, `popup.css` | — | Кнопка просмотра лога. |
| `manifest.json` | — | Добавлены `js/error-logger.js` (MAIN) и `js/error-logger-bridge.js` (ISOLATED). Новых разрешений не требуется. |

### Дедупликация

Ключ записи: `тип ошибки | код | нормализованное сообщение | videoId`.
Сообщение приводится к нижнему регистру, URL заменяются на `URL`, пробелы
схлопываются. Значит:

* та же ошибка на том же видео (в т.ч. после перезагрузки страницы) — **не** записывается;
* та же ошибка на другом видео, другой код или другой тип — записывается отдельно;
* у существующей записи не меняется ни счётчик, ни время — повтор просто игнорируется.

Лог хранится в `chrome.storage.local.errorlog`, файл
`errorlog.json` (в папке расширения, рядом с `channelspeeds.json`).
Очистка — кнопкой в просмотрщике.

### Проверено

`node --check` всех JS + валидность `manifest.json` — без ошибок.
Harness с моком `chrome.storage`: 6 событий (3 дубля, в т.ч. с нормализацией)
→ **4 записи, 4 вызова `storage.set`, 4 сообщения синхронизации** в логе.
Прямой пайп-тест native host: `ping` → `write` с вычисленным путём → файл
`errorlog.json` создан и прочитан.

**Сборка:** `./package-crx.sh` → один файл `../Enhancer_for_YouTube.crx`
(ID `ifojmbdceojdnhhagpmfnmjndpplcndi`).

---

## §16 Скриншот в точную папку Screenshots + имя «Screenshot YouTube <дата>» (2026-11-24)

**Требование:** кнопка скриншота должна сохранять картинку не в «Загрузки»,
а прямо в
`/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/Screenshots`,
с именем вида `Screenshot YouTube ЧЧ-ММ-СС ГГГГ-ММ-ДД.png`.

### Почему не получалось раньше

`chrome.downloads.download()` принимает в `filename` только путь **относительно**
папки загрузок браузера; абсолютные пути и `..` Chrome отбрасывает (§11).
Поэтому расширение и сохраняло в `~/Downloads`, а документация предлагала вручную менять
`chrome://settings/downloads`.

### Решение

| Файл | Изменение |
|---|---|
| `js/youtube-isolated.js` | Обработчик `efyt-screenshot-save` больше не зовёт `chrome.downloads` сам, а шлёт кадр (data URL) в сервис-воркер сообщением `efyt-screenshot-save`. |
| `js/service-worker.js` | `efytScreenshotSave()` режет base64 на куски по 200 000 символов (лимит одного сообщения native messaging — 1 МБ) и шлёт их в уже установленный хост `com.efyt.channelspeeds` (`shot_begin` → `shot_chunk`… → `shot_end`). Имя файла: `Screenshot YouTube ЧЧ-ММ-СС ГГГГ-ММ-ДД.png`. Каталог берётся из `chrome.storage.local.screenshotdir` с дефолтом на папку Screenshots. Fallback — старый `chrome.downloads`, если хост недоступен. |
| `native-host/efyt-json-host.py` | Новые типы сообщений `shot_begin` / `shot_chunk` / `shot_end`: собирают base64, декодируют в PNG и атомарно пишут по абсолютному пути. При совпадении имени добавляют ` (1)`, ` (2)` и т.д. — предыдущие скриншоты не перезаписываются. Копия в буфер обмена (§11) осталась. |

Путь хост уже знает из `native-host/path.txt` (там записан путь к
`channelspeeds.json`); для скриншотов берётся тот же каталог хоста, а абсолютный
путь папки Screenshots передаётся расширением в `shot_begin`. Перерегистрировать
хост **не нужно** — меняется только его `.py`-файл по тому же пути из манифеста
`NativeMessagingHosts/com.efyt.channelspeeds.json`.

### Проверено

`node --check` + `py_compile` + валидность `manifest.json` — без ошибок.
Пайп-тест хоста с настоящим 1×1 PNG, нарезанным на куски по 12 символов:
файл записан в целевую папку, байты совпадают с исходником (70 байт), повторная
запись создала `__efyt_test_shot (1).png`; тестовые файлы удалены.

**Сборка/установка:** `./package-crx.sh` → один CRX
`../Enhancer_for_YouTube.crx`, распакован в установленную папку расширения
Яндекс.Браузера (как в §13–§15). Версия поднята до **3.1.2**, папка установки —
`3.1.2_1`; причины и способ обновления — в §17.

---

## §17 Почему скриншот всё равно не сохранялся — диагностика и лечение (2026-11-25)

### Причина 1 — не выдано разрешение `nativeMessaging`

Файлы расширения менялись на диске «мимо» браузера, поэтому в
`~/.config/yandex-browser/Default/Preferences` в записи расширения остались
старые `active_permissions` / `granted_permissions` и старый сохранённый
манифест: только `contextMenus`, `downloads`, `storage`. Хотя на диске манифест
уже содержал `nativeMessaging`, во время исполнения `chrome.runtime.connectNative`
был недоступен. Сервис-воркер ловил исключение и уходил в fallback
`chrome.downloads` → кадр падал в «Загрузки», а не в нужную папку.

### Причина 2 — Яндекс.Браузер держал старый service worker

Даже после исправления прав воркер продолжал работать со старым кодом.
Проверено через CDP в консультационном контексте воркера:

| Проверка | Было |
|---|---|
| `config.speed` в globals воркера | `1` (старое значение) |
| `config.qualityvideos` | `hd720` |
| `typeof efytScreenshotSave` | `undefined` |
| `fetch(chrome.runtime.getURL('js/config.js'))` | новый файл (`hd1440`, `defaultSettings`) |

То есть файлы на диске новые, а загруженный воркер — старый: браузер кэшировал
скрипт расширения. Очистка `Code Cache` / `Cache` не помогла.

### Что сделано

1. В `Preferences` (при выключенном браузере) добавлен `nativeMessaging` в
   `active_permissions.api` и `granted_permissions.api`, сохранённый `manifest`
   заменён на актуальный с диска, `withholding_permissions=false`.
   Бэкап: `_backups-screenshot-20261124/Preferences.bak-20261125`.
2. Версия в `manifest.json` поднята `3.1.0` → **3.1.2**; CRX пересобран и
   распакован в новую папку
   `~/.config/yandex-browser/Default/Extensions/ifojmbdceojdnhhagpmfnmjndpplcndi/3.1.2_1/`;
   в `Preferences` обновлён `path` на `…/3.1.2_1`. Бэкап прежней установки —
   `_backups-screenshot-20261124/yandex-installed-3.1.0_1`.
3. Старый service worker снят с регистрации из страницы расширения:
   `navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()))`,
   после чего браузер был перезапущен и зарегистрировал воркер заново — уже с
   новым кодом.

### Проверено в живом Яндекс.Браузере (headless + CDP)

| Проверка | Результат |
|---|---|
| `typeof chrome.runtime.connectNative` | `function` |
| `chrome.runtime.getManifest().permissions` | `contextMenus, downloads, nativeMessaging, storage` |
| `config.speed` / `config.qualityvideos` в воркере | `1.2` / `hd1440` |
| `typeof efytScreenshotSave` | `function` |
| native `ping` | `{"ok":true,"host":"com.efyt.channelspeeds",…}` |
| `efytScreenshotSave(dataURL)` из воркера | `…/Project/Screenshots/Screenshot YouTube 22-32-07 2026-11-25.png` |
| `document.dispatchEvent(new CustomEvent('efyt-screenshot-save',{detail:{data:…}}))` на `youtube.com` | `…/Project/Screenshots/Screenshot YouTube 22-32-39 2026-11-25.png` |

Оба тестовых файла (70 байт, 1×1 PNG) удалены из папки Screenshots. После
выключения браузера `Preferences` сохранил `path=…/3.1.2_1`, версию `3.1.2` и
все четыре разрешения.

**Важно на будущее:** при ручной замене файлов расширения в Яндекс.Браузере
одновременно проверяйте `Preferences` (права + сохранённый манифест) и
перерегистрируйте service worker — иначе браузер продолжает выполнять старый
код, хотя `fetch(chrome.runtime.getURL(...))` показывает новые файлы.
