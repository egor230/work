import tkinter
from tkinter import ttk, messagebox
import os
import subprocess
import tomli
import tomli_w


import os
import subprocess
import tkinter
from tkinter import ttk, messagebox

import tomli
import tomli_w


class XemuUltimateEditor:
    """
    Xemu Master Config Pro
    Корректный редактор keyboard_controller_scancode_map
    Используются HID Keyboard Usage IDs (USB HID / SDL2 / xemu)
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Xemu Master Config Pro")
        self.root.geometry("900x600")

        # Путь к конфигу xemu
        self.path = os.path.expanduser("~/.local/share/xemu/xemu/xemu.toml")
        self.data = {}

        # ============================================================
        # HID Keyboard Usage IDs (КЛЮЧЕВО: это НЕ evdev!)
        # ============================================================
        self.scancodes = {
            # === Буквы ===
            "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9,
            "G": 10, "H": 11, "I": 12, "J": 13, "K": 14, "L": 15,
            "M": 16, "N": 17, "O": 18, "P": 19, "Q": 20, "R": 21,
            "S": 22, "T": 23, "U": 24, "V": 25, "W": 26, "X": 27,
            "Y": 28, "Z": 29,

            # === Цифры ===
            "1": 30, "2": 31, "3": 32, "4": 33, "5": 34,
            "6": 35, "7": 36, "8": 37, "9": 38, "0": 39,

            # === Основные клавиши ===
            "ENTER": 40,
            "ESC": 41,
            "BACKSPACE": 42,
            "TAB": 43,
            "SPACE": 44,

            # === Символы ===
            "MINUS": 45,
            "EQUAL": 46,
            "LEFTBRACE": 47,
            "RIGHTBRACE": 48,
            "BACKSLASH": 49,
            "SEMICOLON": 51,
            "APOSTROPHE": 52,
            "GRAVE": 53,
            "COMMA": 54,
            "DOT": 55,
            "SLASH": 56,

            # === Функциональные ===
            "CAPSLOCK": 57,
            "F1": 58, "F2": 59, "F3": 60, "F4": 61,
            "F5": 62, "F6": 63, "F7": 64, "F8": 65,
            "F9": 66, "F10": 67, "F11": 68, "F12": 69,

            "PRINTSCREEN": 70,
            "SCROLLLOCK": 71,
            "PAUSE": 72,

            # === Навигация ===
            "INSERT": 73,
            "HOME": 74,
            "PAGEUP": 75,
            "DELETE": 76,
            "END": 77,
            "PAGEDOWN": 78,

            # === Стрелки ===
            "RIGHT": 79,
            "LEFT": 80,
            "DOWN": 81,
            "UP": 82,

            # === NumPad ===
            "NUMLOCK": 83,
            "KPSLASH": 84,
            "KPASTERISK": 85,
            "KPMINUS": 86,
            "KPPLUS": 87,
            "KPENTER": 88,
            "KP1": 89, "KP2": 90, "KP3": 91,
            "KP4": 92, "KP5": 93, "KP6": 94,
            "KP7": 95, "KP8": 96, "KP9": 97,
            "KP0": 98,
            "KPDOT": 99,

            # === Модификаторы (ВАЖНО) ===
            "LEFTCTRL": 224,
            "LEFTSHIFT": 225,
            "LEFTALT": 226,
            "LEFTGUI": 227,

            "RIGHTCTRL": 228,
            "RIGHTSHIFT": 229,
            "RIGHTALT": 230,
            "RIGHTGUI": 231,
        }

        # Обратный словарь: код → имя
        self.code_to_name = {str(v): k for k, v in self.scancodes.items()}

        # ============================================================
        # Xbox кнопки (keyboard_controller_scancode_map)
        # ============================================================
        self.xbox_keys = [
            "a", "b", "x", "y",
            "back", "start",
            "white", "black",

            # Клик стиков
            "lstick_btn",
            "rstick_btn",

            # Центральная кнопка Xbox
            "guide",

            # Направления стиков (цифровая эмуляция)
            "lstick_up",
            "lstick_down",
            "lstick_left",
            "lstick_right",

            # Триггеры
            "ltrigger",
            "rtrigger",
        ]

        self.init_ui()
        self.load_settings()

    # ============================================================
    # UI
    # ============================================================
    def init_ui(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_input = ttk.Frame(self.nb)
        self.tab_sys = ttk.Frame(self.nb)
        self.tab_raw = ttk.Frame(self.nb)

        self.nb.add(self.tab_input, text="Управление (Xbox)")
        self.nb.add(self.tab_sys, text="Системные пути")
        self.nb.add(self.tab_raw, text="RAW конфиг")

        # === Управление ===
        self.input_widgets = {}
        names = sorted(self.scancodes.keys())

        row, col = 0, 0
        for key in self.xbox_keys:
            ttk.Label(
                self.tab_input,
                text=key.upper(),
                font=("", 10, "bold")
            ).grid(row=row, column=col, sticky="w", padx=8, pady=4)

            cb = ttk.Combobox(
                self.tab_input,
                values=names,
                state="readonly",
                width=18
            )
            cb.grid(row=row, column=col + 1, padx=10, pady=4)

            self.input_widgets[key] = cb

            row += 1
            if row >= 9:
                row = 0
                col += 2

        # === Пути ===
        self.path_widgets = {}
        paths = [
            "bootrom_path",
            "flashrom_path",
            "eeprom_path",
            "hdd_path",
            "dvd_path",
        ]

        for i, name in enumerate(paths):
            ttk.Label(self.tab_sys, text=name).grid(row=i, column=0, sticky="w", padx=10, pady=6)
            entry = ttk.Entry(self.tab_sys, width=80)
            entry.grid(row=i, column=1, padx=10, pady=6)
            self.path_widgets[name] = entry

        self.setup_raw_tab()

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", pady=10)

        ttk.Button(
            bottom,
            text="СОХРАНИТЬ (sudo)",
            command=self.save_all
        ).pack(side="right", padx=20)

    # ============================================================
    # RAW редактор
    # ============================================================
    def setup_raw_tab(self):
        canvas = tkinter.Canvas(self.tab_raw)
        scrollbar = ttk.Scrollbar(self.tab_raw, orient="vertical", command=canvas.yview)
        self.raw_frame = ttk.Frame(canvas)

        canvas.create_window((0, 0), window=self.raw_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.raw_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self.raw_entries = {}

    # ============================================================
    # Конфиг
    # ============================================================
    def get_map(self):
        self.data.setdefault("input", {})
        inp = self.data["input"]
        inp.setdefault("keyboard_controller_scancode_map", {})
        return inp["keyboard_controller_scancode_map"]

    def load_settings(self):
        if not os.path.exists(self.path):
            messagebox.showwarning("Нет файла", self.path)
            return

        with open(self.path, "rb") as f:
            self.data = tomli.load(f)

        mapping = self.get_map()

        for key, widget in self.input_widgets.items():
            code = mapping.get(key)
            if code is not None:
                widget.set(self.code_to_name.get(str(code), f"UNKNOWN_{code}"))

        files = self.data.get("sys", {}).get("files", {})
        for k, w in self.path_widgets.items():
            w.delete(0, "end")
            w.insert(0, files.get(k, ""))

    # ============================================================
    # Сохранение
    # ============================================================
    def save_all(self):
        mapping = self.get_map()

        for key, widget in self.input_widgets.items():
            name = widget.get()
            if name:
                mapping[key] = self.scancodes[name]
            else:
                mapping.pop(key, None)

        self.data.setdefault("sys", {}).setdefault("files", {})

        for k, w in self.path_widgets.items():
            val = w.get().strip()
            if val:
                self.data["sys"]["files"][k] = val

        tmp = "/tmp/xemu_config_tmp.toml"
        with open(tmp, "wb") as f:
            tomli_w.dump(self.data, f)

        subprocess.run(["pkexec", "cp", tmp, self.path], check=True)
        messagebox.showinfo("Готово", "Конфиг сохранён")


# ============================================================
# Запуск
# ============================================================
if __name__ == "__main__":
    root = tkinter.Tk()
    XemuUltimateEditor(root)
    root.mainloop()
