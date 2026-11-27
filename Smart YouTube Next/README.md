# Smart YouTube Next TV

**Подробное руководство по модифицированному клиенту YouTube для Android TV.**

Документ отвечает на четыре вопроса:

1. **Что это за программа** и откуда она взялась;
2. **Почему YouTube тормозил/падал на приставке** — разбор реальных логов;
3. **Как именно устроены обходы** — каждый механизм с объяснением «почему так»;
4. **Как обновлять, проверять и диагностировать** — готовые команды.

Актуально на **21.11.2026**. Версия приложения — **32.80**, все правки установлены на приставку и проверены.

---

## Содержание

- [1. Обзор](#1-обзор)
- [2. Исходники и сборка](#2-исходники-и-сборка)
- [3. Первопричина Problems: разбор логов](#3-первопричина-проблем-разбор-логов)
- [4. Как устроены обходы](#4-как-устроены-обходы)
  - [4.1. DPI-обход nfqws / zaprett](#41-dpi-обход-nfqws--zaprett)
  - [4.2. Живучесть обхода: жизненный цикл и фоновое воспроизведение](#42-живучесть-обхода-жизненный-цикл-и-фоновое-воспроизведение)
  - [4.3. Авто-фикс при явной ошибке сети](#43-авто-фикс-при-явной-ошибке-сети)
  - [4.4. Watchdog для «тихого» зависания](#44-watchdog-для-тихого-зависания)
  - [4.5. Логгер ошибок и дедупликация](#45-логгер-ошибок-и-дедупликация)
  - [4.6. Быстродействие интерфейса](#46-быстродействие-интерфейса)
  - [4.7. Прочие исправления](#47-прочие-исправления)
  - [4.8. Wink и OTT Navigator](#48-wink-и-ott-navigator)
- [5. Настройки и бэкапы](#5-настройки-и-бэкапы)
- [6. Практика: обновление и диагностика](#6-практика-обновление-и-диагностика)
- [7. Эмулятор для проверок](#7-эмулятор-для-проверок)
- [8. Структура папки проекта](#8-структура-папки-проекта)
- [9. История работ](#9-история-работ)

---

## 1. Обзор

**Smart YouTube Next TV** — это модифицированная сборка **[SmartTube](https://github.com/yuliskov/SmartTube)** (ветка `master`) для телевизора/приставки. Мы не писали свой YouTube-клиент с нуля: взяли готовый открытый проект и точечно дописали то, чего ему не хватало в условиях конкретной сети и конкретного железа.

| Параметр | Значение |
|---|---|
| Пакет | `com.egor.youtubetv` |
| Версия | 32.80 (база — upstream `master`) |
| Устройство | **Ugoos AM9 PRO**, Amlogic S905X4, Android 14, arm64-v8a, 4K |
| Root | Magisk (нужен только для DPI-обхода) |
| Имя в лаунчере | **Smart YouTube Next TV** |
| Подпись | та же, что у прежней сборки (SHA-256 `81f8d2a1…`) |
| Тип сборки | **release** (без флага `DEBUGGABLE`) |

Это **не веб-обёртка**. Плеер нативный: ExoPlayer + SABR/DASH, собственный API-клиент YouTube, свои списки и настройки. Интерфейс — стандартный для SmartTube: левая панель секций, ряды карточек, управление с пульта.

### Зачем вообще понадобились правки

На приставке YouTube показывал ролики нестабильно: одни видео грузились минутами, другие падали с «Unexpected playback error», иногда экран просто висел на спиннере. Причиной оказалась не мощность железа и не кодек, а **доступ к CDN `*.googlevideo.com`** — подробности в [разделе 3](#3-первопричина-проблем-разбор-логов).

### Другие приложения в экосистеме

| Приложение | Назначение |
|---|---|
| `com.egor.youtubetv` — Smart YouTube Next TV | основной рабочий клиент |
| `com.egor.webtube` — WebTube 1.0 TV | запасной клиент: YouTube внутри Android WebView (`m.youtube.com`). Выручает, когда нативный плеер капризничает |
| `org.smarttube.stable` 32.71 | официальный релиз с GitHub, без наших правок — эталон для сравнения |

---

## 2. Исходники и сборка

### 2.1 Откуда код

- Репозиторий: `https://github.com/yuliskov/SmartTube`, ветка `master`.
- Подмодули:
  - `SharedModules` — коммит `5475d318…`;
  - `MediaServiceCore` — актуальный `master`.

Правки вносятся **поверх** upstream и по возможности минимальны — чтобы при обновлении базы не приходилось переписывать весь проект заново. Список изменённых файлов можно увидеть в `scripts/patch_lifecycle.py` и в истории коммитов.

### 2.2 Как собирать

Окружение: JDK 17, Android SDK в `/home/egor/android-tv-emu/sdk`.

```bash
cd /tmp/opencode/SmartTubeRel          # быстрая сборка на /tmp (FUSE-монтаж workspace очень медленный)

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/home/egor/android-tv-emu/sdk
export ANDROID_SDK_ROOT=/home/egor/android-tv-emu/sdk

# РЕКОМЕНДУЕМЫЙ вариант — release:
./gradlew :smarttubetv:assembleStstableRelease

# Старый вариант (debug, медленнее):
./gradlew :smarttubetv:assembleStstableDebug --offline
```

Результат: `smarttubetv/build/outputs/apk/ststable/release/SmartTube_stable_32.80_arm64-v8a.apk`.

**Важно:** release-сборка требует доступа к сети — Gradle докачивает `lint-gradle` и связанные jar'ы. С флагом `--offline` release падает; debug собирается offline.

### 2.3 Подпись — почему не нужно заново логиниться

В корне исходников лежит `keystore.properties`:

```properties
storeFile=/home/egor/.android/debug.keystore
storePassword=android
keyAlias=androiddebugkey
keyPassword=android
```

Это **стандартный debug-keystore Android SDK** (пароли «android» известны и не являются секретом). Раньше приложение собиралось как debug и подписывалось именно им. Когда мы перешли на release, я прописал тот же ключ в `signingConfigs.release` — в результате отпечаток сертификата не изменился:

```
Signer #1 certificate SHA-256 digest: 81f8d2a1a93ae9abccd5f70869ce73c5ac29f00d8a9d6e8659ea835b4d6f8c7a
```

Поэтому `adb install -r` обновляет приложение **без потери данных**: Google-аккаунт, channels, настройки остаются на месте.

> ⚠️ **Жёсткие правила:**
> - не менять `applicationId` (`com.egor.youtubetv`);
> - не менять ключ подписи;
> - **никогда не делать `pm clear`** — это удалит токены, и вход в Google придётся проходить заново;
> - обновлять только через `docs/update_app.sh`.

### 2.4 Что делает `update_app.sh`

Скрипт решает задачу «обновить APK, но сохранить аккаунт»:

```bash
docs/update_app.sh /path/to/app.apk
```

1. `tar czf /sdcard/appdata_backup.tgz -C /data/data/com.egor.youtubetv .` — полный бэкап данных приложения;
2. `adb pull` — забираем бэкап на ПК (`/tmp/opencode/appdata_backup/`);
3. `adb install -r` — ставим новый APK;
4. `adb push` + `tar xzf` + `chown` — возвращаем данные на место с правильным владельцем.

Если установка не удалась, скрипт останавливается (`set -e`), а бэкап остаётся в `/tmp/opencode/appdata_backup/` — данные не теряются.

---

## 3. Первопричина проблем: разбор логов

До правок я снял с приставки `autofix_errors.log` — 23 ошибки за 19–20.11. Классификация:

| Ошибка | Кол-во | Что это значит |
|---|---:|---|
| `HttpDataSourceException: Unable to connect to …googlevideo.com` → `SocketTimeoutException: Read timed out` | 11 | TLS-соединение с CDN установилось, но чтение данных зависло |
| тот же класс → `NoRouteToHostException: Host unreachable` | 6 | до узла нет маршрута (характерно для «кривых» DNS-ответов) |
| `SabrReloadPlayerError` | 3 | YouTube просит заново получить player response |
| `SabrPoTokenError: PENDING / PENDING_MISSING` | 2 | токен `poToken` ещё не готов |

**Ключевой вывод:** ошибки сетевые, а не кодековые. В логах встречаются av1, avc, vp9 — зависимости от конкретного формата нет. Чаще всего падали ролики `M6TBfUTfuOc` (6 раз) и `gMhKHUYPm_g` (5 раз).

Отсюда и стратегия лечения: **чинить канал до `googlevideo.com`**, а не «переключать кодек ради кодека».

### Дополнительные симптомы и их разбор

**«Тихий» завис.** Некоторые ролики (4K, свежий poToken) висели на спиннере вообще без вызова `onEngineError` — авто-фикс по ошибке не срабатывал. Лечится отдельным watchdog'ом ([4.4](#44-watchdog-для-тихого-зависания)).

**`Unknown part encountered: id=9023, size=-50620897`.** Классический признак оборванного DASH-потока. Возникал, когда обход выключался при уходе на главный экран, а фоновое воспроизведение продолжалось — см. [4.2](#42-живучесть-обхода-жизненный-цикл-и-фоновое-воспроизведение).

**`null - Космос Просто` в строке фонового плеера.** Ролик, открытый внешним `VIEW`-intent, приходил без заполненного `title` — см. [4.7](#47-прочие-исправления).

---

## 4. Как устроены обходы

Все механизмы работают вместе и дополняют друг друга. Ниже — каждый по отдельности.

### 4.1. DPI-обход nfqws / zaprett

Это **главное** решение сетевых проблем.

#### Что такое DPI и зачем обход

DPI (Deep Packet Inspection) — система провайдера, которая смотрит не только на IP, но и на содержимое TLS- handshake. По набору признаков (SNI, порядок extension'ов, длины пакетов) она определяет, что вы идёте на YouTube, и начинает душить/подменять соединение. Отсюда `Read timed out` и `NoRouteToHost`.

`nfqws` перехватывает исходящие TCP-пакеты через **NFQUEUE** (iptables, цепочка `mangle`) и*mangling* их так, чтобы DPI не смог распознать трафик: разбивает TLS ClientHello на части, добавляет «мусор», подменяет SNI, имитирует другой клиент. Для YouTube это проверенная схема.

#### Почему именно zaprett 7.1.0

В проекте используются бинарники **nfqws 1** из **zaprett 7.1.0**. Причина принципиальная: более новые версии (nzapret) перешли на `nfqws2` + Lua-скрипты и **не совместимы** с вашей сохранённой стратегией `general_alt12`. Мы используем именно ту реализацию, под которую стратегия писалась.

#### Что именно вшито в APK

`DpiBypassInstaller` при первом запуске (нужен root/Magisk) раскладывает:

| Куда | Что |
|---|---|
| `/data/adb/modules/zaprett/system/bin/zaprett` | бинарник сервиса |
| `/data/adb/modules/zaprett/system/lib/arm64-v8a/libnfqws.so` | движок nfqws |
| `/data/adb/modules/zaprett/system/lib/arm64-v8a/libnfqws2.so` | совместимая библиотека |
| `/storage/emulated/0/zaprett/config.json` | конфигурация сервиса |
| `/storage/emulated/0/zaprett/strategies/general_alt12.txt` | сама стратегия |
| `/storage/emulated/0/zaprett/manifests/strategies/general_alt12.json` | манифест |
| `/storage/emulated/0/zaprett/files/bin`, `files/lists` | payload и списки |

Все файлы берутся из `assets/dpi/` внутри APK. Установка происходит **один раз** — marker-файл `dpi_bypass_installed` в `filesDir` защищает от перезаписи при обновлении, поэтому ваши настройки и стратегия не перетираются.

#### Параметры стратегии `general_alt12`

Стратегия перенесена из вашего сохранённого `general_alt12.bat` **без переделки**:

```
fake,multisplit
split-seqovl=664
split-pos=1
fooling=ts
repeats=8
hostfakesplit для Google с host=www.google.com
QUIC fake ×11
payload: tls_clienthello_www_sferum_ru.bin + stun.bin
```

#### Как запускать вручную

```bash
export LD_LIBRARY_PATH=/data/adb/modules/zaprett/system/lib/arm64-v8a
/data/adb/modules/zaprett/system/bin/zaprett status   # «zaprett is working»
/data/adb/modules/zaprett/system/bin/zaprett start
/data/adb/modules/zaprett/system/bin/zaprett stop
```

Проверено: после старта в `iptables -t mangle` появляются NFQUEUE-правила, ролик `5dGHRR1uizI` играет без новых ошибок.

> ⚠️ Обход **системный** (iptables/NFQUEUE) и требует root. Если root недоступен — приложение работает как обычное, тихо fallback'ится (в лог пишется `no root available — DPI bypass skipped`).

### 4.2. Живучесть обхода: жизненный цикл и фоновое воспроизведение

Обход должен работать **только когда приложение активно** — но фоновое воспроизведение считается активным. Здесь была тонкая ошибка, исправленная в два этапа.

**Этап 1 (20.11).** `DpiBypassInstaller` зарегистрирован как `ActivityLifecycleCallbacks` в `MainApplication`:
- первый `onActivityResumed` → `zaprett start`;
- последний `onActivityPaused` → `zaprett stop`.

Это дало нужное поведение: ушли на главный экран ТВ — обход выключился.

**Проблема (21.11).** Если включено фоновое воспроизведение (звук / PiP / play-behind), видео продолжает идти, а обход уже выключен. Поток рвётся, появляется `Unknown part encountered`, видео тормозит и могут быть вылеты.

**Решение.** Добавлен `PlaybackStateHolder` в common-модуле — общий флаг «видео сейчас играет»:

- `ErrorFixerController.onPlay()` → `setActive(true)`;
- `onPause()` / `onFinish()` → `setActive(false)`;
- `DpiBypassInstaller.onBackground()` при активном воспроизведении **не** останавливает zaprett, а пишет в лог:
  `app background, but playback active — keep nfqws`;
- когда воспроизведение фактически заканчивается, слушатель состояния останавливает обход.

**Проверено на приставке:**

```
играет           → zaprett is working
HOME (фон)       → zaprett is working   (в логе «keep nfqws»)
пауза            → zaprett is stopped
```

### 4.3. Авто-фикс при явной ошибке сети

Если `onEngineError` всё же случился, срабатывает `ErrorFixerController.applyAutoDnsFix()` — лестница из шагов. Защита от циклов: шаг меняется не чаще, чем раз в 15 секунд, счётчик хранится в `autodns_fix`.

| Шаг | Действие |
|---|---|
| 0 | `PLAYER_DATA_SOURCE_OKHTTP` + DNS **Google (8.8.8.8)** → перезапуск приложения |
| 1 | DNS **IPv4** → перезапуск |
| 2 | DNS **System** → перезапуск |
| 3 | **H.264 720p + SW-декодер** (`VIDEO_HD_AVC_30`) → `restartEngine()` |
| 4 | **Смена YouTube-клиента** → сброс счётчика на 0, цикл заново |

Логика простая: сначала пробуем самый «чистый» путь (публичный DNS + HTTP-источник), затем сужаемCircuit до системного DNS, потом уходим на «дешёвый» кодек и софтверный декодер (ему всё равно, что DPI душит аппаратный путь), и наконец меняем клиент — у разных клиентов разные TLS-отпечатки, и один может пройти там, где другой не прошёл.

### 4.4. Watchdog для «тихого» зависания

Отдельный `Handler` с таймаутом **30 секунд** (`STUCK_PLAYBACK_TIMEOUT_MS`). Если прошло 30 секунд, а `getPositionMs()` всё ещё 0 — значит видео висит без ошибки. В этом случае:

```
watchdog: stalled playback, switching client
→ YouTubeServiceManager.switchNextClientNow()
→ reloadVideo()
```

Важно: watchdog сначала **меняет клиент**, а не дёргает `restartEngine()` — при тихом зависе перезапуск движка часто ничего не менял, зато добавлял задержку.

Таймер снимается в `onPlay()` и перезапускается в `onBuffering()` / `onPause()` — см. код `ErrorFixerController`.

### 4.5. Логгер ошибок и дедупликация

`ErrorLog` пишет в `/data/data/com.egor.youtubetv/files/autofix_errors.log`:

- время, videoId, позиция воспроизведения;
- сетевой движок, выбранный DNS, SW-декодер, формат;
- полный стек ошибки (до 4096 символов на запись);
- лимит файла — **5 МиБ**; при переполнении остаются последние 4 МиБ.

**Дедупликация (21.11).** Раньше одна и та же ошибка записывалась десятки раз, и лог быстро превращался в нечитаемое полотно. Теперь перед записью вычисляется **сигнатура**:

```
signal = класс исключения + первые 3 кадра стека
(для служебных сообщений — сам текст с вырезанным временем)
```

Уже виденные сигнатуры хранятся в `files/autofix_seen.txt` (до 500 штук) и **сохраняются между перезапусками**. Проверено: после перезапуска в лог добавилась только 1 новая строка, старые не повторяются.

Запись файла идёт в фоновом потоке `webtube-errorlog` — чтобы дисковая операция не тормозила UI (подробнее в [4.6](#46-быстродействие-интерфейса)).

Внешний перехват: `docs/capture_errors.py` дублирует важные строки из `logcat` в `error_log.txt`.

### 4.6. Быстродействие интерфейса

Это была отдельная боль: «включаю видео и хочу нажать — приходится ждать несколько секунд». Нашлись **три** причины, все устранены.

#### Причина 1: root-команды на главном потоке

При каждом входе/выходе экрана `DpiBypassInstaller` синхронно вызывал `su`:

```
hasRoot() → id -u
status    → zaprett status
start     → zaprett start
stop      → zaprett stop
+ при первом запуске ~15 команд cp/mkdir/chmod
```

Каждый вызов `su` — 100–500 мс, вместе — несколько секунд. Пока `su` выполнялся, главный поток не отрисовывал интерфейс.

**Лечение:** все root-операции перенесены в отдельный поток `webtube-dpi`. Состояние root (`sRootAvailable`) и флаг запуска (`sRunning`) кэшируются, чтобы не дёргать `su` без нужды. Слушатель `PlaybackStateHolder` тоже был переведён с синхронного `stopInternal()` на асинхронный `stop()` — иначе остановка фонового воспроизведения всё равно блокировала бы UI.

#### Причина 2: запись лога на главном потоке

`ErrorLog` открывал и перезаписывал файл прямо в `log()`. Теперь запись идёт в поток `webtube-errorlog`.

#### Причина 3: debug-сборка с флагом `DEBUGGABLE`

`dumpsys package com.egor.youtubetv` показывал:

```
pkgFlags=[ DEBUGGABLE HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP LARGE_HEAP ]
```

В режиме `debuggable` Android отключает часть оптимизаций ART и включает дополнительные проверки фреймворка. Переход на **release** с тем же ключом ([2.3](#23-подпись--почему-не-нужно-заново-логиниться)) убрал флаг:

```
pkgFlags=[ HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP LARGE_HEAP ]
```

#### Результат (замер на приставке)

Холодный старт → появление `BrowseActivity`:

| Сборка | Время |
|---|---:|
| debug (было) | 3572 мс |
| **release (стало)** | **1273 мс** |

Плюс исчезли задержки при переходе в плеер и обратно — потому что больше нет синхронных `su` на главном потоке.

### 4.7. Прочие исправления

**Кнопка OK: панель плеера + пауза одновременно (21.11).**
В upstream поведение OK настраивается (`PlayerData.OK_ONLY_UI`, `OK_UI_AND_PAUSE`,
`OK_ONLY_PAUSE`, `OK_TOGGLE_SPEED`), по умолчанию — `OK_ONLY_UI`. На приставке это
вылилось в неудобство: при нажатии OK панель не появлялась, а видео продолжало идти —
приходилось жать «вниз», чтобы увидеть кнопки.

В нашей сборке в `PlayerUIController.handleConfirmKey()` поведение принудительно
переведено в `OK_UI_AND_PAUSE` — при скрытой панели OK делает **два действия сразу**:

1. `getPlayer().showOverlay(true)` — показывает панель плеера (название, кнопки, шкалу);
2. `getPlayer().setPlayWhenReady(!...)` — ставит видео на паузу или снимает её.

Поведение при уже видимой панели не тронуто — OK активирует сфокусированную кнопку.
Кнопка «вниз» по-прежнему просто показывает панель. Новые установки получают
`OK_UI_AND_PAUSE` в `PlayerData` как значение по умолчанию.

Проверено на приставке через `dumpsys media_session` + скриншот:

```
до OK    → state=PLAYING(3), панель скрыта
после OK → state=PAUSED(2),  панель видна (иконка ▶, кнопки, шкала)
ещё OK   → state=PLAYING(3)
```

**Заголовок «null — Автор» в фоновом мини-плеере.**
При открытии ролика внешним `VIEW`-intent у объекта `Video` не всегда заполнен `title`, и бегущая строка показывала `null - Космос Просто`. В `VideoStateController.onMetadata()` добавлен fallback: если `title` пустой или равен строке `"null"`, берём `metadata.getTitle()`.

**Кнопка «Открыть канал».**
У ролика из плеера `channelId` был `null`, а `ChannelPresenter` пытался загрузить метаданные повторно — на AM9 это висло. Теперь ID берётся из уже загруженных метаданных (`onMetadata` → `video.channelId`), плюс fallback-поиск по автору.

**Радио-иконки в диалоге формата.**
Системный vector `abc_btn_radio_material` рисовался «перевёрнутой C». Заменён на простые shape/radio drawable — теперь обычные кружки.

**AmlogicFix.**
На S905X4 ExoPlayer занижал лимит макс. разрешения декодера → поток не выбирался, чёрный экран. Переключатель поднимает лимит до 1920×1089; в базу настроек входит, на AM9 включён.

**Back-кнопка (честно, не до конца вылечено).**
В upstream при открытии ролика **внешней ссылкой** намеренно включается «player only mode» (`SplashPresenter.enablePlayerOnlyModeIfNeeded`), и BACK возвращает в предыдущую задачу Android (лаунчер/файловый менеджер). Мы добавили возврат в `BrowseActivity` в `PlaybackActivity.finish()` и `ViewManager.startParentView()`, но на внешнем intent автотест результат не подтвердил. Если ролики открываются **из интерфейса приложения** — BACK работает штатно.

**Сохранены upstream-механизмы.**
Playback recovery, SABR backoff, обработка 403/poToken и decoder errors из оригинала не тронуты — мы их не заменяли, а только добавили свои шаги.

### 4.12. ByeByeDPI с встроенным nfqws (27.11)
На основе официального репозитория `romanvht/ByeByeDPI` (ветка master) собрана
версия с тем же пакетом `io.github.romanvht.byedpi`, тем же интерфейсом и
настройками, но **вместо старого движка ByeDPI** используется встроенный
**nfqws из zaprett 7.1.0 со стратегией `general_alt12`** — как в SmartTube.

Что изменено:
- в `assets/dpi/` добавлены бинарники nfqws, списки и стратегия из нашего проекта;
- новый класс `services/NfqwsEngine.kt` раскладывает списки в каталог модуля
  (обход ошибки SELinux `Permission denied`), пишет config/manifest и стартует
  `zaprett`;
- `NativeSession.startNative()`/_stop()_ переведены с `ByeDpiProxy` на `NfqwsEngine`;
- сборка нативной части ByeDPI отключена (движок больше не используется).

APK: `apk/ByeByeDPI-nfqws-general_alt12.apk`. Подпись отладочная — при установке
поверх原来 приложения его нужно сначала удалить (`pm uninstall`).

---

### 4.11. ПОЧЕМУ СТРАТЕГИЯ НЕ РАБОТАЛА И КАК ЭТО ИСПРАВЛЕНО (26.11)
Точная причина найдена в логе самого движка
`/data/adb/modules/zaprett/tmp/nfqws.err`:

```
file_open_test: Permission denied
cannot access hostlist file '/storage/emulated/0/zaprett/files/lists/list-google.txt'
```

Демон nfqws ( SELinux) **не может читать списки хостов из `/storage/emulated/0`**.
Поэтому стратегия `general_alt12` применялась к нулю доменов — обход числился
«working», но реально ничего не десинхронизировал, и YouTube блокировался.
На ПК такой проблемы нет: nfqws читает списки из `user-lists/` без ограничений.

**Исправление встроено в приложение** (`DpiBypassInstaller`):
- при каждом старте списки и payload копируются в `/data/adb/modules/zaprett/lists`
  и `/data/adb/modules/zaprett/bin` (каталог модуля доступен демону), права 755;
- пути в `strategies/general_alt12.txt` автоматически переписываются на module-пути;
- добавляется `--dpi-desync-fwmark=0x40000000` и PC-подобные iptables-правила с
  исключением уже помеченных nfqws-пакетов;
- надёжно определяется синтаксис `su` (Magisk `su -c` / AOSP `su 0 sh -c`) —
  раньше приложение ошибочно решало «no root available».

**Проверено на приставке:** при запуске приложения `zaprett is working`,
ролик `pbgaEcNKPzo` идёт с картинкой, сетевых ошибок 0; после HOME во время
воспроизведения обход остаётся включённым, после паузы и выхода — выключается.

---

### 4.10. Финальная схема запрета (25.11)
Запрет **полностью встроен в приложение** и не зависит от сторонних программ:

- при старте процесса (`MainApplication.onCreate`) сразу вызывается
  `DpiBypassInstaller.initialize()` и `DpiBypassInstaller.start()` — обход поднимается
  **до того, как откроется любое видео**, в том числе внешним `VIEW`-intent;
- движок **nfqws из zaprett 7.1.0** со стратегией `general_alt12` раскладывается
  из `assets/dpi/` в `/data/adb/modules/zaprett/` и `/storage/emulated/0/zaprett/`;
- при уходе приложения в фон обход выключается, но **остаётся включённым при
  фоновом воспроизведении** (`PlaybackStateHolder`);
- запуск стороннего `io.github.romanvht.byedpi` из приложения **удалён** — два
  DPI-движка одновременно конфликтуют и ломают поток;
- лог ошибок пишет только новые incidents (`дата + videoId + класс + стек`).

> ⚠️ Если на приставке включён **ByeDPI VPN** (`tun0`), его нужно отключить:
> `am force-stop io.github.romanvht.byedpi`. Иначе встроенный nfqws и VPN
> перехватывают один и тот же трафик, и видео не идёт.

---

### 4.9. Устойчивость к «не идут некоторые ролики» (22.11)
Причиной отказа является не кодек и не мощность приставки, а **TLS-handshake
с конкретным узлом `*.googlevideo.com`** (таймаут/сброс на `sn-*-узлах CDN`).
Подтверждено: ролик `hw2nRLPsYyE` на той же приставке играет с 0 ошибок, а
проблемные — висят на спиннере с 8–23 ошибками; включение/выключение nfqws
на исход не влияет.

Что добавлено:

1. **Лог только новых ошибок, но с правильной сигнатурой.**
   `ErrorLog.signature()` теперь = `дата + videoId + класс + первые 3 кадра стека`.
   Один и тот же сбой в том же ролике в тот же день пишется **один раз**; тот же
   сбой в другом ролике или в другой день считается новым. Проверено на приставке:
   в `autofix_seen.txt` появилась запись `2026-11-22|vid=WiIMnyGHnZ8|...`.

2. **Новый первый шаг авто-фикса — свежий player response.**
   `YouTubeServiceManager.invalidateFormatCache()` + `reloadVideo()` дают новый
   CDN-узел, не расходуя шаги DNS/кодек/клиент. Лестница стала:
   `свежий URL → Google DNS → IPv4 → System → H.264/SW → смена клиента`.

3. **Watchdog на 12 сек по прогрессу позиции.**
   `isPlaying()` возвращает true и во время BUFFERING, а позиция может быть
   восстановлена из истории — поэтому «не идёт» определяется по тому, сдвинулся
   ли `getPositionMs()` хотя бы на 500 мс. Первый срабатывание — свежий URL,
   второе — смена клиента. Таймер самоперезапускается и перезапускается в
   `onBuffering()`.

4. **PoToken PENDING** — не мгновенная смена клиента, а 2 повтора с свежим
   ответом через 4 секунды.

**Результат проверки:** из четырёх роликов, ранее не игравших, два завелись
(`hw2nRLPsYyE`, `PCYZ7zXQFYA`, последний ранее падал с HTTP 503); два
(`WiIMnyGHnZ8`, `KNI5NL3QeB8`) по-прежнему буферизуются — это конкретные
CDN-узлы/сторона YouTube, авто-фикс не может гарантировать их 100%.

---

### 4.8. Wink и OTT Navigator

Отдельная проблема — не в SmartTube, а в IPTV-плеере **OTT Navigator** (`studio.scillarium.ottnavigator`).

**Симптом:** на некоторых каналах Wink показывает «недоступно на этой территории».

**Причина:** провайдер отдаёт поток с геоблоком, а плеер шлёт «не тот» User-Agent.

**Лечение:** у активного провайдера в «Свойствах» выставить User-Agent:

```
WINK/1.28.2 (AndroidTV/9) HlsWinkPlayer
```

На приставке это выставлено напрямую в `studio.scillarium.ottnavigator_preferences.xml` у провайдера `все` (id `232303082`), после чего приложение перезапущено. Альтернативные значения, которые тоже упоминаются в обсуждениях: `IPTV` (для стоп-каналов в РФ) и `IPTVPLAYER`.

Это решение не требует root и не влияет на SmartTube.

---

## 5. Настройки и бэкапы

| Что | Где |
|---|---|
| Резерв prefs с приставки | `/sdcard/yt_prefs_backup/shared_prefs/` |
| Последний полный бэкап (интерфейс, каналы, аккаунт) | `/storage/emulated/0/Documents/SmartTubeBackup/com.egor.youtubetv_20261119-012330.zip` |
| Вшитые в APK значения по умолчанию | `settings/default_prefs/` |
| Настройки интерфейса и сайдбар с ТВ | `settings/main_ui_data2`, `settings/sidebar_fixiki.txt` |
| Восстановление настроек | `docs/restore_settings.sh` |
| Обновление приложения | `docs/update_app.sh` |

**Где хранится вход в Google:** `files/global_prefs/media_service_account_data` в данных приложения. Он сохраняется при `adb install -r` тем же ключом — повторный вход **не требуется**. Именно поэтому мы так бережём подпись и никогда не делаем `pm clear`.

**Что вшито по умолчанию:** 74+ канала сайдбара (включая «Фиксики»), настройки интерфейса `main_ui_data2` и профиль `егор_щербанов`. Но **только при первом запуске** — при обновлении существующие настройки не перетираются.

> 🔒 `settings/latest_backup.zip` содержит OAuth-токены — **на GitHub не отправляется** (исключён в `updata git.sh`).

---

## 6. Практика: обновление и диагностика

### 6.1 Обновить приложение

```bash
docs/update_app.sh /path/to/SmartTube_stable_32.80_arm64-v8a-release.apk
```

Скрипт сам сделает бэкап, поставит APK и вернёт данные. Проверить результат:

```bash
adb shell "dumpsys package com.egor.youtubetv | grep pkgFlags"   # DEBUGGABLE быть не должно
adb shell "su -c 'export LD_LIBRARY_PATH=/data/adb/modules/zaprett/system/lib/arm64-v8a; \
  /data/adb/modules/zaprett/system/bin/zaprett status'"          # zaprett is working
```

### 6.2 Снять лог ошибок

```bash
adb shell "su -c 'cat /data/data/com.egor.youtubetv/files/autofix_errors.log'" > errors.txt
```

Или внешний перехват: `docs/capture_errors.py` → `error_log.txt`.

### 6.3 Что искать в логе

| Строка | Диагноз |
|---|---|
| `Unable to connect to …googlevideo.com` + `SocketTimeoutException` | сеть/CDN, таймаут чтения |
| `NoRouteToHostException` | маршрут/Wi-Fi/DNS |
| `SabrPoTokenError` | poToken / клиент |
| `SabrReloadPlayerError` | защита потока YouTube, нужна перезагрузка player response |
| `Unknown part encountered` | оборванный поток (часто — обход выключился при фоне) |
| `watchdog: stalled playback` | тихий завис, смена клиента |
| `app background, but playback active — keep nfqws` | обход корректно удержан при фоновом воспроизведении |
| `DpiBypass ... nfqws START/STOP` | статус обхода |
| `no root available — DPI bypass skipped` | нет root, обход не работает |

### 6.4 Проверить обход

```bash
export LD_LIBRARY_PATH=/data/adb/modules/zaprett/system/lib/arm64-v8a
zaprett status
# ожидаем: zaprett is working
```

Если обход «stopped» при активном приложении — проверьте, не нажата ли пауза и не ушло ли приложение в фон без воспроизведения.

---

## 7. Эмулятор для проверок

- AVD **`AM9_x86_14`**: Android **14 (API 34)**, Android TV, x86, 1920×1080, 3 ГБ, KVM.
- Запуск отдельным процессом, чтобы не зависеть от таймаутов:

```bash
setsid nohup /home/egor/android-tv-emu/sdk/emulator/emulator -avd AM9_x86_14 \
  -no-audio -no-snapshot -gpu swiftshader_indirect -memory 3072 &
```

- arm64-образ на этом x86_64-хосте **не запускается** (Emulator 37: «CPU Architecture arm64 is not supported»). Эмулятор годится для проверки логики и UI, но **не** для Amlogic-кодек-багов и не для nfqws (нет root/NFQUEUE) — тестировать это нужно на реальной приставке.

---

## 8. Структура папки проекта

```
Smart YouTube Next/
├── README.md                       ← этот документ
├── source/                         ← полные исходники SmartTube с нашими правками
│   ├── keystore.properties         ← ключ подписи (стандартный debug.keystore)
│   ├── common/                     ← ErrorLog, PlaybackStateHolder, ErrorFixerController,
│   │                                  VideoStateController, ViewManager
│   └── smarttubetv/src/main/assets/dpi/  ← zaprett + стратегия general_alt12
├── apk/                            ← готовые APK
│   ├── SmartTube_stable_32.80_arm64-v8a.apk          (debug)
│   ├── SmartTube_stable_32.80_arm64-v8a-release.apk  (рекомендуемый)
│   ├── SmartTube_stable_32.80_armeabi-v7a.apk
│   ├── SmartTube_stable_32.80_universal.apk
│   ├── SmartTube_stable_32.80_x86.apk
│   └── WebTube_1.0_tv.apk
├── settings/
│   ├── default_prefs/              ← вшитые значения по умолчанию
│   └── latest_backup.zip           ← ⚠️ НЕ отправлять на GitHub (OAuth-токены)
├── scripts/
│   └── patch_lifecycle.py          ← патч жизненного цикла DPI-обхода
├── docs/
│   ├── update_app.sh               ← безопасное обновление с сохранением данных
│   ├── restore_settings.sh         ← восстановление настроек
│   ├── capture_errors.py           ← перехват logcat → error_log.txt
│   ├── patch_all.py                ← сводный патч правок
│   ├── README_APPS.md              ← заметки по приложениям экосистемы
│   ├── zapret_conf.ini
│   ├── zapret_general_alt12.bat    ← исходная стратегия (эталон)
│   └── zapret_general_alt12.md     ← описание стратегии
└── webtube/                        ← исходники WebTube
```

---

## 9. История работ

| Дата | Что сделано |
|---|---|
| 19–20.11 | Изучены лог и документация; найдена первопричина — таймаут `googlevideo.com`, а не кодек |
| 20.11 | Лестница авто-фикса (DNS → H.264/SW → клиент), watchdog на 30 сек, логгер `ErrorLog` |
| 20.11 | Восстановлены 74+ каналов и настройки интерфейса из бэкапа; вход в Google сохранён |
| 20.11 | Исправлены «Открыть канал» и радио-иконки в диалоге формата |
| 20.11 | Встроены nfqws/zaprett и стратегия `general_alt12`; обход привязан к жизненному циклу приложения |
| 21.11 | Обход стал учитывать фоновое воспроизведение (`PlaybackStateHolder`) |
| 21.11 | Исправлен заголовок `null - Автор` в фоновом мини-плеере |
| 21.11 | `ErrorLog` пишет только новые ошибки, дедупликация с сохранением между перезапусками |
| 21.11 | Устранены тормоза UI: root-команды и запись лога вынесены в фоновые потоки |
| 21.11 | Переход на release-сборку с тем же ключом: холодный старт 3572 → 1273 мс |
| 21.11 | Документ переработан и дополнен; всё отправлено на GitHub |
| 21.11 | Кнопка OK теперь одновременно показывает панель плеера и ставит видео на паузу; проверено через `media_session` и скриншот |
| 22.11 | Лог «только новые» с videoId+датой; авто-фикс: свежий player response первым шагом, watchdog 12 сек по прогрессу, PoToken retry |
| 25.11 | Запрет запускается при старте процесса до открытия видео; сторонний ByeDPI удалён из приложения |
| 26.11 | Найдена и устранена главная причина: nfqws не читал списки из /storage из-за SELinux; списки перенесены в каталог модуля, видео идёт |

---

### Итог

Приложение работает штатно: аккаунт и настройки сохраняются при обновлении, обход включается вместе с приложением и не выключается при фоновом воспроизведении, ошибки пишутся компактно и только новые, интерфейс отзывается без задержек. Все правки — точечные и поверх upstream `yuliskov/SmartTube`, чтобы проект можно было обновлять и дальше.
