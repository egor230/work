# ByeByeDPI с встроенным nfqws (`general_alt12`)

Документ о кастомной сборке приложения **ByeByeDPI** для Ugoos AM9 PRO:
внешний вид — **1 в 1 как в исходном APK пользователя**, внутри — актуальный
механизм обхода блокировок **nfqws из zaprett 7.1.0** со стратегией `general_alt12`.

---

## 1. Что это за приложение

База: официальный репозиторий **[romanvht/ByeByeDPI](https://github.com/romanvht/ByeByeDPI)**,
**тег `v.1.7.7`** (`versionName 1.7.7`, `versionCode 1770`) — точно та версия,
которая была в исходном APK `ByeByeDP-general_alt12.apk`.

| Параметр | Значение |
|---|---|
| Пакет | `io.github.romanvht.byedpi` |
| Версия | 1.7.7 (1770) |
| Интерфейс | **только одна кнопка питания**: панели «Редактор/Настройки/Подбор/Списки» скрыты (и в portrait, и в landscape) |
| Движок | встроенный nfqws/zaprett 7.1.0 |
| Стратегия | `general_alt12` (сохранена без переделки) |
| Устройство | Ugoos AM9 PRO, Android 14, arm64, root (Magisk) |

Отличие от оригинала — **только внутренняя библиотека**. Всё остальное
(внешний вид, меню, настройки, логика приложения) оставлено как было.

---

## 2. Зачем заменялся движок

Старый ByeDPI (VPN-прокси на базе `libbyedpi.so`) использует устаревшие методы
обхода и на текущей сети приставки не справляется: ролики падали с
`Unable to connect … googlevideo.com` / `SocketTimeoutException` при TLS-handshake.

Вместо него внутри приложения теперь работает тот же механизм, который
проверен на этой же приставке в Smart YouTube Next:

- **nfqws 1 из zaprett 7.1.0** (arm64-бинарник `zaprett-aarch64`, `libnfqws.so`);
- стратегия **`general_alt12`**: `fake,multisplit`, `split-seqovl=664`,
  `split-pos=1`, `fooling=ts`, `repeats=8`, `hostfakesplit` для Google,
  QUIC `fake` ×11, payload `tls_clienthello_www_sferum_ru.bin` + `stun.bin`.

В приложении **ByeDPI-библиотека больше не загружается и не используется** —
сборка её нативной части отключена, вызовы `System.loadLibrary` безопасны.

---

## 3. Что именно изменено в исходниках

| Файл | Изменение |
|---|---|
| `app/src/main/assets/dpi/` | добавлены бинарники nfqws, списки, payload и `strategy.txt` |
| `services/NfqwsEngine.kt` (новый) | установка движка, запуск/остановка `zaprett`, подготовка списков |
| `services/ByeDpiVpnService.kt`, `ByeDpiProxyService.kt` | старт/стоп движка переведены с `ByeDpiProxy` на `NfqwsEngine` |
| `activities/MainActivity.kt` | при открытии приложения стратегия запускается сама (кнопка становится зелёной) |
| `res/layout/activity_main.xml`, `res/layout-land/activity_main.xml` | скрыты панели дополнительных кнопок в обоих режимах — остаётся только кнопка питания |
| `app/build.gradle.kts` | отключена сборка нативной части старого ByeDPI |

Интерфейс, названия пунктов меню, цвета и поведение кнопки сохранены.

---

## 4. Важное решение: SELinux и списки хостов

Причина, по которой nfqws «работает», но не обходит блокировку:

```
file_open_test: Permission denied
cannot access hostlist file '/storage/emulated/0/zaprett/files/lists/list-google.txt'
```

Демон nfqws под SELinux **не может читать списки из `/storage/emulated/0`**.
Поэтому `NfqwsEngine` при каждом запуске копирует списки и payload в каталог
модуля, куда демону разрешён доступ:

```
/data/adb/modules/zaprett/lists/
/data/adb/modules/zaprett/bin/
```

Пути внутри `strategies/general_alt12.txt` автоматически переписываются на
module-пути. Дополнительно добавляются PC-подобные iptables-правила с исключением
уже помеченных nfqws-пакетов (`-m mark ! --mark 0x40000000/0x40000000`).

---

## 5. Установка

APK: **`apk/ByeByeDPI-nfqws-general_alt12.apk`** (arm64-v8a, 1.7.7).

```bash
adb -s 192.168.0.7:5555 install -r -d apk/ByeByeDPI-nfqws-general_alt12.apk
```

- `-d` нужен при понижении версии с 1.8.2 на 1.7.7;
- подпись отладочная. Если на приставке стояла сборка с другой подписью —
  сначала `pm uninstall io.github.romanvht.byedpi`;
- после установки нужно выдать приложению root в Magisk (первый запуск нового UID):
  в Superuser появится запрос от `io.github.romanvht.byedpi`.

---

## 6. Проверка

1. Открыть приложение — кнопка питания **зелёная**, статус «Подключено (VPN)».
2. Проверить обход:
   ```bash
   adb -s 192.168.0.7:5555 shell "su -c 'export LD_LIBRARY_PATH=/data/adb/modules/zaprett/system/lib/arm64-v8a; /data/adb/modules/zaprett/system/bin/zaprett status'"
   ```
   Ожидаемо: `zaprett is working`.
3. Запустить YouTube — ролик идёт без `Unable to connect` / `Chunk load failed`.

Проверено на приставке: `zaprett is working`, видео `pbgaEcNKPzo` воспроизводится,
сетевых ошибок 0.

---

## 7. Источники и сборка

- Репозиторий: `https://github.com/romanvht/ByeByeDPI`, тег `v.1.7.7`.
- Сборка: JDK 17, Android SDK `/home/egor/android-tv-emu/sdk`, NDK 27.
  ```bash
  ./gradlew :app:assembleDebug
  ```
- Готовый APK копируется в `apk/ByeByeDPI-nfqws-general_alt12.apk`.

> ⚠️ Исходный APK пользователя (`ByeByeDP-general_alt12.apk`, 3,1 МБ) был
> перезаписан во время экспериментов. Текущая сборка сделана из точного тега
> `v.1.7.7` с сохранением кастомного интерфейса (одна кнопка).
