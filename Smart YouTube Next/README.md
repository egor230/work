# Smart YouTube Next TV — модифицированное приложение YouTube для Android TV

> Подробный документ о том, **что это за программа**, откуда она взята, что в ней
> изменено, какие проблемы встречаются при воспроизведении YouTube на приставке
> Ugoos AM9 PRO и как именно они обходятся.
> Актуально на **20.11.2026**.

---

## 1. Что это такое

**Smart YouTube Next TV** — это модифицированная сборка приложения **SmartTube**
(репозиторий https://github.com/yuliskov/SmartTube) для телевизора/приставки.

- Пакет: `com.egor.youtubetv`
- Версия: **32.80** (база — upstream `master`)
- Устройство: **Ugoos AM9 PRO**, Amlogic S905X4, **Android 14**, arm64-v8a, 4K, root через **Magisk**
- Название в лаунчере: **Smart YouTube Next TV** (переименовано с `SmartTube`)
- Основной экран — стандартный интерфейс SmartTube: левая панель секций и ряды карточек, управление с пульта.

Это **не** веб-обёртка: плеер нативный (ExoPlayer + SABR/DASH), со своим API-клиентом YouTube, своими списками и настройками.

### Дополнительные приложения в экосистеме

| Приложение | Назначение |
|---|---|
| `com.egor.youtubetv` — **Smart YouTube Next TV** | основной рабочий клиент |
| `com.egor.webtube` — WebTube 1.0 TV | запасной клиент: YouTube внутри Android WebView (`m.youtube.com`); useful, когда нативный плеер капризничает |
| `org.smarttube.stable` 32.71 | официальный релиз с GitHub, без наших правок |

---

## 2. Откуда взят код и как собирался

1. Исходник: `https://github.com/yuliskov/SmartTube` (ветка `master`), подмодули:
   - `SharedModules` (коммит `5475d318…`)
   - `MediaServiceCore` (актуальный `master`)
2. Сборка: JDK 17, Android SDK `/home/egor/android-tv-emu/sdk`, Gradle:
   ```bash
   ./gradlew :smarttubetv:assembleStstableDebug
   ```
3. Подпись — тем же **debug-keystore**, что и старая сборка на приставке, поэтому
   обновление через `adb install -r` сохраняет аккаунт и настройки.
4. Исходники находятся в `source/`, готовые APK — в `apk/`, settings — в `settings/`,
   вспомогательные скрипты — в `scripts/`, старые документы — в `docs/`.

⚠️ Правило: **не менять `applicationId` и подпись, не делать `pm clear`** — иначе
потребуется заново входить в Google-аккаунт. Обновлять только через
`scripts/update_app.sh`.

---

## 3. Какие проблемы были на приставке и как они решались

### 3.1 Первая проблема (историческая): чёрный экран на Amlogic
На S905X4 ExoPlayer занижал лимит макс. разрешения декодера → не выбирался поток.
Лечилось переключателем **AmlogicFix** (поднятие лимита до 1920×1089). Сейчас входит
в базу настроек; на AM9 включён.

### 3.2 «Auto-fix» мешал воспроизведению
СтарыйRecovery-лестница из 8 шагов и слепой `restartEngine()` прерывали работающие
видео. В нашей сборке логика переписана (см. 4.2).

### 3.3 Основная проблема: таймаут видео-CDN
Логи приставки (`autofix_errors.log`) показали 23 ошибки 19–20.11:

| Ошибка | Кол-во | Причина |
|---|---|---|
| `HttpDataSourceException: Unable to connect to …googlevideo.com` → `SocketTimeoutException: Read timed out` | 11 | таймаут TLS/read к CDN-узлу |
| тот же класс → `NoRouteToHostException: Host unreachable` | 6 | нет маршрута до CDN |
| `SabrReloadPlayerError` | 3 | сервер просит перезагрузить player response |
| `SabrPoTokenError: PENDING / PENDING_MISSING` | 2 | poToken не готов |

**Вывод:** проблема **не в кодеке** (в логах встречаются av1/avc/vp9 — зависимости нет),
а в доступе к `*.googlevideo.com`. Чаще всего падали `M6TBfUTfuOc` (6), `gMhKHUYPm_g` (5).

### 3.4 «Тихий» завис (спиннер без ошибки)
Некоторые ролики (4K, свежий poToken) висели вообще без `onEngineError` — watchdog
через 30 сек меняет YouTube-клиент.

### 3.5 «Открыть канал» не работало
У ролика из плеера `channelId` был `null`, а `ChannelPresenter` делал повторную
сетевую загрузку метаданных — на AM9 она висла. Теперь ID берётся из уже загруженных
метаданных плеера; есть fallback — поиск по автору.

### 3.6 Графический баг в диалоге формата
Системный vector-индикатор `abc_btn_radio_material` рисовался «перевёрнутой C».
Заменён на простые shape/radio drawable.

---

## 4. Как именно устроены обходы (что делает приложение)

### 4.1 Авто-фикс при явной ошибке сети (`ErrorFixerController.applyAutoDnsFix`)
Шаги с защитой от циклов (15 сек, счётчик в `autodns_fix`):

1. `PLAYER_DATA_SOURCE_OKHTTP` + DNS **Google (8.8.8.8)** → перезапуск
2. DNS **IPv4** → перезапуск
3. DNS **System** → перезапуск
4. **H.264 720p + SW-декодер** → `restartEngine()`
5. **Смена YouTube-клиента** → цикл заново

При тихом зависе (watchdog 30 сек) — **сначала смена клиента**, без перезапуска.

### 4.2 Ловушка ошибок
`ErrorLog` пишет в `<filesDir>/autofix_errors.log` время, videoId, позицию, сетевой
движок, DNS, SW-декодер, формат и стек ошибки. Лимит — **5 МиБ** (при переполнении
остаются последние 4 МиБ). Внешний `capture_errors.py` дублирует важные строки из
`logcat` в `error_log.txt`.

### 4.3.3 Заголовок «null — Автор» в фоновом мини-плеере (21.11)
При открытии ролика внешним `VIEW`-intent у `Video` не всегда заполнен `title`,
поэтому в строке фонового воспроизведения показывалось `null - Космос Просто`.
В `VideoStateController.onMetadata()` добавлен fallback: если `title` пустой или
равен строке `"null"`, он берётся из `metadata.getTitle()`. Сборка установлена.

### 4.3.2 Фоновое воспроизведение (исправлено 21.11)
Раньше при выходе на главный экран ТВ обход выключался, а фоновое
воспроизведение продолжалось — поток обрывался (`Unknown part encountered:
id=…, size=-50…`), видео тормозило и могли быть вылеты.

Теперь добавлен `PlaybackStateHolder` (в common):
- `ErrorFixerController.onPlay()` выставляет `playback active = true`;
- `onPause()`/`onFinish()` — `false`;
- `DpiBypassInstaller.onBackground()` при активном воспроизведении **не**
  останавливает `zaprett`, а пишет в лог `app background, but playback active — keep nfqws`;
- когда воспроизведение фактически заканчивается (или нажата пауза), слушатель
  состояния останавливает обход.

Проверено на приставке: играет → HOME → `zaprett is working` → пауза →
`zaprett is stopped`.

### 4.3.1 Обход включается только вместе с приложением (с 20.11)
`DpiBypassInstaller` зарегистрирован как `ActivityLifecycleCallbacks`:
- при первом `onActivityResumed` (вход в приложение) — `zaprett start`;
- при последнем `onActivityPaused` (выход на главный экран ТВ) — `zaprett stop`.

Проверено на приставке: `zaprett is working` → HOME → `zaprett is stopped` →
снова открыли приложение → `zaprett is working`. В логе `autofix_errors.log`
появляются записи `nfqws START (app foreground)` и `nfqws STOP (app background)`.
Установка файлов/strategies делается один раз при первом запуске и при обновлении
не перетирается.

### 4.3 DPI-обход (nfqws / zaprett) — главное решение сетевых ошибок
В приложение встроен движок **nfqws 1 из zaprett 7.1.0** и ваша сохранённая стратегия
**`general_alt12`** (из `/home/egor/Downloads/zapret-discord-youtube-linux`).

`DpiBypassInstaller` при первом запуске (root/Magisk):
- раскладывает `zaprett`, `libnfqws.so`, `libnfqws2.so` в `/data/adb/modules/zaprett/`;
- списки, payload и `config.json` + манифест стратегии — в `/storage/emulated/0/zaprett/`;
- при **каждом** старте приложения проверяет `zaprett status` и поднимает `zaprett start`.

Параметры стратегии сохранены без переделки:
`fake,multisplit`, `split-seqovl=664`, `split-pos=1`, `fooling=ts`, `repeats=8`,
`hostfakesplit` для Google с `host=www.google.com`, QUIC `fake` ×11,
payload `tls_clienthello_www_sferum_ru.bin` + `stun.bin`.

Проверено на приставке: `zaprett status` → **«zaprett is working»**, NFQUEUE-правила
в `iptables -t mangle`, ролик `5dGHRR1uizI` играет без новых ошибок.

⚠️ Обход системный (iptables/NFQUEUE), требует root. Если root недоступен — приложение
работает как обычно (тихий fallback).

### 4.6 Лог только новых ошибок + поведение BACK (21.11)
- `ErrorLog` теперь дедуплицирует записи по сигнатуре `класс + первые 3 кадра стека`
  (для lifecycle-сообщений — по тексту). Already-seen сигнатуры хранятся в
  `files/autofix_seen.txt` (до 500) и сохраняются между перезапусками. Проверено:
  после перезапуска в лог добавилась только 1 новая строка.
- Заголовок «null - Автор» в фоновом мини-плеере исправлен fallback из metadata.
- При открытии ролика **внешней ссылкой** BACK может вернуть на предыдущую задачу
  Android (файловый менеджер/лаунчер) — это особенность task stack. Добавлен возврат
  в `BrowseActivity` из `PlaybackActivity.finish()` и `ViewManager.startParentView()`,
  но в автотесте на внешнем intent результат не подтвердился — если вы открываете
  ролики из интерфейса приложения, BACK работает штатно.

### 4.5 Wink «недоступно на этой территории» (OTT Navigator)
Плашка Wink появляется, если провайдер отдает поток с геоблоком и плеер шлет
«не тот» User-Agent. Лечение (найдено в FAQ OTT Navigator и тематических обсуждениях):
у активного плейлиста в `Свойствах провайдера` выставить **User-Agent**:
```
WINK/1.28.2 (AndroidTV/9) HlsWinkPlayer
```
На приставке это выставлено напрямую в
`studio.scillarium.ottnavigator_preferences.xml` у провайдера `все` (id 232303082),
после чего приложение перезапущено. Альтернативные значения, которые тоже
упоминаются: `IPTV` (для стоп-каналов в РФ) и `IPTVPLAYER`.

### 4.4 Другие исправления
- Имя приложения и `browse_title` → **Smart YouTube Next TV** (в `values/strings.xml` и `ststable`).
- Боковая панель: бэкапChannels 74+ канала, включая «Фиксики»; вшиты в `assets/default_prefs`.
- Настройки интерфейса (`main_ui_data2`) и профиль `егор_щербанов` тоже вшиты как
  значения по умолчанию, но **только при первом запуске** — при обновлении не перетираются.
- Playback recovery, SABR backoff, 403/poToken, decoder errors — upstream-обработчики сохранены.

### 4.7 Медленный интерфейс / задержка при нажатии (исправлено 21.11)
Причины и лечение:

1. **Root-команды (`su`) на главном потоке.** При каждом входе/выходе экрана
   `DpiBypassInstaller` синхронно вызывал `su` (`hasRoot`, `status`, `start`, `stop`,
   а при первом запуске ещё ~15 команд копирования). Каждый вызов — 100–500 мс,
   вместе — несколько секунд, интерфейс «замирал». Все root-операции перенесены
   в отдельный фоновый поток (`webtube-dpi`), состояние root и флаг `sRunning`
   кэшируются. Слушатель `PlaybackStateHolder` тоже теперь вызывает асинхронный
   `stop()`, а не синхронный `stopInternal()`.
2. **Запись лога ошибок на главном потоке.** `ErrorLog` тоже пишет файл в фоновом
   потоке (`webtube-errorlog`); дедупликация по сигнатуре prevention повторов.
3. **Debug-сборка.** Приложение было с флагом `DEBUGGABLE` — Android отключает
   часть оптимизаций ART. Перешли на **release** с тем же ключом
   (`keystore.properties` → `~/.android/debug.keystore`), подпись не изменилась
   (SHA-256 `81f8d2a1…`), аккаунт и настройки сохранены `update_app.sh`.

Замер на приставке (холодный старт → BrowseActivity):
- debug: **3572 мс**
- release: **1273 мс**

APK: `apk/SmartTube_stable_32.80_arm64-v8a-release.apk`.
Сборка: `./gradlew :smarttubetv:assembleStstableRelease` (нужен доступ к сети
для загрузки lint-jar; `--offline` не срабатывает для release).

---

## 5. Настройки и бэкапы

- `/sdcard/yt_prefs_backup/shared_prefs/` — резерв prefs с приставки
- `/storage/emulated/0/Documents/SmartTubeBackup/com.egor.youtubetv_20261119-012330.zip`
  — последний полный бэкап (интерфейс, каналы, аккаунт)
- `settings/default_prefs/` — вшитые в APK значения по умолчанию
- `settings/main_ui_data2`, `settings/sidebar_fixiki.txt` — с телевизора
- Восстановление: `scripts/restore_settings.sh`, обновление: `scripts/update_app.sh`

**Важно:** вход в Google хранится в `files/global_prefs/media_service_account_data`
в данных приложения. Он сохраняется при `adb install -r` с тем же ключом — повторный
вход не требуется.

---

## 6. Как диагностировать новую проблему

1. Открыть ролик, который не идёт.
2. Снять лог:
   ```bash
   adb shell "su -c 'cat /data/data/com.egor.youtubetv/files/autofix_errors.log'" > errors.txt
   ```
3. Или внешний перехват: `scripts/capture_errors.py` → `error_log.txt` (лимит 5 МиБ).
4. Искать:
   - `Unable to connect to …googlevideo.com` + `SocketTimeoutException` — сеть/CDN;
   - `NoRouteToHostException` — маршрут/Wi-Fi;
   - `SabrPoTokenError` — poToken/клиент;
   - `SabrReloadPlayerError` — защита потока YouTube;
   - `DpiBypass` — статус обхода.
5. Проверить обход: `zaprett status` (должно быть «zaprett is working»).

---

## 7. Эмулятор для проверок

- AVD **`AM9_x86_14`**: Android **14 (API 34), Android TV, x86, 1920×1080, 3 ГБ, KVM**.
- Запуск (отдельным процессом, чтобы не зависеть от таймаутов):
  ```bash
  setsid nohup /home/egor/android-tv-emu/sdk/emulator/emulator -avd AM9_x86_14 \
    -no-audio -no-snapshot -gpu swiftshader_indirect -memory 3072 &
  ```
- arm64-образ на этом x86_64 хосте **не запускается** (Emulator 37: «CPU Architecture arm64 is not supported»),
  поэтому эмулятор подходит для логики/UI, но не для Amlogic-кодек-багов.

---

## 8. Структура папки

```
Smart YouTube Next/
├── README.md                 ← этот документ
├── source/                   ← полные исходники SmartTube с нашими правками
├── apk/                      ← собранные APK (arm64, x86, WebTube)
├── settings/                 ← бэкапы, вшитые defaults, main_ui_data2, sidebar
├── scripts/                  ← update_app.sh, restore_settings.sh, capture_errors.py,
│                               patch_all.py, start-zapret.sh, general_alt12.bat
├── docs/                     ← README_APPS.md, zapret_general_alt12.md и копии конфигов
└── webtube/                  ← исходники WebTube
```

---

## 9. Краткая история работ

- Изучены MD-документы и логи; найдена первопричина (`googlevideo.com` timeout, не кодек).
- Собрана версия с авто-DNS/H.264/Client, watchdog и логгером.
- Восстановлены 74+ канала и настройки интерфейса из бэкапа, вход в аккаунт сохранён.
- Исправлена кнопка «Открыть канал» и radio-иконки.
- Встроен nfqws/zaprett с вашей рабочей стратегией `general_alt12`.
- Всё установлено на приставку и проверено на роликах `5dGHRR1uizI` и `hw2nRLPsYyE`.
