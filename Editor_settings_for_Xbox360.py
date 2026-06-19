import sys, os, json, time, glob, subprocess  # Базовые библиотеки
from pathlib import Path
from collections import deque  # Для сглаживания мыши
from select import select  # Для опроса событий
import evdev  # Для работы с устройствами
from evdev import UInput, AbsInfo, ecodes  # Для создания геймпада
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox, QFileDialog
from PyQt6.QtGui import QKeySequence, QPalette, QColor, QAction
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from Ui_Editor_settings_for_Xbox360 import MainWindow, VirtualKeyboard, ZONE_DEFINITIONS, KEY_MAPPER

IMAGE_PATH = os.path.join(os.getcwd(), "gamepad xbox 360.png")
SETTINGS_FILE = Path.cwd() / "editor_for_Xbox360_app_settings.json"  # Файл настроек

# Маппинг логических имен кнопок геймпада в коды ecodes
GAMEPAD_EC = { "A": ecodes.BTN_A, "B": ecodes.BTN_B, "X": ecodes.BTN_X, "Y": ecodes.BTN_Y,
 "LEFT_SHOULDER": ecodes.BTN_TL, "RIGHT_SHOULDER": ecodes.BTN_TR, "LEFT_TRIGGER": ecodes.ABS_Z,
 "RIGHT_TRIGGER": ecodes.ABS_RZ, "GUIDE": ecodes.BTN_MODE, "BACK": ecodes.BTN_SELECT, "START": ecodes.BTN_START,
 "DPAD_UP": ecodes.ABS_HAT0Y, "DPAD_DOWN": ecodes.ABS_HAT0Y, "DPAD_LEFT": ecodes.ABS_HAT0X,
 "DPAD_RIGHT": ecodes.ABS_HAT0X, "LEFT_THUMB_UP": ecodes.ABS_Y, "LEFT_THUMB_DOWN": ecodes.ABS_Y,
 "LEFT_THUMB_LEFT": ecodes.ABS_X, "LEFT_THUMB_RIGHT": ecodes.ABS_X, "RIGHT_THUMB_UP": ecodes.ABS_RY,
 "RIGHT_THUMB_DOWN": ecodes.ABS_RY, "RIGHT_THUMB_LEFT": ecodes.ABS_RX, "RIGHT_THUMB_RIGHT": ecodes.ABS_RX,
 "LEFT_THUMB_PRESSED": ecodes.BTN_THUMBL, "RIGHT_THUMB_PRESSED": ecodes.BTN_THUMBR}

# Кнопки, для которых применим комбинированный режим (hold/repeat + обычное нажатие)
# D-pad и стики обрабатываются немедленно (несколько логических кнопок на одну ось)
SIMPLE_BUTTONS = {"A", "B", "X", "Y", "LEFT_SHOULDER", "RIGHT_SHOULDER",
                  "LEFT_TRIGGER", "RIGHT_TRIGGER", "GUIDE", "BACK", "START",
                  "LEFT_THUMB_PRESSED", "RIGHT_THUMB_PRESSED"}

# ======================================================================
# ПОТОК ЭМУЛЯЦИИ ГЕЙМПАДА
# Принцип: обычные маппинги и триггерные режимы (hold/repeat) хранятся
# раздельно. Для кнопок с триггерным режимом вычисляется комбинированное
# состояние: hold ИЛИ repeat_импульс ИЛИ обычное_нажатие.
# Это позволяет одной клавише делать обычное нажатие, а другой —
# удержание той же кнопки геймпада без конфликтов.
# ======================================================================
class Worker(QThread):
 status_sig = pyqtSignal(str)
 error_sig = pyqtSignal(str)

 def __init__(self, keymap, trigger_modes, mouse_on, sens, smooth, grab):
  # keymap — словарь обычных маппингов (строки: "RIGHT_TRIGGER" -> "KEY_N")
  # trigger_modes — словарь триггерных режимов ("RIGHT_TRIGGER" -> {"key":"KEY_H","mode":"hold"})
  super().__init__()
  self.km = keymap
  self.tm = trigger_modes
  self.mouse_on, self.sens, self.smooth, self.grab = mouse_on, sens, smooth, grab
  self.running = False
  self.ui = None
  self.kb_dev, self.m_dev = None, None
  self.kb_grabbed = False
  self.hat = {"x": 0, "y": 0}
  self.m_rx, self.m_ry = 0.0, 0.0
  self.kb_rx, self.kb_ry = 0, 0
  self.smoother = deque(maxlen=20)
  # Состояния триггерных режимов
  self.hold_states = {}        # logical_name -> bool (включено ли удержание)
  self.repeat_active = {}      # logical_name -> bool (активен ли повтор)
  self.repeat_start_time = {}  # logical_name -> float (время начала повтора)
  self.REPEAT_PERIOD = 0.1    # Полный цикл повтора: 50мс вкл + 50мс выкл
  # Отслеживание физически нажатых клавиш (key_code)
  self.physically_pressed = set()
  # Последнее отправленное значение для каждой кнопки (чтобы не слать дубли)
  self.last_output = {}
  # Набор кнопок, для которых применяется комбинированная логика
  self.combined_set = set()
  # Обратный маппинг: logical_name -> [key_codes] для обычных нажатий
  self.normal_logical_to_keys = {}

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
  # Определение текущего состояния NumLock и установка LED
  # ------------------------------------------------------------
  self.numlock_state = 0
  try:
   import subprocess
   result = subprocess.run(['xset', 'q'], capture_output=True, text=True, timeout=1)
   for line in result.stdout.split('\n'):
    if 'Num Lock' in line:
     self.numlock_state = 1 if 'on' in line.lower() else 0
     break
  except Exception:
   try:
    import glob as glob2
    led_files = glob2.glob("/sys/class/leds/input*::numlock/brightness")
    if led_files:
     with open(led_files[0], 'r') as f:
      val = f.read().strip()
      self.numlock_state = 1 if int(val) > 0 else 0
   except Exception:
    pass

  # Устанавливаем LED NumLock на устройстве
  self.kb_dev.write(ecodes.EV_LED, ecodes.LED_NUML, self.numlock_state)
  self.kb_dev.syn()

  try:
   if self.grab:  # Захват клавиатуры (перехват всех событий)
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
   time.sleep(0.3)
   self._neutral()
  except Exception as e:
   self.error_sig.emit(f"UInput ошибка: {e}")
   self._clean()
   return

  self.running = True
  msg = f"Активно | KB: {self.kb_dev.name}"
  self.status_sig.emit(msg)

  # ------------------------------------------------------------
  # Построение инвертированных маппингов
  # normal_inv: key_code -> [logical_names] — для обычных нажатий
  # trigger_inv: key_code -> [(logical_name, mode)] — для hold/repeat
  # ------------------------------------------------------------
  normal_inv = {}
  trigger_inv = {}
  for logical, val in self.km.items():
   # Пропускаем пустые строки и не-строки (на случай старого формата)
   if not isinstance(val, str) or not val:
    continue
   if hasattr(ecodes, val):
    k_code = getattr(ecodes, val)
    normal_inv.setdefault(k_code, []).append(logical)

  for logical, info in self.tm.items():
   if not isinstance(info, dict):
    continue
   key_str = info.get("key", "")
   mode = info.get("mode", "")
   if key_str and hasattr(ecodes, key_str):
    k_code = getattr(ecodes, key_str)
    trigger_inv.setdefault(k_code, []).append((logical, mode))

  # Обратный маппинг: logical -> [key_codes] для обычных нажатий
  self.normal_logical_to_keys = {}
  for k_code, logicals in normal_inv.items():
   for logical in logicals:
    self.normal_logical_to_keys.setdefault(logical, []).append(k_code)

  # Набор кнопок с триггерным режимом (только SIMPLE_BUTTONS — не стики/DPAD)
  self.combined_set = set()
  for logical, info in self.tm.items():
   if logical in SIMPLE_BUTTONS and isinstance(info, dict):
    self.combined_set.add(logical)

  fds = [self.kb_dev] + ([self.m_dev] if self.m_dev else [])

  # ===================== ГЛАВНЫЙ ЦИКЛ =====================
  while self.running:
   r, _, _ = select(fds, [], [], 0.02)
   for d in r:
    try:
     for ev in d.read():
      if d is self.kb_dev and ev.type == ecodes.EV_KEY:
       p = ev.value in (1, 2)  # True при нажатии или автоповторе ядра

       # ESC — остановка эмуляции
       if ev.code == ecodes.KEY_ESC and p:
        self.running = False
        break

       # Обновляем множество физически нажатых клавиш
       if ev.value == 1 or ev.value == 2:
        self.physically_pressed.add(ev.code)
       elif ev.value == 0:
        self.physically_pressed.discard(ev.code)

       # === Триггерные режимы (hold/repeat) — приоритет ===
       if ev.code in trigger_inv:
        for logical, mode in trigger_inv[ev.code]:
         self._handle_trigger_key(logical, mode, ev.value)

       # === Обычные маппинги ===
       elif ev.code in normal_inv:
        for logical in normal_inv[ev.code]:
         if logical in self.combined_set:
          # Кнопка с триггерным режимом — НЕ отправляем сразу,
          # состояние будет вычислено ниже в комбинированной логике
          pass
         else:
          # Обычная кнопка без триггерного режима — немедленная отправка
          self._dispatch(logical, p)

      elif d is self.m_dev:
       self._mouse_ev(ev)
    except:
     self.running = False
     self.error_sig.emit("Устройство отключилось!")
     break

   # --------------------------------------------------------
   # Комбинированная логика для кнопок с триггерными режимами
   # Вычисляем итоговое состояние: hold OR repeat_пульс OR обычное_нажатие
   # --------------------------------------------------------
   now = time.time()
   for logical in self.combined_set:
    # Проверяем удержание (hold) — переключается по нажатию
    hold_active = self.hold_states.get(logical, False)

    # Проверяем повтор (repeat) — пульсация: 50мс вкл, 50мс выкл
    repeat_on = False
    if self.repeat_active.get(logical, False):
     start = self.repeat_start_time.get(logical, now)
     elapsed = now - start
     phase = elapsed % self.REPEAT_PERIOD
     repeat_on = phase < (self.REPEAT_PERIOD / 2)  # Первая половина цикла — включено

    # Проверяем, нажата ли обычная клавиша для этой кнопки
    normal_on = False
    if logical in self.normal_logical_to_keys:
     for k in self.normal_logical_to_keys[logical]:
      if k in self.physically_pressed:
       normal_on = True
       break

    # Итоговое состояние: включено, если ХОТЯ БЫ ОДИН источник активен
    desired = hold_active or repeat_on or normal_on

    # Определяем выходное значение (аналоговый триггер: 0/255, кнопка: 0/1)
    if logical in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
     output_val = 255 if desired else 0
    else:
     output_val = 1 if desired else 0

    # Отправляем только если значение изменилось (избегаем лишних событий)
    last_val = self.last_output.get(logical, 0)
    if output_val != last_val:
     ec = GAMEPAD_EC.get(logical)
     if ec is not None:
      if logical in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
       self.ui.write(ecodes.EV_ABS, ec, output_val)
      else:
       self.ui.write(ecodes.EV_KEY, ec, output_val)
      self.ui.syn()
      self.last_output[logical] = output_val

   # Затухание мыши (右 стик эмуляция)
   self.m_rx *= 0.85
   self.m_ry *= 0.85
   if abs(self.m_rx) < 200: self.m_rx = 0
   if abs(self.m_ry) < 200: self.m_ry = 0
   rx = self.kb_rx if self.kb_rx != 0 else int(self.m_rx)
   ry = self.kb_ry if self.kb_ry != 0 else int(self.m_ry)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RX, rx)
   self.ui.write(ecodes.EV_ABS, ecodes.ABS_RY, ry)
   self.ui.syn()

  self._clean()

 def _handle_trigger_key(self, logical, mode, ev_value):
  """Обрабатывает нажатие клавиши для триггерного режима (hold/repeat).
     НЕ отправляет события напрямую — это делает комбинированная логика."""
  if mode == "hold":
   # Переключение при нажатии (value=1), игнорируем автоповтор (value=2)
   if ev_value == 1:
    current = self.hold_states.get(logical, False)
    self.hold_states[logical] = not current
  elif mode == "repeat":
   if ev_value == 1:  # Начало повтора
    self.repeat_active[logical] = True
    self.repeat_start_time[logical] = time.time()
   elif ev_value == 0:  # Остановка повтора
    self.repeat_active[logical] = False
    self.repeat_start_time.pop(logical, None)

 def _mouse_ev(self, ev):
  """Обработка событий мыши — преобразование в оси правого стика и триггеры"""
  if ev.type == ecodes.EV_REL:
   dx = ev.value * self.sens if ev.code == ecodes.REL_X else 0
   dy = ev.value * self.sens if ev.code == ecodes.REL_Y else 0
   self.smoother.append((dx, dy))
   if self.smooth:
    dx = sum(x[0] for x in self.smoother) / len(self.smoother)
    dy = sum(x[1] for x in self.smoother) / len(self.smoother)
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

 def _dispatch(self, t, p):
  """Немедленная отправка события для кнопок БЕЗ триггерного режима
     (D-pad, стики, и обычные кнопки без hold/repeat)"""
  if t in GAMEPAD_EC:
   ec = GAMEPAD_EC[t]
   if t.startswith("DPAD"):
    # D-pad: несколько направлений на одну ось
    if "LEFT" in t:   ax, v = ecodes.ABS_HAT0X, -1 if p else 0
    elif "RIGHT" in t: ax, v = ecodes.ABS_HAT0X, 1 if p else 0
    elif "UP" in t:   ax, v = ecodes.ABS_HAT0Y, -1 if p else 0
    else:             ax, v = ecodes.ABS_HAT0Y, 1 if p else 0  # DOWN
    self.ui.write(ecodes.EV_ABS, ax, v)
   elif t in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
    # Аналоговые триггеры: 0 или 255
    self.ui.write(ecodes.EV_ABS, ec, 255 if p else 0)
   elif "THUMB" in t and "PRESSED" not in t:
    # Стики: несколько направлений на одну ось
    F = 32767
    if "UP" in t or "RIGHT" in t:
     val = F if p else 0
    elif "DOWN" in t or "LEFT" in t:
     val = -F if p else 0
    else:
     val = 0
    if "RIGHT_THUMB" in t:
     # Правый стик: пишем через kb_rx/kb_ry (комбинируется с мышью)
     if "LEFT" in t or "RIGHT" in t:
      self.kb_rx = val
     elif "UP" in t or "DOWN" in t:
      self.kb_ry = val
    else:
     self.ui.write(ecodes.EV_ABS, ec, val)
   else:
    # Обычные цифровые кнопки (A, B, X, Y, плечи, и т.д.)
    self.ui.write(ecodes.EV_KEY, ec, int(p))
   self.ui.syn()

 def _neutral(self):
  """Установка всех осей и триггеров в нейтральное положение"""
  for a in [ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  for a in [ecodes.ABS_Z, ecodes.ABS_RZ]:
   self.ui.write(ecodes.EV_ABS, a, 0)
  self.ui.syn()

 def _clean(self):
  """Освобождение ресурсов: отжим кнопок, закрытие устройств"""
  if self.kb_dev and self.kb_grabbed:
   try:
    self.kb_dev.ungrab()
   except:
    pass
   self.kb_grabbed = False
  if self.ui:
   try:
    self._neutral()
    self.ui.close()
   except:
    pass
   self.ui = None

 def stop(self):
  self.running = False
  self.wait(2000)


# ======================================================================
# МЕНЕДЖЕР ПРОФИЛЕЙ
# Хранит обычные маппинги (profiles) и триггерные режимы (trigger_modes)
# РАЗДЕЛЬНО, чтобы одна кнопка геймпада могла иметь одновременно
# и обычное нажатие, и hold/repeat от разных клавиш клавиатуры.
# ======================================================================
class ProfileManager:
 def __init__(self):
  self.profiles = {}           # Имя профиля -> {логическая_кнопка: "KEY_X"}
  self.trigger_modes = {}      # Имя профиля -> {логическая_кнопка: {"key":"KEY_X","mode":"hold"}}
  self.current_profile = "Default"

 def load_profiles(self, data):
  """Загрузка профилей и триггерных режимов из JSON с миграцией старого формата"""
  self.profiles = data.get("profiles", {})
  if not self.profiles:
   self.profiles["Default"] = KEY_MAPPER.default_mapping()
  self.current_profile = data.get("last_profile", "Default")
  if self.current_profile not in self.profiles:
   self.current_profile = "Default"

  # Загрузка триггерных режимов (новый формат)
  self.trigger_modes = data.get("trigger_modes", {})

  # Миграция: если в старом профиле есть dict-значения, переносим в trigger_modes
  for profile_name, mapping in self.profiles.items():
   migrated = False
   for logical, val in list(mapping.items()):
    if isinstance(val, dict):
     # Старый формат: {"key":"KEY_H","mode":"hold"} прямо в маппинге
     key = val.get("key", "")
     mode = val.get("mode", "hold")
     if profile_name not in self.trigger_modes:
      self.trigger_modes[profile_name] = {}
     self.trigger_modes[profile_name][logical] = {"key": key, "mode": mode}
     mapping[logical] = ""  # Очищаем обычный маппинг (пользователь назначит заново)
     migrated = True
   if migrated:
    # Убеждаемся что ключ профиля есть в trigger_modes
    if profile_name not in self.trigger_modes:
     self.trigger_modes[profile_name] = {}

 def get_mapping(self):
  """Возвращает обычные маппинги текущего профиля (только строки)"""
  return self.profiles.get(self.current_profile, KEY_MAPPER.default_mapping())

 def get_trigger_modes(self):
  """Возвращает триггерные режимы текущего профиля"""
  return self.trigger_modes.get(self.current_profile, {})

 def update_mapping(self, logical, key_str):
  """Обновляет обычный маппинг для кнопки (строковое значение клавиши)"""
  if self.current_profile in self.profiles:
   if isinstance(key_str, dict):
    # На случай старого формата — переносим в trigger_modes
    if self.current_profile not in self.trigger_modes:
     self.trigger_modes[self.current_profile] = {}
    self.trigger_modes[self.current_profile][logical] = key_str
    self.profiles[self.current_profile][logical] = ""
   else:
    self.profiles[self.current_profile][logical] = key_str

 def set_trigger_mode(self, logical, mode, key):
  """Устанавливает триггерный режим (hold/repeat) для кнопки.
     Сохраняется ОТДЕЛЬНО от обычного маппинга."""
  if self.current_profile not in self.trigger_modes:
   self.trigger_modes[self.current_profile] = {}
  self.trigger_modes[self.current_profile][logical] = {"key": key, "mode": mode}

 def clear_trigger_mode(self, logical):
  """Удаляет триггерный режим для кнопки. Обычный маппинг НЕ затрагивается."""
  if self.current_profile in self.trigger_modes:
   if logical in self.trigger_modes[self.current_profile]:
    del self.trigger_modes[self.current_profile][logical]

 def new_profile(self, name, template_name=None):
  """Создаёт новый профиль (копируя маппинги из шаблона)"""
  if name in self.profiles:
   return False
  if template_name and template_name in self.profiles:
   self.profiles[name] = self.profiles[template_name].copy()
  else:
   self.profiles[name] = KEY_MAPPER.default_mapping()
  # Копируем триггерные режимы из шаблона
  if template_name and template_name in self.trigger_modes:
   self.trigger_modes[name] = {}
   for k, v in self.trigger_modes[template_name].items():
    self.trigger_modes[name][k] = v.copy()
  return True

 def delete_profile(self, name):
  """Удаляет профиль (кроме 'Default')"""
  if name in self.profiles and name != "Default":
   del self.profiles[name]
   if name in self.trigger_modes:
    del self.trigger_modes[name]
   return True
  return False


# ======================================================================
# КОНТРОЛЛЕР ПРИЛОЖЕНИЯ — связывает UI с логикой профилей и воркером
# ======================================================================
class AppController:
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

  # Горячая клавиша F3 для отладки
  sc = QAction(self.window)
  sc.setShortcut(QKeySequence("F3"))
  sc.triggered.connect(lambda: self.window.debug_cb.setChecked(not self.window.debug_cb.isChecked()))
  self.window.addAction(sc)

  # Сигналы панели триггерных режимов
  self.window.trigger_button_combo.currentIndexChanged.connect(self._on_trigger_button_changed)
  self.window.trigger_mode_combo.currentIndexChanged.connect(self._on_trigger_mode_changed)
  self.window.trigger_key_btn.clicked.connect(self._on_trigger_key_clicked)
  self.window.trigger_clear_btn.clicked.connect(self._on_trigger_clear)

  # Инициализация
  self._load_app_settings()
  self._refresh_combo()
  self._refresh_bindings()
  self._sync_trigger_ui()       # Восстановление UI из загруженных настроек
  self._update_trigger_status()
  self._start_emulation()       # Автоматический запуск эмуляции

 def _load_app_settings(self):
  """Загрузка всех настроек из JSON файла"""
  if SETTINGS_FILE.exists():
   try:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
     data = json.load(f)
    if data.get("image_path") and os.path.exists(data["image_path"]):
     self._current_image_path = data["image_path"]
    self.window.gamepad.set_image(self._current_image_path)
    if data.get("zones"):
     self.window.gamepad.set_zones_data(data["zones"])
    self.pm.load_profiles(data)  # Загружает профили + триггерные режимы + миграция
    # Восстановление настроек мыши (раскомментировать если чекбоксы есть в UI)
    # self.window.chk_mouse.setChecked(data.get("mouse_on", False))
    # self.window.sl_sens.setValue(data.get("sens", 5))
    # self.window.chk_smooth.setChecked(data.get("smooth", True))
    # self.window.chk_grab.setChecked(data.get("grab", True))
   except:
    self.pm.load_profiles({})
  else:
   self.pm.load_profiles({})
  self.window.gamepad.set_image(self._current_image_path)

 def _save_app_settings(self):
  """Сохранение ВСЕХ настроек в JSON (профили + триггерные режимы раздельно)"""
  data = {
   "image_path": self._current_image_path,
   "zones": self.window.gamepad.get_zones_data(),
   "last_profile": self.pm.current_profile,
   "profiles": self.pm.profiles,
   "trigger_modes": self.pm.trigger_modes,  # Триггерные режимы отдельно от маппингов
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
  """Обновление выпадающего списка профилей"""
  self.window.profile_combo.blockSignals(True)
  self.window.profile_combo.clear()
  for p in self.pm.profiles:
   display = p.capitalize() if p != "Default" else "Default"
   self.window.profile_combo.addItem(display, p)
  idx = self.window.profile_combo.findData(self.pm.current_profile)
  if idx >= 0:
   self.window.profile_combo.setCurrentIndex(idx)
  self.window.profile_combo.blockSignals(False)

 def _refresh_bindings(self):
  """Обновление отображения привязок на изображении геймпада и перезапуск эмуляции"""
  mapping = self.pm.get_mapping()
  self.window.gamepad.update_all_bindings(mapping)
  if self.worker and self.worker.isRunning():
   self._start_emulation()  # Перезапуск для применения изменений

 def _on_zone_clicked(self, logical_name):
  """Клик по зоне геймпада — назначение обычной клавиши"""
  def callback(key):
   self.pm.update_mapping(logical_name, key)
   self._refresh_bindings()
   self._save_app_settings()
   self._update_trigger_status()
  VirtualKeyboard(self.window, callback).exec()

 def _on_profile_select(self, text):
  """Смена текущего профиля"""
  raw = self.window.profile_combo.currentData()
  if raw and raw != self.pm.current_profile:
   self.pm.current_profile = raw
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()       # Обновляем панель триггеров
   self._update_trigger_status()

 def _new_profile(self):
  """Создание нового профиля"""
  n, ok = QInputDialog.getText(self.window, "Создать профиль", "Имя профиля:")
  if ok and n.strip():
   if self.pm.new_profile(n.strip(), template_name=self.pm.current_profile):
    self.pm.current_profile = n.strip()
    self._refresh_combo()
    idx = self.window.profile_combo.findData(n.strip())
    if idx >= 0:
     self.window.profile_combo.setCurrentIndex(idx)
    self._refresh_bindings()
    self._save_app_settings()
    self._sync_trigger_ui()
    self._update_trigger_status()
   else:
    QMessageBox.warning(self.window, "Ошибка", "Профиль уже существует")

 def _delete_profile(self):
  """Удаление текущего профиля (кроме Default)"""
  if self.pm.current_profile == "Default":
   QMessageBox.warning(self.window, "Ошибка", "Нельзя удалить 'Default'")
   return
  if QMessageBox.question(self.window, "Подтверждение", f"Удалить '{self.pm.current_profile}'?") == QMessageBox.StandardButton.Yes:
   self.pm.delete_profile(self.pm.current_profile)
   self.pm.current_profile = "Default"
   self._refresh_combo()
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()

 def _set_defaults(self):
  """Сброс всех привязок текущего профиля к значениям по умолчанию"""
  if QMessageBox.question(self.window, "Подтверждение", "Сбросить привязки?") == QMessageBox.StandardButton.Yes:
   self.pm.profiles[self.pm.current_profile] = KEY_MAPPER.default_mapping()
   # Также очищаем триггерные режимы
   if self.pm.current_profile in self.pm.trigger_modes:
    self.pm.trigger_modes[self.pm.current_profile] = {}
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()

 def _browse_image(self):
  """Выбор изображения геймпада"""
  p, _ = QFileDialog.getOpenFileName(self.window, "Изображение геймпада", "", "Изображения (*.png *.jpg *.bmp *.webp)")
  if p:
   self._current_image_path = p
   self.window.gamepad.set_image(p)
   self._refresh_bindings()
   self._save_app_settings()

 def _toggle_emulation(self):
  """Переключение эмуляции: запуск/остановка"""
  if self.worker and self.worker.isRunning():
   self._stop_emulation()
  else:
   self._start_emulation()

 def _start_emulation(self):
  """Запуск потока эмуляции геймпада"""
  self._stop_emulation()
  mapping = self.pm.get_mapping()           # Обычные маппинги (строки)
  trigger_modes = self.pm.get_trigger_modes()  # Триггерные режимы (dict)
  self.worker = Worker(mapping, trigger_modes,
                       self.window.chk_mouse.isChecked(), self.window.sl_sens.value(),
                       self.window.chk_smooth.isChecked(), self.window.chk_grab.isChecked())
  self.worker.status_sig.connect(self._update_status)
  self.worker.error_sig.connect(lambda e: (QMessageBox.critical(self.window, "Ошибка", e), self._stop_emulation()))
  self.worker.finished.connect(self._stop_emulation)
  self.worker.start()

 def _update_status(self, msg):
  """Обновление строки статуса при успешном запуске"""
  self.window.st_lbl.setText(f"Статус: {msg}")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #198754; font-size: 14px;")
  self.window.btn_start.setText("■  ОСТАНОВИТЬ")
  self.window.btn_start.setStyleSheet("background:#DC3545;color:white;border:none;border-radius:4px;")

 def _stop_emulation(self):
  """Остановка потока эмуляции"""
  if self.worker:
   self.worker.stop()
   self.worker = None
  self.window.st_lbl.setText("Статус: Остановлен")
  self.window.st_lbl.setStyleSheet("font-weight: 600; color: #6C757D; font-size: 14px;")
  self.window.btn_start.setText("▶  ЗАПУСК  ЭМУЛЯЦИИ")
  self.window.btn_start.setStyleSheet("background:#198754;color:white;border:none;border-radius:4px;")

 # -------------------- Панель триггерных режимов --------------------

 def _on_trigger_button_changed(self):
  """Смена выбранной кнопки в выпадающем списке триггеров"""
  self._update_trigger_status()

 def _on_trigger_mode_changed(self):
  """Смена режима (hold/repeat) в выпадающем списке"""
  self._update_trigger_status()

 def _on_trigger_key_clicked(self):
  """Назначение клавиши для триггерного режима выбранной кнопки"""
  logical = self.window.trigger_button_combo.currentText()
  mode_index = self.window.trigger_mode_combo.currentIndex()
  mode = "hold" if mode_index == 0 else "repeat"

  def callback(key):
   self.pm.set_trigger_mode(logical, mode, key)  # Сохраняем ОТДЕЛЬНО от обычного маппинга
   self._refresh_bindings()
   self._save_app_settings()
   self._sync_trigger_ui()
   self._update_trigger_status()
   # Перезапуск эмуляции для применения
   if self.worker and self.worker.isRunning():
    self._start_emulation()

  VirtualKeyboard(self.window, callback).exec()

 def _on_trigger_clear(self):
  """Очистка триггерного режима для выбранной кнопки (обычный маппинг НЕ затрагивается)"""
  logical = self.window.trigger_button_combo.currentText()
  self.pm.clear_trigger_mode(logical)
  self._refresh_bindings()
  self._save_app_settings()
  self._sync_trigger_ui()
  self._update_trigger_status()
  if self.worker and self.worker.isRunning():
   self._start_emulation()

 def _update_trigger_status(self):
  """Обновление метки статуса для выбранной кнопки триггера"""
  logical = self.window.trigger_button_combo.currentText()
  trigger_modes = self.pm.get_trigger_modes()
  val = trigger_modes.get(logical)
  if isinstance(val, dict):
   key_display = KEY_MAPPER.to_display(val.get("key", ""))
   mode = val.get("mode", "")
   mode_display = "Удержание" if mode == "hold" else "Повтор"
   self.window.trigger_status_label.setText(f"{logical}: {key_display} ({mode_display})")
  else:
   self.window.trigger_status_label.setText(f"{logical}: обычный")

 def _sync_trigger_ui(self):
  """Синхронизация панели триггеров с загруженными настройками.
     Восстанавливает и кнопку, и режим (hold/repeat) в выпадающих списках."""
  trigger_modes = self.pm.get_trigger_modes()
  target_logical = None
  target_mode = None
  # Ищем первую кнопку с назначенным триггерным режимом
  for logical, val in trigger_modes.items():
   if isinstance(val, dict):
    target_logical = logical
    target_mode = val.get("mode", "hold")
    break
  if target_logical:
   # Устанавливаем выбранную кнопку в выпадающем списке
   idx = self.window.trigger_button_combo.findText(target_logical)
   if idx >= 0:
    self.window.trigger_button_combo.setCurrentIndex(idx)
   # Восстанавливаем режим (hold/repeat) в выпадающем списке
   if target_mode:
    mode_idx = 0 if target_mode == "hold" else 1
    self.window.trigger_mode_combo.setCurrentIndex(mode_idx)

if __name__ == "__main__":
 # Перезагрузка модуля uinput для чистоты
 subprocess.run("modprobe -r uinput && sleep 0.3 && modprobe uinput && sleep 0.3 && chmod 666 /dev/uinput",
      shell=True, stderr=subprocess.DEVNULL)
 app = QApplication(sys.argv)
 app.setStyle("Fusion")
 # Тёмная тема
 palette = QPalette()
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