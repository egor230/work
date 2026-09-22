# Enhancer for YouTube™ — кастомная копия

Распакованная копия Chrome-расширения Enhancer for YouTube (MV3, store 3.1.0)
с локальными правками (см. ниже). Собирается в .crx собственным скриптом
`package-crx.sh` (раздел 3).

---

## Что изменено (2026-09-17)

### 1. Прокрутка громкости колёсиком мыши — по всему плееру

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

### 2. Скорость воспроизведения — таблица по каналам (ID + название)

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

### 3. Скрипт упаковки в .crx (CRX3, канонический формат Chromium)

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
(header 581 байт — ровно как у store-файлов; ~422 КБ).

Результат: `../Enhancer_for_YouTube.crx` (имя — из поля `name` манифеста).

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh                # пакует текущий каталог
                                # сам проверяет результат; битый .crx не запишет
```

---

## Файлы, изменённые в этой сессии

| Файл | Что |
|---|---|
| `js/youtube-main.js` | `gd` (колесо=громкость), `efytChannelName`, `efytSpdSave`, `efytAskChannelSpeed`, `sb` (вызов `efytAskChannelSpeed`), `efytApplySpeed` (защита на `S.style`) |
| `js/youtube-isolated.js` | `channel-speed-get`/`set` — два ключа (id + `name:`) |
| `js/config.js` | `controlvolume:!0` |
| `manifest.json` | `key` → публичный ключ `efyt_private.pem` (ID `fecamaihcghhlonfaaaa`) |
| `package-crx.sh` | скрипт упаковки в CRX3: канонический формат Chromium + встроенная верификация |
| `efyt_private.pem` | приватный ключ подписи CRX (PKCS#8, RSA-2048) — определяет ID |

Оригинальные `key`, `version`, `_locales`, `vendor`, `css` не тронуты.
