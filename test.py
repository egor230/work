import time, json, os, subprocess, psutil, pyperclip, sys, re, io, pyautogui
from os import path
# import pytesseract
# Загрузите изображение с использованием PIL
from PIL import Image, ImageFilter, ImageEnhance
# time.sleep(4.3)
# pyautogui.hotkey('ctrl', 'v')
import pkg_resources
import sys, urllib.parse
import base64
from transformers import AutoTokenizer, AutoModelForCausalLM
from evdev import InputDevice, list_devices

devices = [InputDevice(fn) for fn in list_devices()]

print("Список устройств ввода:")
for dev in devices:
    print(f"Путь: {dev.path} | Имя: {dev.name} | Физ. путь: {dev.phys}")
def get_webcam_source_id():# Определяет текущий Source ID (например, '53') для HD Webcam C525,
 # Постоянное имя вашего микрофона с веб-камеры (из вашего вывода)
 TARGET_NAME = "alsa_input.usb-046d_HD_Webcam_C525_79588C20-00.mono-fallback"
 try:
  # Самый быстрый способ — использовать pactl list sources в "short" формате
  result = subprocess.run(  ['pactl', 'list', 'sources', 'short'],
   capture_output=True, text=True, check=True  )

  # Формат строки: 53    alsa_input.usb-046d_HD_Webcam_C525_...mono-fallback    PipeWire    s16le 1ch 4800Hz    RUNNING
  for line in result.stdout.splitlines():
   fields = line.split()
   if len(fields) >= 2 and TARGET_NAME in fields[1]:
    return fields[0]  # это и есть ID источника

  print("Webcam C525 не найдена в pactl list sources short", file=sys.stderr)
  return None

 except FileNotFoundError:
  print("pactl не найден. Установлен PipeWire/PulseAudio?", file=sys.stderr)
  return None
 except subprocess.CalledProcessError as e:
  print(f"pactl вернул ошибку: {e}", file=sys.stderr)
  return None


def set_mute(mute: str, source_id: str):
 if source_id is None:
  print("source_id = None → ничего не делаем", file=sys.stderr)
  return

 # mute = "1" или "0"
 subprocess.run(["pactl", "set-source-mute", source_id, mute], check=True)
 # Опционально — сразу ставим нормальную громкость
 subprocess.run(["pactl", "set-source-volume", source_id, "80%"], check=True)
source_id = get_webcam_source_id()      # ← твоя функция
set_mute("0", source_id)



# Загрузка токенизатора и модели
# tokenizer = AutoTokenizer.from_pretrained("EleutherAI/gpt-j-6B")
# model = AutoModelForCausalLM.from_pretrained("EleutherAI/gpt-j-6B")
#
# # Сохранение модели и токенизатора локально
# model.save_pretrained("./gpt-j-6b")
# tokenizer.save_pretrained("./gpt-j-6b")
# print("Ок ")
# input()

# result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
# name_scrypt = sys.argv[0]
# # Вызываем скрипт
# i=0
# try:
#  for line in result.split("\n"):
#   process_name = ' '.join(line.split()[10:])
#   if name_scrypt in process_name:
#     i=i+1
#     if i==2:
#       sys.exit(0)
#       break
#
# except:
#   pass

# find_nemo = '''#!/bin/bash
# top -b -n 1 | while read line; do
#   pid=$(echo "$line" | awk '{print $1}')
#   active_window_id=$(xdotool getactivewindow 2>/dev/null)
#   if [ -n "$active_window_id" ]; then
#     process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
#   fi
#   if echo "$line" | grep -q "nemo " && [[ "$pid" == "$process_id_active" ]]; then
#     exit 0
#   fi
# done
# exit 1
# '''
import subprocess

# Получаем ID активного окна
def get_active_window_pid():
    try:
        # Получаем идентификатор активного окна
        active_window_id = subprocess.run(
            ['xdotool', 'getactivewindow'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        ).stdout.strip()

        if active_window_id:
            # Получаем PID процесса, связанного с активным окном
            process_id_active = subprocess.run(
                ['xdotool', 'getwindowpid', active_window_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ).stdout.strip()
            return int(process_id_active)
        else:
            return 0  # Если нет активного окна
    except Exception as e:
        print(f"Ошибка: {e}")
        return 0

# Получаем командную строку процесса по его PID
def get_process_command_line(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "r") as f:
            cmdline = f.read().replace('\x00', ' ').strip()  # Замена нулевых символов на пробелы
            return cmdline
    except FileNotFoundError:
        return None


while 1:
  time.sleep(3)
  # Пример использования
  pid = get_active_window_pid()
  if pid > 0:
    print(f"PID активного окна: {pid}")
    process_cmd = get_process_command_line(pid)
    if process_cmd:
      print(f"Командная строка процесса: {process_cmd}")
    else:
      print("Процесс не найден.")
  else:
    print("Активное окно не найдено.")
  # region = (1500, 33, 1600, 300)  # Укажите область # Пример области
  # image_path = 'Search button.png'  # Укажите путь к вашему изображению
  # # Проверяем, есть ли изображение на экране
  # location = pyautogui.locateOnScreen(image_path, confidence=0.6, region=region)  # Уровень
  # #res_nemo = subprocess.run(['bash'], input=find_nemo.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  # if location:#Ж and res_nemo:
  #   print("дбль")
  #   break
# input()
# # Путь к изображению
# image_path = "/mnt/807EB5FA7EB5E954/работа/12 01 1989 Егор/DSC01779.JPG"
# # Команда для копирования изображения в буфер обмена
# image_path_utf8 = image_path.encode('utf-8')
#
# # Команда для копирования изображения в буфер обмена
# script = f'cat "{image_path}" | xclip -selection clipboard -t image/png'
#
# # Запускаем скрипт
# result = subprocess.run(['bash', '-c', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# get_process_id_active = f'''#!/bin/bash
# # Получаем идентификатор активного окна
# active_window_id=$(xdotool getactivewindow)
# process_id_active=$(xdotool getwindowpid $active_window_id) # Получаем идентификатор процесса активного окна
# echo "$process_id_active" # Выводим только идентификатор процесса
# exit '''
# result1 = subprocess.run(['bash'], input=get_process_id_active, stdout=subprocess.PIPE, text=True).stdout.strip()
# lines = result1.split('\n')  # Разбиваем вывод по новой строке и извлекаем значения
# process_id_active = int(lines[0].split(': ')[0])


# # Перемещение мыши к координатам (100, 100)
# pyautogui.moveTo(100, 100)
#
# # Нажатие левой кнопки мыши
# pyautogui.click()
#
# # Ввод текста
# pyautogui.typewrite('Hello, world!')
#
# # Нажатие клавиши Enter
# pyautogui.press('enter')
#
# # Скриншот экрана
# screenshot = pyautogui.screenshot()
# screenshot.save('screenshot.png')
#
# # Поиск изображения на экране и нажатие на его центр
# location = pyautogui.locateCenterOnScreen('image.png')
# if location:
#     pyautogui.click(location)
#
# # Задержка на 2 секунды
# time.sleep(2)
#
# # Получение текущих координат мыши
# x, y = pyautogui.position()
# print(f'Текущие координаты мыши: ({x}, {y})')

# Скрипт для получения текста из буфера обмена
# script = '''#!/bin/bash
# xclip -o -selection primary
# '''
# time.sleep(1)  # Задержка
# # Запускаем скрипт и получаем текущий текст из буфера обмена
# current_text = subprocess.run(['bash', '-c', script], stdout=subprocess.PIPE, text=True).stdout.strip()
#
# # Проверяем, отличается ли текущий текст от предыдущего
# if current_text :
#   text= ("```\n{0}\n```\n\n").format(current_text)
#   with open("","a") as f:
#     f.write(text)

# clipboard_text = pyperclip.paste()
# print(clipboard_text)
# import sys
# from PyQt5.QtWidgets import QApplication, QFileDialog
#
#
#
# app = QApplication(sys.argv)
#
# file_dialog = QFileDialog()
# file_dialog.setFileMode(QFileDialog.Directory)
# file_dialog.setOption(QFileDialog.ShowDirsOnly, True)
#
# if file_dialog.exec_():
#   selected_directory = file_dialog.selectedFiles()[0]
#   print(f"Выбранная директория: {selected_directory}")
#   # Здесь вы можете выполнить дальнейшие действия с выбранной директорией
# else:
#   print("Директория не выбрана")
#
# sys.exit(app.exec_())







# # Получаем список всех установленных пакетов
# installed_packages = pkg_resources.working_set
#
# # Проходим по каждому пакету и обновляем его
# for package in installed_packages:
#     name = package.project_name
#     print(f"Обновление пакета: {name}")
#     call("pip install --upgrade " + name, shell=True)

# Очищаем буфер обмена
clean = '''#!/bin/bash
echo -n "" | xclip -i -selection primary
'''
subprocess.run(['bash', '-c', clean])

# Скрипт для получения текста из буфера обмена
script = '''#!/bin/bash
xclip -o -selection primary
'''
previous_text = ""

# while True:  # Бесконечный цикл
#   time.sleep(1)  # Задержка
#   # Запускаем скрипт и получаем текущий текст из буфера обмена
#   current_text = subprocess.run(['bash', '-c', script], stdout=subprocess.PIPE, text=True).stdout.strip()
#
#   # Проверяем, отличается ли текущий текст от предыдущего
#   if current_text and current_text != previous_text:
#       print(current_text)  # Выводим новый текст
#       previous_text = current_text  # Обновляем предыдущий текст
#
#       # Используем f-строку для удобного форматирования
#       copy_script = f'''#!/bin/bash
#       copyq insert 1 "{current_text}"'''
#
#       # Выполняем команду
#       subprocess.run(['bash', '-c', copy_script])

# script = '''#!/bin/bash
#       copyq paste
# '''
# subprocess.run(['bash', '-c', script])
# # Получить данные изображения из буфера обмена
# p = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'], stdout=subprocess.PIPE)
# image_data, _ = p.communicate()
# 
# # Преобразовать данные в изображение
# image = Image.open(io.BytesIO(image_data))
# image.save('clipboard_image.png')

# Установите путь к исполняемому файлу tesseract здесь, если он не в PATH
# pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def preprocess_image(image_path):
  image = Image.open(image_path)

  # Увеличение масштаба изображения
  base_width = 1600  # Рекомендуемая ширина изображения для OCR
  w_percent = (base_width / float(image.size[0]))
  h_size = int((float(image.size[1]) * float(w_percent)))
  # Используйте Image.Resampling.LANCZOS для улучшения качества при увеличении изображения
  image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)

  # Преобразование в черно-белое изображение (бинаризация)
  image = image.convert('L')
  # Применение фильтра для удаления шума
  image = image.filter(ImageFilter.MedianFilter())

  # Увеличение контрастности
  enhancer = ImageEnhance.Contrast(image)
  image = enhancer.enhance(2)

  # Увеличение резкости
  enhancer = ImageEnhance.Sharpness(image)
  image = enhancer.enhance(2)

  return image


# # Путь к изображению
# image_path = '/home/egor/Рабочий стол/HUoHFwVCwz4.jpg'
# image = preprocess_image(image_path)
#
# # Используйте pytesseract для распознавания текста
# text = pytesseract.image_to_string(image, lang='eng')  # Укажите нужный язык
#
# # Выведите распознанный текст
# print(text)

# print("ok")
# input()

KEYS = {"BACKSPACE": "BackSpace",
        "TAB": "Tab", "CLEAR": 0x0C, "RETURN": "Return", "KP_Enter" : "KP_Enter",
        "SHIFT": 0x10, "CONTROL": 0x11, "MENU": 0x12, "PAUSE": 0x13, "CAPITAL": 0x14,
        "KANA": 0x15, "JUNJA": 0x17, "FINAL": 0x18, "KANJI": 0x19, "ESCAPE": 0x1B,
        "CONVERT": 0x1C, "NONCONVERT": 0x1D, "ACCEPT": 0x1E, "MODECHANGE": 0x1F, "SPACE": "space",
        "PRIOR": 0x21, "NEXT": 0x22, "END": "0x23", "HOME": "Home", "LEFT": 0x25, "UP": 0x26,
        "RIGHT": 0x27, "DOWN": 0x28, "SELECT": 0x29, "PRINT": 0x2A, "EXECUTE": 0x2B, "SNAPSHOT": 0x2C,
        "INSERT": 0x2D, "DELETE": "Delete", "HELP": 0x2F,  "LWIN": "Super_L", "RWIN": "Super_R",

        "KEY0": 0, "KEY1": 1, "KEY2": 2, "KEY3": 3, "KEY4": 4, "KEY5": 5, "KEY6": 6,
        "KEY7": 7, "KEY8": 8, "KEY9": 9, "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F",
        "G": "G", "H": "H", "I": "I", "J": "J", "K": "K", "L": "L", "M": "M", "N": "N", "O": "O",
        "P": "P", "Q": "Q", "R": "R", "S": "S", "T": "T", "U": "U", "V": "V", "W": "W", "X": "X", "Y": "Y",
        "Z": "Z",

        "APPS": 0x5D, "SLEEP": 0x5F, "NUMPAD0": 0x60, "NUMPAD1": 79,
        "NUMPAD2": 80, "NUMPAD3": 81, "NUMPAD4": 82, "NUMPAD5": 83, "NUMPAD6": 84, "NUMPAD7": 85,
        "NUMPAD8": 86, "NUMPAD9": 87, "MULTIPLY": 0x6A, "ADD": 78, "SEPARATOR": 0x6C, "SUBTRACT": 0x6D,
        "DECIMAL": 0x6E, "DIVIDE": 0x6F, "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4", "F5": "F5",
        "F6": "F6", "F7": "F7", "F8": "F8", "F9": "F9", "F10": "F10", "F11": "F11", "F12": "F12",

        "F13": 0x7C, "F14": 0x7D, "F15": 0x7E, "F16": 0x7F, "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83, "F21": 0x84,
        "F22": 0x85, "F23": 0x86, "F24": 0x87,"NUMLOCK": "Num_Lock", "SCROLL": "Scroll_Lock",
         "OEM_FJ_JISHO": 0x92, "OEM_FJ_MASSHOU": 0x93,
        "OEM_FJ_TOUROKU": 0x94, "OEM_FJ_LOYA": 0x95, "OEM_FJ_ROYA": 0x96, "LSHIFT": "Shift_L", "RSHIFT": "Shift_R", "LCONTROL": "ISO_Next_Group",
        "RCONTROL": "Control_R",  "LMENU": 0xA4, "RMENU": 0xA5, "BROWSER_BACK": 0xA6,
        "BROWSER_FORWARD": 0xA7, "BROWSER_REFRESH": 0xA8, "BROWSER_STOP": 0xA9, "BROWSER_SEARCH": 0xAA, "BROWSER_FAVORITES": 0xAB, "BROWSER_HOME": 0xAC, "VOLUME_MUTE": 0xAD, "VOLUME_DOWN": 0xAE,
        "VOLUME_UP": 0xAF, "MEDIA_NEXT_TRACK": 0xB0, "MEDIA_PREV_TRACK": 0xB1, "MEDIA_STOP": 0xB2, "MEDIA_PLAY_PAUSE": 0xB3, "LAUNCH_MAIL": 0xB4, "LAUNCH_MEDIA_SELECT": 0xB5, "LAUNCH_APP1": 0xB6,
        "LAUNCH_APP2": 0xB7, "OEM_1": 0xBA, "OEM_PLUS": 0xBB, "OEM_COMMA": 0xBC, "OEM_MINUS": 0xBD, "OEM_PERIOD": 0xBE, " OEM_2": 0xBF, "OEM_3": 0xC0, "ABNT_C1": 0xC1, "ABNT_C2": 0xC2, "OEM_4": 0xDB,
        "OEM_5": 0xDC, "OEM_6": 0xDD, "OEM_7": 0xDE, "OEM_8": 0xDF, "OEM_AX": 0xE1,
        "OEM_102": 0xE2, "ICO_HELP": 0xE3, "PROCESSKEY": 0xE5, "ICO_CLEAR": 0xE6, "PACKET": 0xE7, "OEM_RESET": 0xE9, "OEM_JUMP": 0xEA, "OEM_PA1": 0xEB, "OEM_PA2": 0xEC, "OEM_PA3": 0xED,
        "OEM_WSCTRL": 0xEE, "OEM_CUSEL": 0xEF, "OEM_ATTN": 0xF0, "OEM_FINISH": 0xF1, "OEM_COPY": 0xF2, "OEM_AUTO": 0xF3, "OEM_ENLW": 0xF4, "OEM_BACKTAB": 0xF5, "ATTN": 0xF6, "CRSEL": 0xF7, "EXSEL": 0xF8, " EREOF": 0xF9, "PLAY": 0xFA, "ZOOM": 0xFB, "PA1": 0xFD, " OEM_CLEAR": 0xFE
        }

# print(list(KEYS.keys()))
def get_key_bindings():
  keys=['BACKSPACE', 'TAB', 'CLEAR', 'RETURN', 'KP_Enter', 'SHIFT', 'CONTROL', 'MENU', 'PAUSE', 'CAPITAL', 'KANA', 'JUNJA', 'FINAL', 'KANJI', 'ESCAPE',
        'CONVERT', 'NONCONVERT', 'ACCEPT', 'MODECHANGE', 'SPACE', 'PRIOR', 'NEXT', 'END', 'HOME', 'LEFT', 'UP', 'RIGHT', 'DOWN', 'SELECT', 'PRINT',
        'EXECUTE', 'SNAPSHOT', 'INSERT', 'DELETE', 'HELP', 'LWIN', 'RWIN', 'KEY0', 'KEY1', 'KEY2', 'KEY3', 'KEY4', 'KEY5', 'KEY6', 'KEY7', 'KEY8',
        'KEY9', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
        'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
        'APPS', 'SLEEP', 'NUMPAD0', 'NUMPAD1', 'NUMPAD2', 'NUMPAD3', 'NUMPAD4', 'NUMPAD5', 'NUMPAD6', 'NUMPAD7', 'NUMPAD8', 'NUMPAD9', 'MULTIPLY', 'ADD', 'SEPARATOR', 'SUBTRACT', 'DECIMAL', 'DIVIDE', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19', 'F20', 'F21', 'F22', 'F23', 'F24', 'NUMLOCK', 'SCROLL', 'OEM_FJ_JISHO', 'OEM_FJ_MASSHOU', 'OEM_FJ_TOUROKU', 'OEM_FJ_LOYA', 'OEM_FJ_ROYA', 'LSHIFT', 'RSHIFT', 'LCONTROL', 'RCONTROL', 'LMENU', 'RMENU', 'BROWSER_BACK', 'BROWSER_FORWARD', 'BROWSER_REFRESH', 'BROWSER_STOP', 'BROWSER_SEARCH', 'BROWSER_FAVORITES', 'BROWSER_HOME', 'VOLUME_MUTE', 'VOLUME_DOWN', 'VOLUME_UP', 'MEDIA_NEXT_TRACK', 'MEDIA_PREV_TRACK', 'MEDIA_STOP', 'MEDIA_PLAY_PAUSE', 'LAUNCH_MAIL', 'LAUNCH_MEDIA_SELECT', 'LAUNCH_APP1', 'LAUNCH_APP2', 'OEM_1', 'OEM_PLUS', 'OEM_COMMA', 'OEM_MINUS', 'OEM_PERIOD', ' OEM_2', 'OEM_3', 'ABNT_C1', 'ABNT_C2', 'OEM_4', 'OEM_5', 'OEM_6', 'OEM_7', 'OEM_8', 'OEM_AX', 'OEM_102', 'ICO_HELP', 'PROCESSKEY', 'ICO_CLEAR', 'PACKET', 'OEM_RESET', 'OEM_JUMP', 'OEM_PA1', 'OEM_PA2', 'OEM_PA3', 'OEM_WSCTRL', 'OEM_CUSEL', 'OEM_ATTN', 'OEM_FINISH', 'OEM_COPY', 'OEM_AUTO', 'OEM_ENLW', 'OEM_BACKTAB', 'ATTN', 'CRSEL',
        'EXSEL', ' EREOF', 'PLAY', 'ZOOM', 'PA1', ' OEM_CLEAR']
  # Команда для получения текущих привязок клавиш
  command = "xmodmap -pke"

  # Выполнение команды и сбор стандартного вывода
  # result = subprocess.run(['bash', '-c', command], stdout=subprocess.PIPE, text=True, check=True)
  #
  # # Разделение вывода по строкам и возврат в виде списка
  # keybindings_list = result.stdout.strip().split('\n')
  #
  # # Создание словаря
  # keybindings_dict = {}
  # # Создание словаря где ключ - это строка после слова "keycode" до "=",
  # for line in keybindings_list:
  #   # Проверяем наличие 'keycode' на строке
  #   if 'keycode' in line:
  #     # Разделяем строку на две части: до и после знака "="
  #     line_parts = line.split('=')
  #     key_part = line_parts[0].strip()
  #     value_part = line_parts[1].strip() if len(line_parts) > 1 else ''
  #
  #     # Извлекаем число из строки до "=" и преобразуем в шестнадцатеричное
  #     keycode_number = int(key_part.split()[1])
  #     hex_keycode = hex(keycode_number)
  #
  #     # Если после "=" нет ключевых слов, пропускаем
  #     if not value_part:
  #       continue
  #
  #     # Для каждого ключевого слова после "=" создаем запись в словаре
  #     for key in value_part.split():
  #       keybindings_dict[key] = hex_keycode
  # Пример словаря, который Вы сможете получить:
  # print(keybindings_dict)

  keybindings_dict={'Escape': '0x9', 'NoSymbol': '0xff', '1': '0x57', 'exclam': '0x57', '2': '0xb', 'quotedbl': '0x30', 'at': '0xb', '3': '0x59', 'numerosign': '0xc', 'numbersign': '0x59',
   '4': '0xd', 'semicolon': '0x2f', 'dollar': '0xd', '5': '0xe', 'percent': '0xe', '6': '0xf', 'colon': '0x2f', 'asciicircum': '0xf', '7': '0x4f', 'question': '0x4f',
   'ampersand': '0x10', '8': '0x11', 'asterisk': '0x11', 'U20BD': '0x11', '9': '0x12', 'parenleft': '0xbb', '0': '0x13', 'parenright': '0xbc', 'minus': '0x14',
   'underscore': '0x14', 'equal': '0x15', 'plus': '0x15', 'BackSpace': '0x16', 'Terminate_Server': '0x16', 'Tab': '0x17', 'ISO_Left_Tab': '0x17', 'Cyrillic_shorti': '0x18',
   'Cyrillic_SHORTI': '0x18', 'q': '0x18', 'Q': '0x18', 'Cyrillic_tse': '0x19', 'Cyrillic_TSE': '0x19', 'w': '0x19', 'W': '0x19', 'Cyrillic_u': '0x1a', 'Cyrillic_U': '0x1a',
   'e': '0x1a', 'E': '0x1a', 'Cyrillic_ka': '0x1b', 'Cyrillic_KA': '0x1b', 'r': '0x1b', 'R': '0x1b', 'Cyrillic_ie': '0x1c', 'Cyrillic_IE': '0x1c', 't': '0x1c', 'T': '0x1c',
   'Cyrillic_en': '0x1d', 'Cyrillic_EN': '0x1d', 'y': '0x1d', 'Y': '0x1d', 'Cyrillic_ghe': '0x1e', 'Cyrillic_GHE': '0x1e', 'u': '0x1e', 'U': '0x1e', 'Cyrillic_sha': '0x1f',
   'Cyrillic_SHA': '0x1f', 'i': '0x1f', 'I': '0x1f', 'Cyrillic_shcha': '0x20', 'Cyrillic_SHCHA': '0x20', 'o': '0x20', 'O': '0x20', 'Cyrillic_ze': '0x21', 'Cyrillic_ZE': '0x21',
   'p': '0x21', 'P': '0x21', 'Cyrillic_ha': '0x22', 'Cyrillic_HA': '0x22', 'bracketleft': '0x22', 'braceleft': '0x22', 'Cyrillic_hardsign': '0x23', 'Cyrillic_HARDSIGN': '0x23',
   'bracketright': '0x23', 'braceright': '0x23', 'Return': '0x24', 'ISO_Next_Group': '0x41', 'Cyrillic_ef': '0x26', 'Cyrillic_EF': '0x26', 'a': '0x26', 'A': '0x26',
   'Cyrillic_yeru': '0x27', 'Cyrillic_YERU': '0x27', 's': '0x27', 'S': '0x27', 'Cyrillic_ve': '0x28', 'Cyrillic_VE': '0x28', 'd': '0x28', 'D': '0x28', 'Cyrillic_a': '0x29',
   'Cyrillic_A': '0x29', 'f': '0x29', 'F': '0x29', 'Cyrillic_pe': '0x2a', 'Cyrillic_PE': '0x2a', 'g': '0x2a', 'G': '0x2a', 'Cyrillic_er': '0x2b', 'Cyrillic_ER': '0x2b',
   'h': '0x2b', 'H': '0x2b', 'Cyrillic_o': '0x2c', 'Cyrillic_O': '0x2c', 'j': '0x2c', 'J': '0x2c', 'Cyrillic_el': '0x2d', 'Cyrillic_EL': '0x2d', 'k': '0x2d', 'K': '0x2d',
   'Cyrillic_de': '0x2e', 'Cyrillic_DE': '0x2e', 'l': '0x2e', 'L': '0x2e', 'Cyrillic_zhe': '0x2f', 'Cyrillic_ZHE': '0x2f', 'Cyrillic_e': '0x30', 'Cyrillic_E': '0x30',
   'apostrophe': '0x30', 'Cyrillic_io': '0x31', 'Cyrillic_IO': '0x31', 'grave': '0x31', 'asciitilde': '0x31', 'Shift_L': '0x32', 'backslash': '0x33', 'slash': '0x5e',
   'bar': '0x5e', 'Cyrillic_ya': '0x34', 'Cyrillic_YA': '0x34', 'z': '0x34', 'Z': '0x34', 'Cyrillic_che': '0x35', 'Cyrillic_CHE': '0x35', 'x': '0x35', 'X': '0x35',
   'Cyrillic_es': '0x36', 'Cyrillic_ES': '0x36', 'c': '0x36', 'C': '0x36', 'Cyrillic_em': '0x37', 'Cyrillic_EM': '0x37', 'v': '0x37', 'V': '0x37', 'Cyrillic_i': '0x38',
   'Cyrillic_I': '0x38', 'b': '0x38', 'B': '0x38', 'Cyrillic_te': '0x39', 'Cyrillic_TE': '0x39', 'n': '0x39', 'N': '0x39', 'Cyrillic_softsign': '0x3a', 'Cyrillic_SOFTSIGN': '0x3a',
   'm': '0x3a', 'M': '0x3a', 'Cyrillic_be': '0x3b', 'Cyrillic_BE': '0x3b', 'comma': '0x3d', 'less': '0x3b', 'Cyrillic_yu': '0x3c', 'Cyrillic_YU': '0x3c', 'period': '0x3d',
   'greater': '0x3c', 'Shift_R': '0x3e', 'KP_Multiply': '0x3f', 'XF86ClearGrab': '0x3f', 'Alt_L': '0xcc', 'space': '0x41', 'Caps_Lock': '0x42', 'F1': '0x43',
   'XF86Switch_VT_1': '0x43', 'F2': '0x44', 'XF86Switch_VT_2': '0x44', 'F3': '0x45', 'XF86Switch_VT_3': '0x45', 'F4': '0x46', 'XF86Switch_VT_4': '0x46', 'F5': '0x47',
   'XF86Switch_VT_5': '0x47', 'F6': '0x48', 'XF86Switch_VT_6': '0x48', 'F7': '0x49', 'XF86Switch_VT_7': '0x49', 'F8': '0x4a', 'XF86Switch_VT_8': '0x4a', 'F9': '0x4b',
   'XF86Switch_VT_9': '0x4b', 'F10': '0x4c', 'XF86Switch_VT_10': '0x4c', 'Num_Lock': '0x4d', 'Scroll_Lock': '0x4e', 'KP_Up': '0x50', 'KP_8': '0x50', 'KP_Prior': '0x51',
   'KP_9': '0x51', 'KP_Subtract': '0x52', 'XF86Prev_VMode': '0x52', 'KP_Left': '0x53', 'KP_4': '0x53', 'KP_Begin': '0x54', 'KP_5': '0x54', 'KP_Right': '0x55', 'KP_6': '0x55',
   'KP_Add': '0x56', 'XF86Next_VMode': '0x56', 'KP_Down': '0x58', 'KP_2': '0x58', 'KP_Insert': '0x5a', 'KP_0': '0x5a', 'Delete': '0x77', 'ISO_Level3_Shift': '0x5c',
   'brokenbar': '0x5e', 'F11': '0x5f', 'XF86Switch_VT_11': '0x5f', 'F12': '0x60', 'XF86Switch_VT_12': '0x60', 'Katakana': '0x62', 'Hiragana': '0x63', 'Henkan_Mode': '0x64',
   'Hiragana_Katakana': '0x65', 'Muhenkan': '0x66', 'KP_Enter': '0x68', 'Control_R': '0x69', 'KP_Divide': '0x6a', 'XF86Ungrab': '0x6a', 'Print': '0xda', 'Sys_Req': '0x6b',
   'Alt_R': '0x6c', 'Meta_R': '0x6c', 'Linefeed': '0x6d', 'Home': '0x6e', 'Up': '0x6f', 'Prior': '0x70', 'Left': '0x71', 'Right': '0x72', 'End': '0x73', 'Down': '0x74',
   'Next': '0x75', 'Insert': '0x76', 'XF86AudioMute': '0x79', 'XF86AudioLowerVolume': '0x7a', 'XF86AudioRaiseVolume': '0x7b', 'XF86PowerOff': '0x7c', 'KP_Equal': '0x7d',
   'plusminus': '0x7e', 'Pause': '0x7f', 'Break': '0x7f', 'XF86LaunchA': '0x80', 'KP_Decimal': '0x81', 'Hangul': '0x82', 'Hangul_Hanja': '0x83', 'Super_L': '0xce',
   'Super_R': '0x86', 'Menu': '0x87', 'Cancel': '0xe7', 'Redo': '0xbe', 'SunProps': '0x8a', 'Undo': '0x8b', 'SunFront': '0x8c', 'XF86Copy': '0x8d', 'XF86Open': '0x8e',
   'XF86Paste': '0x8f', 'Find': '0x90', 'XF86Cut': '0x91', 'Help': '0x92', 'XF86MenuKB': '0x93', 'XF86Calculator': '0x94', 'XF86Sleep': '0x96', 'XF86WakeUp': '0x97',
   'XF86Explorer': '0x98', 'XF86Send': '0xef', 'XF86Xfer': '0x9b', 'XF86Launch1': '0x9c', 'XF86Launch2': '0x9d', 'XF86WWW': '0x9e', 'XF86DOS': '0x9f', 'XF86ScreenSaver': '0xa0',
   'XF86RotateWindows': '0xa1', 'XF86TaskPane': '0xa2', 'XF86Mail': '0xdf', 'XF86Favorites': '0xa4', 'XF86MyComputer': '0xa5', 'XF86Back': '0xa6', 'XF86Forward': '0xa7',
   'XF86Eject': '0xae', 'XF86AudioNext': '0xab', 'XF86AudioPlay': '0xd7', 'XF86AudioPause': '0xd1', 'XF86AudioPrev': '0xad', 'XF86AudioStop': '0xae', 'XF86AudioRecord': '0xaf',
   'XF86AudioRewind': '0xb0', 'XF86Phone': '0xb1', 'XF86Tools': '0xbf', 'XF86HomePage': '0xb4', 'XF86Reload': '0xb5', 'XF86Close': '0xd6', 'XF86ScrollUp': '0xb9',
   'XF86ScrollDown': '0xba', 'XF86New': '0xbd', 'XF86Launch5': '0xc0', 'XF86Launch6': '0xc1', 'XF86Launch7': '0xc2', 'XF86Launch8': '0xc3', 'XF86Launch9': '0xc4',
   'XF86AudioMicMute': '0xc6', 'XF86TouchpadToggle': '0xc7', 'XF86TouchpadOn': '0xc8', 'XF86TouchpadOff': '0xc9', 'Mode_switch': '0xcb', 'Meta_L': '0xcd', 'Hyper_L': '0xcf',
   'XF86Launch3': '0xd2', 'XF86Launch4': '0xd3', 'XF86LaunchB': '0xd4', 'XF86Suspend': '0xd5', 'XF86AudioForward': '0xd8', 'XF86WebCam': '0xdc', 'XF86AudioPreset': '0xdd',
   'XF86Messenger': '0xe0', 'XF86Search': '0xe1', 'XF86Go': '0xe2', 'XF86Finance': '0xe3', 'XF86Game': '0xe4', 'XF86Shop': '0xe5', 'XF86MonBrightnessDown': '0xe8',
   'XF86MonBrightnessUp': '0xe9', 'XF86AudioMedia': '0xea', 'XF86Display': '0xeb', 'XF86KbdLightOnOff': '0xec', 'XF86KbdBrightnessDown': '0xed', 'XF86KbdBrightnessUp': '0xee',
   'XF86Reply': '0xf0', 'XF86MailForward': '0xf1', 'XF86Save': '0xf2', 'XF86Documents': '0xf3', 'XF86Battery': '0xf4', 'XF86Bluetooth': '0xf5', 'XF86WLAN': '0xf6',
   'XF86MonBrightnessCycle': '0xfb', 'XF86WWAN': '0xfe', 'XF86RFKill': '0xff'}



  # print(keybindings_list)
  # # Регулярное выражение для извлечения части строки после 'keycode <число> ='
  # keycode_pattern = re.compile(r'^keycode \d+ = (.+)')
  # 
  # # Фильтрация и извлечение нужной части строки
  # filtered_keybindings_list = []  # Создание пустого списка для отфильтрованных привязок клавиш
  # 
  # for line in keybindings_list:
  #   if keycode_pattern.match(line):
  #     # Разбиение строки на список символов
  #     symbols = keycode_pattern.match(line).group(1).split()
  #     # Удаление 'NoSymbol' и пустых строк
  #     symbols = [symbol for symbol in symbols if symbol not in ['', 'NoSymbol']]
  #     # Удаление дублирующих символов
  #     symbols = list(set(symbols))
  #     # Добавление обработанных символов в общий список
  #     filtered_keybindings_list.extend(symbols)
  # # print(filtered_keybindings_list)
  # filtered_keybindings_list.append("NoSymbol")
  # all_keys_dict = {key: None for key in keys}
  # filtered_keys_dict = {key: None for key in filtered_keybindings_list}
  # 
  # all_keys_dict.update(filtered_keys_dict)
  symbol_map = {'!': 'exclam', '@': 'at', '#': 'numbersign', '$': 'dollar', '%': 'percent', '^': 'asciicircum',
                '&': 'ampersand', '*': 'asterisk', '(': 'parenleft', ')': 'parenright', '-': 'minus', '+': 'plus', '=': 'equal',
                '[': 'bracketleft', ']': 'bracketright', '{': 'braceleft', '}': 'braceright', '|': 'bar', '\\': 'backslash',
                 '/': 'slash', '.': 'period', ',': 'comma', '"': 'quotedbl', "'": 'apostrophe'}
  # print(symbol_map)
  # print(all_keys_dict)
  # # Извлечение первых пяти элементов
  # keybindings = filtered_keybindings_list[:5]
  # return keybindings

# get_key_bindings()

backup_script_path = f'''#!/bin/bash
current_user=$(whoami);
echo $current_user
exit;# Завершаем выполнение скрипта
'''

# Вызываем скрипт
user = subprocess.run(['bash'], input=backup_script_path , stdout=subprocess.PIPE, text=True).stdout.strip()

def check_current_active_window():# Получаем идентификатор активного окна

 try:
  a = []
  result = str(subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout)  # print(result)
  active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
  process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
  process_id = int(process_id)
  for line in result.split("\n"):
   user_name = ' '.join(line.split()[0]).replace(" ", "")
   process_name = ' '.join(line.split()[10:])
   if user_name=="egor":
     filename = process_name.split('\\')[-1]
     pid_id = int(line.split()[1])  # или используйте другой индекс, если нужны другие данные
     print(process_name)
     # if '.exe' in filename and process_id == pid_id:
     #   process_name = re.findall(r'"([^"]*)"', process_name)[0]
       # print(line)    # print(process_name)     # print(user_name)       # print(process_id)       # print(pid_id)
       # a.append({'dir': process_name, 'pid': pid_id, 'exe': filename})# нашли pid активного  окна
       # return True# активного окна

  return False
 except :
    pass

# while 1:
#   time.sleep(3)
#   if check_current_active_window():
#     print("ok")
    # pass










# print(sys.version)
# print(sys.prefix)
# print(sys.executable)

# import keyboard as keybo
# from pynput.keyboard import Controller
#
# import psutil
#
# import requests
#
# from spellchecker import SpellChecker
# import pymorphy2
# from language_tool_python import LanguageTool


# def check_spelling(text):
#   morph = pymorphy2.MorphAnalyzer()
#   words = text.split()
#   corrected_words = [morph.parse(word)[0].normal_form for word in words]
#   text1 = ' '.join(corrected_words)
#   spell = SpellChecker(language='ru')
#   words = text1.split()
#   corrected_words = [spell.correction(word) for word in words]
#   text1 = ' '.join(corrected_words)
#   tool = LanguageTool('ru')
#
# # Отправляем текст на сервер для проверки
#   matches = tool.check(text1)
# # Выводим исправления
#   for match in matches:
#     print(match)

import g4f
# import subprocess
#
# # Получение списка установленных пакетов
# result = subprocess.run(['pip', 'list', '--format=freeze'], capture_output=True, text=True)
# installed_packages = result.stdout.split('\n')
#
# # Обновление каждого пакета
# for package in installed_packages:
#     package_name = package.split('==')[0]
#     print(package_name)
#     subprocess.run(['pip', 'install', '--upgrade', package_name])
# g4f.debug.logging = True  # Enable logging
# g4f.check_version = False  # Disable automatic version checking
# print(g4f.version) # Check version
# print(g4f.Provider.Ails.params) # Supported args
#
# # Automatic selection of provider
#
# # Streamed completion
# response = g4f.ChatCompletion.create(
#  model="gpt-3.5-turbo",
#  messages=[{"role": "user", "content": "Hello"}],
#  stream=True,
# )
#
# for message in response:
#  print(message, flush=True, end='')


# text = "хороший погода." \
#        "."
# text1=check_spelling(text)
# print(text1)
# class save_word:
#    def __init__(self):
#      self.key = None
#    def save_b(self, key1):
#       self.key =key1
#
#    def return_word(self):
#       return self.key
# cli= save_word()
# import xerox
# def check_clipboard():
#  while 1:
#   try:
#     time.sleep(1)
#     # Получить текст из буфера обмена
#     clipboard_text = xerox.paste()
#     #subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'])
#     #pyperclip.paste()#
#     if clipboard_text and clipboard_text != cli.return_word():
#       cli.save_b(clipboard_text)
#       print("copy")
#       print(clipboard_text)
#     if not clipboard_text and clipboard_text !=cli.return_word() :
#       print("Буфер обмена обновлен")
#
#       # Установить текст в буфер обмена
#       xerox.copy(cli.return_word())
#       # pyperclip.copy(cli.return_word())
#         #
#     #   print("Буфер обмена содержит текст:", clipboard_text)
#   except :
#     continue
#     print("Ошибка при получении содержимого буфера обмена")
#
#
# check_clipboard()






# key='KP_Enter'
# press_release = '''#!/bin/bash
# xte 'keydown {}' 'keyup {}'
# '''
# for key in text:
#   time.sleep(0.5)
#   print(key)
# subprocess.call(['bash', '-c', press_release.format(key, key)])
# class work_key:
#   def __init__(self):
#    self.keys_list = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'a', 's', 'd', 'f', 'g',
#                 'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'BackSpace', 'Tab', 'Return',
#                 'Escape', 'Delete', 'Home', 'End', 'Page_Up', 'Page_Down', 'F1', 'Up', 'Down', 'Left',
#                 'Right', 'Control_R', 'Shift_L', 'Shift_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R',
#                 'Caps_Lock', 'Num_Lock', 'Scroll_Lock', 'space','F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7',
#                 'F8', 'F9', 'F10', 'F11', 'F12']
#
#   def key_press(self, app):
#     self.path_current_app = app
#
#   def key_release(self):  # Получить путь текущего окна.
#     return self.path_current_app
#
#   def key_press_release(self, key):  #
#
#     press_release = '''#!/bin/bash
#     xte 'keydown {}' 'keyup {}'
#     '''
#     if key in self.keys_list:
#      subprocess.call(['bash', '-c', press_release.format(key, key)])

# press_release = '''#!/bin/bash
# xte 'keydown {}' 'keyup {}'
# '''
# for key in text:
#   time.sleep(0.5)
#   print(key)
#   subprocess.call(['bash', '-c', press_release.format(key, key)])
# Backspace = f'''#!/bin/bash
# xte 'keydown BackSpace' 'keyup BackSpace'
# '''



# def get_path_current_active():# Получаем идентификатор активного окна
#  while 1:
#   time.sleep(4)
#   try:
#    active_window_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode().strip()
#    # Получаем идентификатор процесса, связанного с активным окном
#    process_id = subprocess.check_output(['xdotool', 'getwindowpid', active_window_id]).decode().strip()
#    process_list = [p.info for p in psutil.process_iter(attrs=['name', 'pid', 'exe'])]
#    for process in process_list:
#     # print(str(process['exe']))
#     if int(process_id)== int(process['pid']):
#      r= str(process['exe'])
#      print(r)
#     #  return r
#   except :
#     pass
#
# get_path_current_active()

# # Получаем имя процесса по его идентификатору
# process_name = subprocess.check_output(['ps', '-p', process_id, '-o', 'comm=']).decode().strip()
#
# print("Активное окно процесса:", process_name)




# layout = {'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's',
#             'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm', 'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>',
#             ',': '?', 'Ё': '~'}
#
# liter = 'й'  # Replace 'й' with the desired key
#
# print(liter)
# print(layout[liter])



# d={
#     'q': 'й',
#     'w': 'ц',
#     'e': 'у',
#     'r': 'к',
#     't': 'е',
#     'y': 'н',
#     'u': 'г',
#     'i': 'ш',
#     'o': 'щ',
#     'p': 'з',
#     '[': 'х',
#     ']': 'ъ',
#     'a': 'ф',
#     's': 'ы',
#     'd': 'в',
#     'f': 'а',
#     'g': 'п',
#     'h': 'р',
#     'j': 'о',
#     'k': 'л',
#     'l': 'д',
#     ';': 'ж',
#     "'": 'э',
#     'z': 'я',
#     'x': 'ч',
#     'c': 'с',
#     'v': 'м',
#     'b': 'и',
#     'n': 'т',
#     'm': 'ь',
#     ',': 'б',
#     '.': 'ю',
#     '/': '.',
#     '`': 'ё',
#     'Q': 'Й',
#     'W': 'Ц',
#     'E': 'У',
#     'R': 'К',
#     'T': 'Е',
#     'Y': 'Н',
#     'U': 'Г',
#     'I': 'Ш',
#     'O': 'Щ',
#     'P': 'З',
#     '{': 'Х',
#     '}': 'Ъ',
#     'A': 'Ф',
#     'S': 'Ы',
#     'D': 'В',
#     'F': 'А',
#     'G': 'П',
#     'H': 'Р',
#     'J': 'О',
#     'K': 'Л',
#     'L': 'Д',
#     ':': 'Ж',
#     '"': 'Э',
#     'Z': 'Я',
#     'X': 'Ч',
#     'C': 'С',
#     'V': 'М',
#     'B': 'И',
#     'N': 'Т',
#     'M': 'Ь',
#     '<': 'Б',
#     '>': 'Ю',
#     '?': ',',
#     '~': 'Ё'
# }
#
# flipped_dict = {v: k for k, v in d.items()}
#
#
# print(flipped_dict)
# input()
# layout = dict(
#   zip(map('''qwertyuiop[]asdfghjkl;'zxcvbnm,./`QWERTYUIOP{}ASDFGHJKL:"ZXCVBNM<>?~''',
#           '''йцукенгшщзхъфывапролджэячсмитьбю.ёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё'''))
# )
#
# print(layout)
# a={}
# text="АаБбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя AаВвСсDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrTtUuVvWwXxYyZz123456789!@#$%^&*()-+=[{}|\/.," \
#      "?|\'\"\""
# number=0
# for i in text:
#   a[number]=i
#   number= number+1
# print(a)

keys_codes={0: 'А', 1: 'а', 2: 'Б', 3: 'б', 4: 'В', 5: 'в', 6: 'Г', 7: 'г', 8: 'Д', 9: 'д', 10: 'Е', 11: 'е', 12: 'Ё', 13: 'ё',
            14: 'Ж', 15: 'ж', 16: 'З', 17: 'з', 18: 'И', 19: 'и', 20: 'Й', 21: 'й', 22: 'К', 23: 'к', 24: 'Л', 25: 'л', 26: 'М',
            27: 'м', 28: 'Н', 29: 'н', 30: 'О', 31: 'о', 32: 'П', 33: 'п', 34: 'Р', 35: 'р', 36: 'С', 37: 'с', 38: 'Т', 39: 'т',
            40: 'У', 41: 'у', 42: 'Ф', 43: 'ф', 44: 'Х', 45: 'х', 46: 'Ц', 47: 'ц', 48: 'Ч', 49: 'ч', 50: 'Ш', 51: 'ш', 52: 'Щ',
            53: 'щ', 54: 'Ъ', 55: 'ъ', 56: 'Ы', 57: 'ы', 58: 'Ь', 59: 'ь', 60: 'Э', 61: 'э', 62: 'Ю', 63: 'ю', 64: 'Я', 65: 'я',
            66: ' ', 67: 'A', 68: 'а', 69: 'В', 70: 'в', 71: 'С', 72: 'с', 73: 'D', 74: 'd', 75: 'E', 76: 'e', 77: 'F', 78: 'f',
            79: 'G', 80: 'g', 81: 'H', 82: 'h', 83: 'I', 84: 'i', 85: 'J', 86: 'j', 87: 'K', 88: 'k', 89: 'L', 90: 'l', 91: 'M',
            92: 'm', 93: 'N', 94: 'n', 95: 'O', 96: 'o', 97: 'P', 98: 'p', 99: 'Q', 100: 'q', 101: 'R', 102: 'r', 103: 'T',
            104: 't', 105: 'U', 106: 'u', 107: 'V', 108: 'v', 109: 'W', 110: 'w', 111: 'X', 112: 'x', 113: 'Y', 114: 'y', 115: 'Z',
            116: 'z', 117: '1', 118: '2', 119: '3', 120: '4', 121: '5', 122: '6', 123: '7', 124: '8', 125: '9', 126: '!', 127: '@',
            128: '#', 129: '$', 130: '%', 131: '^', 132: '&', 133: '*', 134: '(', 135: ')', 136: '-', 137: '+', 138: '=', 139: '[',
            140: '{', 141: '}', 142: '|', 143: '\\', 144: '/', 145: '.', 146: ',', 147: '?', 148: '|', 149: '"', 150: ';', 151: ':'}
from pynput.keyboard import Key, Controller
from pynput import *

from tkinter import *
import threading

# d  = {"ол" : "Ольга Александровна", "нг":"Новый год"}
# longest_key_length = len(max(d.keys(), key=len))
# print(longest_key_length)

class save_key:
   def __init__(self):
     self.key = ""
     self.swit=None
   def update(self, key1):
      self.key =str(self.key)+str(key1).replace("'","")

   def return_key(self):
      return self.key

   def backspace(self):
     self.key = str(self.key[1:])
     return self.key
k=save_key()
def show_tooltip(self, event):
  x, y, _, _ = self.widget.bbox("insert")
  x += self.widget.winfo_rootx() + 25
  y += self.widget.winfo_rooty() + 25

  self.tooltip = root.Toplevel(self.widget)
  self.tooltip.wm_overrideredirect(True)
  self.tooltip.wm_geometry(f"+{x}+{y}")

  label = root.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
  label.pack()

class ToolTip(object):
  def __init__(self, widget):
   self.widget = widget
   self.tipwindow = None
   self.id = None
   self.x = self.y = 0

  def showtip(self, text):
   "Display text in tooltip window"
   self.text = text
   if self.tipwindow or not self.text:
    return
   x, y, cx, cy = self.widget.bbox("insert")
   x = x + self.widget.winfo_rootx() + 27
   y = y + cy + self.widget.winfo_rooty() +7
   self.tipwindow = tw = Toplevel(self.widget)
   tw.wm_overrideredirect(1)
   tw.wm_geometry("+%d+%d" % (x, y))
   label = Label(tw, text=self.text, justify=LEFT,
                      background="#ffffe0", relief=SOLID, borderwidth=1,
                      font=("tahoma", "10", "normal"))
   label.pack(ipadx=1)

   def hidetip(self):
    tw = self.tipwindow
    self.tipwindow = None
    if tw:
      tw.destroy()

def CreateToolTip(widget, text):
    toolTip = ToolTip(widget)
    toolTip.showtip(text)

def on_release(key):
 pass

def hide_tooltip(self, event):
  if self.tooltip:
    self.tooltip.destroy()
    self.tooltip = None
global root,event
def on_press1(key):
  key = str(key).replace(" ", "")
  if key == "Key.space":
     print("unkey")
     hide_tooltip(root, event)  # Call hide_tooltip function with the appropriate arguments
     return True

def start1():
    listener = keyboard.Listener(
        on_press=on_press1,
        on_release=on_release
    )
    listener.start()

def press_key(res):
    k.swit = True
    print(res)
    root = Tk()
    root.withdraw()
    CreateToolTip(root, text=res)
    t2 = threading.Thread(target=start1, args=())
    t2.start()
    root.mainloop()
def update_word(key):# обновить слово
  k.update(str(key))# сложить слово
  key = k.return_key()# вернуть слово
  keys_words=[]
  # for key1, val in d.items():
  #  if len(key)>longest_key_length:# если оно максимальной длины.
  #   key = k.backspace()# Удалить первую букву в слове
  #   # print(key)
  #  if str(key) == str(key1):#
  #   res=(str(d[key1]))
  #   press_key(res)
def on_press(key):#обработчик клави.
 key=str(key).replace(" ","") # print(key)
 global timestamp # print(time.time()- timestamp )
 try:
  if key=='Key.ctrl_l' or key=='\' \'' or key=='Key.shift_l'or key=='.' or key==',' or key=='Key.shift_r'\
  or  key=='\'\'' or key =="Key.ctrl_r" or key == "Key.delete"or key =="Key.right"or key =="Key.left"\
  or key =="Key.down" or key =="Key.up" or key =="Key.delete" or key == "Key.space"or key=='\'.\''\
  or key=='\',\''or key=='\\\\':
   # print("unkey")
   return True

  if key != 'Key.ctrl_l' and key !="Key.caps_lock" and key !="Key.tab" and key !="Key.alt_l"\
   and key !="Key.ctrl_r"and key !="Key.alt_r" and key != "Key.shift_r"  and key !="Key.shift" \
   and key !="Key.shift" and key != "Key.tab" and key !="Key.backspace"and key !="Key.down"\
   and key !="Key.up" and key !="Key.left" and key !="Key.right" and key !="Key.enter"\
   and key !="Key.space" and key !="Key.backspace" and key !="Key.cmd"and key !="Key.delete"\
   and key !="<96>" and key !="<97>" and key !="<98>" and key !="<99>" and key !="<100>"\
   and key !="<101>" and key !="<102>" and key !="<103>" and key !="<104>" and key !="<105>" \
   and key !="+" and key !="-" and key !="*" and key !="/" and key != "Key.num_lock" \
   and key !="Key.page_down"and key != "Key.page_up" and key != "Key.end" and key != "Key.home" \
   and key !="Key.delete" and key !="Key.insert"and key !='\'/\'' and key !='\'\ \''\
   and key !='\'.\'' and key != "<65032>" and key !="\'1\'" and key !="\'2\'" and key !="\'3\'"\
   and key !="\'4\'" and key !="\'5\'" and key !="\'6\'" and key !="\'7\'" and key !="\'8\'" \
   and key !="\'9\'" and key !="<65437>":  # print(key)
   key= update_word(key)# обновить слово   print(key)
   return True

 except Exception as ex:
    print(ex)
    pass

# listener = keyboard.Listener(
#         on_press=on_press,
#         on_release=on_release)
# listener.start()
#
# while 1:
#     pass






# import sounddevice as sd
#
# # Проверка наличия звука через микрофон
# def callback(indata, frames, time, status):
#     if any(indata):
#         print("True")
#     else:
#         print("False")
#
# # Проверка и вывод результата
# while 1:
#     with sd.InputStream(callback=callback):
#         sd.sleep(10000)

# import keyboard as keybord_from
# time.sleep(9)
# print("jgfc")
# for i in range(79, 87):
#     print(i)
#     time.sleep(0.8)
#     keybord_from.press(i)
#     keybord_from.release(i)
#
#
#


# import psutil
#
# # Получить список всех PID процессов
# pid_list = psutil.pids()
#
# # Вывести информацию о каждом процессе
# for pid in pid_list:
#  try:
#    process = psutil.Process(pid)
#    process_list = [i for i in process.cmdline() if 'Mouse_setting_control_for_buttons_python_for_linux.py' in i]
#    if len(process_list)>2:
#     return False
#    else:
#     return True
#  except psutil.NoSuchProcess:
#    pass
#

# script = '''#!/bin/bash
# ids=$(xinput list | grep -Ei ".*mouse.*id=[0-9]+" | grep -oE "id=[0-9]+" | cut -c 4-)
# for id in $ids
# do
#     echo "$id"
# done
# '''
#
# output = subprocess.check_output(['bash', '-c', script])
# id_list = list(map(int, output.decode().split()))
# print(id_list)

data = "list for replacements.json"  # файл настроек.
# data = data.replace(' ', '\ ')
# if os.path.exists(data):  # есть ли этот файл.
#   print("kmjhb")
#   with open(data, encoding="cp1251") as json_file:  # загрузка настроек из файла.
#     res = json.load(json_file)  # проходимся по каждому элементу словаря
#     print(res)
# list_for_block_button=[ecodes.BTN_EXTRA]
# if list_for_block_button== list_for_block_button1:
# print(os.geteuid() )
# input()
# filename = str("yandex")
# d={}
# for root, dirs, files in os.walk("/"):
#  s = str(root)
#  if s.startswith("/mnt/"):
#    continue
#  else:
#   # print(root)
#   for f in dirs:
#    # print(f)
#    if str(filename) in str(f):
#     path_file=str(os.path.join(root, f))
#     d[path_file]=f
#     # break
# print(d)

# adress={'/.yandex_update': '.yandex_update', '/usr/share/doc/yandex-browser-stable': 'yandex-browser-stable', '/opt/ytest.pyandex': 'yandex',
#  '/opt/yandex/browser/video_translation/_metadata/yandex': 'yandex', '/home/egor/.yandex': '.yandex',
#  '/home/egor/.cache/yandex-browser': 'yandex-browser', '/home/egor/.config/yandex-browser': 'yandex-browser',
# }
# os.chdir("/")
# subprocess.run(["bash", "-c", "tar cvzf folders.tar.gz folder1"], stdout=subprocess.PIPE)
# for k,v in adress.items():
 # res = subprocess.run(["tar", "cvzf", "backup.tar.gz", "--ignore-empty-directories", "-C", k],
 #                     stdout=subprocess.PIPE)
 # print(res)


      # break
    # break

# finally:
#    pass
   # driver.close()
   # driver.quit()



# import evdev, uinput
# from evdev import InputDevice, ecodes

   # option.add_argument("--incognito")
   # option.add_argument("--remote-debugging-port=9222")
   # Создание сеанса веб-драйвера с указанием уникального идентификатора контекста
#    context_id = str("d251a41c-01b2-4338-944a-ebc20bb4ae66")# Генерация уникального идентификатора контекста
   # driver.session_id = context_id
   # print(type(context_id))
   # driver = webdriver.Chrome(options=option)

#
# events = ( uinput.KEY_LEFTCTRL,
#     uinput.KEY_A)
# global device
# event_devices = 0
# number=0
# for device in glob.glob("/dev/input/event*"):
#     event_devices += 1
# script = '''#!/bin/bash
# gnome-terminal -- bash -c 'echo "1" | sudo -S chown root:input /dev/uinput;
# sudo chmod g+rw /dev/uinput;
# sudo usermod -a -G input egor;
# sudo chown root:input /dev/uinput;
# for i in {0..event_devices}
# do
#     sudo chmod a+rw /dev/input/event$i
# done
# '
# '''
# subprocess.call(['bash', '-c', script])
# devices = []
# for i in range(0,event_devices):
#  dev1 = InputDevice('/dev/input/event{}'.format(i))
#  s=str(dev1.name) # print(i)
#
#  if s== "Logitech Logitech USB Keyboard":
#   number=i
#   break
# dev = InputDevice('/dev/input/event{}'.format(number))# открываем устройство клавиатуры
# device = uinput.Device(events)# подписываемся на события # dev.grab()








# print("АаБбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФф"
#                    "ХхЦцЧч ШшЩщЪъЫыЬь ЭэЮюЯя AаВвСсDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrTtUuVvWwXxYyZz")
# test="Вот текст, в котором есть все буквы английского и русского алфавитов и который несёт какой-то смысл текст, в" \
#      "A jumbled wizzard slyly used hexing potions. Без забот бродил по полю ёж, щипля травку и пчёл." \
#      "Ёж остановился, и ветер воет во тьме, пока луна светит над ёжом одиноким.Вдруг крик взлетел высоко в небеса! " \
#      "Ёж увидел фею, нимфу во сне. Quickly jumped the hedgehog to see the fairy. Она была мала, как звук колокольчика," \
#      " но о, так светилась, что озарила всё вокруг!Крохотная фея озарила ёжа своим светом и улыбнулась ему. И" \
#      " ёж почувствовал себя счастливым. В этом тексте есть история о еже, который встретил фею. Повествование переходит " \
#      "с английского на русский язык, чтобы передать атмосферу. Текст содержит все буквы русского и английского алфавитов."
# input()
# press_keys(device, test)
# input()
# press_keys(device, test)
# input()