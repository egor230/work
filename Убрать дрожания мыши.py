#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import evdev
from evdev import ecodes, UInput
import time
import sys
import signal
from collections import deque

# ===== НАСТРОЙКИ (можно менять) =====
TIME_WINDOW = 0.04  # 40 мс - окно анализа (дрожание происходит за 30-50 мс)
MIN_EVENTS = 3  # Минимум событий в окне для детекта
MAX_AMPLITUDE = 3  # Макс. амплитуда (большинство дрожаний ±1-3)
MIN_SIGN_CHANGES = 2  # Минимум смен направления


# ====================================

def find_mouse_device():
 devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
 for device in devices:
  capabilities = device.capabilities(verbose=False)
  if ecodes.EV_REL in capabilities:
   rel_axes = capabilities[ecodes.EV_REL]
   if ecodes.REL_X in rel_axes and ecodes.REL_Y in rel_axes:
    return device
 return None


def create_virtual_mouse():
 cap = {
  ecodes.EV_REL: (ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL),
  ecodes.EV_KEY: (ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE),
  ecodes.EV_SYN: ()
 }
 return UInput(cap, name='VirtualFilteredMouse', phys='virtual/filtered')


class JitterFilter:
 def __init__(self, time_window, min_events, max_amplitude, min_sign_changes):
  self.time_window = time_window
  self.min_events = min_events
  self.max_amplitude = max_amplitude
  self.min_sign_changes = min_sign_changes
  
  self.buffer_x = deque()
  self.buffer_y = deque()
 
 def add_event(self, axis, value, timestamp):
  buffer = self.buffer_x if axis == 'x' else self.buffer_y
  buffer.append((timestamp, value))
  
  # Удаляем старые события
  while buffer and (timestamp - buffer[0][0]) > self.time_window:
   buffer.popleft()
 
 def is_jitter(self, axis, timestamp):
  buffer = self.buffer_x if axis == 'x' else self.buffer_y
  
  if len(buffer) < self.min_events:
   return False
  
  # Считаем смены направления
  sign_changes = 0
  max_amp = 0
  
  for i in range(1, len(buffer)):
   prev_val = buffer[i - 1][1]
   curr_val = buffer[i][1]
   
   # Смена знака
   if (prev_val > 0 and curr_val < 0) or (prev_val < 0 and curr_val > 0):
    sign_changes += 1
   
   max_amp = max(max_amp, abs(curr_val))
  
  # Проверяем условия дрожания
  return (sign_changes >= self.min_sign_changes) and (max_amp <= self.max_amplitude)
 
 def reset(self, axis):
  if axis == 'x':
   self.buffer_x.clear()
  else:
   self.buffer_y.clear()


physical_dev = None
virtual_ui = None


def cleanup(signum=None, frame=None):
 global physical_dev, virtual_ui
 print("\n\nОсвобождение мыши...")
 if physical_dev:
  try:
   physical_dev.ungrab()
  except:
   pass
 if virtual_ui:
  try:
   virtual_ui.close()
  except:
   pass
 print("Готово.")
 sys.exit(0)


def filter_mouse():
 global physical_dev, virtual_ui
 
 signal.signal(signal.SIGINT, cleanup)
 signal.signal(signal.SIGTERM, cleanup)
 
 physical_dev = find_mouse_device()
 if not physical_dev:
  print("✗ Мышь не найдена!")
  sys.exit(1)
 
 print(f"✓ Мышь: {physical_dev.name}")
 
 try:
  physical_dev.grab()
 except Exception as e:
  print(f"✗ Не удалось захватить мышь: {e}")
  print("  Запустите с sudo!")
  sys.exit(1)
 
 virtual_ui = create_virtual_mouse()
 jitter_filter = JitterFilter(TIME_WINDOW, MIN_EVENTS, MAX_AMPLITUDE, MIN_SIGN_CHANGES)
 
 print(f"✓ Фильтр активен")
 print()
 print("=" * 60)
 print(f"  ВРЕМЕННОЕ ОКНО: {TIME_WINDOW * 1000:.0f} мс")
 print(f"  МИН. СОБЫТИЙ: {MIN_EVENTS}")
 print(f"  МАКС. АМПЛИТУДА: {MAX_AMPLITUDE}")
 print(f"  МИН. СМЕН НАПРАВЛЕНИЯ: {MIN_SIGN_CHANGES}")
 print(f"  Ctrl+C для выхода")
 print("=" * 60)
 print()
 
 filtered = 0
 passed = 0
 
 try:
  for event in physical_dev.read_loop():
   current_time = time.time()
   
   if event.type == ecodes.EV_REL:
    if event.code == ecodes.REL_X:
     jitter_filter.add_event('x', event.value, current_time)
     
     if jitter_filter.is_jitter('x', current_time):
      filtered += 1
      jitter_filter.reset('x')
      continue
     else:
      passed += 1
      virtual_ui.write(ecodes.EV_REL, event.code, event.value)
    
    elif event.code == ecodes.REL_Y:
     jitter_filter.add_event('y', event.value, current_time)
     
     if jitter_filter.is_jitter('y', current_time):
      filtered += 1
      jitter_filter.reset('y')
      continue
     else:
      passed += 1
      virtual_ui.write(ecodes.EV_REL, event.code, event.value)
    
    else:
     virtual_ui.write(ecodes.EV_REL, event.code, event.value)
   
   elif event.type == ecodes.EV_KEY:
    virtual_ui.write(ecodes.EV_KEY, event.code, event.value)
   
   elif event.type == ecodes.EV_SYN:
    virtual_ui.write(ecodes.EV_SYN, ecodes.SYN_REPORT, 0)
   
   # Статистика
   if event.type == ecodes.EV_SYN and (filtered + passed) > 0:
    if (filtered + passed) % 500 == 0:
     total = filtered + passed
     pct = (filtered / total) * 100 if total > 0 else 0
     print(f"  [Стат] Отфильтровано: {filtered} | "
           f"Пропущено: {passed} | "
           f"Фильтрация: {pct:.1f}%")
 
 except Exception as e:
  print(f"\n✗ Ошибка: {e}")
  cleanup()


if __name__ == "__main__":
 filter_mouse()

def create_virtual_mouse(physical_device):
 """Создаёт виртуальную мышь через uinput"""
 cap = {
  ecodes.EV_REL: (ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL),
  ecodes.EV_KEY: (ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE),
  ecodes.EV_SYN: ()
 }
 
 ui = UInput(cap, name='VirtualFilteredMouse', phys='virtual/filtered')
 return ui


# Глобальные переменные для корректного завершения
physical_dev = None
virtual_ui = None


def cleanup(signum=None, frame=None):
 """Освобождает мышь при выходе"""
 global physical_dev, virtual_ui
 print("\n\nОсвобождение мыши...")
 if physical_dev:
  try:
   physical_dev.ungrab()
  except:
   pass
 if virtual_ui:
  try:
   virtual_ui.close()
  except:
   pass
 print("Готово. Мышь возвращена системе.")
 sys.exit(0)


def filter_mouse():
 """Основная функция фильтрации"""
 global physical_dev, virtual_ui
 
 # Обработчики сигналов для безопасного выхода
 signal.signal(signal.SIGINT, cleanup)
 signal.signal(signal.SIGTERM, cleanup)
 
 physical_dev = find_mouse_device()
 if not physical_dev:
  print("✗ Мышь не найдена!")
  sys.exit(1)
 
 print(f"✓ Найдена мышь: {physical_dev.name} ({physical_dev.path})")
 
 # Захватываем физическую мышь (она перестаёт работать напрямую)
 try:
  physical_dev.grab()
  print(f"✓ Мышь захвачена (grab)")
 except Exception as e:
  print(f"✗ Не удалось захватить мышь: {e}")
  print("  Запустите с sudo!")
  sys.exit(1)
 
 # Создаём виртуальную мышь
 virtual_ui = create_virtual_mouse(physical_dev)
 print(f"✓ Виртуальная мышь создана")
 print()
 print("=" * 60)
 print(f"  МЁРТВАЯ ЗОНА (DEAD_ZONE): {DEAD_ZONE} counts")
 print(f"  Движения <= {DEAD_ZONE} будут ИГНОРИРОВАТЬСЯ")
 print(f"  Нажмите Ctrl+C для выхода")
 print("=" * 60)
 print()
 
 filtered_count = 0
 passed_count = 0
 
 try:
  for event in physical_dev.read_loop():
   if event.type == ecodes.EV_REL:
    # Фильтруем только оси X и Y
    if event.code in (ecodes.REL_X, ecodes.REL_Y):
     value = event.value
     
     # Если движение в пределах мёртвой зоны - игнорируем
     if abs(value) <= DEAD_ZONE:
      filtered_count += 1
      continue  # ПРОПУСКАЕМ событие
     else:
      passed_count += 1
    
    # Пропускаем все остальные REL-события (колесо и т.д.) как есть
    virtual_ui.write(ecodes.EV_REL, event.code, event.value)
   
   elif event.type == ecodes.EV_KEY:
    # Кнопки мыши пропускаем всегда
    virtual_ui.write(ecodes.EV_KEY, event.code, event.value)
   
   elif event.type == ecodes.EV_SYN:
    # Синхронизация обязательна!
    virtual_ui.write(ecodes.EV_SYN, ecodes.SYN_REPORT, 0)
   
   # Статистика каждые 5 секунд
   if event.type == ecodes.EV_SYN and filtered_count + passed_count > 0:
    if (filtered_count + passed_count) % 500 == 0:
     total = filtered_count + passed_count
     pct = (filtered_count / total) * 100 if total > 0 else 0
     print(f"  [Стат] Отфильтровано: {filtered_count} | "
           f"Пропущено: {passed_count} | "
           f"Фильтрация: {pct:.1f}%")
 
 except Exception as e:
  print(f"\n✗ Ошибка: {e}")
  cleanup()


if __name__ == "__main__":
 filter_mouse()