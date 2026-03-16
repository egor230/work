import threading
import time
from pynput import keyboard

# Переменные для управления состоянием
is_active = False
key_to_press = 'e'  # Кнопка для быстрого нажатия
toggle_key = 'm'  # Кнопка-переключатель


def press_button():
 """Функция, которая имитирует нажатия в отдельном потоке."""
 controller = keyboard.Controller()
 while True:
  if is_active:
   controller.press(key_to_press)
   controller.release(key_to_press)
   # Задержка 0.05 секунды (20 нажатий в секунду)
   time.sleep(0.05)
   controller.release(key_to_press)
  else:
   # Небольшая пауза, когда скрипт в режиме ожидания
   time.sleep(0.1)


def on_press(key):
 """Отслеживание нажатия клавиши M."""
 global is_active
 try:
  # Твой участок кода (сохранен)
  key = str(key).replace(" ", "").replace("key", "")
  if "m" in key or "ь" in key:
   is_active = not is_active
   status = "ЗАПУЩЕНО" if is_active else "ОСТАНОВЛЕНО"
   print(f"Статус: {status}")
   # Запуск потока для кликера
   click_thread = threading.Thread(target=press_button, daemon=True)
   click_thread.start()
   time.sleep(1.3)  # Небольшая задержка чтобы избежать множественных срабатываний
 except AttributeError:
  pass

# Запуск прослушивания клавиатуры
print(f"Скрипт готов. Нажмите '{toggle_key}' для включения/выключения спама '{key_to_press}'.")
with keyboard.Listener(on_press=on_press) as listener:
 listener.join()