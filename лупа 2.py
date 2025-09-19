import tkinter as tk
from PIL import Image, ImageTk
from pynput import keyboard
import subprocess, time

window = 140

class ScreenMagnifier:
 def __init__(self, root):
   self.root = root
   self.scale = 1.0
   self.window_width = window
   self.window_height = window
   self.x_center = 960  # Начальная позиция центра
   self.y_center = 540
   self.target_workspace = 1  # Второй рабочий стол (0-based)
 
   # Настройка главного окна
   self.root.title("Экранная Лупа")
   self.root.overrideredirect(True)
   self.root.geometry(f"{self.window_width}x{self.window_height}+750+500")
   self.root.configure(bg='black')
 
   # Создаем холст для изображения
   self.canvas = tk.Canvas(root, width=self.window_width, height=self.window_height, highlightthickness=0, bd=0)
   self.canvas.pack()
 
   # Слушатель клавиатуры с использованием pynput
   self.listener = keyboard.Listener(on_press=self.on_key_press)
   self.listener.start()
 
   # Запуск обновления
   self.update_image()
 
 def on_key_press(self, key):# Обработка нажатий клавиш
   step = 10
   scale_step = 0.25
 
   # Перемещение
   if key == keyboard.Key.up:
       self.y_center -= step
   elif key == keyboard.Key.down:
       self.y_center += step
   elif key == keyboard.Key.left:
       self.x_center -= step
   elif key == keyboard.Key.right:
       self.x_center += step
 
   # Масштабирование и выбор рабочего пространства
   try:
       if key.char == '+':
           self.scale += scale_step
       if key.char == '-':
           self.scale = max(0.5, self.scale - scale_step)
       if key.char == '1':
           self.target_workspace = 0
       if key.char == '2':
           self.target_workspace = 1
   except AttributeError:
       pass
 
   # Корректировка границ
   screen = (1920, 1080)  # Замените на ваше разрешение экрана (xdpyinfo | grep dimensions)
   half_w = (self.window_width / self.scale) / 2
   half_h = (self.window_height / self.scale) / 2
   self.x_center = max(half_w, min(self.x_center, screen[0] - half_w))
   self.y_center = max(half_h, min(self.y_center, screen[1] - half_h))
 
 def update_image(self):# Обновление изображения с окна weston"""
   # Рассчет области захвата
   capture_w = int(self.window_width / self.scale)
   capture_h = int(self.window_height / self.scale)
   x = int(self.x_center - capture_w // 2)
   y = int(self.y_center - capture_h // 2)
 
   # Захват с окна weston
   try:   # Найти окно weston
       window_id = subprocess.check_output(["xdotool", "search", "--class", "weston"]).decode().strip().split('\n')[0]
       subprocess.run(["maim", "-i", window_id, "-g", f"{capture_w}x{capture_h}+{x}+{y}", "temp.png"])
       img = Image.open("temp.png").resize(  (self.window_width, self.window_height),
           Image.LANCZOS       )
   except (subprocess.CalledProcessError, FileNotFoundError) as e:
       print(f"Ошибка: weston или maim не настроены: {e}")
       img = Image.new("RGB", (self.window_width, self.window_height), "black")
 
   # Отображение на холсте
   self.photo = ImageTk.PhotoImage(img)
   self.canvas.delete("all")
   self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
 
   # Планирование следующего обновления
   self.root.after(10, self.update_image)
 
 def quit(self):# Закрытие приложения"""
   self.listener.stop()
   self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenMagnifier(root)
    root.mainloop()