#!/usr/bin/env python3
"""
Тестовый скрипт для непрерывного выполнения find_main_window.py.
Демонстрирует, как скрипт работает постоянно.
"""

import subprocess
import sys
import time

print("=" * 80)
print("ТЕСТ find_main_window.py - непрерывное выполнение")
print("=" * 80)
print()
print("Это запустит скрипт в режиме наблюдения, который будет постоянно:")
print("  1. Сканировать все процессы на наличие .exe файлов")
print("  2. Определять активное окно")
print("  3. Искать игровой процесс, связанный с активным окном")
print("  4. Печатать результаты каждые 3 секунды")
print()
print("Нажмите Ctrl+C для остановки")
print()

# Запускаем скрипт в режиме наблюдения с интервалом 3 секунды
try:
    subprocess.run(
        [sys.executable, "find_main_window.py", "watch", "--interval", "3"],
        check=True
    )
except KeyboardInterrupt:
    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН - Скрипт остановлен пользователем")
    print("=" * 80)
    sys.exit(0)

# Этот код не будет достигнут, если скрипт выполняется должным образом
print("Скрипт завершил работу", file=sys.stderr)
