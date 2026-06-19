#!/usr/bin/env python3
"""
Виртуальный геймпад Xbox 360 (Клавиатура + Мышь)
Для работы в Linux требуется запуск от имени root (sudo) для доступа к /dev/input/
"""

import sys, os, json, time, glob, subprocess  # Базовые библиотеки
from collections import deque  # Очередь для сглаживания мыши
from select import select  # Неблокирующее чтение событий
import evdev  # Работа с устройствами ввода
from evdev import UInput, AbsInfo, ecodes  # Создание виртуального геймпада
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLabel, QComboBox, QPushButton, QMessageBox, QInputDialog, QCheckBox, QSlider)
from PyQt6.QtCore import QThread, pyqtSignal, Qt  # Многопоточность и сигналы

# ═══════════ ОЧИСТКА СТАРЫХ ГЕЙМПАДОВ ═══════════
print("Очистка старых виртуальных устройств...")
subprocess.run(["modprobe", "-r", "uinput"], stderr=subprocess.DEVNULL)  # Выгрузка модуля ядра
time.sleep(0.2)
subprocess.run(["modprobe", "uinput"], stderr=subprocess.DEVNULL)  # Загрузка обратно
time.sleep(0.2)
subprocess.run(["chmod", "666", "/dev/uinput"], stderr=subprocess.DEVNULL)  # Права доступа

# ═══════════ КОНСТАНТЫ ═══════════
CONFIG_FILE = "profiles.json"  # Файл для сохранения настроек

# Список клавиш (сначала буквы, потом модификаторы, затем нумпад)
KEYS = [
 # Буквы
 "KEY_A", "KEY_B", "KEY_C", "KEY_D", "KEY_E", "KEY_F", "KEY_G", "KEY_H", "KEY_I", "KEY_J", "KEY_K", "KEY_L", "KEY_M",
 "KEY_N", "KEY_O", "KEY_P", "KEY_Q", "KEY_R", "KEY_S", "KEY_T", "KEY_U", "KEY_V", "KEY_W", "KEY_X", "KEY_Y", "KEY_Z",
 # Спец. клавиши
 "KEY_SPACE", "KEY_ENTER", "KEY_LEFTSHIFT", "KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_TAB", "KEY_BACKSPACE",
 # Стрелки
 "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
 # Цифры верхнего ряда
 "KEY_1", "KEY_2", "KEY_3", "KEY_4", "KEY_5", "KEY_6", "KEY_7", "KEY_8", "KEY_9", "KEY_0",
 # F-клавиши
 "KEY_F1", "KEY_F2", "KEY_F3", "KEY_F4", "KEY_F5", "KEY_F6", "KEY_F7", "KEY_F8", "KEY_F9", "KEY_F10", "KEY_F11", "KEY_F12",
 # Numpad (Цифры и операторы)
 "KEY_KP1", "KEY_KP2", "KEY_KP3", "KEY_KP4", "KEY_KP5", "KEY_KP6", "KEY_KP7", "KEY_KP8", "KEY_KP9", "KEY_KP0",
 "KEY_KPENTER", "KEY_KPDOT", "KEY_KPPLUS", "KEY_KPMINUS", "KEY_KPASTERISK", "KEY_KPSLASH"
]

# Отображение внутренних кодов геймпада в читаемые имена для UI
GP_BTNS = {
 "BTN_A": "A", "BTN_B": "B", "BTN_X": "X", "BTN_Y": "Y", "BTN_TL": "LB", "BTN_TR": "RB",
 "BTN_START": "Start", "BTN_SELECT": "Back", "BTN_MODE": "Guide",
 "BTN_DPAD_UP": "D▲", "BTN_DPAD_DOWN": "D▼", "BTN_DPAD_LEFT": "D◄", "BTN_DPAD_RIGHT": "D►",
 "ABS_LEFT_STICK_X_POS": "L→", "ABS_LEFT_STICK_X_NEG": "L←", "ABS_LEFT_STICK_Y_POS": "L↓", "ABS_LEFT_STICK_Y_NEG": "L↑",
 "ABS_RIGHT_STICK_X_POS": "R→", "ABS_RIGHT_STICK_X_NEG": "R←", "ABS_RIGHT_STICK_Y_POS": "R↓", "ABS_RIGHT_STICK_Y_NEG": "R↑",
 "BTN_THUMBL": "L3", "BTN_THUMBR": "R3", "ABS_LT": "LT", "ABS_RT": "RT"
}

# Маппинг имен кнопок в системные коды evdev (только цифровые кнопки)
DIG = {"BTN_A": ecodes.BTN_A, "BTN_B": ecodes.BTN_B, "BTN_X": ecodes.BTN_X, "BTN_Y": ecodes.BTN_Y,
       "BTN_TL": ecodes.BTN_TL, "BTN_TR": ecodes.BTN_TR, "BTN_START": ecodes.BTN_START,
       "BTN_SELECT": ecodes.BTN_SELECT, "BTN_MODE": ecodes.BTN_MODE, "BTN_THUMBL": ecodes.BTN_THUMBL, "BTN_THUMBR": ecodes.BTN_THUMBR}


# ═══════════ ПОТОК ЭМУЛЯЦИИ (WORKER) ═══════════
class Worker(QThread):
 # Сигналы для безопасного общения с интерфейсом из другого потока
 status_sig = pyqtSignal(str)  # Обновление статуса
 error_sig = pyqtSignal(str)  # Вывод ошибки
 visual_sig = pyqtSignal(str, bool)  # Подсветка кнопок
 
 def __init__(self, keymap, mouse_on, sens, smooth):
  super().__init__()
  self.km = keymap  # Текущий профиль маппинга
  self.mouse_on = mouse_on  # Включена ли мышь
  self.sens = sens  # Чувствительность мыши
  self.smooth = smooth  # Сглаживание мыши
  self.running = False  # Флаг работы потока
  self.ui = None  # Виртуальный геймпад UInput
  self.kb_dev = None  # Физическая клавиатура
  self.m_dev = None  # Физическая мышь
  self.kb_grabbed = False  # Захвачена ли клавиатура
  
  # Переменные для расчетов осей и мыши
  self.hat = {"x": 0, "y": 0}  # Крестовина (D-Pad)
  self.m_rx = 0.0  # Наклон мыши по X
  self.m_ry = 0.0  # Наклон мыши по Y
  self.kb_rx = 0  # Наклон правого стика с клавиатуры X
  self.kb_ry = 0  # Наклон правого стика с клавиатуры Y
  self.smoother = deque(maxlen=20)  # Очередь для сглаживания
 
 def run(self):
  # 1. Поиск реальной клавиатуры Logitech (исключая Consumer и System)
  self.kb_dev = None
  for path in glob.glob("/dev/input/event*"):
   try:
    dev = evdev.InputDevice(path)
    if "Logitech" in dev.name and "Keyboard" in dev.name and "Consumer" not in dev.name and "System" not in dev.name:
     self.kb_dev = dev
     break
   except:
    continue
  
  # Если Logitech не найдена, ищем любую подходящую клавиатуру
  if not self.kb_dev:
   skip = ("xbox", "x-box", "gamepad", "pad", "virtual", "uinput", "microsoft", "xenia", "360", "consumer", "system")
   self.kb_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                       if not any(w in evdev.InputDevice(p).name.lower() for w in skip)
                       and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                       and ecodes.KEY_A in evdev.InputDevice(p).capabilities()[ecodes.EV_KEY]), None)
  
  if not self.kb_dev:
   self.error_sig.emit("Клавиатура не найдена!")
   return
  
  # 2. Эксклюзивный захват клавиатуры (чтобы нажатия не шли в систему)
  try:
   self.kb_dev.grab()
   self.kb_grabbed = True
  except Exception as e:
   self.error_sig.emit(f"Ошибка захвата клавиатуры (нужен sudo?): {e}")
   return
  
  # 3. Поиск мыши (если включено)
  self.m_dev = None
  if self.mouse_on:
   self.m_dev = next((evdev.InputDevice(p) for p in evdev.list_devices()
                      if ecodes.EV_REL in evdev.InputDevice(p).capabilities()
                      and ecodes.EV_KEY in evdev.InputDevice(p).capabilities()
                      and ecodes.REL_X in evdev.InputDevice(p).capabilities()[ecodes.EV_REL]), None)
  
  # 4. Создание виртуального Xbox 360 контроллера
  try:
   cap = {ecodes.EV_KEY: list(DIG.values()), ecodes.EV_ABS: [
    (ecodes.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)),
    (ecodes.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)), (ecodes.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
    (ecodes.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)), (ecodes.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
    (ecodes.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)), (ecodes.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0))]}
   self.ui = UInput(cap, name="Microsoft X-Box 360 pad", vendor=0x045e, product=0x028e, version=0x0114, bustype=ecodes.BUS_USB)
   time.sleep(0.3)
   self._neutral()  # Сброс стиков в центр
  except Exception as e:
   self.error_sig.emit(f"Ошибка создания UInput: {e}")
   self._clean()
   return
  
  self.running = True
  msg = f"Активно | KB: {self.kb_dev.name}" + (f" | Mouse: {self.m_dev.name}" if self.m_dev else "")
  self.status_sig.emit(msg)  # Сигнал в UI
  
  # Инвертируем маппинг: из "Кнопка геймпада -> Клавиша" делаем "Клавиша -> Кнопки геймпада"
  inv = {}
  for g, k_str in self.km.items():
   if hasattr(ecodes, k_str):  # Безопасное получение кода клавиши (работает и для нумпада)
    k_code = getattr(ecodes, k_str)
    inv.setdefault(k_code, []).append(g)
  
  fds = [self.kb_dev] + ([self.m_dev] if self.m_dev else [])  # Список файловых дескрипторов для опроса
  
  # 5. Главный цикл обработки нажатий
  while self.running:
   r, _, _ = select(fds, [], [], 0.02)  # Опрос каждые 20мс
   for d in r:
    try:
     for ev in d.read():
      if d is self.kb_dev and ev.type == ecodes.EV_KEY:
       p = ev.value in (1, 2)  # 1=нажато, 2=удерживается
       if ev.code == ecodes.KEY_ESC and p:  # Экстренная остановка по ESC
        self.running = False
        break
       for t in inv.get(ev.code, []):  # Отправка на все привязанные кнопки
        self._dispatch(t, p)
      elif d is self.m_dev:
       self._mouse_ev(ev)
    except Exception:
     self.running = False
     self.error_sig.emit("Устройство отключилось во время работы!")
     break
   
   # Плавное затухание мыши (возврат стика в 0)
   self.m_rx *= 0.85
   self.m_ry *= 0.85
   if abs(self.m_rx) < 200: self.m_rx = 0
   if abs(self.m_ry) < 200: self.m_ry = 0
   
   # Приоритет клавиатуры для правого стика
   rx = self.kb_rx if self.kb_rx != 0 else int(self.m_rx)
   ry = self.kb_ry if self.kb_ry != 0 else int(self.m_ry)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RX, rx)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RY, ry)
   self.ui.syn()
  
  self._clean()  # Очистка при выходе из цикла
 
 def _mouse_ev(self, ev):
  """Обработка движений и кликов мыши"""
  if ev.type == ecodes.EV_REL:  # Движение мыши
   dx = ev.value * self.sens if ev.code == ecodes.REL_X else 0
   dy = ev.value * self.sens if ev.code == ecodes.REL_Y else 0
   self.smoother.append((dx, dy))
   if self.smooth:  # Усреднение значений для плавности
    dx = sum(x[0] for x in self.smoother) / len(self.smoother)
    dy = sum(x[1] for x in self.smoother) / len(self.smoother)
   self.m_rx = max(-32767, min(32767, self.m_rx + dx * 40))
   self.m_ry = max(-32767, min(32767, self.m_ry + dy * 40))
  elif ev.type == ecodes.EV_KEY:  # Кнопки мыши
   if ev.code == ecodes.BTN_LEFT:  # ЛКМ = RT
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_RZ, 255 if ev.value else 0)
    self.visual_sig.emit("ABS_RT", bool(ev.value))
   elif ev.code == ecodes.BTN_RIGHT:  # ПКМ = LT
    self.ui.write(ecodes.EV_ABS, ecodes.ABS_Z, 255 if ev.value else 0)
    self.visual_sig.emit("ABS_LT", bool(ev.value))
   elif ev.code == ecodes.BTN_MIDDLE:  # СКМ = R3
    self.ui.write(ecodes.EV_KEY, ecodes.BTN_THUMBR, ev.value)
    self.visual_sig.emit("BTN_THUMBR", bool(ev.value))
   self.ui.syn()
 
 def _dispatch(self, t, p):
  """Маршрутизация нажатия на нужную кнопку или ось геймпада"""
  self.visual_sig.emit(t, p)  # Сигнал подсветки для UI
  
  if t in DIG:  # Обычные кнопки (A, B, X, Y, Start...)
   self.ui.write(ecodes.EV_KEY, DIG[t], int(p))
   self.ui.syn()
   return
  
  if t.startswith("BTN_DPAD"):  # Крестовина (D-Pad)
   if "LEFT" in t:
    ax, v = ecodes.ABS_HAT0X, -1 if p else 0
   elif "RIGHT" in t:
    ax, v = ecodes.ABS_HAT0X, 1 if p else 0
   elif "UP" in t:
    ax, v = ecodes.ABS_HAT0Y, -1 if p else 0
   else:
    ax, v = ecodes.ABS_HAT0Y, 1 if p else 0
   self.hat["x" if ax == ecodes.ABS_HAT0X else "y"] = v
   self.ui.write(ecodes.EV_ABS, ax, v)
   self.ui.syn()
   return
  
  F = 32767  # Максимальное отклонение стика
  # Левый стик
  if t == "ABS_LEFT_STICK_X_POS":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_X, F if p else 0)
  elif t == "ABS_LEFT_STICK_X_NEG":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_X, -F if p else 0)
  elif t == "ABS_LEFT_STICK_Y_POS":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_Y, F if p else 0)
  elif t == "ABS_LEFT_STICK_Y_NEG":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_Y, -F if p else 0)
  # Правый стик (через клавиатуру)
  elif t == "ABS_RIGHT_STICK_X_POS":
   self.kb_rx = F if p else 0
  elif t == "ABS_RIGHT_STICK_X_NEG":
   self.kb_rx = -F if p else 0
  elif t == "ABS_RIGHT_STICK_Y_POS":
   self.kb_ry = F if p else 0
  elif t == "ABS_RIGHT_STICK_Y_NEG":
   self.kb_ry = -F if p else 0
  # Триггеры
  elif t == "ABS_LT":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_Z, 255 if p else 0)
  elif t == "ABS_RT":
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RZ, 255 if p else 0)
  
  self.ui.syn()
 
 def _neutral(self):
  """Сброс всех осей в центр (0)"""
  for a in [ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  for a in [ecodes.ABS_Z, ecodes.ABS_RZ]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  self.ui.syn()
 
 def _clean(self):
  """Освобождение захваченной клавиатуры и удаление геймпада"""
  if self.kb_dev and self.kb_grabbed:
   try:
    self.kb_dev.ungrab()
   except:
    pass
   self.kb_grabbed = False
  if self.ui:
   try:
    self._neutral(); self.ui.close()
   except:
    pass
   self.ui = None
 
 def stop(self):
  """Безопасная остановка потока извне"""
  self.running = False
  self.wait(2000)  # Ждем завершения цикла


# ═══════════ ГЛАВНОЕ ОКНО (UI) ═══════════
class MainWindow(QMainWindow):
 def __init__(self):
  super().__init__()
  self.setWindowTitle("Xbox 360 Virtual Controller")
  self.setMinimumSize(900, 550)
  self.cfg = {}  # Словарь конфигурации
  self.prof = "Default"  # Текущий профиль
  self.combos = {}  # Словарь выпадающих списков
  self.labels = {}  # Словарь подписей кнопок
  self.worker = None  # Ссылка на поток эмуляции
  self.ui_lock = False  # Блокировка событий при программном изменении списков
  self._load_cfg()
  self._setup_ui()
  self._sync_ui_with_cfg()
 
 def _def_cfg(self):
  """Настройки по умолчанию"""
  layout = {
   "BTN_A": "KEY_SPACE", "BTN_B": "KEY_B", "BTN_X": "KEY_X", "BTN_Y": "KEY_Y",
   "BTN_TL": "KEY_E", "BTN_TR": "KEY_R", "BTN_START": "KEY_ENTER", "BTN_SELECT": "KEY_BACKSPACE",
   "BTN_MODE": "KEY_F12", "BTN_DPAD_UP": "KEY_UP", "BTN_DPAD_DOWN": "KEY_DOWN",
   "BTN_DPAD_LEFT": "KEY_LEFT", "BTN_DPAD_RIGHT": "KEY_RIGHT",
   "ABS_LEFT_STICK_X_POS": "KEY_D", "ABS_LEFT_STICK_X_NEG": "KEY_A",
   "ABS_LEFT_STICK_Y_POS": "KEY_S", "ABS_LEFT_STICK_Y_NEG": "KEY_W",
   "ABS_RIGHT_STICK_X_POS": "KEY_H", "ABS_RIGHT_STICK_X_NEG": "KEY_J",
   "ABS_RIGHT_STICK_Y_POS": "KEY_T", "ABS_RIGHT_STICK_Y_NEG": "KEY_G",
   "BTN_THUMBL": "KEY_Q", "BTN_THUMBR": "KEY_Z", "ABS_LT": "KEY_1", "ABS_RT": "KEY_2"
  }
  self.cfg = {"last_profile": "Default", "profiles": {"Default": layout}, "mouse_on": False, "sens": 5, "smooth": True}
  self.prof = "Default"
  self._save_cfg()
 
 def _load_cfg(self):
  """Загрузка настроек из файла"""
  if os.path.exists(CONFIG_FILE):
   try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
     self.cfg = json.load(f)
    self.prof = self.cfg.get("last_profile", "Default")
    if self.prof not in self.cfg.get("profiles", {}): self.prof = next(iter(self.cfg["profiles"]))
   except Exception:
    self._def_cfg()
  else:
   self._def_cfg()
 
 def _save_cfg(self):
  """Сохранение настроек в файл"""
  try:
   self.cfg.update({"last_profile": self.prof, "mouse_on": self.chk_m.isChecked(), "sens": self.sl_s.value(), "smooth": self.chk_sm.isChecked()})
   with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(self.cfg, f, indent=2, ensure_ascii=False)
  except Exception as e:
   QMessageBox.critical(self, "Ошибка", str(e))
 
 def _setup_ui(self):
  """Построение интерфейса и стилей"""
  self.setStyleSheet("""
            QMainWindow { background-color: #F8F9FA; }
            QWidget { background-color: #F8F9FA; color: #212529; font-family: 'Segoe UI', 'Ubuntu', sans-serif; font-size: 13px; }
            QGroupBox { border: 1px solid #DEE2E6; border-radius: 8px; margin-top: 12px; padding-top: 15px; font-weight: 600; background: #FFFFFF; }
            QComboBox { background: #FFFFFF; border: 1px solid #CED4DA; border-radius: 4px; padding: 4px 8px; min-width: 110px; }
            QComboBox:hover { border: 1px solid #ADB5BD; }
            QComboBox::drop-down { border: none; width: 20px; }
            QLabel { color: #495057; font-weight: 500; }
            QPushButton { background-color: #E9ECEF; border: 1px solid #CED4DA; border-radius: 6px; padding: 6px 12px; font-weight: 600; }
            QPushButton:hover { background-color: #DEE2E6; }
            QPushButton#StartBtn { background-color: #198754; color: white; border: none; font-size: 14px; }
            QPushButton#StartBtn:hover { background-color: #157347; }
            QPushButton#StopBtn { background-color: #DC3545; color: white; border: none; font-size: 14px; }
            QPushButton#StopBtn:hover { background-color: #BB2D3B; }
            QCheckBox { spacing: 8px; }
            QSlider::groove:horizontal { background: #E9ECEF; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #0D6EFD; width: 16px; margin: -5px 0; border-radius: 8px; }
        """)
  central_widget = QWidget()
  self.setCentralWidget(central_widget)
  root_layout = QVBoxLayout(central_widget)
  root_layout.setSpacing(12)
  root_layout.setContentsMargins(15, 15, 15, 15)
  
  # Панель профилей
  top_layout = QHBoxLayout()
  top_layout.addWidget(QLabel("Профиль:"))
  self.cb_prof = QComboBox()
  self.cb_prof.currentTextChanged.connect(self._on_profile_changed)
  top_layout.addWidget(self.cb_prof, 1)
  for text, handler in [("Создать", self._add_profile), ("Удалить", self._remove_profile), ("Сохранить", self._save_profile_btn)]:
   btn = QPushButton(text)
   btn.clicked.connect(handler)
   top_layout.addWidget(btn)
  root_layout.addLayout(top_layout)
  
  # Сетка маппинга
  grid_layout = QGridLayout()
  grid_layout.setSpacing(8)
  grid_layout.setContentsMargins(10, 10, 10, 10)
  row, col = 0, 0
  for bid, bname in GP_BTNS.items():
   lbl = QLabel(bname)
   lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
   lbl.setStyleSheet("padding: 4px; border-radius: 4px;")
   grid_layout.addWidget(lbl, row, col)
   self.labels[bid] = lbl
   cb = QComboBox()
   cb.addItems(KEYS)
   cb.currentTextChanged.connect(lambda text, btn_id=bid: self._on_key_changed(btn_id, text))
   grid_layout.addWidget(cb, row, col + 1)
   self.combos[bid] = cb
   col += 2
   if col >= 8: col = 0; row += 1  # Перенос на новую строку
  root_layout.addLayout(grid_layout)
  
  # Настройки мыши
  mouse_layout = QHBoxLayout()
  self.chk_m = QCheckBox("Мышь → Правый стик (ЛКМ=RT, ПКМ=LT)")
  mouse_layout.addWidget(self.chk_m)
  mouse_layout.addSpacing(20)
  mouse_layout.addWidget(QLabel("Чувствительность:"))
  self.sl_s = QSlider(Qt.Orientation.Horizontal)
  self.sl_s.setRange(1, 15)
  self.lbl_s = QLabel("5")
  self.sl_s.valueChanged.connect(lambda v: self.lbl_s.setText(str(v)))
  mouse_layout.addWidget(self.sl_s)
  mouse_layout.addWidget(self.lbl_s)
  self.chk_sm = QCheckBox("Сглаживание")
  self.chk_sm.setChecked(True)
  mouse_layout.addWidget(self.chk_sm)
  mouse_layout.addStretch()
  root_layout.addLayout(mouse_layout)
  
  # Нижняя панель статуса и кнопки запуска
  bot_layout = QHBoxLayout()
  self.st_lbl = QLabel("Статус: Остановлен")
  self.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  bot_layout.addWidget(self.st_lbl, 1)
  self.btn = QPushButton("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.btn.setObjectName("StartBtn")
  self.btn.setMinimumWidth(280)
  self.btn.setMinimumHeight(45)
  self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
  self.btn.clicked.connect(self._toggle)
  bot_layout.addWidget(self.btn)
  root_layout.addLayout(bot_layout)
  
  # Применение загруженных настроек к UI
  self.cb_prof.addItems(list(self.cfg.get("profiles", {}).keys()))
  self.cb_prof.setCurrentText(self.prof)
  self.chk_m.setChecked(self.cfg.get("mouse_on", False))
  self.sl_s.setValue(self.cfg.get("sens", 5))
  self.chk_sm.setChecked(self.cfg.get("smooth", True))
 
 def _sync_ui_with_cfg(self):
  """Синхронизация выпадающих списков с текущим профилем"""
  self.ui_lock = True  # Блокируем сигналы изменений
  act = self.cfg["profiles"].get(self.prof, {})
  for b, cb in self.combos.items():
   cb.blockSignals(True)
   val = act.get(b, KEYS[0]) if act.get(b) in KEYS else KEYS[0]
   cb.setCurrentText(val)
   cb.blockSignals(False)
  self.ui_lock = False
 
 def _on_profile_changed(self, name):
  if not name or name == self.prof: return
  self._save_cfg()
  self.prof = name
  self._sync_ui_with_cfg()
  if self.worker and self.worker.isRunning(): self._restart()
 
 def _on_key_changed(self, target_btn, new_key):
  if self.ui_lock: return
  act = self.cfg["profiles"][self.prof]
  # Проверка на дубликаты: если клавиша уже занята, меняем её на пустую
  for b, k in act.items():
   if b != target_btn and k == new_key:
    used = set(act.values())
    free_key = next((k for k in KEYS if k not in used), KEYS[0])
    act[b] = free_key
    self.ui_lock = True
    self.combos[b].setCurrentText(free_key)
    self.ui_lock = False
    break
  act[target_btn] = new_key
  self._save_cfg()
  if self.worker and self.worker.isRunning(): self._restart()
 
 def _add_profile(self):
  name, ok = QInputDialog.getText(self, "Новый профиль", "Введите имя:")
  if ok and name and name not in self.cfg["profiles"]:
   self.cfg["profiles"][name] = self.cfg["profiles"][self.prof].copy()
   self.prof = name
   self.cb_prof.addItem(name)
   self.cb_prof.setCurrentText(name)
   self._save_cfg()
 
 def _remove_profile(self):
  if len(self.cfg["profiles"]) <= 1: return
  if QMessageBox.question(self, "Подтверждение", f"Удалить профиль '{self.prof}'?") == QMessageBox.StandardButton.Yes:
   del self.cfg["profiles"][self.prof]
   self.prof = next(iter(self.cfg["profiles"]))
   self.cb_prof.removeItem(self.cb_prof.currentIndex())
   self._sync_ui_with_cfg()
   self._save_cfg()
 
 def _save_profile_btn(self):
  self._save_cfg()
  QMessageBox.information(self, "Успех", "Настройки профиля сохранены!")
 
 def _toggle(self):
  if self.worker and self.worker.isRunning():
   self._stop()
  else:
   self._start()
 
 def _start(self):
  act = self.cfg["profiles"].get(self.prof, {})
  self.worker = Worker(act, self.chk_m.isChecked(), self.sl_s.value(), self.chk_sm.isChecked())
  self.worker.status_sig.connect(self._update_status)
  self.worker.error_sig.connect(lambda e: (QMessageBox.critical(self, "Ошибка", e), self._stop()))
  self.worker.visual_sig.connect(self._visual_feedback)
  self.worker.finished.connect(self._stop)  # Автоматический возврат UI при падении потока
  self.worker.start()
 
 def _update_status(self, msg):
  self.st_lbl.setText(f"Статус: {msg}")
  self.st_lbl.setStyleSheet("font-weight: 600; color: #198754; font-size: 14px;")
  self.btn.setText("■  ОСТАНОВИТЬ")
  self.btn.setObjectName("StopBtn")
  self.btn.style().unpolish(self.btn)  # Обновление стилей кнопки
  self.btn.style().polish(self.btn)
  self.btn.update()
 
 def _stop(self):
  if self.worker: self.worker.stop(); self.worker = None
  self.st_lbl.setText("Статус: Остановлен")
  self.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  self.btn.setText("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.btn.setObjectName("StartBtn")
  self.btn.style().unpolish(self.btn)
  self.btn.style().polish(self.btn)
  self.btn.update()
  for lbl in self.labels.values(): lbl.setStyleSheet("padding: 4px; border-radius: 4px;")
 
 def _restart(self):
  self._stop(); self._start()
 
 def _visual_feedback(self, target, is_pressed):
  """Подсветка нажатой кнопки геймпада в интерфейсе"""
  lbl = self.labels.get(target)
  if lbl:
   if is_pressed:
    lbl.setStyleSheet("padding: 4px; border-radius: 4px; background-color: #0D6EFD; color: white; font-weight: bold;")
   else:
    lbl.setStyleSheet("padding: 4px; border-radius: 4px;")
 
 def closeEvent(self, event):
  self._save_cfg(); self._stop(); event.accept()


if __name__ == "__main__":
 app = QApplication(sys.argv)
 app.setApplicationName("Xbox 360 Virtual Controller")
 window = MainWindow()
 window.show()
 sys.exit(app.exec())