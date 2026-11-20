> **Встроено в приложение (20.11):** `DpiBypassInstaller` раскладывает движок и
> эту стратегию на приставке и поднимает обход при каждом запуске приложения.

# Рабочая стратегия обхода DPI (`general_alt12.bat`)

Скопирована из `/home/egor/Downloads/zapret-discord-youtube-linux/zapret-latest/general_alt12.bat`.
Сохранена в `conf.ini` как **текущая/рабочая** и запускается скриптом
`/mnt/807EB5FA7EB5E954/python_linux/start-zapret.sh`.

## Запуск

```bash
# сохранённая стратегия (conf.ini = general_alt12.bat):
/mnt/807EB5FA7EB5E954/python_linux/start-zapret.sh
# или напрямую:
/home/egor/Downloads/zapret-discord-youtube-linux/service.sh \
  kill && /home/egor/Downloads/zapret-discord-youtube-linux/service.sh \
  run -s general_alt12.bat -i any
```

Статус: `pgrep -a nfqws` — процесс должен быть с параметрами ниже.

## Ключевые параметры (что именно «работает идеально»)

| Канал | Фильтр | Действие |
|---|---|---|
| UDP 443 (QUIC) | `list-general`, `ipset-all` | `--dpi-desync=fake --dpi-desync-repeats=11 --dpi-desync-fake-quic=bin/quic_initial_www_google_com.bin` |
| UDP Discord/STUN | 19294–19344, 50000–50100 | `fake`, repeats=3, fake `stun.bin` / `ACTIVE_DISCORD_UDP.bin` |
| TCP 2053/2083/2087/2096/8443 | discord.media | `fake,multisplit`, seqovl=681, split-pos=1, fooling=ts, repeats=8, fake TLS `tls_clienthello_www_google_com.bin` |
| TCP 443 Google | `list-google.txt` | `--ip-id=zero --dpi-desync=hostfakesplit --dpi-desync-fooling=ts --dpi-desync-hostfakesplit-mod=host=www.google.com` |
| TCP 80/443 общий | `list-general`, `ipset-all` | `fake,multisplit`, **seqovl=664**, **split-pos=1**, **fooling=ts**, **repeats=8**, pattern/fake TLS `tls_clienthello_www_sferum_ru.bin`, fake `stun.bin` |
| TCP 80/443/8443 по IP | `ipset-all.txt` | тот же `fake,multisplit` с seqovl=664 / repeats=8 |
| Игры TCP/UDP | `ipset-all`, GameFilter | `fake,multisplit`, `any-protocol`, `cutoff=n4`, repeats=8/10 |

Отличие `alt12` от `alt11`: для Google используется `hostfakesplit` вместо
`fake,multisplit`, а в общих правилах fake-TLS берётся `stun.bin` (в `alt11` — `stun2.bin`).

## Важно для приставки

`nfqws` запущен **на компьютере** и влияет только на трафик компьютера.
На AM9 он не действует. Чтобы применить эту же стратегию к приставке, нужно
одно из:
- поднять nfqws на роутере (если прошивка позволяет) — тогда через него идёт весь трафик ТВ;
- дать приставке ходить через компьютер (VPN/прокси/маршрут по умолчанию через ПК);
- использовать Android-аналог на самой приставке (`io.github.romanvht.byedpi`
  или `com.cherret.zaprett` — оба уже установлены на AM9) с эквивалентными
  параметрами desync.

Файлы: `zapret_general_alt12.bat`, `zapret_conf.ini` в этой папке.
