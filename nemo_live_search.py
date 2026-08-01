#!/usr/bin/env python3
"""Nemo Live Search — компактная версия (2 функции)."""

import sys
import time
import socket
import subprocess
import pyatspi
from gi.repository import GLib

ENTRY_NAMES = ("file_search_entry", "content_search_entry")
DEBOUNCE_MS = 1500
COOLDOWN_SEC = 1.0

# Состояние для каждого окна: key = id(frame), value = [timer_id, last_text, cooldown_until]
states = {}

def main():
    # Блокировка, чтобы не запускать второй экземпляр
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.bind("\0nemo-live-search-lock")
    except OSError:
        print("Другой экземпляр уже запущен.")
        return

    pyatspi.Registry.registerEventListener(on_text_changed, "object:text-changed")
    try:
        pyatspi.Registry.start()
    except KeyboardInterrupt:
        pass

def on_text_changed(event):
    obj = event.source
    if not obj:
        return

    # Проверка, что это поле ввода в Nemo
    try:
        app = obj.getApplication()
        if not app or (app.name or "").lower() != "nemo":
            return
        if obj.getRole() != pyatspi.ROLE_TEXT:
            return
        name = obj.name or ""
        if name not in ENTRY_NAMES:
            # Отсекаем ложные срабатывания внутри списка файлов
            cur = obj.parent
            while cur:
                try:
                    if cur.getRole() in (pyatspi.ROLE_TABLE, pyatspi.ROLE_TREE_TABLE, pyatspi.ROLE_ICON):
                        return
                except:
                    pass
                cur = cur.parent
    except:
        return

    # Находим окно (frame) для идентификации
    frame = None
    cur = obj
    while cur:
        try:
            if cur.getRole() in (pyatspi.ROLE_FRAME, pyatspi.ROLE_DIALOG, pyatspi.ROLE_WINDOW):
                frame = cur
                break
        except:
            pass
        cur = cur.parent
    if not frame:
        return
    key = id(frame)

    # Отменяем предыдущий таймер для этого окна
    if key in states and states[key][0]:
        GLib.source_remove(states[key][0])

    # Функция, которая выполнится после паузы
    def fire():
        try:
            text = obj.queryText().getText(0, -1) or ""
            if not text.strip():
                return
            # Проверяем cooldown и повтор текста
            now = time.time()
            if now < states.get(key, [None, "", 0.0])[2]:
                return
            last = states.get(key, [None, "", 0.0])[1]
            if text == last:
                return
            # Обновляем состояние
            states[key] = [None, text, now + COOLDOWN_SEC]
            # Эмулируем Enter
            subprocess.run('xte "keydown Return" "keyup Return"', shell=True, check=False)
        except:
            pass
        # Сбрасываем timer_id в состоянии
        if key in states:
            states[key][0] = None

    timer_id = GLib.timeout_add(DEBOUNCE_MS, fire)

    # Сохраняем состояние: [timer_id, last_text, cooldown_until]
    if key in states:
        states[key][0] = timer_id
    else:
        states[key] = [timer_id, "", 0.0]

if __name__ == "__main__":
    main()