#!/usr/bin/env python3
"""
Виртуальная мышь без прокрутки (перехват физической мыши)
Захватывает физическую мышь, блокирует события колесика,
остальное передает в виртуальную мышь.
"""

import os
import sys
from evdev import UInput, InputDevice, ecodes

def auto_sudo():
    """Если не root, перезапускаем через sudo."""
    if os.geteuid() != 0:
        print("🔑 Запрашиваем права root...", file=sys.stderr)
        os.execvp("sudo", ["sudo"] + [sys.executable] + sys.argv)

def find_mouse():
    """Ищет устройство физической мыши (не тачпад, не виртуальное)."""
    for path in os.listdir("/dev/input"):
        if not path.startswith("event"):
            continue
        try:
            dev = InputDevice(f"/dev/input/{path}")
            # Исключаем тачпады и виртуальные устройства
            name = dev.name.lower()
            if "mouse" in name and "virtual" not in name:
                return dev
        except:
            continue
    # Если не нашли по имени, ищем первое устройство с относительными осями
    for path in os.listdir("/dev/input"):
        if not path.startswith("event"):
            continue
        try:
            dev = InputDevice(f"/dev/input/{path}")
            caps = dev.capabilities()
            if ecodes.EV_REL in caps and ecodes.REL_X in caps[ecodes.EV_REL]:
                return dev
        except:
            continue
    return None

def main():
    auto_sudo()

    try:
        from evdev import UInput, InputDevice, ecodes
    except ImportError:
        print("❌ Модуль evdev не найден. Установите: pip install evdev", file=sys.stderr)
        sys.exit(1)

    mouse = find_mouse()
    if not mouse:
        print("❌ Не найдена физическая мышь", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Найдена мышь: {mouse.name}")

    # Создаём виртуальную мышь БЕЗ колёсика
    caps = {
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y],   # только X и Y
        ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE],
    }
    vmouse = UInput(caps, name="No-Scroll Virtual Mouse", bustype=ecodes.BUS_USB)
    print("✅ Виртуальная мышь создана (без прокрутки)")

    # Захватываем физическую мышь, чтобы её события не доходили до системы
    mouse.grab()
    print("🖱️  Захват мыши активирован. Прокрутка заблокирована. Ctrl+C для выхода.")

    try:
        # Читаем события с физической мыши и передаём в виртуальную
        for event in mouse.read_loop():
            if event.type == ecodes.EV_REL:
                # Пропускаем события прокрутки
                if event.code in (ecodes.REL_WHEEL, ecodes.REL_HWHEEL):
                    continue
            # Передаём всё остальное (движение, кнопки)
            vmouse.write(event.type, event.code, event.value)
            vmouse.syn()
    except KeyboardInterrupt:
        print("\n👋 Выход...")
    finally:
        mouse.ungrab()
        vmouse.close()

if __name__ == "__main__":
    main()