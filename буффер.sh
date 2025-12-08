#!/bin/bash
gnome-terminal -- bash -c '
(sleep 0.5; xdotool getactivewindow set_desktop_for_window 1 windowminimize)
while true; do
 sleep 2
 if [ -z "$(xsel -b)" ]; then # Попытка считать содержимое буфера обмена как изображение
  echo "empty"
  copyq select 0
  sleep 6
 else
  echo "full"
  sleep 2
fi
done

exit;
exec bash'
