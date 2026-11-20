SysBackup Standalone (AppImage)
===============================

Папка содержит готовую сборку SysBackup:

- SysBackup-x86_64.AppImage  — AppImage (x86_64), включает исходники проекта и bundled Python 3.12 (stdlib)
- SysBackup.AppDir/          — AppDir, из которого собран AppImage

Запуск
------

GUI (если в системе доступны зависимости GTK/PyGObject: python3-gi, gir1.2-gtk-3.0 и т.п.):
  ./SysBackup-x86_64.AppImage

CLI (без графического интерфейса):
  ./SysBackup-x86_64.AppImage --cli --help
  ./SysBackup-x86_64.AppImage check
  ./SysBackup-x86_64.AppImage check --source /path/to/backup
  ./SysBackup-x86_64.AppImage backup --dest /path/to/backup
  ./SysBackup-x86_64.AppImage restore --source /path/to/backup
  ./SysBackup-x86_64.AppImage disable-sudo-password

Можно также вызывать команды напрямую (без --cli):
  ./SysBackup-x86_64.AppImage backup --dest /path/to/backup
  ./SysBackup-x86_64.AppImage serve --host 0.0.0.0 --port 8765

Работа по сети (headless/удалённое управление)
----------------------------------------------

На целевой машине (где нужно выполнять бэкап/восстановление) запустите сервер:
  ./SysBackup-x86_64.AppImage serve --host 0.0.0.0 --port 8765 --token SECRET

С другой машины отправьте команду:
  ./SysBackup-x86_64.AppImage remote-backup  --host <IP> --port 8765 --token SECRET --dest /path/on/target/backup
  ./SysBackup-x86_64.AppImage remote-restore --host <IP> --port 8765 --token SECRET --source /path/on/target/backup
  ./SysBackup-x86_64.AppImage remote-disable-sudo-password --host <IP> --port 8765 --token SECRET

Примечания:
- Сервер выполняет операции локально на своей машине (пути --dest/--source интерпретируются на стороне сервера).
- Рекомендуется использовать --token и ограничивать доступ к порту (фаервол/VPN/доверенная сеть), так как операции выполняются с правами root через sudo.
- Для сетевых хранилищ можно использовать смонтированные пути (NFS/SMB/SSHFS и т.д.) на стороне сервера, например /mnt/nas/backup.

Зависимости и ограничения переносимости
--------------------------------------
- Для операций бэкапа/восстановления на целевой системе должны быть доступны системные утилиты: sudo, rsync, а также соответствующие менеджеры пакетов (dpkg/apt-get, flatpak, snap) — по наличию.
- AppImage включает Python, но графический интерфейс (GUI) зависит от системных библиотек PyGObject/GTK (GI typelibs). На минимальных/чужих системах GUI может не запуститься без установки этих пакетов; CLI/serve режимы не требуют GTK.
- Переносимость бинарного Python между разными дистрибутивами ограничена совместимостью glibc/системных библиотек. На Linux Mint и близких Ubuntu-системах x86_64 обычно работает; при проблемах используйте исходную версию из папки проекта (sysbackup-cli/sysbackup-gui) с установленным Python 3.

Логи
----
~/.local/share/sysbackup/sysbackup.log
