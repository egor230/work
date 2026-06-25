import Xlib
from Xlib import X, display

import subprocess

# Получаем список всех окон с помощью wmctrl
output = subprocess.check_output(['wmctrl', '-l']).decode('utf-8')

# Выводим названия окон
for line in output.splitlines():
    parts = line.split(maxsplit=3)  # Разделяем строку на части
    if len(parts) >= 4:
        window_id = parts[0]  # ID окна
        window_title = parts[3]  # Название окна
        print(f"ID: {window_id}, Title: {window_title}")