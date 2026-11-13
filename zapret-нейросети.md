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
./service.sh download-deps --default   # скачает nfqws + свежие стратегии
```

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

## Рабочие стратегии (на этом компьютере, проверено 13.11.2026)

Стратегия в `conf.ini` **не менялась** — там ваш `general_alt9.bat`.

| Стратегия | YouTube |
|-----------|---------|
| **general_alt9.bat** (текущая, в conf.ini) | ✅ 200 |
| general_alt4.bat | ✅ 200 |
| general_alt11.bat | ✅ 200 |
| general_alt12.bat | ✅ 200 |
| general_fake_tls_auto.bat | ✅ 200 |

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
