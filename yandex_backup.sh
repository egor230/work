gnome-terminal -- bash -c "
sleep 1;
current_user=$(whoami);
current_directory=$(pwd)/yandex-browser
echo "$current_directory"

# Проверяем, существует ли папка
if [ ! -d "$current_directory" ]; then
    mkdir -p "$current_directory";
fi

source_directory=\"/home/\$current_user/.config/yandex-browser\";
sudo rsync -a --info=progress2 --update \"\$source_directory\" \"\$current_directory\" | pv -lep -s \"\$(du -sb \"\$source_directory\" | awk '{print \$1}')\" > /dev/null;

exit;
exec bash"

#xdotool key F3;cd /home/$current_user/.config;# Переходим в директорию /home/имя_пользователя
#chown -R $USER;
