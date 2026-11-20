# SysBackup

Утилита с графическим (GTK) и консольным интерфейсом для резервного копирования и восстановления системы Linux (Linux Mint, Manjaro и совместимые дистрибутивы) в офлайн-режиме.

## Возможности

- Отключение запроса пароля sudo для текущего пользователя (создание `/etc/sudoers.d/sysbackup-nopasswd`)
- Создание бэкапа:
  - APT: список пакетов (`dpkg --get-selections`), конфигурации репозиториев, кэш `.deb`
  - Flatpak: список приложений и офлайн-копия (`flatpak create-usb`, с fallback на bundle)
  - Snap: список и скачанные `.snap`/`.assert` (`snap download`)
  - Системные конфиги: `/etc` (через `rsync -aAX`)
  - Данные пользователя: `/home/<user>` включая скрытые файлы (по умолчанию исключается `~/.cache`)
  - Метаданные: `backup_info.json`
- Восстановление из локальной или сетевой папки бэкапа (например, `/mnt/nas/backup`)
- GUI: `sysbackup-gui`
- CLI: `sysbackup-cli`
- Логирование в `~/.local/share/sysbackup/sysbackup.log`

## Структура проекта

- `sysbackup-gui` — запуск графического интерфейса
- `sysbackup-cli` — запуск консольного интерфейса
- `core/` — основная логика (бэкап, восстановление, пакеты, sudoers, утилиты)
- `gui/` — код GTK-интерфейса

## Зависимости

### Системные
- Python 3
- `rsync`
- `sudo`
- `dpkg`, `apt-get` (для Debian/Ubuntu/Mint)
- `flatpak` (опционально)
- `snap` (опционально)
- `apt-clone` (опционально, рекомендуется для более полного клонирования состояния APT)

### Python/GUI
- PyGObject (`python3-gi`, `gir1.2-gtk-3.0` в Debian/Ubuntu/Mint; `python-gobject`, `gtk3` в Manjaro/Arch)

## Установка

```bash
# Linux Mint / Ubuntu / Debian
sudo apt update
sudo apt install -y python3 python3-gi gir1.2-gtk-3.0 rsync

# Manjaro / Arch
sudo pacman -S --needed python python-gobject gtk3 rsync
```

Сделайте скрипты исполняемыми (при необходимости):

```bash
chmod +x sysbackup-cli sysbackup-gui
```

## Использование

### GUI

```bash
./sysbackup-gui
```

В окне доступны кнопки:
- **Отключить запрос пароля (sudo)** — создаёт правило NOPASSWD для текущего пользователя
- **Создать бэкап** — выбрать папку назначения и выполнить резервное копирование
- **Восстановить из бэкапа** — выбрать папку бэкапа и выполнить восстановление

### CLI

```bash
# Создать бэкап
./sysbackup-cli backup --dest /path/to/backup

# Восстановить из бэкапа
./sysbackup-cli restore --source /path/to/backup

# Отключить запрос пароля sudo
./sysbackup-cli disable-sudo-password

# Запустить сетевой сервер (headless, для удалённого управления)
./sysbackup-cli serve --host 0.0.0.0 --port 8765 --token SECRET

# Удалённо запустить операции на сервере SysBackup
./sysbackup-cli remote-backup --host <IP> --port 8765 --token SECRET --dest /path/on/target/backup
./sysbackup-cli remote-restore --host <IP> --port 8765 --token SECRET --source /path/on/target/backup
./sysbackup-cli remote-disable-sudo-password --host <IP> --port 8765 --token SECRET
```

CLI поддерживает локальные и сетевые пути (например, `/mnt/nas/backup`), если они доступны в файловой системе. Сетевой режим (`serve`/`remote-*`) позволяет выполнять бэкап/восстановление на удалённой машине без GUI.

## Standalone-сборка (AppImage)

В директории `sysbackup-standalone/` подготовлена сборка:

- `sysbackup-standalone/SysBackup-x86_64.AppImage` — AppImage (x86_64) с bundled Python 3.12 и исходным кодом приложения
- `sysbackup-standalone/SysBackup.AppDir/` — AppDir сборки
- `sysbackup-standalone/README.txt` — инструкции по запуску (GUI/CLI/сетевой режим)

Примеры:

```bash
./sysbackup-standalone/SysBackup-x86_64.AppImage --cli --help
./sysbackup-standalone/SysBackup-x86_64.AppImage serve --host 0.0.0.0 --port 8765 --token SECRET
```

**Важно:** GUI зависит от системных библиотек GTK/PyGObject (GI typelibs), поэтому на некоторых системах может потребоваться их установка; CLI и `serve` (headless/сетевой режим) работают без GTK. Полная бинарная переносимость AppImage зависит от совместимости glibc/библиотек целевой системы.

## Примечания и ограничения

- Операции бэкапа/восстановления требуют прав root и выполняются через `sudo`.
- При первом запуске `disable-sudo-password` (и других операций без активного NOPASSWD) будет запрошен пароль sudo.
- Восстановление может перезаписать системные конфигурации и пользовательские файлы. Рекомендуется выполнять его осознанно (лучше в сходной среде/на чистой установке).
- Для полностью офлайн-восстановления важно, чтобы в бэкапе присутствовали необходимые `.deb`/snap/flatpak артефакты. Доступность всех зависимостей зависит от состояния системы на момент бэкапа и особенностей дистрибутива.
- Бэкап домашних данных по умолчанию исключает `~/.cache` для экономии места.
- На разных дистрибутивах набор пакетных менеджеров отличается (APT/Flatpak/Snap); отсутствующие инструменты автоматически пропускаются.
- Сетевой режим `serve`/`remote-*` не использует шифрование канала; применяйте токен и запускайте только в доверенной сети/VPN или через защищённый туннель.
