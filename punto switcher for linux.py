from pynput.keyboard import Key, Controller, Listener
from pynput import keyboard
from tkinter import Tk, Toplevel, Label
import time, json, threading, subprocess, os, re, sys, pyautogui

data = "dictionary of substitutions.json"

if os.path.exists(data):
  with open(data) as json_file:
    d = json.load(json_file)
    longest_key_length = len(max(d.keys(), key=len))
    list_words_ab = sorted(list(d.keys()))

class dict_key:
  def __init__(self):
    self.key = ""
    self.swit = False
    self.list_words_ab = []
  def update(self, key1):
    self.key = self.key + str(key1).replace("'", "")
  def clean(self):
    self.key = ''
  def return_key(self):
    return self.key
  def backspace(self):
    self.key = self.key[1:] if self.key else ''
    return self.key
  def save(self, list_words_ab):
    self.list_words_ab = list_words_ab
  def get(self):
    return self.list_words_ab

punto = dict_key()

def get_current_keyboard_layout():
  try:
    result = subprocess.run(['xset', 'q'], capture_output=True, text=True)
    if result.returncode == 0:
      output = result.stdout
      for line in output.split('\n'):
        if 'LED mask' in line:
          match = re.search(r"LED mask:\s+(\d+)", line)
          if match:
            number = match.group(1)
            return "en" if '00001002' in number else "ru"
  except Exception:
    return "ru"  # Fallback to ru if detection fails
  return "ru"

l = {
  'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
  'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
  'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
  'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y',
  'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F',
  'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C',
  'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'}

class ToolTip:
  def __init__(self, widget):
    self.widget = widget
    self.tipwindow = None
    self.text = None
  def showtip(self, text):
    self.text = text
    if self.tipwindow or not self.text:
      return
    x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
    x = x + self.widget.winfo_rootx() + 22
    y = y + self.widget.winfo_rooty() + 7
    self.tipwindow = tw = Toplevel(self.widget)
    tw.wm_overrideredirect(True)
    tw.wm_geometry(f"+{x}+{y}")
    label = Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
    label.pack(ipadx=1)
  def hidetip(self):
    if self.tipwindow:
      self.tipwindow.destroy()
      self.tipwindow = None

def CreateToolTip(widget, text):
  toolTip = ToolTip(widget)
  toolTip.showtip(text)
  return toolTip

def typing_text(text):#  print(text)
  for char in text:
    time.sleep(0.1)             # Удерживать 0.1 секунды
    if char == ' ':
     pyautogui.keyDown('space')  # Нажать пробел
     time.sleep(0.1)             # Удерживать 0.1 секунды
     pyautogui.keyUp('space')    # Отпустить пробел
    else:
        # В противном случае вводим символ как обычно
        subprocess.call(['xdotool', 'type', '--delay', '9', char])

def replacing_words(word, res):
  for _ in range(len(word) + 1):
    subprocess.run(['xte', 'key BackSpace'])
    time.sleep(0.01)
  typing_text(res)

def on_press2(key, root, word, res, listener1):
  key = str(key).replace(" ", "")
  res = ' '.join(res.lstrip().rsplit())
  punto.swit = False
  listener1.stop()
  if key == "Key.space":
    threading.Thread(target=replacing_words, args=(word, res), daemon=True).start()
    root.destroy()
  else:
    root.destroy()
  return False

def start1(root, word, res, listener1):
  with keyboard.Listener(on_press=lambda key: on_press2(key, root, word, res, listener1)) as listener:
    listener.join()

def press_key1(word, res):
  root = Tk()
  root.withdraw()
  tooltip = CreateToolTip(root, res)
  listener1 = keyboard.Listener()
  t2 = threading.Thread(target=start1, args=(root, word, res, listener1), daemon=True)
  t2.start()
  root.mainloop()

def update_word(liter, list_words_ab):
  if get_current_keyboard_layout() == "en":
    liter = str(liter).replace("'", "")
    liter = l.get(liter, liter)
  else:
    liter = str(liter).replace("'", "")
  punto.update(liter)
  key = punto.return_key()
  if len(key) > longest_key_length:
    punto.backspace()
  for word in list_words_ab:
    if len(key) >= len(word) and key[-len(word):] == word:
      res = d[word]
      punto.clean()
      punto.swit = True
      press_key1(word, res)
      break

timestamp = time.time()
def on_press(key):
  global timestamp
  if time.time() - timestamp < 0.3 or punto.swit:
    timestamp = time.time()
    return
  timestamp = time.time()
  key = str(key).replace(" ", "")
  if key in ("Key.ctrl_l", "Key.ctrl_r", "Key.shift", "Key.shift_r", "Key.alt_l", "Key.alt_r",
             "Key.tab", "Key.caps_lock", "Key.enter", "Key.backspace", "Key.delete",
             "Key.left", "Key.right", "Key.up", "Key.down", "Key.cmd", "Key.num_lock",
             "Key.page_up", "Key.page_down", "Key.home", "Key.end", "Key.insert",
             "\\", "/", ",", ".", "' '", "'.'"):
    return
  try:
    update_word(key, list_words_ab)
  except Exception:
    pass

def main():
  punto.save(list_words_ab)
  with keyboard.Listener(on_press=on_press) as listener:
    listener.join()

if __name__ == "__main__":
  main()
