import sys
import os
import re
import shutil
import tomllib
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QInputDialog, QDialog,
    QFrame, QGraphicsDropShadowEffect, QMessageBox, QLineEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont


class GlowButton(QPushButton):
    def __init__(self, text="", glow_color="#0298ff", parent=None):
        super().__init__(text, parent)
        self._glow_color = QColor(glow_color)
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setColor(self._glow_color)
        self.shadow_effect.setBlurRadius(0)
        self.shadow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow_effect)
        self.glow_animation = QPropertyAnimation(self.shadow_effect, b"blurRadius")
        self.glow_animation.setDuration(300)
        self.glow_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

    def enterEvent(self, event):
        self.glow_animation.stop()
        self.glow_animation.setStartValue(self.shadow_effect.blurRadius())
        self.glow_animation.setEndValue(20)
        self.glow_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.glow_animation.stop()
        self.glow_animation.setStartValue(self.shadow_effect.blurRadius())
        self.glow_animation.setEndValue(0)
        self.glow_animation.start()
        super().leaveEvent(event)


class VirtualKeyboard(QDialog):
    def __init__(self, parent, callback_func=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор клавиши")
        self.setFixedSize(1410, 450)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 15px;
                border: 2px solid #3949ab;
            }
        """)
        self.callback_func = callback_func
        self.create_keyboard_layout()

    def create_keyboard_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("ВЫБЕРИТЕ КЛАВИШУ")
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                background: rgba(57, 73, 171, 0.3);
                border-radius: 10px;
                border: 1px solid #5c6bc0;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        keyboard_widget = QWidget()
        keyboard_widget.setMinimumSize(850, 340)

        BUTTON_WIDTH = 60
        BUTTON_HEIGHT = 40
        BASE_X_STEP = 70
        BASE_Y_STEP = 50
        X_OFFSET = 6
        Y_OFFSET = 6

        keyboard_layout = [
            ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
             'Insert', 'Delete', 'Home', 'End', 'PgUp', 'PgDn'],
            ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '*\n8', '(\n9',
             ')\n0', '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '*', '-'],
            ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\',
             ' 7\nHome', '8\n↑', '9\nPgUp', '+'],
            ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'',
             '\nEnter\n', '4\n←', '5\n', '6\n→'],
            ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift_R',
             '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
            ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r',
             'up', '0\nIns', ' . '],
            ['Left', 'Down', 'Right']
        ]

        style_sheet = """
            QPushButton {
                background-color: #3949ab;
                color: white;
                border: 2px solid #5c6bc0;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5c6bc0;
                border: 2px solid #7986cb;
            }
            QPushButton:pressed {
                background-color: #283593;
                color: #bbdefb;
            }
        """
        keyboard_widget.setStyleSheet(style_sheet)

        numpad_shifts = {'first': 69, 'second': 140, 'third': 210}
        first_column_keys = [' 7\nHome', '8\n↑', '9\nPgUp', '+']
        second_column_keys = ['4\n←', '5\n', '6\n→']
        third_column_keys = ['1\nEnd', '2\n↓', '3\nPgDn', 'KEnter']

        for i, row in enumerate(keyboard_layout):
            for j, key in enumerate(row):
                x1 = BASE_X_STEP * j + X_OFFSET
                y1 = BASE_Y_STEP * i + Y_OFFSET
                w = BUTTON_WIDTH
                h = BUTTON_HEIGHT

                btn = QPushButton(key, keyboard_widget)

                if self.callback_func:
                    clean_key = key.split('\n')[0].strip()
                    special_map = {
                        'Esc': 'ESCAPE', 'F1': 'F1', 'F2': 'F2', 'F3': 'F3', 'F4': 'F4',
                        'F5': 'F5', 'F6': 'F6', 'F7': 'F7', 'F8': 'F8', 'F9': 'F9',
                        'F10': 'F10', 'F11': 'F11', 'F12': 'F12',
                        'Insert': 'INSERT', 'Delete': 'DELETE', 'Home': 'HOME', 'End': 'END',
                        'PgUp': 'PAGEUP', 'PgDn': 'PAGEDOWN', 'Backspace': 'BACKSPACE',
                        'Tab': 'TAB', 'Caps Lock': 'CAPSLOCK', 'Enter': 'ENTER',
                        'Shift_L': 'LEFTSHIFT', 'Shift_R': 'RIGHTSHIFT',
                        'Ctrl': 'LEFTCTRL', 'Ctrl_r': 'RIGHTCTRL',
                        'Windows': 'LEFTMETA', 'Alt_L': 'LEFTALT', 'Alt_r': 'RIGHTALT',
                        'space': 'SPACE', 'Fn': 'FN', 'Menu': 'MENU',
                        'up': 'UP', 'down': 'DOWN', 'left': 'LEFT', 'right': 'RIGHT',
                        'Num Lock': 'NUMLOCK', '/': 'NUMPADDIVIDE', '*': 'NUMPADMULTIPLY',
                        '-': 'NUMPADMINUS', '+': 'NUMPADPLUS', 'KEnter': 'NUMPADENTER',
                        '0\nIns': 'INSERT', ' . ': 'NUMPADDECIMAL'
                    }
                    for num in range(10):
                        special_map[str(num)] = str(num)
                        special_map[f' {num}\n'] = str(num)
                    key_for_xenia = special_map.get(clean_key, clean_key.upper())
                    btn.clicked.connect(
                        lambda checked, k=key_for_xenia: (self.callback_func(k), self.accept())
                    )

                x_pos = x1
                y_pos = y1

                if key == 'Backspace':
                    w = 120
                elif i == 1 and j > 13:
                    x_pos = x1 + 69
                if i >= 2:
                    if key in first_column_keys:
                        x_pos += numpad_shifts['first']
                        if key == "+":
                            btn.setText(" + ")
                    if key in second_column_keys:
                        x_pos += numpad_shifts['second']
                    if key in third_column_keys:
                        x_pos += numpad_shifts['third']
                        if key == "KEnter":
                            h = BUTTON_HEIGHT * 2 + 5
                            btn.setText(" Enter ")

                if key == '\nEnter\n':
                    w = 140
                    h = BUTTON_HEIGHT * 2 + 5

                if i == 5:
                    if key == "space":
                        w = 300
                        x_pos = x1
                    elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
                        x_pos = x1 + 210
                    elif key == 'up':
                        x_pos = x1 + 280
                    elif key == "0\nIns":
                        x_pos = x1 + 420
                        w = 120
                    elif key == ' . ':
                        x_pos = x1 + 490

                if i == 6:
                    if key in ['Left', 'Down', 'Right']:
                        x_pos = x1 + 770
                        y_pos = y1 - 9

                btn.setGeometry(x_pos, y_pos, w, h)

        layout.addWidget(keyboard_widget)


class XeniaConfigManager:
    """
    Менеджер конфигураций Xenia.

    КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Xenia использует Windows Virtual Key (VK) коды
    в формате 0xNN для специальных клавиш, а также префиксы-модификаторы:
      ^ = Ctrl (например ^S = Ctrl+S)
      _ = Shift (например _S = Shift+S)
    Простые буквы (A-Z, 0-9) пишутся как есть.
    Несколько клавиш разделяются пробелом (например "Q I").

    Предыдущая версия писала имена клавиш типа "UP", "DOWN", "SPACE",
    которые Xenia НЕ понимает. Теперь скрипт корректно конвертирует
    имена клавиш в VK-коды и обратно.
    """

    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.profiles = {}  # имя профиля -> словарь маппинга (логическая_кнопка -> строка_клавиши)
        self.key_map = {
            "A": "keybind_a", "B": "keybind_b", "X": "keybind_x", "Y": "keybind_y",
            "LEFT_SHOULDER": "keybind_left_shoulder", "RIGHT_SHOULDER": "keybind_right_shoulder",
            "LEFT_TRIGGER": "keybind_left_trigger", "RIGHT_TRIGGER": "keybind_right_trigger",
            "GUIDE": "keybind_guide", "BACK": "keybind_back", "START": "keybind_start",
            "DPAD_UP": "keybind_dpad_up", "DPAD_DOWN": "keybind_dpad_down",
            "DPAD_LEFT": "keybind_dpad_left", "DPAD_RIGHT": "keybind_dpad_right",
            "LEFT_THUMB_UP": "keybind_left_thumb_up", "LEFT_THUMB_DOWN": "keybind_left_thumb_down",
            "LEFT_THUMB_LEFT": "keybind_left_thumb_left", "LEFT_THUMB_RIGHT": "keybind_left_thumb_right",
            "RIGHT_THUMB_UP": "keybind_right_thumb_up", "RIGHT_THUMB_DOWN": "keybind_right_thumb_down",
            "RIGHT_THUMB_LEFT": "keybind_right_thumb_left", "RIGHT_THUMB_RIGHT": "keybind_right_thumb_right",
            "LEFT_THUMB_PRESSED": "keybind_left_thumb", "RIGHT_THUMB_PRESSED": "keybind_right_thumb"
        }
        self.display_name_map = {
            "SPACE": "SPACE", "ENTER": "ENTER", "BACKSPACE": "BACK", "TAB": "TAB",
            "ESCAPE": "ESC", "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT",
            "INSERT": "INS", "DELETE": "DEL", "HOME": "HOME", "END": "END",
            "PAGEUP": "PGUP", "PAGEDOWN": "PGDN", "CAPSLOCK": "CAPS", "NUMLOCK": "NUM",
            "LEFTCTRL": "CTRL", "RIGHTCTRL": "RCTRL", "LEFTALT": "ALT", "RIGHTALT": "RALT",
            "LEFTSHIFT": "SHIFT", "RIGHTSHIFT": "RSHIFT", "LEFTMETA": "WIN", "MENU": "MENU",
            "NUMPAD0": "NUM0", "NUMPAD1": "NUM1", "NUMPAD2": "NUM2", "NUMPAD3": "NUM3",
            "NUMPAD4": "NUM4", "NUMPAD5": "NUM5", "NUMPAD6": "NUM6", "NUMPAD7": "NUM7",
            "NUMPAD8": "NUM8", "NUMPAD9": "NUM9", "NUMPADPLUS": "NUM+", "NUMPADMINUS": "NUM-",
            "NUMPADMULTIPLY": "NUM*", "NUMPADDIVIDE": "NUM/", "NUMPADENTER": "NUMENT",
            "NUMPADDECIMAL": "NUM."
        }

        # =====================================================================
        # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Маппинг имён клавиш (с виртуальной клавиатуры)
        # в формат Xenia (Windows VK-коды в hex)
        # =====================================================================
        self.key_to_xenia = {
            # Буквы и цифры — пишутся как есть (одиночный символ)
            "A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F",
            "G": "G", "H": "H", "I": "I", "J": "J", "K": "K", "L": "L",
            "M": "M", "N": "N", "O": "O", "P": "P", "Q": "Q", "R": "R",
            "S": "S", "T": "T", "U": "U", "V": "V", "W": "W", "X": "X",
            "Y": "Y", "Z": "Z",
            "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
            "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
            # Специальные клавиши — VK-коды
            "ESCAPE": "0x1B",
            "F1": "0x70", "F2": "0x71", "F3": "0x72", "F4": "0x73",
            "F5": "0x74", "F6": "0x75", "F7": "0x76", "F8": "0x77",
            "F9": "0x78", "F10": "0x79", "F11": "0x7A", "F12": "0x7B",
            "INSERT": "0x2D", "DELETE": "0x2E",
            "HOME": "0x24", "END": "0x23",
            "PAGEUP": "0x21", "PAGEDOWN": "0x22",
            "UP": "0x26", "DOWN": "0x28", "LEFT": "0x25", "RIGHT": "0x27",
            "SPACE": "0x20",
            "BACKSPACE": "0x08",
            "TAB": "0x09",
            "ENTER": "0x0D",
            "CAPSLOCK": "0x14",
            "NUMLOCK": "0x90",
            # Модификаторы
            "LEFTSHIFT": "0xA0", "RIGHTSHIFT": "0xA1",
            "LEFTCTRL": "0xA2", "RIGHTCTRL": "0xA3",
            "LEFTALT": "0xA4", "RIGHTALT": "0xA5",
            "LEFTMETA": "0x5B",  # Windows key
            "MENU": "0x5D",     # Menu/Application key
            # Numpad
            "NUMPAD0": "0x60", "NUMPAD1": "0x61", "NUMPAD2": "0x62",
            "NUMPAD3": "0x63", "NUMPAD4": "0x64", "NUMPAD5": "0x65",
            "NUMPAD6": "0x66", "NUMPAD7": "0x67", "NUMPAD8": "0x68",
            "NUMPAD9": "0x69",
            "NUMPADPLUS": "0x6B", "NUMPADMINUS": "0x6D",
            "NUMPADMULTIPLY": "0x6A", "NUMPADDIVIDE": "0x6F",
            "NUMPADENTER": "0x6C", "NUMPADDECIMAL": "0x6E",
        }

        # Обратный маппинг: Xenia формат → внутреннее имя клавиши
        # Включает VK-коды и префиксы-модификаторы
        self.xenia_to_key = {}
        for key_name, xenia_val in self.key_to_xenia.items():
            self.xenia_to_key[xenia_val.upper()] = key_name
            # Также добавляем lowercase-вариант для надёжности
            self.xenia_to_key[xenia_val.lower()] = key_name

        # Добавляем отдельные VK-коды для ключей, которые могут быть
        # записаны с префиксами-модификаторами (^X, _X)
        # Префиксы обрабатываются отдельно в _xenia_token_to_display

        # Маппинг комментариев для каждой клавиши keybind
        self.keybind_comments = {
            "keybind_a": "List of keys to bind to A, separated by spaces",
            "keybind_b": "List of keys to bind to B, separated by spaces",
            "keybind_x": "List of keys to bind to X, separated by spaces",
            "keybind_y": "List of keys to bind to Y, separated by spaces",
            "keybind_left_shoulder": "List of keys to bind to LEFT_SHOULDER, separated by spaces",
            "keybind_right_shoulder": "List of keys to bind to RIGHT_SHOULDER, separated by spaces",
            "keybind_left_trigger": "List of keys to bind to LEFT_TRIGGER, separated by spaces",
            "keybind_right_trigger": "List of keys to bind to RIGHT_TRIGGER, separated by spaces",
            "keybind_guide": "List of keys to bind to GUIDE, separated by spaces",
            "keybind_back": "List of keys to bind to BACK, separated by spaces",
            "keybind_start": "List of keys to bind to START, separated by spaces",
            "keybind_dpad_up": "List of keys to bind to DPAD_UP, separated by spaces",
            "keybind_dpad_down": "List of keys to bind to DPAD_DOWN, separated by spaces",
            "keybind_dpad_left": "List of keys to bind to DPAD_LEFT, separated by spaces",
            "keybind_dpad_right": "List of keys to bind to DPAD_RIGHT, separated by spaces",
            "keybind_left_thumb_up": "List of keys to bind to LEFT_THUMB_UP, separated by spaces",
            "keybind_left_thumb_down": "List of keys to bind to LEFT_THUMB_DOWN, separated by spaces",
            "keybind_left_thumb_left": "List of keys to bind to LEFT_THUMB_LEFT, separated by spaces",
            "keybind_left_thumb_right": "List of keys to bind to LEFT_THUMB_RIGHT, separated by spaces",
            "keybind_right_thumb_up": "List of keys to bind to RIGHT_THUMB_UP, separated by spaces",
            "keybind_right_thumb_down": "List of keys to bind to RIGHT_THUMB_DOWN, separated by spaces",
            "keybind_right_thumb_left": "List of keys to bind to RIGHT_THUMB_LEFT, separated by spaces",
            "keybind_right_thumb_right": "List of keys to bind to RIGHT_THUMB_RIGHT, separated by spaces",
            "keybind_left_thumb": "List of keys to bind to LEFT_THUMB_PRESSED, separated by spaces",
            "keybind_right_thumb": "List of keys to bind to RIGHT_THUMB_PRESSED, separated by spaces",
        }

    # =================================================================
    # Конвертация: внутреннее имя клавиши → формат Xenia (для записи)
    # =================================================================
    def _key_name_to_xenia(self, key_name: str) -> str:
        """
        Конвертирует внутреннее имя клавиши (с виртуальной клавиатуры)
        в формат, понятный Xenia.

        Примеры:
          "UP" -> "0x26"
          "A"  -> "A"
          "SPACE" -> "0x20"
          "LEFTSHIFT" -> "0xA0"
        """
        if not key_name:
            return ""
        result = self.key_to_xenia.get(key_name)
        if result is not None:
            return result
        # Если это одиночный символ (цифра или буква), возвращаем как есть
        if len(key_name) == 1:
            return key_name.upper()
        # Неизвестная клавиша — пробуем uppercase
        return key_name.upper()

    # =================================================================
    # Конвертация: формат Xenia → отображаемое имя (для UI)
    # =================================================================
    def _xenia_token_to_display(self, token: str) -> str:
        """
        Конвертирует один токен из формата Xenia в отображаемое имя.

        Токены Xenia:
          - "0x26" -> VK-код стрелки вверх
          - "^S"   -> Ctrl+S
          - "_S"   -> Shift+S
          - "A"    -> просто клавиша A
        """
        if not token:
            return ""

        token = token.strip()

        # Проверяем префикс-модификатор Ctrl (^)
        if token.startswith('^') and len(token) > 1:
            base = token[1:]
            base_display = self._xenia_token_to_display(base)
            return f"Ctrl+{base_display}"

        # Проверяем префикс-модификатор Shift (_)
        if token.startswith('_') and len(token) > 1:
            base = token[1:]
            base_display = self._xenia_token_to_display(base)
            return f"Shift+{base_display}"

        # Проверяем VK-код в hex формате (0xNN)
        if token.startswith('0x') or token.startswith('0X'):
            upper_token = token.upper()
            if upper_token in self.xenia_to_key:
                key_name = self.xenia_to_key[upper_token]
                return self.display_name_map.get(key_name, key_name)
            # Неизвестный VK-код — возвращаем как есть
            return token

        # Одиночный символ (буква/цифра)
        if len(token) == 1:
            return token.upper()

        # Пробуем найти в обратном маппинге
        if token.upper() in self.xenia_to_key:
            key_name = self.xenia_to_key[token.upper()]
            return self.display_name_map.get(key_name, key_name)

        return token

    def _xenia_value_to_display(self, xenia_value: str) -> str:
        """
        Конвертирует полное значение keybind из формата Xenia
        (может содержать несколько токенов через пробел)
        в отображаемую строку.

        Пример: "Q I" -> "Q I", "^W" -> "Ctrl+W", "0x26" -> "UP"
        """
        if not xenia_value:
            return ""
        tokens = xenia_value.strip().split()
        displays = [self._xenia_token_to_display(t) for t in tokens]
        return " ".join(displays)

    def load_profiles(self):
        """Сканирует папку config_dir и загружает все *.config.toml файлы как профили."""
        self.profiles.clear()
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return

        for file in self.config_dir.glob("*.config.toml"):
            profile_name = file.stem.replace(".config", "")  # убираем .config
            mapping = self._read_mapping_from_file(file)
            self.profiles[profile_name] = mapping

        # Если нет ни одного профиля, создаём default
        if not self.profiles:
            self.new_profile("default")

    def _read_mapping_from_file(self, filepath: Path):
        """
        Читает секцию [HID.WinKey] из toml файла и возвращает словарь
        логическая_кнопка -> отображаемое имя клавиши (для UI).

        ВАЖНО: Теперь храним отображаемое имя в маппинге, а при сохранении
        конвертируем обратно в формат Xenia.
        """
        mapping = {}
        try:
            with open(filepath, "rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, FileNotFoundError, OSError):
            return self._get_default_mapping()

        hid_section = data.get("HID", {}).get("WinKey", {})
        for logical, config_key in self.key_map.items():
            if config_key in hid_section:
                value = hid_section[config_key]
                # значение может быть строкой, убираем кавычки если есть
                if isinstance(value, str):
                    raw_value = value.strip('"')
                else:
                    raw_value = str(value)
                # Конвертируем формат Xenia в отображаемое имя для UI
                mapping[logical] = self._xenia_value_to_display(raw_value)
            else:
                mapping[logical] = ""

        # Заполняем отсутствующие значениями по умолчанию
        for logical in self.key_map:
            if logical not in mapping or not mapping[logical]:
                mapping[logical] = self._get_default_for_logical(logical)
        return mapping

    def _get_default_mapping(self):
        """Возвращает маппинг по умолчанию (в формате отображаемых имён для UI)."""
        defaults = {
            "A": "A", "B": "B", "X": "X", "Y": "Y",
            "LEFT_SHOULDER": "Q", "RIGHT_SHOULDER": "E",
            "LEFT_TRIGGER": "Q I", "RIGHT_TRIGGER": "E O",
            "GUIDE": "ESC", "BACK": "BACK", "START": "SPACE",
            "DPAD_UP": "Ctrl+W", "DPAD_DOWN": "Ctrl+S",
            "DPAD_LEFT": "Ctrl+A", "DPAD_RIGHT": "Ctrl+D",
            "LEFT_THUMB_UP": "Shift+W", "LEFT_THUMB_DOWN": "Shift+S",
            "LEFT_THUMB_LEFT": "Shift+A", "LEFT_THUMB_RIGHT": "Shift+D",
            "RIGHT_THUMB_UP": "UP", "RIGHT_THUMB_DOWN": "DOWN",
            "RIGHT_THUMB_LEFT": "LEFT", "RIGHT_THUMB_RIGHT": "RIGHT",
            "LEFT_THUMB_PRESSED": "F", "RIGHT_THUMB_PRESSED": "K"
        }
        return defaults

    def _get_default_for_logical(self, logical):
        defaults = self._get_default_mapping()
        return defaults.get(logical, "")

    # =================================================================
    # Конвертация: отображаемое имя → формат Xenia (для записи в файл)
    # =================================================================
    def _display_to_xenia_value(self, display_value: str) -> str:
        """
        Конвертирует отображаемое имя клавиши (из UI) обратно
        в формат Xenia для записи в .config.toml.

        Примеры:
          "UP"     -> "0x26"
          "Ctrl+W" -> "^W"
          "Shift+S" -> "_S"
          "A"      -> "A"
          "Q I"    -> "Q I"  (несколько клавиш)
        """
        if not display_value:
            return ""

        tokens = display_value.strip().split()
        xenia_tokens = []

        for token in tokens:
            xenia_tokens.append(self._display_token_to_xenia(token))

        return " ".join(xenia_tokens)

    def _display_token_to_xenia(self, display_token: str) -> str:
        """
        Конвертирует один отображаемый токен в формат Xenia.

        Поддерживаемые форматы токенов из UI:
          "Ctrl+W"    -> "^W"
          "Shift+S"   -> "_S"
          "UP"        -> "0x26"
          "A"         -> "A"
          "BACK"      -> "0x08"
        """
        if not display_token:
            return ""

        # Проверяем модификатор Ctrl+
        if display_token.startswith("Ctrl+") and len(display_token) > 5:
            base_name = display_token[5:]
            base_xenia = self._single_key_to_xenia(base_name)
            return f"^{base_xenia}"

        # Проверяем модификатор Shift+
        if display_token.startswith("Shift+") and len(display_token) > 6:
            base_name = display_token[6:]
            base_xenia = self._single_key_to_xenia(base_name)
            return f"_{base_xenia}"

        # Обычная клавиша
        return self._single_key_to_xenia(display_token)

    def _single_key_to_xenia(self, key_display: str) -> str:
        """
        Конвертирует отображаемое имя одиночной клавиши в формат Xenia.

        Использует обратный поиск по display_name_map и key_to_xenia.
        """
        if not key_display:
            return ""

        # Сначала проверяем: может это буква/цифра
        if len(key_display) == 1:
            return key_display.upper()

        # Ищем в display_name_map обратное соответствие
        for internal_name, disp in self.display_name_map.items():
            if disp == key_display:
                # Нашли! Теперь конвертируем internal_name в формат Xenia
                return self.key_to_xenia.get(internal_name, key_display)

        # Пробуем как внутреннее имя напрямую
        if key_display in self.key_to_xenia:
            return self.key_to_xenia[key_display]

        # Неизвестная клавиша — возвращаем как есть
        return key_display

    def _save_profile_to_file(self, profile_name: str):
        """
        Сохраняет маппинг профиля в соответствующий .config.toml файл
        (обновляет секцию [HID.WinKey] в формате Xenia).

        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Теперь конвертирует отображаемые имена
        клавиш в формат Xenia (VK-коды, префиксы ^ и _) перед записью.
        """
        filepath = self.config_dir / f"{profile_name}.config.toml"
        mapping = self.profiles.get(profile_name, {})
        if not mapping:
            mapping = self._get_default_mapping()

        # Читаем существующий файл, если он есть
        existing_data = {}
        if filepath.exists():
            try:
                with open(filepath, "rb") as f:
                    existing_data = tomllib.load(f)
            except Exception:
                existing_data = {}

        # Обновляем/добавляем секцию [HID.WinKey]
        if "HID" not in existing_data:
            existing_data["HID"] = {}
        if "WinKey" not in existing_data["HID"]:
            existing_data["HID"]["WinKey"] = {}

        for logical, config_key in self.key_map.items():
            display_value = mapping.get(logical, "")
            if display_value:
                # КОНВЕРТИРУЕМ отображаемое имя → формат Xenia
                xenia_value = self._display_to_xenia_value(display_value)
                existing_data["HID"]["WinKey"][config_key] = xenia_value

        # Читаем файл как текст для точечной замены секции
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""

        # Генерируем новую секцию [HID.WinKey] в формате Xenia
        new_section = self._generate_winkey_section(mapping)

        # Ищем существующую секцию [HID.WinKey] и заменяем
        # Шаблон: от [HID.WinKey] до следующей секции [XXX] или конца файла
        pattern = r'(\[HID\.WinKey\].*?)(?=\n\[|\Z)'
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            # Секции [HID.WinKey] нет — нужно создать
            if "[HID]" in content:
                # Вставим после секции [HID]
                # Ищем позицию после всей секции [HID] (до следующей [ или конца)
                hid_pattern = r'(\[HID\].*?)(?=\n\[|\Z)'
                hid_match = re.search(hid_pattern, content, re.DOTALL)
                if hid_match:
                    end_pos = hid_match.end()
                    new_content = content[:end_pos] + "\n\n" + new_section + content[end_pos:]
                else:
                    new_content = content.rstrip() + "\n\n" + new_section
            else:
                new_content = content.rstrip() + "\n\n" + new_section

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    def _generate_winkey_section(self, mapping):
        """
        Генерирует текст секции [HID.WinKey] для записи в файл
        В ФОРМАТЕ XENIA (VK-коды, префиксы ^, _).

        Пример результата:
        [HID.WinKey]
        keybind_a = "0xBA"                                      # List of keys to bind to A, separated by spaces
        keybind_b = "0xDE"                                      # List of keys to bind to B, separated by spaces
        """
        lines = ["[HID.WinKey]"]
        for logical, config_key in self.key_map.items():
            display_value = mapping.get(logical, "")
            if display_value:
                # КОНВЕРТИРУЕМ отображаемое имя → формат Xenia
                xenia_value = self._display_to_xenia_value(display_value)
                comment = self.keybind_comments.get(config_key, "")
                if comment:
                    lines.append(f'{config_key} = "{xenia_value}"\t\t\t\t#{comment}')
                else:
                    lines.append(f'{config_key} = "{xenia_value}"')
        return "\n".join(lines)

    def new_profile(self, name):
        """Создаёт новый профиль: новый .config.toml файл с маппингом по умолчанию."""
        if name in self.profiles:
            return False
        default_mapping = self._get_default_mapping()
        self.profiles[name] = default_mapping
        # Создаём файл
        filepath = self.config_dir / f"{name}.config.toml"
        if not filepath.exists():
            # Создаём базовый toml с секцией [HID.WinKey]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._generate_winkey_section(default_mapping))
        else:
            self._save_profile_to_file(name)
        return True

    def delete_profile(self, name):
        """Удаляет профиль и соответствующий файл."""
        if name in self.profiles and name != "default":
            filepath = self.config_dir / f"{name}.config.toml"
            if filepath.exists():
                filepath.unlink()
            del self.profiles[name]
            return True
        return False

    def update_mapping(self, profile, logical_name, key_string):
        """
        Обновляет маппинг для конкретной кнопки.

        key_string приходит из виртуальной клавиатуры в формате:
        "A", "UP", "ESCAPE", "LEFTSHIFT" и т.д.

        Мы конвертируем это в отображаемое имя для хранения в маппинге.
        """
        if profile in self.profiles:
            # Конвертируем имя клавиши с клавиатуры в отображаемое имя
            display_name = self.display_name_map.get(key_string, key_string)
            # Для одиночных символов используем сам символ
            if len(key_string) == 1:
                display_name = key_string.upper()
            self.profiles[profile][logical_name] = display_name
            self._save_profile_to_file(profile)

    def set_default_mapping(self, profile):
        if profile in self.profiles:
            self.profiles[profile] = self._get_default_mapping()
            self._save_profile_to_file(profile)

    def get_mapping(self, profile, logical_name):
        return self.profiles.get(profile, {}).get(logical_name, "")

    def validate_mapping_complete(self, profile):
        required = list(self.key_map.keys())
        mapping = self.profiles.get(profile, {})
        missing = [r for r in required if r not in mapping or not mapping[r]]
        if missing:
            return False, f"Не настроены кнопки: {', '.join(missing)}"
        return True, "OK"

    def get_key_display_name(self, key_string):
        """Возвращает отображаемое имя для кнопки в UI."""
        if len(key_string) == 1:
            return key_string.upper()
        return self.display_name_map.get(key_string, key_string.capitalize())


class XeniaUltimateEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xenia Master Config Pro")
        self.setFixedSize(1050, 800)
        self.setStyleSheet("background-color: #141526;")

        self.colors = {
            "bg": "#141526",
            "frame_bg": "#1c1e3d",
            "border": "#2c2f5a",
            "accent_blue": "#2d5cf7",
            "btn_blue": "#0070d2",
            "btn_orange": "#f39c12",
            "btn_green": "#4cd137",
            "key_bg": "#3d447e",
            "text": "white"
        }

        self.config_manager = None
        self.current_profile = "default"
        self.input_btns = {}

        self.create_widgets()
        self.set_default_config_path()
        self.load_config_manager()

    def set_default_config_path(self):
        default_path = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/xbox 360/Emulators/Xenia Canary/config"
        if os.path.exists(default_path):
            self.config_path_edit.setText(default_path)
        else:
            self.config_path_edit.setText(os.path.expanduser("~/.xenia/config"))

    def load_config_manager(self):
        config_dir = self.config_path_edit.text().strip()
        if not config_dir:
            QMessageBox.warning(self, "Ошибка", "Укажите папку с конфигами Xenia")
            return
        self.config_manager = XeniaConfigManager(config_dir)
        self.config_manager.load_profiles()
        self.current_profile = "default" if "default" in self.config_manager.profiles else next(iter(self.config_manager.profiles))
        self.update_profile_combo()
        self.update_button_labels()

    def create_widgets(self):
        # Верхняя панель
        header = QFrame(self)
        header.setStyleSheet(f"""
            background-color: {self.colors['frame_bg']};
            border: 1px solid {self.colors['accent_blue']};
        """)
        header.setGeometry(20, 20, 1010, 100)

        title_label = QLabel("XENIA ULTIMATE CONFIG", header)
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
        title_label.setGeometry(20, 22, 350, 40)

        profile_label = QLabel("ПРОФИЛЬ:", header)
        profile_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
        profile_label.setGeometry(380, 28, 100, 25)

        self.profile_combo = QComboBox(header)
        self.profile_combo.setStyleSheet("background-color: #0d0e1a; color: white; border: none;")
        self.profile_combo.setGeometry(460, 28, 220, 25)
        self.profile_combo.currentTextChanged.connect(self.on_profile_select)

        create_profile_btn = QPushButton("СОЗДАТЬ ПРОФИЛЬ", header)
        create_profile_btn.setStyleSheet(f"background-color: {self.colors['btn_blue']}; color: white; border: none;")
        create_profile_btn.setGeometry(700, 25, 140, 32)
        create_profile_btn.clicked.connect(self.new_profile)

        delete_profile_btn = QPushButton("УДАЛИТЬ ПРОФИЛЬ", header)
        delete_profile_btn.setStyleSheet(f"background-color: #e74c3c; color: white; border: none;")
        delete_profile_btn.setGeometry(850, 25, 140, 32)
        delete_profile_btn.clicked.connect(self.delete_profile)

        default_btn = QPushButton("ПО УМОЛЧАНИЮ", header)
        default_btn.setStyleSheet(f"background-color: {self.colors['btn_orange']}; color: white; border: none;")
        default_btn.setGeometry(700, 65, 140, 28)
        default_btn.clicked.connect(self.set_default_values)

        # Выбор папки с конфигами
        config_label = QLabel("Папка конфигов Xenia:", header)
        config_label.setStyleSheet(f"background-color: {self.colors['frame_bg']}; color: white;")
        config_label.setGeometry(20, 68, 130, 25)

        self.config_path_edit = QLineEdit(header)
        self.config_path_edit.setStyleSheet("background-color: #0d0e1a; color: white; border: 1px solid #2c2f5a;")
        self.config_path_edit.setGeometry(160, 68, 400, 25)
        self.config_path_edit.editingFinished.connect(self.load_config_manager)

        config_browse_btn = QPushButton("Обзор", header)
        config_browse_btn.setStyleSheet(f"background-color: {self.colors['btn_blue']}; color: white; border: none;")
        config_browse_btn.setGeometry(570, 66, 80, 28)
        config_browse_btn.clicked.connect(self.browse_config_dir)

        reload_btn = QPushButton("Перезагрузить", header)
        reload_btn.setStyleSheet(f"background-color: {self.colors['btn_blue']}; color: white; border: none;")
        reload_btn.setGeometry(660, 66, 110, 28)
        reload_btn.clicked.connect(self.load_config_manager)

        # Основная область
        main = QWidget(self)
        main.setStyleSheet(f"background-color: {self.colors['bg']};")
        main.setGeometry(20, 130, 1010, 580)

        # Боковые кнопки
        self.create_key(main, 30, 20, "LB", "#7f8c8d", w=105, h=50, logical_name="LEFT_SHOULDER")
        self.create_key(main, 30, 80, "LT", "#e67e22", w=105, h=50, logical_name="LEFT_TRIGGER")
        self.create_key(main, 870, 20, "RB", "#7f8c8d", w=105, h=50, logical_name="RIGHT_SHOULDER")
        self.create_key(main, 870, 80, "RT", "#e67e22", w=105, h=50, logical_name="RIGHT_TRIGGER")

        # Центральные кнопки
        self.create_key(main, 390, 330, "Guide", "#3498db", w=100, h=50, logical_name="GUIDE")
        self.create_key(main, 490, 330, "Back", "#9b59b6", w=70, h=50, logical_name="BACK")
        self.create_key(main, 550, 330, "Start", "#9b59b6", w=70, h=50, logical_name="START")

        # Крестовины
        self.draw_cross_group(main, 80, 220, "D-PAD", "D-PAD",
                              "DPAD_UP", "DPAD_LEFT", "DPAD_RIGHT", "DPAD_DOWN",
                              center_clickable=False)
        self.draw_cross_group(main, 780, 220, "Right Stick", "RS",
                              "RIGHT_THUMB_UP", "RIGHT_THUMB_LEFT", "RIGHT_THUMB_RIGHT", "RIGHT_THUMB_DOWN",
                              center_clickable=True, center_logical_name="RIGHT_THUMB_PRESSED")
        self.draw_cross_group(main, 80, 440, "Left Stick", "LS",
                              "LEFT_THUMB_UP", "LEFT_THUMB_LEFT", "LEFT_THUMB_RIGHT", "LEFT_THUMB_DOWN",
                              center_clickable=True, center_logical_name="LEFT_THUMB_PRESSED")
        self.draw_cross_group(main, 780, 440, "ABXY", "ABXY",
                              "Y", "X", "B", "A", center_color="#57606f", center_clickable=False)

        # Кнопка применения
        apply_btn = QPushButton("ПРИМЕНИТЬ НАСТРОЙКИ В XENIA", self)
        apply_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        apply_btn.setStyleSheet(f"background-color: {self.colors['btn_green']}; color: white; border: none;")
        apply_btn.setGeometry(20, 720, 1010, 40)
        apply_btn.clicked.connect(self.export_xenia_config)

    def browse_config_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку с конфигами Xenia")
        if path:
            self.config_path_edit.setText(path)
            self.load_config_manager()

    def create_key(self, parent, x, y, text, color, w=40, h=40, clickable=True, logical_name=None):
        btn = GlowButton(text, glow_color="#0298ff", parent=parent)
        btn.setFixedSize(w, h)
        btn.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border: none;
            font-weight: bold;
            font-size: 10px;
        """)
        btn.move(x, y)
        if clickable and logical_name:
            self.input_btns[logical_name] = btn
            btn.clicked.connect(lambda checked, k=logical_name: self.show_kb(k))
        return btn

    def draw_cross_group(self, parent, x, y, title, center_txt,
                         up_key, left_key, right_key, down_key,
                         center_color="#2d5cf7", center_clickable=False, center_logical_name=None):
        title_lbl = QLabel(title, parent)
        title_lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"background-color: {self.colors['bg']}; color: white;")
        title_lbl.setGeometry(x + 40, y - 30, 150, 30)

        btn_size = 42
        self.create_key(parent, x + btn_size, y, "", self.colors["key_bg"],
                        w=btn_size, h=btn_size, logical_name=up_key)
        self.create_key(parent, x, y + btn_size, "", self.colors["key_bg"],
                        w=btn_size, h=btn_size, logical_name=left_key)

        if center_clickable and center_logical_name:
            self.create_key(parent, x + btn_size, y + btn_size, center_txt, center_color,
                            w=btn_size + 15, h=btn_size, logical_name=center_logical_name)
        else:
            lbl = QLabel(center_txt, parent)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Arial", 7, QFont.Weight.Bold))
            lbl.setStyleSheet(f"background-color: {center_color}; color: white; border: none;")
            lbl.setGeometry(x + btn_size, y + btn_size, btn_size + 15, btn_size)

        self.create_key(parent, x + (btn_size * 2) + 15, y + btn_size, "", self.colors["key_bg"],
                        w=btn_size, h=btn_size, logical_name=right_key)
        self.create_key(parent, x + btn_size, y + (btn_size * 2), "", self.colors["key_bg"],
                        w=btn_size, h=btn_size, logical_name=down_key)

    def show_kb(self, key):
        if not self.config_manager:
            QMessageBox.warning(self, "Ошибка", "Не загружен менеджер конфигов")
            return
        def callback(k):
            self.config_manager.update_mapping(self.current_profile, key, k)
            self.update_button_labels()

        kb = VirtualKeyboard(self, callback)
        kb.exec()

    def update_button_labels(self):
        if not self.config_manager or self.current_profile not in self.config_manager.profiles:
            return
        mapping = self.config_manager.profiles[self.current_profile]
        for logical, btn in self.input_btns.items():
            key_str = mapping.get(logical, "")
            if key_str:
                btn.setText(f"{self.get_display_name(logical)}\n({key_str})")
            else:
                btn.setText(self.get_display_name(logical))

    def update_button_label(self, logical, key_str):
        if logical in self.input_btns:
            btn = self.input_btns[logical]
            if key_str:
                display = self.config_manager.get_key_display_name(key_str)
                btn.setText(f"{self.get_display_name(logical)}\n({display})")
            else:
                btn.setText(self.get_display_name(logical))

    def get_display_name(self, logical_name):
        names = {
            "LEFT_SHOULDER": "LB", "RIGHT_SHOULDER": "RB",
            "LEFT_TRIGGER": "LT", "RIGHT_TRIGGER": "RT",
            "GUIDE": "Guide", "BACK": "Back", "START": "Start",
            "LEFT_THUMB_PRESSED": "LS", "RIGHT_THUMB_PRESSED": "RS",
            "A": "A", "B": "B", "X": "X", "Y": "Y",
            "DPAD_UP": "Up", "DPAD_DOWN": "Dn", "DPAD_LEFT": "Lt", "DPAD_RIGHT": "Rt",
            "LEFT_THUMB_UP": "Up", "LEFT_THUMB_DOWN": "Dn",
            "LEFT_THUMB_LEFT": "Lt", "LEFT_THUMB_RIGHT": "Rt",
            "RIGHT_THUMB_UP": "Up", "RIGHT_THUMB_DOWN": "Dn",
            "RIGHT_THUMB_LEFT": "Lt", "RIGHT_THUMB_RIGHT": "Rt",
        }
        return names.get(logical_name, logical_name)

    def update_profile_combo(self):
        if not self.config_manager:
            return
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self.config_manager.profiles:
            self.profile_combo.addItem(profile)
        if self.current_profile in self.config_manager.profiles:
            self.profile_combo.setCurrentText(self.current_profile)
        elif self.profile_combo.count() > 0:
            self.current_profile = self.profile_combo.itemText(0)
            self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)

    def on_profile_select(self, text):
        if text and text != self.current_profile:
            self.current_profile = text
            self.update_button_labels()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "Создать профиль", "Имя профиля (без расширения .config.toml):")
        if ok and name.strip():
            if self.config_manager.new_profile(name.strip()):
                self.update_profile_combo()
                self.profile_combo.setCurrentText(name.strip())
                self.current_profile = name.strip()
                self.update_button_labels()
            else:
                QMessageBox.warning(self, "Ошибка", "Профиль с таким именем уже существует")

    def delete_profile(self):
        if self.current_profile == "default":
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить профиль 'default'")
            return
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Удалить профиль '{self.current_profile}' и файл {self.current_profile}.config.toml?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.config_manager.delete_profile(self.current_profile):
                self.update_profile_combo()
                if self.profile_combo.count() > 0:
                    self.current_profile = self.profile_combo.currentText()
                self.update_button_labels()

    def set_default_values(self):
        if not self.config_manager:
            return
        reply = QMessageBox.question(self, "Подтверждение",
                                     f"Установить значения по умолчанию для профиля '{self.current_profile}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.set_default_mapping(self.current_profile)
            self.update_button_labels()
            QMessageBox.information(self, "Готово", "Значения по умолчанию установлены!")

    def export_xenia_config(self):
        if not self.config_manager:
            QMessageBox.warning(self, "Ошибка", "Сначала выберите папку с конфигами")
            return
        # Сохраняем все изменения принудительно
        self.config_manager._save_profile_to_file(self.current_profile)
        QMessageBox.information(self, "Готово", "Настройки сохранены в файл конфигурации Xenia.\n\n"
                               "Формат ключей: VK-коды (0x26=Up, 0x28=Down и т.д.)\n"
                               "^ = Ctrl, _ = Shift")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = XeniaUltimateEditor()
    window.show()
    sys.exit(app.exec())
