#!/bin/bash
gnome-terminal -- bash -c '
# Получаем текущую директорию и сохраняем ее в переменную current_directory
current_directory=$(pwd)

# Получаем имя текущего пользователя и сохраняем его в переменную current_user
current_user=$(whoami)

# Переходим в директорию /home/имя_пользователя
cd /home/$current_user;

# Создаем архив с названием openoffice_backup.tar и архивируем все файлы и директории внутри директории .openoffice
tar -cvf openoffice_backup.tar .openoffice;

# Перемещаем архив openoffice_backup.tar в директорию current_directory
mv openoffice_backup.tar $current_directory;

# Завершаем выполнение скрипта
exit;
exec bash'
