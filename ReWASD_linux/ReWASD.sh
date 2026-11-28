#!/bin/bash
#gnome-terminal -- bash -c ' 
PYTHON_EXECUTABLE="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project/myvenv/bin/python" # Путь к скрипту
SCRIPT_PATH="/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/ReWASD_linux/ReWASD.py"; # Команда для запуска:
# Библиотека мыши и editor_settings читают settings.json относительно cwd —
# переходим в каталог приложения, иначе при запуске из другой папки они
# работают с другим файлом настроек.
cd "$(dirname "$SCRIPT_PATH")" || exit 1
"$PYTHON_EXECUTABLE" "$SCRIPT_PATH";
exit;
#exec bash'
 