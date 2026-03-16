#!/bin/bash
#gnome-terminal -- bash -c '
sudo apt-get update
sudo apt-get -y install dconf-editor gedit xed-encoding-extras linux-generic
# Настройка кодировок для xed (редактор среды X-Apps)
# Добавляем WINDOWS-1251 в список автоопределения
gsettings set org.x.editor.preferences.encodings auto-detected "['UTF-8', 'WINDOWS-1251', 'CURRENT', 'ISO-8859-15', 'UTF-16']"

# Настройка кодировок для Gedit (на случай использования обеих программ)
# Пробуем первый вариант ключа
gsettings set org.gnome.gedit.preferences.encodings auto-detected "['UTF-8', 'WINDOWS-1251', 'CURRENT', 'ISO-8859-15', 'UTF-16']" 2>/dev/null

# Если первый вариант не сработал, пробуем альтернативный ключ candidate-encodings
if [ $? -ne 0 ]; then
  gsettings set org.gnome.gedit.preferences.encodings candidate-encodings "['UTF-8', 'WINDOWS-1251', 'KOI8-R', 'CURRENT', 'ISO-8859-15', 'UTF-16']"
fi

echo "Настройка завершена. Теперь кириллица в xed должна отображаться корректно."
exit
#exec bash'
 
