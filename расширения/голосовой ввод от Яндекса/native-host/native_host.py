#!/usr/bin/env python3
# ============================================================
# native_host.py — native messaging host "voice_input_yandex"
# Получает от расширения {"cmd": "print", "text": "..."} и печатает
# текст ТАМ, ГДЕ ФОКУС СИСТЕМЫ — через write_text_fast
# (SmartTyper/evdev + process_text: регистр, автозамены).
#
# Протокол Chrome native messaging:
#   stdin : 4 байта little-endian длина + JSON UTF-8
#   stdout: то же самое для ответа (нам ответы не нужны)
# ============================================================
import sys
import os
import json
import struct
import threading

# КРИТИЧНО: write_text_fast внутри делает print() (например, press_keys печатает
# текст). Если это уйдёт в stdout, Chrome примет это за битое native-сообщение
# и убьёт хост. Перенаправляем весь stdout в stderr (Chrome stderr игнорирует).
sys.stdout = sys.stderr

# КРИТИЧНО №2 (репорт «текст в диалоге есть, но не печатается»):
# браузер стартует native host в стерильном окружении — БЕЗ DISPLAY.
# Печать требует X (pynput при импорте, xte/xset в set_layout). Если DISPLAY
# нет — восстанавливаем типичное окружение X-сессии пользователя.
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"
if not os.environ.get("XAUTHORITY"):
    for cand in (
        os.path.expanduser("~/.Xauthority"),
        f"/run/user/{os.getuid()}/gdm/Xauthority",
    ):
        if os.path.exists(cand):
            os.environ["XAUTHORITY"] = cand
            break

# путь к Project, где лежит write_text_fast.py
PROJECT_DIR = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/Project"
sys.path.insert(0, PROJECT_DIR)

from write_text_fast import process_text  # печать + подготовка текста


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len or len(raw_len) < 4:
        return None
    length = struct.unpack("<I", raw_len)[0]
    data = sys.stdin.buffer.read(length)
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def _print_phrase(text):
    """Печать + страховка: текст также в буфер обмена (не теряется,
    можно вставить Ctrl+V в окнах, где evdev-печать не сработала)."""
    try:
        import subprocess
        subprocess.run(["xclip", "-selection", "clipboard"],
                       input=text.encode("utf-8"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass  # нет xclip — не страшно, печать ниже всё равно идёт
    process_text(text + " ")


def main():
    # кнопки/мьют не трогаем: микрофоном управляет сайт Алисы
    while True:
        try:
            msg = read_message()
        except Exception:
            break
        if msg is None:
            break
        if msg.get("cmd") == "print":
            text = msg.get("text", "")
            if text:
                # печать в отдельном потоке, чтобы не блокировать чтение
                threading.Thread(target=_print_phrase, args=(text,), daemon=True).start()


if __name__ == "__main__":
    main()
