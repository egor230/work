# android-tv-emu — модифицированное YouTube-приложение для Ugoos AM9 PRO

> **Единый актуальный документ.** Обновлён **19.11.2026**.
> Папка: `/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/android-tv-emu/`
> Приставка: **Ugoos AM9 PRO**, Amlogic S905X4, Android 14, arm64-v8a, ADB `192.168.0.7:5555`.

---

## 1. Что в итоге получилось

| | Приложение | Статус |
|---|---|---|
| **Основное** | **Smart YouTube Next TV** (`com.egor.youtubetv`) — сборка **SmartTube 32.80** с патчем авто-смены DNS и восстановленными 74 каналами | ✅ установлено на приставку, ролик воспроизводится |
| Дополнительное | `org.smarttube.stable` — официальный релиз **SmartTube 32.71** с GitHub | ✅ установлен (скачан за 5 сек), настройки перенесены; **патча нет** |
| Дополнительное | `WebTube_1.0_tv.apk` (в этой папке) — YouTube в Android WebView | ✅ установлен на приставку, работает; **не является основным** |

Старые сборки SmartTube (`_old/`, `SmartTube/`, `SmartTube_gh/`, `am9_backup/`, `.idsig`, probing-скрипты) **удалены** как неудачные эксперименты.

---

## 2. В чём была проблема

**Симптом:** на приставке видео не запускалось — чёрный экран со спиннером, хотя интерфейс и рекомендации отображались.

**Диагноз по `logcat` приставки:**
```
D/OkHttp: <-- 200 OK https://www.youtube.com/youtubei/v1/...     ← API работает
D/OkHttp: <-- HTTP FAILED: java.net.SocketTimeoutException: Read timed out
E/DefaultSabrChunkSource: Chunk load failed: Unable to connect to
          https://rr3---sn-aj4g55-ct.googlevideo.com/videoplayback?...
```

То есть **не кодек и не несовместимость S905X4**: YouTube-API отвечает, а поток с хоста `*.googlevideo.com` не грузится (таймаут). Другой хост (`rr2---sn-gvnuxaxjvh-ovwl.googlevideo.com`, локальный Google-кеш) с того же бокса работает — значит проблема в маршрутизации/DNS до конкретного CDN-узла.

Дополнительно: в старой сборке `com.egor.youtubetv` авто-исправления сети были отключены, поэтому приложение просто висело. Проверка смены системного Private DNS на `dns.google` не изменила резолвинг — настройка возвращена в `opportunistic`.

---

## 3. Откуда взят исходник

**Репозиторий:** https://github.com/yuliskov/SmartTube (чистый `master`, версия **32.80**).
Подмодули: `MediaServiceCore`, `SharedModules` (`git submodule update --init --depth 1`).

Локальные пути:
- исходники с правками: `/tmp/opencode/SmartTubeDNS/`  ⚠️ временная папка — при перезагрузке/очистке `/tmp` может исчезнуть;
- готовый APK: `/tmp/opencode/SmartTubeDNS/smarttubetv/build/outputs/apk/ststable/debug/SmartTube_stable_32.80_arm64-v8a.apk`.

Официальный APK скачан отсюда (релиз `32.71s`):
`https://github.com/yuliskov/SmartTube/releases/download/32.71s/SmartTube_stable_32.71_arm64-v8a.apk`

---

## 4. Что именно модифицировано

Изменения сделаны **только в логике восстановления после сетевой ошибки**, внешний вид/интерфейс не трогался.

### 4.1 `common/.../playback/controllers/ErrorFixerController.java`

При ошибке `Unable to connect to…` (ровно наш `SocketTimeoutException`) вместо простого переключения движка запускается `applyAutoDnsFix()`:

1. принудительно ставится `PLAYER_DATA_SOURCE_OKHTTP` — только OkHttp учитывает встроенную настройку DNS приложения;
2. цикл DNS: **Google (8.8.8.8) → IPv4 → системный** (`preferred_dns_type`);
3. если все три варианта исчерпаны — `switchNextClientNow()` (другие URL потоков) и цикл начинается заново;
4. защита от зацикливания: повтор не чаще раз в **15 сек**; счётчик сбрасывается при успешном `onPlay()` и на новом видео;
5. состояние хранится в `SharedPreferences autodns_fix` (`dns_step`, `dns_last_ms`).

В логах это выглядит как `Auto-fix: DNS -> Google (8.8.8.8). Restarting app…` (перезапуск нужен, чтобы OkHttp пересоздал внутренние объекты с новым резолвером — так же делает upstream в аналогичном случае).

### 4.2 `smarttubetv/build.gradle`
- у flavour `ststable` `applicationId` заменён с `org.smarttube.stable` на **`com.egor.youtubetv`** — чтобы поставить поверх существующего приложения;
- в `smarttubetv/google-services.json` добавлен client для `com.egor.youtubetv` (копия `org.smarttube.stable`), иначе Firebase-плагин падал: `No matching client found for package name`.

### 4.3 Подпись
APK подписан тем же `~/.android/debug.keystore` (Android Debug, SHA-1 `60:F5:A8:...`), что и старая сборка — поэтому `adb install -r` сохранил данные/настройки. Официальный релиз подписан ключом SmartTube, поэтому встаёт только под своим пакетом `org.smarttube.stable`.

### 4.4 Название приложения
`smarttubetv/src/main/res/values/strings.xml` **и** `src/ststable/res/values/strings.xml`: `app_name` и `browse_title` заменены с `SmartTube` на **`Smart YouTube Next TV`**. (Правка только `main/strings.xml` не срабатывает — flavour `ststable` переопределяет значение.)

### 4.9 Кнопка «Перейти на канал» не открывала канал
**Причина:** у `Video`, открытого из плеера, `channelId` равен `null`. И кнопка в плеере (`PlayerUIController.openChannel()`), и пункт контекстного меню (`VideoMenuPresenter` → `MediaServiceManager.chooseChannelPresenter()`) ultimately вызывали `ChannelPresenter.openChannel(Video)` → `extractChannelId()` → повторную загрузку метаданных через сеть. На AM9 этот запрос висел/падал, колбэк не приходил — не открывалось ничего.

**Исправление (2 файла):**
- `VideoStateController.onMetadata()` — теперь сохраняет `metadata.getChannelId()` в `getVideo().channelId` сразу при загрузке метаданных плеера. Поэтому `extractChannelId()` идёт по синхронной ветке `item.channelId != null` и открывает канал мгновенно.
- `ChannelPresenter.extractChannelId()` — если метаданные всё-таки не вернули ID (ошибка сети/клиента), последним средством открывается поиск по автору (`SearchPresenter.onSearch(author)`), чтобы кнопка не была «мёртвой».

### 4.10 Ловушка ошибок (диагностика «не запускается видео»)
Добавлен `common/.../misc/ErrorLog.java`: при каждой ошибке плеера
(`onEngineError`, `loadFormatInfo`, срабатывание watchdog, шаги авто-фикса)
в файл `<filesDir>/autofix_errors.log` пишется короткая запись:
время, videoId, позиция, сетевой движок, DNS, SW-декодер, текущий формат и
текст/стек ошибки (стек обрезается до 4 КБ). Размер файла **жёстко ограничен
5 МиБ** — при превышении сохраняются последние 4 МиБ.

Забрать файл:
```bash
adb shell "su -c 'cat /data/data/com.egor.youtubetv/files/autofix_errors.log'" > error_log_from_box.txt
```

Дополнительно (без установки APK) работает внешний перехват логов
`capture_errors.py` в папке проекта: он читает `adb logcat`, отбирает строки с
ошибками и пишет их в `android-tv-emu/error_log.txt`, тоже с лимитом 5 МиБ.
Процесс запущен через `setsid nohup` и сам подключится, когда приставка снова
появится в сети.

### 4.11 Эмулятор, максимально близкий к приставке
На этом ПК (x86_64) **нельзя** запустить arm64-образ: Android Emulator 37
даёт `Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator
on x86_64 host`. Поэтому поднят наиболее близкий вариант:

- `AVD AM9_x86_14`: **Android 14 (API 34), Android TV, x86, 1920×1080, 3 ГБ RAM**;
- включён KVM (`/dev/kvm` есть), загрузка ~1 мин;
- в эмуляторе работает сеть и YouTube (в отличие от старого API 31 образа);
- ставится **x86-split APK**: `SmartTube_stable_32.80_x86.apk`
  (`adb -s emulator-5554 install -r …`).

```bash
# запускать отдельным процессом, иначе эмулятор умирает вместе с командой:
setsid nohup /home/egor/android-tv-emu/sdk/emulator/emulator -avd AM9_x86_14 \
  -no-audio -no-snapshot -gpu swiftshader_indirect -memory 3072 \
  >/tmp/opencode/emulator_am9.log 2>&1 < /dev/null &
adb -s emulator-5554 shell am start -n \
  com.egor.youtubetv/com.liskovsoft.smartyoutubetv2.tv.ui.main.SplashActivity
```

Ограничение: эмулятор не воспроизводит Amlogic-специфичные кодек-баги — для
них нужна реальная приставка. Но логику авто-фиксов и логгер можно проверить
здесь.

### 4.12 Настройки пользователя «по умолчанию» (вшиты в APK)
С пользовательского FTP-бэкапа
`/run/user/1000/gvfs/ftp:host=127.0.0.1,port=2121,user=pc/device/Documents/SmartTubeBackup`
взяты подготовленные настройки интерфейса и сохранены в `assets/default_prefs/`:
- `shared_prefs/` — `GlobalPreferences.xml`, `com.egor.youtubetv_preferences.xml`
  (профиль `егор_щербанов`), `yt_service_prefs.xml`, appupdatechecker;
- `app_prefs/main_ui_data2` — настройки интерфейса (624 байта);
- `app_prefs/егор_щербанов_sidebar_data` — 74+ канала, включая «Фиксики» (32030 байт).

При **первом** запуске `MainApplication.applyDefaultSettings()` копирует их в
данные приложения и ставит маркер `files/default_settings_applied`. Поэтому при
обновлениях через `update_app.sh` аккаунт и текущие настройки не перетираются.

### 4.14 Встроенный DPI-обход Autostart (реализовано 20.11)
В приложение встроен `DpiBypassInstaller` + движок **nfqws из zaprett 7.1.0**:
- assets `dpi/`: `zaprett-aarch64`, `libnfqws.so`, `libnfqws2.so`, payload `stun.bin`,
  `tls_clienthello_www_sferum_ru.bin`, `quic_initial_www_google_com.bin`, списки и `strategy.txt`;
- при первом запуске с root (`su`) файлы раскладываются в
  `/data/adb/modules/zaprett/` и `/storage/emulated/0/zaprett/`, пишутся `config.json`
  и манифест стратегии `general_alt12.json`;
- при **каждом** запуске приложения проверяется `zaprett status` и, если обход не
  активен, выполняется `zaprett start`. Результат пишется в `autofix_errors.log`.

Исходники перенесены в постоянную папку: `android-tv-emu/SmartTubeDNS/`
(больше не в `/tmp`, который очищается системой). Patch-скрипт для повторного
применения всех правок: `android-tv-emu/patch_all.py`.

### 4.13 Стратегия обхода DPI (zapret), рабочая
С пользовательской стратегии `general_alt12.bat` (conf.ini) снята и сохранена
копия: `zapret_general_alt12.bat`, `zapret_conf.ini`, подробности —
`zapret_general_alt12.md`. Запускается на ПК скриптом
`/mnt/807EB5FA7EB5E954/python_linux/start-zapret.sh` (сейчас `nfqws` уже запущен).
Ключ: `fake,multisplit` + `seqovl=664`, `split-pos=1`, `fooling=ts`,
`repeats=8`, fake-TLS `tls_clienthello_www_sferum_ru.bin` / `stun.bin`,
QUIC `fake` ×11, для Google — `hostfakesplit` с `host=www.google.com`.

⚠️ nfqws на ПК не обходит DPI для приставки — нужен роутер или Android-аналог
на AM9 (`byedpi` / `zaprett` уже установлены).

### 4.7 Обновление без повторного входа в Google
Причина «надо снова входить» — не приложение, а способ обновления: вход живёт в
`/data/data/com.egor.youtubetv/` (`files/global_prefs/media_service_account_data`,
`oauth2_account_data`, profile `егор_щербанов`). Если при обновлении делать
`pm clear` или менять подпись/пакет — данные удаляются и вход сбрасывается.

**ПРАВИЛО ДЛЯ ВСЕХ БУДУЩИХ ОБНОВЛЕНИЙ:** всегда тот же package
`com.egor.youtubetv`, тот же debug-keystore, **никогда `pm clear`** — тогда
повторный вход в Google не требуется.

Для этого в папке проекта лежит скрипт **`update_app.sh`**. Он:
1. архивирует данные приложения (аккаунт, профиль, настройки, 74 канала) с приставки;
2. ставит новый APK через `adb install -r`;
3. распаковывает данные обратно и восстанавливает владельца.

```bash
cd "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/android-tv-emu"
./update_app.sh /path/to/SmartTube_stable_32.80_arm64-v8a.apk
```

При обновлении 19.11 вход действительно не сбросился: `media_service_account_data`
на месте, `last_profile_name=егор_щербанов`, приложение открывается в профиле.

### 4.8 «Висит без ошибки» — смена клиента вместо цикла DNS
Если ролик висит со спиннером, но `onEngineError` не приходит (чаще всего
зависает генерация poToken в конкретном YouTube-клиенте), watchdog через
30 сек **сначала переключает YouTube-клиент** и делает `reloadVideo()` — без
перезапуска приложения и без бесконечного цикла DNS. DNS → H.264 → клиент
остаётся только для явных ошибок `Unable to connect to…`.

### 4.6 Графический баг «незаконченные кружочки» в диалоге формата
В `SharedModules/sharedutils` диалоги использовали системные vector-индикаторы
`?android:attr/listChoiceIndicatorSingle` / `...Multiple` (`abc_btn_radio_material`).
На прошивке AM9 они рисовались обрезанными («перевёрнутая C»). Заменены на
простые shape-диаграммы:
- `drawable/smart_radio_button.xml` (selector) + `smart_radio_checked/unchecked.xml`;
- `drawable/smart_check_button.xml` (selector) + `smart_check_checked/unchecked.xml`;
- в `res/layout/dialog_check_item_single.xml` и `dialog_check_item_multi.xml`
  атрибут `android:checkMark` теперь указывает на наши drawable.

### 4.5 Боковая панель — 74 канала
Бэкап `am9_backup/` был удалён как «неудачный эксперимент», но данные сохранились в старом APK: константа `DefaultSidebarData.DATA` в `classes2.dex` (извлечена через `dexdump`, 74 записи, ~30 КБ).

- добавлен `common/.../presenters/service/DefaultSidebarData.java` с этой константой;
- в `SidebarService.restoreState()` если `mPrefs.getSidebarData()` пуст — подставляется `DefaultSidebarData.DATA` и сразу `persistState()`;
- поверх этого на приставке файл `/data/data/com.egor.youtubetv/files/app_prefs/егор_щербанов_sidebar_data` заменён на извлечённые 74 записи (73 разделителя `%AR%`, первый канал `Лена и Ваня LIFE`).

⚠️ Если перед запуском уже существует маленький файл `…_sidebar_data`, дефолт не применится — поэтому файл заменяют вручную (команды ниже).

---

## 5. Как собирали

```bash
cd /tmp/opencode/SmartTubeDNS
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/home/egor/android-tv-emu/sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
./gradlew :smarttubetv:assembleStstableDebug --no-daemon --console=plain
```
Первый запуск: ~1 мин (упал на Firebase); после правки `google-services.json`: **43 сек**. Время ушло не на сборку, а на медленное клонирование репозитория с подмодулями (~25–30 мин). Готовый APK из GitHub скачивается за ~5 сек, но в нём нет патча.

---

## 6. Установка на приставку

```bash
adb connect 192.168.0.7:5555

# основное приложение (с патчем):
adb install -r /tmp/opencode/SmartTubeDNS/smarttubetv/build/outputs/apk/ststable/debug/SmartTube_stable_32.80_arm64-v8a.apk

# открыть нужный ролик:
adb shell am start -a android.intent.action.VIEW \
  -d 'https://www.youtube.com/watch?v=cMumHa4p2O4' -p com.egor.youtubetv

# официальный релиз (без патча):
adb install /tmp/opencode/SmartTube_stable_32.71_arm64-v8a.apk
```

Бэкап настроек перед переустановкой делался через root (Magisk):
`/sdcard/yt_prefs_backup/shared_prefs/` на приставке. При переносе между пакетами файл `com.egor.youtubetv_preferences.xml` копируется в `org.smarttube.stable_preferences.xml`, права — `chown` на uid приложения.

⚠️ Перенос **всех** старых prefs обратно вызвал повторное зависание (устаревшие кэш-файлы `MediaServiceCache`, `yt_service_prefs`, `WebViewChromiumPrefs`, `yt_cache_service2*`). Оставлять следует только `com.egor.youtubetv_preferences.xml` (профиль), `GlobalPreferences.xml` (DNS) и `autodns_fix.xml`.

---

## 7. Проверка результата

Ролик `https://www.youtube.com/watch?v=cMumHa4p2O4` («Как исправить проблему, когда приложение YouTube не открывается на Smart TV — решение», Waylohr, 1:04):

```
D/SabrStream: Found known part: id=21, size=32769, position=...
D/SabrStream: The UMP stream is ended.
D/TrackingService: Updating watch time short... Video Id: cMumHa4p2O4, length: 64.0, position: 64.0
```

Видео **проигралось до конца**; `Chunk load failed` / `SocketTimeout` — 0; авто-фикс не срабатывал (не был нужен). Если таймаут повторится — он сработает сам и покажет сообщение на экране.

**Последний проблемный ролик** `5dGHRR1uizI` («18.11 Мост которого больше нет…», Олег Жданов) — ✅ пользователь подтвердил просмотр после обновления. До правки он висел со спиннером и авто-фикс циклил DNS (`Auto-fix: DNS -> Google (8.8.8.8). Restarting app…`); после правки watchdog сначала меняет YouTube-клиент, и ролик воспроизводится.

**Вход в профиль:** ✅ выполнен повторно. Через `SignInActivity` (код **NTG BTM KYQX**, ссылка **https://yt.be/activate**, только Firefox/Chrome; код был скопирован в буфер обмена ПК) в аккаунт вошли; в диалоге «Выбрать аккаунт» выбран профиль **егор щербанов (eglive892001@gmail.com)**. Диалог подтверждён, приложение вернулось в `BrowseActivity`.

Версии на приставке:
```
com.egor.youtubetv   32.80   (наш патч, основной)
org.smarttube.stable 32.71   (официальный релиз с GitHub)
com.egor.webtube     1.0     (WebTube, обновлён с TV-режимом)
```

---

## 8. WebTube (дополнительное приложение)

`WebTube_1.0_tv.apk` — это YouTube в **Android WebView** (`m.youtube.com`): тёмная тема, TV-инъекция CSS/JS для навигации D-pad, скорость, OSD. Исходники — `WebTube/` в этой папке (AGP 7.4.2, JDK 17).

Зачем оно: проверка показала, что через WebView тот же ролик на этой же приставке играет (1080p60), то есть сеть/кодек в порядке и проблема именно в сетевом движке нативного плеера. WebTube — рабочий запасной вариант, но **основным считается SmartTube с патчем**.

---

## 9. Полезные команды

```bash
# логи приставки в момент проигрывания
adb logcat -v time | grep -E "Chunk load failed|Unable to connect|Auto-fix|SabrStream|Updating watch time"

# DNS/HOST на приставке
adb shell ping -c 1 -W 2 rr3---sn-aj4g55-ct.googlevideo.com
adb shell settings get global private_dns_mode        # opportunistic = по умолчанию

# версия/пакеты
adb shell dumpsys package com.egor.youtubetv | grep versionName
adb shell pm list packages | grep -E 'smarttube|youtubetv|webtube'

# обновление без потери аккаунта (скрипт лежит в папке проекта):
./update_app.sh /tmp/opencode/SmartTubeDNS/smarttubetv/build/outputs/apk/ststable/debug/SmartTube_stable_32.80_arm64-v8a.apk

# принудительная установка 74 каналов боковой панели
adb shell am force-stop com.egor.youtubetv
adb push /tmp/opencode/sidebar_data.txt /sdcard/sidebar_data.txt
adb shell "su -c 'cp /sdcard/sidebar_data.txt /data/data/com.egor.youtubetv/files/app_prefs/егор_щербанов_sidebar_data && chown 10148:10148 /data/data/com.egor.youtubetv/files/app_prefs/егор_щербанов_sidebar_data'"
```

**Откат:** официальный APK лежит в `/tmp/opencode/SmartTube_stable_32.71_arm64-v8a.apk`; локальный бэкап prefs — `/sdcard/yt_prefs_backup/` на приставке.

---

## 10. Полная логика: что делает приложение, когда YouTube не показывает ролик

Вся логика живёт в одном классе:
`common/src/main/java/com/liskovsoft/smartyoutubetv2/common/app/models/playback/controllers/ErrorFixerController.java`.
Ниже — описание для будущих обновлений, чтобы не «изобретать велосипед» и не ломать уже работающие ветки.

### 10.1 Два разных типа «не идёт»

| Симптом | Что видно в логах | Кто обрабатывает | Действие |
|---|---|---|---|
| **A. Явная ошибка плеера** | `DefaultSabrChunkSource: Chunk load failed`, `Unable to connect to …`, `SocketTimeoutException` | `onEngineError()` → `applyEngineErrorAction()` | см. 10.2–10.4 |
| **B. Тихий завис (спиннер)** | ошибок нет, `youtubei/v1/player` может не приходить; генерация poToken в WebView | watchdog `mStuckWatchdog` (30 сек) | см. 10.5 |

Разделение важно: раньше всё лечили DNS-циклом, из-за чего на «тихом» зависе получался бесконечный `Auto-fix: DNS -> Google … Restarting app…`. Теперь при тихом зависе **сначала меняется клиент**.

### 10.2 Ветка A — явная сетевая ошибка `Unable to connect to…`

Вызывается `applyAutoDnsFix()`, только если **не** включён `isNetworkErrorFixingDisabled()`.

Пошагово (счётчик `dns_step` в `SharedPreferences autodns_fix` на приставке):

| Шаг | Действие | Зачем |
|---|---|---|
| 0 | `PLAYER_DATA_SOURCE_OKHTTP` + `preferred_dns_type = GOOGLE (8.8.8.8)`; `dns_step=1`; `Utils.restartTheApp()` | только OkHttp учитывает встроенный DNS; после смены нужно пересоздать его внутренние объекты |
| 1 | `preferred_dns_type = IPV4`; перезапуск | если Google DNS не помог |
| 2 | `preferred_dns_type = SYSTEM`; перезапуск | системный резолвер — последний вариант DNS |
| 3 | `setTempVideoFormat(VIDEO_HD_AVC_30)` (720p **H.264**) + `setSWDecoderForced(true)`; `restartEngine()` | exclude AV1/VP9-декодер — самая частая причина чёрного экрана на Amlogic |
| 4 | `switchNextClientNow()` + `restartEngine()`, `dns_step=0` | другие URL потоков (другой CDN-узел, другой poToken) |

Защита от зацикливания: повтор не чаще **15 сек** (`KEY_DNS_LAST_MS`); счётчик и время обнуляются в `onPlay()` (успешное воспроизведение) и `onNewVideo()`.

### 10.3 Ветка A — другие ошибки движка (upstream-обработчики, сохранены)

| Ошибка / условие | Решение |
|---|---|
| `SabrReloadPlayerError` | один раз `reloadPlayerResponse(videoId, token)` + `reloadVideo()`; при повторе — обычная обработка |
| `SabrBackoffError` | `reloadVideo()` (не спамить запросами, сервер просит backoff) |
| `OutOfMemoryError` | OkHttp → более лёгкий источник; буфер HIGH/HIGHEST → MEDIUM; иначе снизить качество |
| `Exception in CronetUrlRequest` (не live) | переключиться на `PLAYER_DATA_SOURCE_DEFAULT` |
| `Response code: 403` / `404` / `421`, неверный nParam, `PoTokenException`, `BadWebViewException` | `switchNextClientNow()` (или `switchNextClient()`), `reloadVideo()` |
| `429` / `500` + включены субтитры | выключить субтитры |
| `429` + `highBitrateFormats` | выключить расширенные форматы |
| ошибка видео-рендерера | временно `VIDEO_FHD_AVC_30`; если SW-декодер уже включён — выключить, иначе рестарт движка |
| ошибка аудио-рендерера | `AUDIO_HQ_MP4A`, перезагрузка |
| `Unexpected token / Syntax error / invalid argument` | смена клиента + `reloadVideo()` |
| `is not defined` | `invalidateCache()` + `reloadVideo()` |
| прочее (похоже на «нет интернета») | `reloadVideo()` |

### 10.4 Длинное буферирование (`BufferingDetector` / `onLongBuffering`)

- если поток закончился → `onPlayEnd()`;
- офлайн-видео + включённые субтитры → выключить субтитры + `reloadVideo()`;
- офлайн-видео, позиция 0, ещё не применялся DNS-фикс → OkHttp + Google DNS + перезапуск (тот же механизм, что шаг 0);
- иначе → `switchNextClientNow()` + `reloadVideo()` («fixing stalled client»);
- в остальных случаях просто `reloadVideo()` (SABR может «висеть» из-за большого `backoffTime`).

### 10.5 Ветка B — тихий завис (watchdog)

- `onNewVideo()` запускает `Handler` с задержкой **30 сек**;
- `onPlay()` (реальное начало воспроизведения), `onFinish()` и новая ошибка снимают таймер;
- если за 30 сек `getPlayer().getPositionMs() <= 0` → `Auto-fix: stalled client, switching…`:
  `switchNextClientNow()` + `reloadVideo()` — **без** перезапуска приложения и без DNS-цикла;
- типичные причины: 4K/AV1-ролики и свежий poToken (`GTA 6 — Mount kalaga`, `ilE8AUCujCI`; «18.11 Мост которого больше нет…», `5dGHRR1uizI`).

⚠️ **Известное ограничение:** watchdog стартует только из `onNewVideo()`. Если ролик открыт через внешний `VIEW`-intent, этот колбэк может не прийти — тогда watchdog не сработает. При тестировании открывать ролик **из интерфейса приложения** (История/рекомендации), а не только через `am start -d …`.

### 10.6 Как это наблюдать / проверять

```bash
# сообщения на экране:
#  "Auto-fix: DNS -> Google (8.8.8.8). Restarting app…"
#  "Auto-fix: forcing H.264 codec (SW decoder)…"
#  "Auto-fix: codec/DNS exhausted, switching YouTube client…"
#  "Auto-fix: stalled client, switching…"
adb logcat -v time | grep -E "ErrorFixerController|Auto DNS|Auto-fix|Chunk load failed|Unable to connect|SabrStream|Updating watch time"
adb shell su -c "cat /data/data/com.egor.youtubetv/shared_prefs/autodns_fix.xml"
```

### 10.7 Чего НЕ делать при обновлении

- не менять `applicationId` (`com.egor.youtubetv`) и подпись (debug-keystore) — иначе сбросится вход;
- не делать `pm clear`;
- не удалять `DefaultSidebarData` и правки `SidebarService` — иначе исчезнут 74 канала;
- не убирать `smart_radio_button.xml` / `smart_check_button.xml` — вернётся баг «перевёрнутая C» в диалоге формата;
- не ставить системный DNS через `settings put global private_dns_*` как «лечение» — на этой приставке резолвинг от этого не меняется (проверено 18.11);
- обновлять только через `./update_app.sh` (см. 4.7).
