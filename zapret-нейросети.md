# Zapret для Linux: YouTube + Discord + Нейросети без VPN

## Что такое Zapret

**Zapret** — это не VPN и не прокси. Это программа на базе технологии **nfqueue**, которая перехватывает пакеты трафика на уровне ядра (через nftables/iptables) и меняет заголовки TCP/UDP, делая трафик не распознаваемым для DPI-фильтров провайдера. 

Провайдер замедляет/блокирует YouTube, Discord, ChatGPT и другие сервисы через анализ содержимого пакетов (DPI — Deep Packet Inspection). Zapret «маскирует» эти пакеты, и провайдер перестаёт их распознавать.
У меня сейчас работает очень хорошо это Выбрана стратегия: general_alt12.bat

---

## Структура системы

```
/home/egor/Downloads/zapret-discord-youtube-linux/
├── service.sh              # Основной управляющий скрипт
├── conf.ini                # Сохранённая стратегия (имя .bat файла)
├── nfqws                   # Бинарник (Linux-порт WinDivert)
├── zapret-latest/          # Стратегии (.bat) и списки доменов/IP
│   ├── general.bat
│   ├── general_alt12.bat    # ← рабочая стратегия на данном компьютере
│   ├── general_alt9.bat
│   ├── ...
│   ├── lists/              # Списки доменов и IP (ipset)
│   │   ├── list-general.txt
│   │   ├── list-general-user.txt   # ← пользовательский список (нейросети)
│   │   ├── list-google.txt
│   │   └── ipset-all.txt
│   └── bin/                # Файлы для де-синка (fake QUIC, TLS ClientHello)
├── custom-strategies/      # Симлинки → zapret-latest/*.bat
└── user-lists/             # Пользовательские списки (хардлинки в lists/)
```

---

## Как это работает (пошагово)

### 1. Установка и обновление

```bash
cd /home/egor/Downloads/zapret-discord-youtube-linux
git pull
./service.sh download-deps --default   # рекомендованные версии (nfqws v72.9 + Flowseal 1.9.9a)
```

**Актуальное состояние на 16.11.2026 (обновлено вручную):**

| Компонент | Было | Стало |
|---|---|---|
| nfqws | v72.9 | **v72.13** (`github version 87e058624c72863db53bdaf7fb6f16576dddb6ab`) |
| Стратегии Flowseal | 1.9.9a (28.05.2026) | **1.10.4** (20.10.2026) |

Команда обновления (сначала остановить zapret!):

```bash
cd /home/egor/Downloads/zapret-discord-youtube-linux
./service.sh kill
cp conf.ini conf.ini.bak
cp -a user-lists user-lists.bak
./service.sh download-deps -z v72.13 -s 1.10.4
cp -a user-lists.bak/. user-lists/          # ← ОБЯЗАТЕЛЬНО: при обновлении списки удаляются
ln -f user-lists/* zapret-latest/lists/     # восстановить хардлинки
./service.sh kill
```

> ⚠️ `setup_repository()` в `src/lib/common.sh` делает `rm -f "$user_lists"/*`.
> Без бэкапа **сотрутся 20 доменов нейросетей** из `list-general-user.txt`.
> Полный бэкап на этот раз: `/tmp/zapret-backup-20261116/`.

В 1.10.4 заменён TLS-фейк в **ALT11/ALT12** (`tls_clienthello_www_sferum_ru.bin`),
обновлён IPSet, добавлены стратегии `general_alt13.bat` и `general_exp.bat`.

### 2. Запуск стратегии

Каждая стратегия — это `.bat` файл, который описывает набор правил фильтрации. Скрипт `service.sh` парсит его, настраивает nftables и запускает `nfqws`:

```bash
./service.sh run -s general_alt4.bat -i any
```

### 3. Что происходит внутри

| Шаг | Что делает |
|-----|------------|
| nftables | Перехватывает пакеты TCP/UDP на заданных портах и направляет в очередь `nfqws` (queue 220) |
| nfqws | Читает пакеты из очереди, изменяет заголовки (TLS ClientHello, QUIC Initial) по файлам из `bin/` |
| DPI-фильтр | Перестаёт распознавать трафик YouTube/Discord/ChatGPT → трафик идёт нормально |

---

## Рабочие стратегии (на этом компьютере, проверено 13.11.2026, обновлено 16.11.2026)

Стратегия в `conf.ini` — **`general_alt12.bat`** (в старой версии документа ошибочно указан `alt9`).

| Стратегия | YouTube |
|-----------|---------|
| **general_alt12.bat** (текущая, в conf.ini) | ✅ 200 |
| general_alt4.bat | ✅ 200 |
| general_alt9.bat | ✅ 200 |
| general_alt11.bat | ✅ 200 |
| general_fake_tls_auto.bat | ✅ 200 |
| general_alt13.bat (новая в 1.10.4) | не проверялась |
| general_exp.bat (новая в 1.10.4) | не проверялась |

> Стратегии `general.bat`, `general_alt2`, `alt5`, `alt6`, `alt7`, `alt8` YouTube **не разблокируют** — их лучше не выбирать.

---

## Разблокировка нейросетей (ChatGPT, Claude, Gemini)

### Проблема: DNS-блокировка

DNS провайдера **блокирует** запросы к `chatgpt.com`, `openai.com`, `claude.ai`, `anthropic.com`, отвечая `0.0.0.0`:

```
$ dig chatgpt.com @111.88.96.54 +short   # DNS провайдера
0.0.0.0

$ dig chatgpt.com @8.8.8.8 +short         # Google DNS (не блокирует)
8.47.69.0
```

### Как работает разблокировка (2 механизма)

**Механизм 1 — nfqws (обход DPI-фильтра):**
Когда zapret запущен, nfqws перехватывает трафик к доменам из `list-general-user.txt` (куда добавлены `chatgpt.com`, `claude.ai` и др.) и маскирует их, чтобы DPI-фильтр провайдера не распознавал этот трафик. Это работает для **TCP-трафика**, который уже доходит до сервера.

**Механизм 2 — /etc/hosts (обход DNS-блокировки):**
Браузер сначала резолвит `chatgpt.com` через DNS провайдера. Тот отвечает `0.0.0.0` — браузер не может подключиться. Записи в `/etc/hosts` переопределяют DNS-ответ локально:

```bash
sudo bash -c 'cat >> /etc/hosts << EOF
# AI-services zapret
8.47.69.0      chatgpt.com
8.47.69.0      api.openai.com
104.18.33.45   openai.com
160.79.104.10  claude.ai
160.79.104.10  anthropic.com
142.251.152.2  gemini.google.com
142.251.153.2  gemini.google.com
142.251.143.142 aistudio.google.com
104.18.23.222  copilot.microsoft.com
EOF'
sudo resolvectl flush-caches'
```

IP получены через `dig @8.8.8.8` (Google DNS). После записи в hosts браузер подключается к реальному IP, и nfqws маскирует трафик — сайт открывается.

> Какие домены реально блокируются по DNS у вашего провайдера (проверено): `chatgpt.com`, `api.openai.com`, `openai.com`, `claude.ai`, `anthropic.com`, `gemini.google.com`, `aistudio.google.com`, `copilot.microsoft.com`. Остальные (`perplexity.ai`, `huggingface.co`, `deepseek.com`, `mistral.ai`, `grok.x.ai`) резолвятся нормально и в hosts не нужны.

### Проверка статусов

| Сайт | Статус без zapret | Статус с zapret |
|------|-------------------|-----------------|
| chatgpt.com | `0.0.0.0` (DNS block) | `403` (работает, требуется авторизация) |
| claude.ai | `0.0.0.0` (DNS block) | `302` (работает, редирект на вход) |
| youtube.com | `timeout` (замедление) | `200` (полностью работает) |

> Статус 403 от ChatGPT/OpenAI — это **нормально**: сервер отвечает, но требует авторизацию. Статус 000 (time out) — это блокировка.

### Пользовательский список (list-general-user.txt)

Файл `user-lists/list-general-user.txt` (хардлинк в `zapret-latest/lists/`) содержит домены нейросетей. nfqws подхватывает их автоматически во всех стратегиях через параметр `--hostlist=lists/list-general-user.txt`:

```
chatgpt.com
openai.com
platform.openai.com
api.openai.com
claude.ai
anthropic.com
gemini.google.com
aistudio.google.com
ai.google.com
perplexity.ai
huggingface.co
```

> Эти домены попадают в список `list-general-user.txt`, который включён во все стратегии через параметр `--hostlist=lists/list-general-user.txt`. Это значит, что nfqws будет маскировать и их трафик при активном запущенном zapret.

---

## Скрипт `start-zapret.sh` (НЕ изменялся)

Скрипт остаётся вашим оригинальным, один в один. В нём ничего не правилось.

```bash
bash /mnt/807EB5FA7EB5E954/python_linux/start-zapret.sh
```

### Как он работает

1. Останавливает запущенный zapret (`./service.sh kill`)
2. Если в `conf.ini` есть имя стратегии — запускает её и сразу выходит
3. Если `conf.ini` нет/пуст — прогоняет все стратегии и показывает меню выбора
4. Команды меню: `<номер>` — запустить стратегию, `s` — сохранить в `conf.ini`, `x` — остановить, `q` — выйти

> Важно: чтобы YouTube и нейросети работали, все изменения сделаны **внутри папки программы** (`conf.ini`, `user-lists/`, `custom-strategies/`) и в `/etc/hosts`. Сам скрипт для этого менять не нужно.

### Сохранение рабочей стратегии

```bash
cd /home/egor/Downloads/zapret-discord-youtube-linux
echo "general_alt4.bat" > conf.ini
```

При следующем запуске `start-zapret.sh` стратегия будет загружена автоматически.

---

## Остановка запущенного zapret

```bash
cd /home/egor/Downloads/zapret-discord-youtube-linux
./service.sh kill
```

Это остановит `nfqws` и очистит правила nftables. DNS-записи в `/etc/hosts` останутся (они не мешают работе без zapret).

---

## Обновление библиотеки: `zapret-ai-hosts` (одна команда)

Библиотека `~/.local/bin/zapret-ai-hosts` обновляет IP нейросетей в `/etc/hosts`: берёт свежие адреса через `dig @8.8.8.8`, при недоступности DNS подставляет резервные, чистит старый блок и проверяет доступность сайтов.

```bash
sudo /home/egor/.local/bin/zapret-ai-hosts
```

Вывод в конце — проверка доступа:

```
chatgpt.com              403   OK
api.openai.com           403   OK
openai.com               403   OK
claude.ai                302   OK
anthropic.com            301   OK
gemini.google.com        200   OK
aistudio.google.com      302   OK
copilot.microsoft.com    403   OK
```

Запуск без пароля уже настроен (`/etc/sudoers.d/zapret-ai-hosts`). Делать это нужно раз в 1–4 недели, если сайты перестали открываться.

### Порядок запуска

1. `bash /mnt/807EB5FA7EB5E954/python_linux/start-zapret.sh` — поднимает zapret (nfqws)
2. `sudo /home/egor/.local/bin/zapret-ai-hosts` — обновляет DNS-обход (если нужно)

Сам `start-zapret.sh` и стратегию менять не требуется.

---

## Как обновить вручную (если нужно)

```bash
# 1. Получить свежие IP
IP1=$(dig chatgpt.com @8.8.8.8 +short | grep -E '^[0-9.]+$' | head -1)
IP2=$(dig claude.ai @8.8.8.8 +short | grep -E '^[0-9.]+$' | head -1)

# 2. Удалить старые записи и добавить новые
sudo sed -i '/zapret-ai-begin/,/zapret-ai-end/d' /etc/hosts
sudo bash -c "echo '# zapret-ai-begin' >> /etc/hosts && echo '$IP1 chatgpt.com' >> /etc/hosts && echo '$IP2 claude.ai' >> /etc/hosts && echo '# zapret-ai-end' >> /etc/hosts"
sudo resolvectl flush-caches
```

---

## Одно конкретное видео не играет, остальные работают (16.11.2026)

### Симптом

`https://www.youtube.com/watch?v=dtDWcBdrwVk` («Serious Sam: Next Encounter —
Консольный аркадный Сэм», 45 мин) крутится в Яндекс.Браузере, хотя остальные
ролики идут идеально. Скорость канала и zapret ни при чём.

### Диагноз: не стратегия, а формат и CDN-узел

Страница и метаданные в порядке: `playabilityStatus: OK`, `availability: public`,
`age_limit: 0`. Проблема в потоках `googlevideo.com`. Замер `curl -r 0-65535`
по всем форматам с этой машины:

| itag | codec / качество | HTTP | Что это значит |
|---|---|---|---|
| 18, 133, 134, 135, 160 | **H.264 / AVC** | `302` → `000` | Local cache не держит, уводит на `173.194.x`, там таймаут |
| 139, 140 | **AAC audio** | `302` / `000` | то же |
| 242, 243, 244, 302, 308 | VP9 / WebM 240…1440p | `206` | отдаёт локальный кэш ✅ |
| 394, 396…400 | VP9/AV1 в MP4 144…1440p | `206` | отдаёт локальный кэш ✅ |
| 251 | Opus audio | `206` | отдаёт локальный кэш ✅ |

CDN-узел: `46.61.168.108` (Google Global Cache внутри сети провайдера).
Контрольное видео `jNQXAC9IVRw` отдаёт `206` **сразу**, без редиректов.

То есть YouTube/браузер выбирает H.264-итаг, которого нет в локальном кэше,
получает цепочку `302 → 302 → таймаут`, и плеер висит. DPI-обходы сюда не
относятся: это решение CDN, а не блокировка по DPI.

### Навык проверки любого видео

Установлен `youtube-video-check` (каталог `~/.config/opencode/skills/youtube-video-check/`).

```bash
bash ~/.config/opencode/skills/youtube-video-check/check.sh \
  "https://www.youtube.com/watch?v=dtDWcBdrwVk"
```

Показывает: существует ли видео, `playabilityStatus`, таблицу всех итагов с
HTTP-кодами и IP CDN, список рабочий itag'ов и вердикт. Принимает ссылку или
только 11-значный ID.

### Решение: Enhancer for YouTube — принудительный VP9/AV1

Расширение Яндекс.Браузера `Enhancer for YouTube™` (ID
`ifojmbdceojdnhhagpmfnmjndpplcndi`, версия 3.1.0) доработано: добавлена
настройка **`forcevp9`** (по умолчанию включена). Она запрещает H.264
(`avc1`/`avc3`) через `MediaSource.isTypeSupported` — тот же механизм, которым
штатная опция `blockwebmformats` запрещает WebM. VP9/AV1 остаются доступны.

| Файл | Что добавлено |
|---|---|
| `js/config.js` | `forcevp9:!0` в defaults и в `configEmbed` |
| `js/youtube-main.js` | `d&&d.forcevp9&&/(avc1\|avc3)/i.test(b)` в `MediaSource.isTypeSupported` |
| `js/embed-main.js` | то же для встроенного плеера |
| `html/options.html`, `js/options.js` | чекбокс «Принудительно VP9/AV1» в разделе кодеков |
| `_locales/ru,en_US/messages.json` | строка `force_vp9` |

Рабочая копия и полное описание (§13):
`/home/egor/Downloads/расширения/Enhancer for YouTube/README-CUSTOM.md`.

**Пересборка и установка:**

```bash
cd "/home/egor/Downloads/расширения/Enhancer for YouTube"
./package-crx.sh         # → ../Enhancer_for_YouTube.crx, ID не меняется
```

CRX распакован в папку установленного расширения Яндекс.Браузера:
`~/.config/yandex-browser/Default/Extensions/ifojmbdceojdnhhagpmfnmjndpplcndi/3.1.0_1/`.
Старые файлы сохранены в `/tmp/efyt-yandex-installed-backup-20261116-225124/`.
`chrome.storage.local` **не трогался** — все настройки остались на месте.

### Где Ваши настройки расширения сохранены

| Файл | Содержимое |
|---|---|
| `…/Enhancer for YouTube/config-backup.json` | 14 ключей: 42 скорости по каналам, `maTheme: dark`, `qualityvideos/qualityplaylists: hd1440`, `selectquality: true`, `speed: 1.2`, кнопки плеера и т.д. |
| `/home/egor/Downloads/расширения/config-backup-Yandex-20261116-225019.json` | копия на всякий случай |
| `/tmp/efyt-yandex-settings-20261116-225019.json` | ещё одна копия |

Источник: `~/.config/yandex-browser/Default/Local Extension Settings/ifojmbdceojdnhhagpmfnmjndpplcndi`
(извлечено парсером LevelDB, браузер был выключен).

### Почему в Яндекс.Браузере было иначе

Яндекс.Браузер тянул H.264 (итаги 18/134/135) и резолвил через свой
Yandex DNS / QUIC мимо nfqueue. Теперь принудительно VP9 — браузер берёт
итаги 244/397/398 из локального кэша, и видео идёт так же, как в замерах.

> Ограничение: если в какой-то момент локальный кэш провайдера не будет держать
> даже VP9, поможет только смена IP (WARP/VLESS). Навык покажет это как
> `000`/`302` у всех итагов.

---

## Частые проблемы

### YouTube не работает после запуска стратегии

Попробуйте другую стратегию. Не все стратегии работают на каждом провайдере. На этом компьютере работают: `general_alt4`, `general_alt9`, `general_alt11`, `general_alt12`.

### ChatGPT/нейросети не открываются, хотя zapret запущен

1. Обновите IP одной командой:
   ```bash
   sudo /home/egor/.local/bin/zapret-ai-hosts
   ```

2. Сбросьте DNS-кэш (скрипт делает это сам, но можно вручную):
   ```bash
   sudo resolvectl flush-caches
   ```

3. Перезапустите браузер или откройте новую вкладку.

4. Проверьте, что nfqws запущен:
   ```bash
   pgrep -c nfqws    # должно быть 1 или больше
   ```

### Стратегии не найдены

```bash
cd /home/egor/Downloads/zapret-discord-youtube-linux
./service.sh download-deps --default
```

### Ошибка «nfqws занят» при загрузке зависимостей

Сначала остановите запущенный zapret:
```bash
./service.sh kill
```

---

## Ссылки

- Репозиторий адаптера: https://github.com/Sergeydigl3/zapret-discord-youtube-linux
- Стратегии (Flowseal): https://github.com/Flowseal/zapret-discord-youtube
- Оригинальный zapret: https://github.com/bol-van/zapret
