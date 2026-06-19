import sys, os, json, time, glob, subprocess  # Базовые библиотеки
from pathlib import Path
from collections import deque  # Для сглаживания мыши
from select import select  # Для опроса событий
import evdev  # Для работы с устройствами
from evdev import UInput, AbsInfo, ecodes  # Для создания геймпада
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QFileDialog
from PyQt6.QtGui import QKeySequence, QPalette, QColor, QAction  # Исправлен импорт QAction!
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from Ui_Editor_settings_for_Xbox360 import MainWindow, VirtualKeyboard, ZONE_DEFINITIONS, KEY_MAPPER

IMAGE_PATH = os.path.join(os.getcwd(), "gamepad xbox 360.png")
SETTINGS_FILE = Path.cwd() / "editor_for_Xbox360_app_settings.json"  # Новый файл настроек

# Маппинг логических имен кнопок геймпада в коды ecodes (как в рабочем скрипте)
GAMEPAD_EC = { "A": ecodes.BTN_A, "B": ecodes.BTN_B, "X": ecodes.BTN_X, "Y": ecodes.BTN_Y,
 "LEFT_SHOULDER": ecodes.BTN_TL, "RIGHT_SHOULDER": ecodes.BTN_TR, "LEFT_TRIGGER": ecodes.ABS_Z,
 "RIGHT_TRIGGER": ecodes.ABS_RZ, "GUIDE": ecodes.BTN_MODE, "BACK": ecodes.BTN_SELECT, "START": ecodes.BTN_START,
 "DPAD_UP": ecodes.ABS_HAT0Y, "DPAD_DOWN": ecodes.ABS_HAT0Y, "DPAD_LEFT": ecodes.ABS_HAT0X,
 "DPAD_RIGHT": ecodes.ABS_HAT0X, "LEFT_THUMB_UP": ecodes.ABS_Y, "LEFT_THUMB_DOWN": ecodes.ABS_Y,
 "LEFT_THUMB_LEFT": ecodes.ABS_X, "LEFT_THUMB_RIGHT": ecodes.ABS_X, "RIGHT_THUMB_UP": ecodes.ABS_RY,
 "RIGHT_THUMB_DOWN": ecodes.ABS_RY, "RIGHT_THUMB_LEFT": ecodes.ABS_RX, "RIGHT_THUMB_RIGHT": ecodes.ABS_RX,
 "LEFT_THUMB_PRESSED": ecodes.BTN_THUMBL, "RIGHT_THUMB_PRESSED": ecodes.BTN_THUMBR}

# ПОТОК ЭМУЛЯЦИИ GAMEPAD (из рабочего скрипта)
class Worker(QThread):
 status_sig = pyqtSignal(str)
 error_sig = pyqtSignal(str)
 
 def __init__(self, keymap, mouse_on, sens, smooth, grab):
  super().__init__()
  self.km = keymap  # Словарь маппинга профиля
  self.mouse_on, self.sens, self.smooth, self.grab = mouse_on, sens, smooth, grab
  self.running = False
  self.ui = None
  self.kb_dev, self.m_dev = None, None
  self.kb_grabbed = False
  self.hat = {"x": 0, "y": 0}
  self.m_rx, self.m_ry = 0.0, 0.0
  self.kb_rx, self.kb_ry = 0, 0
  self.smoother = deque(maxlen=20)
 
 def run(self):  # Поиск клавиатуры Logitech (исключая Consumer и System)
  self.kb_dev = None
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "Logitech" in dev.name and "Keyboard" in dev.name and "Consumer" not in dev.name and "System" not in dev.name:
     self.kb_dev = dev
     break
   except:
    continue
  
  if not self.kb_dev:  # Резервный поиск любой подходящей клавиатуры
   skip = ("xbox", "x-box", "gamepad", "pad", "virtual", "uinput", "microsoft", "xenia", "360", "consumer", "system")
   self.kb_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                       if not any(w in evdev.InputDevice(p).name.lower() for w in skip)
                       and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                       and ecodes.KEY_A in evdev.InputDevice(p).capabilities()[ecodes.EV_KEY]), None)
  
  if not self.kb_dev:
   self.error_sig.emit("Клавиатура не найдена!")
   return
  
  # ------------------------------------------------------------
  # Инициализация состояния NumLock и установка LED на устройстве
  # ------------------------------------------------------------
  self.numlock_state = 0  # по умолчанию выключен
  
  # Пытаемся получить текущее состояние NumLock из системы
  try:
   import subprocess
   # Способ 1: через xset (если запущен X11)
   result = subprocess.run(['xset', 'q'], capture_output=True, text=True, timeout=1)
   for line in result.stdout.split('\n'):
    if 'Num Lock' in line:
     self.numlock_state = 1 if 'on' in line.lower() else 0
     break
  except Exception:
   # Способ 2: читаем из sysfs (ядро)
   try:
    import glob as glob2
    led_files = glob2.glob("/sys/class/leds/input*::numlock/brightness")
    if led_files:
     with open(led_files[0], 'r') as f:
      val = f.read().strip()
      self.numlock_state = 1 if int(val) > 0 else 0
   except Exception:
    pass  # оставляем 0, если не удалось определить
  
  # Принудительно устанавливаем LED на устройстве
  self.kb_dev.write(ecodes.EV_LED, ecodes.LED_NUML, self.numlock_state)
  self.kb_dev.syn()

  try:
  # Захват клавиатуры
   if self.grab:
    self.kb_dev.grab()
    self.kb_grabbed = True
  except Exception as e:
   self.error_sig.emit(f"Ошибка захвата: {e}")
   return
  # Поиск мыши
  self.m_dev = None
  if self.mouse_on:
   self.m_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                      if ecodes.EV_REL in evdev.InputDevice(p).capabilities()
                      and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                      and ecodes.REL_X in evdev.InputDevice(p).capabilities()[ecodes.EV_REL]), None)
  
  # Создание виртуального геймпада Xbox 360
  try:
   cap = {ecodes.EV_KEY: [ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y, ecodes.BTN_TL, ecodes.BTN_TR, ecodes.BTN_START, ecodes.BTN_SELECT, ecodes.BTN_MODE, ecodes.BTN_THUMBL, ecodes.BTN_THUMBR],
          ecodes.EV_ABS: [(ecodes.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),
                          (ecodes.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
                          (ecodes.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)), (ecodes.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0))]}
   self.ui = UInput(cap, name="Microsoft X-Box 360 pad", vendor=0x045e, product=0x028e, version=0x0114, bustype=ecodes.BUS_USB)
   time.sleep(0.3);
   self._neutral()
  except Exception as e:
   self.error_sig.emit(f"UInput ошибка: {e}");
   self._clean();
   return
  
  self.running = True
  msg = f"Активно | KB: {self.kb_dev.name}"# + (f" | Mouse: {self.m_dev.name}" if self.m_dev else "")
  self.status_sig.emit(msg)
  
  inv = {}  # Инверсия маппинга для быстрого поиска: код клавиши -> список кнопок геймпада
  for logical, k_str in self.km.items():
   if hasattr(ecodes, k_str):
    k_code = getattr(ecodes, k_str)
    inv.setdefault(k_code, []).append(logical)
  
  fds = [self.kb_dev] + ([self.m_dev] if self.m_dev else [])
  
  # Главный цикл
  while self.running:
   r, _, _ = select(fds, [], [], 0.02)
   for d in r:
    try:
     for ev in d.read():
      if d is self.kb_dev and ev.type == ecodes.EV_KEY:
       p = ev.value in (1, 2)
       if ev.code == ecodes.KEY_ESC and p: self.running = False; break
       for t in inv.get(ev.code, []): self._dispatch(t, p)
      elif d is self.m_dev:
       self._mouse_ev(ev)
    except:
     self.running = False;
     self.error_sig.emit("Устройство отключилось!");
     break
   
   # Затухание мыши
   self.m_rx *= 0.85;
   self.m_ry *= 0.85
   if abs(self.m_rx) < 200: self.m_rx = 0
   if abs(self.m_ry) < 200: self.m_ry = 0
   rx = self.kb_rx if self.kb_rx != 0 else int(self.m_rx)
   ry = self.kb_ry if self.kb_ry != 0 else int(self.m_ry)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RX, rx)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RY, ry)
   self.ui.syn()
  self._clean()
 
 def _mouse_ev(self, ev):
  if ev.type == ecodes.EV_REL:
   dx = ev.value * self.sens if ev.code == ecodes.REL_X else 0
   dy = ev.value * self.sens if ev.code == ecodes.REL_Y else 0
   self.smoother.append((dx, dy))
   if self.smooth: dx, dy = sum(x[0] for x in self.smoother) / len(self.smoother), sum(x[1] for x in self.smoother) / len(self.smoother)
   self.m_rx = max(-32767, min(32767, self.m_rx + dx * 40))
   self.m_ry = max(-32767, min(32767, self.m_ry + dy * 40))
  elif ev.type == ecodes.EV_KEY:
   if ev.code == ecodes.BTN_LEFT:
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_RZ, 255 if ev.value else 0)
   elif ev.code == ecodes.BTN_RIGHT:
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_Z, 255 if ev.value else 0)
   elif ev.code == ecodes.BTN_MIDDLE:
    self.ui.write(ecodes.EV_KEY, ecodes.BTN_THUMBR, ev.value)
   self.ui.syn()
 
 def _dispatch(self, t, p):  # Трансляция логического имени в команды UInput
  if t in GAMEPAD_EC:
   ec = GAMEPAD_EC[t]
   if t.startswith("DPAD"):
    ax, v = (ecodes.ABS_HAT0X, -1 if p else 0) if "LEFT" in t else (ecodes.ABS_HAT0X, 1 if p else 0) if "RIGHT" in t else (ecodes.ABS_HAT0Y, -1 if p else 0) if "UP" in t else (ecodes.ABS_HAT0Y, 1 if p else 0)
    self.ui.write(ecodes.EV_ABS, ax, v)
   elif t in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
    self.ui.write(ecodes.EV_ABS, ec, 255 if p else 0)
   elif "THUMB" in t and "PRESSED" not in t:
    F = 32767
    if "UP" in t or "RIGHT" in t:
     val = F if p else 0
    elif "DOWN" in t or "LEFT" in t:
     val = -F if p else 0
    else:
     val = 0
    if "RIGHT_THUMB" in t:
     self.kb_rx = val if "LEFT" in t or "RIGHT" in t else self.kb_rx;
     self.kb_ry = val if "UP" in t or "DOWN" in t else self.kb_ry
    else:
     self.ui.write(ecodes.EV_ABS, ec, val)
   else:  # Обычные кнопки
    self.ui.write(ecodes.EV_KEY, ec, int(p))
   self.ui.syn()
 
 def _neutral(self):
  for a in [ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y]: self.ui.write(ecodes.EV_ABS, a, 0)
  for a in [ecodes.ABS_Z, ecodes.ABS_RZ]: self.ui.write(ecodes.EV_ABS, a, 0)
  self.ui.syn()
 
 def _clean(self):
  if self.kb_dev and self.kb_grabbed:
   try:
    self.kb_dev.ungrab()
   except:
    pass
   self.kb_grabbed = False
  if self.ui:
   try:
    self._neutral();
    self.ui.close()
   except:
    pass
   self.ui = None
 
 def stop(self):
  self.running = False
  self.wait(2000)

class ProfileManager:# МЕНЕДЖЕР ПРОФИЛЕЙ (работает с JSON)
 def __init__(self):
  self.profiles = {}
  self.current_profile = "Default"
 
 def load_profiles(self, data):
  self.profiles = data.get("profiles", {})
  if not self.profiles: self.profiles["Default"] = KEY_MAPPER.default_mapping()
  self.current_profile = data.get("last_profile", "Default")
  if self.current_profile not in self.profiles: self.current_profile = "Default"
 
 def get_mapping(self):
  return self.profiles.get(self.current_profile, KEY_MAPPER.default_mapping())
 
 def update_mapping(self, logical, key_str):
  if self.current_profile in self.profiles: self.profiles[self.current_profile][logical] = key_str
 
 def new_profile(self, name, template_name=None):
  if name in self.profiles: return False
  if template_name and template_name in self.profiles:
   self.profiles[name] = self.profiles[template_name].copy()
  else:
   self.profiles[name] = KEY_MAPPER.default_mapping()
  return True
 
 def delete_profile(self, name):
  if name in self.profiles and name != "Default":
   del self.profiles[name]
   return True
  return False

class AppController:# КОНТРОЛЛЕР ПРИЛОЖЕНИЯ
 def __init__(self, window: MainWindow):
  self.window = window
  self.pm = ProfileManager()
  self.worker = None
  self._current_image_path = IMAGE_PATH
  
  # Привязка сигналов UI
  self.window.gamepad.zone_clicked.connect(self._on_zone_clicked)
  self.window.profile_combo.currentTextChanged.connect(self._on_profile_select)
  self.window.btn_create.clicked.connect(self._new_profile)
  self.window.btn_delete.clicked.connect(self._delete_profile)
  self.window.btn_defaults.clicked.connect(self._set_defaults)
  self.window.btn_img.clicked.connect(self._browse_image)
  self.window.btn_start.clicked.connect(self._toggle_emulation)
  self.window.closing.connect(self._save_app_settings)
  self.window.gamepad.zones_changed.connect(self._save_app_settings)
  
  # Горячая клавиша F3
  sc = QAction(self.window)
  sc.setShortcut(QKeySequence("F3"))
  sc.triggered.connect(lambda: self.window.debug_cb.setChecked(not self.window.debug_cb.isChecked()))
  self.window.addAction(sc)
  
  self._load_app_settings()
  self._refresh_combo()
  self._refresh_bindings()
  self._start_emulation()  # Начать эмуляцию геймпада
 def _load_app_settings(self):# Загрузка настроек из JSON"""
  if SETTINGS_FILE.exists():
   try:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
     data = json.load(f)
    if data.get("image_path") and os.path.exists(data["image_path"]): self._current_image_path = data["image_path"]
    self.window.gamepad.set_image(self._current_image_path)
    if data.get("zones"): self.window.gamepad.set_zones_data(data["zones"])
    self.pm.load_profiles(data)
    # Восстановление настроек мыши
    # self.window.chk_mouse.setChecked(data.get("mouse_on", False))
    # self.window.sl_sens.setValue(data.get("sens", 5))
    # self.window.chk_smooth.setChecked(data.get("smooth", True))
    # self.window.chk_grab.setChecked(data.get("grab", True))
   except:
    self.pm.load_profiles({})
  else:
   self.pm.load_profiles({})
  self.window.gamepad.set_image(self._current_image_path)
 
 def _save_app_settings(self):# Сохранение всех настроек в JSON"""
  data = {
   "image_path": self._current_image_path,
   "zones": self.window.gamepad.get_zones_data(),
   "last_profile": self.pm.current_profile,
   "profiles": self.pm.profiles,
   "mouse_on": self.window.chk_mouse.isChecked(),
   "sens": self.window.sl_sens.value(),
   "smooth": self.window.chk_smooth.isChecked(),
   "grab": self.window.chk_grab.isChecked()
  }
  try:
   with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)
  except:
   pass
 
 def _refresh_combo(self):
  self.window.profile_combo.blockSignals(True)
  self.window.profile_combo.clear()
  for p in self.pm.profiles:
   display = p.capitalize() if p != "Default" else "Default"
   self.window.profile_combo.addItem(display, p)
  idx = self.window.profile_combo.findData(self.pm.current_profile)
  if idx >= 0: self.window.profile_combo.setCurrentIndex(idx)
  self.window.profile_combo.blockSignals(False)

 def _refresh_bindings(self):
  mapping = self.pm.get_mapping()
  self.window.gamepad.update_all_bindings(mapping)
  print("Обновить выпадающий список ")
  if self.worker and self.worker.isRunning():
   self._start_emulation()  # Начать эмуляцию геймпада
 def _on_zone_clicked(self, logical_name):
  def callback(key):
   self.pm.update_mapping(logical_name, key)
   self._refresh_bindings()
   self._save_app_settings()
  
  VirtualKeyboard(self.window, callback).exec()
 
 def _on_profile_select(self, text):
  raw = self.window.profile_combo.currentData()
  if raw and raw != self.pm.current_profile:
   self.pm.current_profile = raw
   self._refresh_bindings()
   self._save_app_settings()
 
 def _new_profile(self):
  n, ok = QInputDialog.getText(self.window, "Создать профиль", "Имя профиля:")
  if ok and n.strip():
   if self.pm.new_profile(n.strip(), template_name=self.pm.current_profile):
    self.pm.current_profile = n.strip()
    self._refresh_combo()
    idx = self.window.profile_combo.findData(n.strip())
    if idx >= 0: self.window.profile_combo.setCurrentIndex(idx)
    self._refresh_bindings()
    self._save_app_settings()
   else:
    QMessageBox.warning(self.window, "Ошибка", "Профиль уже существует")
 
 def _delete_profile(self):
  if self.pm.current_profile == "Default":
   QMessageBox.warning(self.window, "Ошибка", "Нельзя удалить 'Default'");
   return
  if QMessageBox.question(self.window, "Подтверждение", f"Удалить '{self.pm.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.pm.delete_profile(self.pm.current_profile)
   self.pm.current_profile = "Default"
   self._refresh_combo()
   self._refresh_bindings()
   self._save_app_settings()
 
 def _set_defaults(self):
  if QMessageBox.question(self.window, "Подтверждение", "Сбросить привязки?") == QMessageBox.StandardButton.Yes:
   self.pm.profiles[self.pm.current_profile] = KEY_MAPPER.default_mapping()
   self._refresh_bindings()
   self._save_app_settings()
 
 def _browse_image(self):
  p, _ = QFileDialog.getOpenFileName(self.window, "Изображение геймпада", "", "Изображения (*.png *.jpg *.bmp *.webp)")
  if p:
   self._current_image_path = p
   self.window.gamepad.set_image(p)
   self._refresh_bindings()
   self._save_app_settings()
 
 def _toggle_emulation(self):
  if self.worker and self.worker.isRunning():
   self._stop_emulation()
  else:
   self._start_emulation()
 
 def _start_emulation(self): # Начать эмуляцию геймпада
  self._stop_emulation()
  act = self.pm.get_mapping()
  self.worker = Worker(act, self.window.chk_mouse.isChecked(), self.window.sl_sens.value(), self.window.chk_smooth.isChecked(), self.window.chk_grab.isChecked())
  self.worker.status_sig.connect(self._update_status)
  self.worker.error_sig.connect(lambda e: (QMessageBox.critical(self.window, "Ошибка", e), self._stop_emulation()))
  self.worker.finished.connect(self._stop_emulation)
  self.worker.start()
 
 def _update_status(self, msg):
  self.window.st_lbl.setText(f"Статус: {msg}")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #198754; font-size: 14px;")
  self.window.btn_start.setText("■  ОСТАНОВИТЬ")
  self.window.btn_start.setStyleSheet("background:#DC3545;color:white;border:none;border-radius:4px;")
 
 def _stop_emulation(self):
  if self.worker: self.worker.stop(); self.worker = None
  self.window.st_lbl.setText("Статус: Остановлен")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  self.window.btn_start.setText("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.window.btn_start.setStyleSheet("background:#198754;color:white;border:none;border-radius:4px;")

if __name__ == "__main__":
  subprocess.run(  "modprobe -r uinput && sleep 0.3 && modprobe uinput && sleep 0.3 && chmod 666 /dev/uinput",
      shell=True, stderr=subprocess.DEVNULL )# Очистка модуля uinput от старых сессий
  app = QApplication(sys.argv)
  app.setStyle("Fusion")
  palette = QPalette()  # Темная тема
  palette.setColor(QPalette.ColorRole.Window, QColor("#0f1023"))
  palette.setColor(QPalette.ColorRole.WindowText, QColor("white"))
  palette.setColor(QPalette.ColorRole.Base, QColor("#0d0e1a"))
  palette.setColor(QPalette.ColorRole.Text, QColor("white"))
  palette.setColor(QPalette.ColorRole.Button, QColor("#1c1e3d"))
  palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
  palette.setColor(QPalette.ColorRole.Highlight, QColor("#2d5cf7"))
  app.setPalette(palette)
  
  window = MainWindow()
  controller = AppController(window)
  window.show()
  sys.exit(app.exec())
