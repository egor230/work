#!/bin/bash 
#gnome-terminal -- bash -c '

cd "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project";
image_url=$(copyq read 0)    # Получаем  из буфера обмена  
if [ ! -f "$(copyq clipboard)" ] && [[ -z "$(copyq clipboard)" ]]; then  
 #echo "$image_url"
 sleep 0.8
 copyq select 0  
fi
if xclip -selection clipboard -t image/png -o > /dev/null 2>&1 || xclip -selection clipboard -t image/jpeg -o > /dev/null 2>&1 || xclip -selection clipboard -t image/bmp -o > /dev/null 2>&1 || xclip -selection clipboard -t image/svg+xml -o > /dev/null 2>&1 ; then
  sleep 0.8
  copyq select 0
fi
if [ ! -f "$(copyq clipboard)" ] && [[ "$image_url" == http* && ! "$image_url" =~ "vk.com" ]] && ! ( xclip -selection clipboard -t image/png -o > /dev/null 2>&1 || xclip -selection clipboard -t image/jpeg -o > /dev/null 2>&1 || xclip -selection clipboard -t image/bmp -o > /dev/null 2>&1 || xclip -selection clipboard -t image/svg+xml -o > /dev/null 2>&1 ); then  # Проверяем, есть ли в буфере обмена URL изображения
  source myenv/bin/activate && python "Дополнительные функции буфера обмена.py"
  exit 0
fi
exit 0
# && ! -f  xclip -selection clipboard -t image/png -o > /dev/null 2>&1
 #sleep 0.8
#exec bash;'
#echo "$image_url"
#sleep 3
#  while true; do  # Проверяем, был ли файл успешно скачан
#   sleep 1  # Ждем 1 секунду перед следующей проверкой
#   if [ -f "$filename" ]; then # он есть  
#     break 
#   fi
#  done

#current_text=$(xclip -o -selection primary)
#if ! [ $(copyq read 3) == "$current_text" ] && ! [[ $(copyq read 4) == "$current_text" ]]; then
#  copyq insert 4 "$current_text"
#fi


#  #echo "522225"  sleep 4
#  now=$(date +"%F %T")   # Получить текущую дату/время
#  current_date=$(date +"%F")
#  hours=$(date +"%H") # Разбить на отдельные элементы
#  minutes=$(date +"%M")
#  seconds=$(date +"%S")  # Сформировать имя файла
#  filename="/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project/Screenshots/${hours} ${minutes} ${seconds} ${current_date}.png"
#  curl -L -o "$filename" "$image_url" --retry 3 --retry-delay 1 --fail -k  # Скачиваем изображение
#  sleep 2.3 
#  xclip -selection clipboard -t image/png -i "$filename"
#  #copyq write image/png - < "$filename"
#  sleep 2.3 
#  copyq select 0
#fi
#  while true; do  # Проверяем, был ли файл успешно скачан
#   sleep 1  # Ждем 1 секунду перед следующей проверкой
#   if [ -f "$filename" ]; then # он есть  
#     break 
#   fi
#  done
#if xclip -selection clipboard -t image/png -o > /dev/null;  then # Есть изображение    #echo "no ima"
#  sleep 0.3
#  copyq write image/png - < "$image_url" #copyq select 0
#  sleep 2.1 
#  copyq select 0
#  exit 0
#fi

#image_extensions=("jpg" "jpeg" "png" "gif" "bmp") # Проверяем, существует ли файл
#extension="${image_url##*.}"
#if [ -f "$image_url" ] && [[ " ${image_extensions[*]} " == *" $extension "* ]]; then
#  name=$(basename "$image_url")  #  echo "$image_url"
#  
#  if echo "$name" | grep -q "[а-яА-Я]"; then
#    cd "/mnt/807EB5FA7EB5E954/софт/виртуальная машина/linux must have/python_linux/Project";
#    source myenv/bin/activate && python "inage to buffer.py";
#    exit 0  
#  else 
#    copyq write image/png - < "$image_url"
#    sleep 2.3 
#    copyq select 0
#    exit 0  
#  fi
#fi
#
#exit; 
