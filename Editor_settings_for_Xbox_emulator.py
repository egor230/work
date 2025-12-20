import sys
import os
import shutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QComboBox, QPushButton, QLabel,
                             QInputDialog, QDialog, QFrame, QGraphicsDropShadowEffect,
                             QMessageBox, QSizePolicy)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from XemuLogic import XemuConfigManager

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
        self.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    
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
        self.setWindowTitle("Настройка клавиши")
        self.setFixedSize(1410, 450)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
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
            ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Insert', 'Delete', 'Home', 'End', 'PgUp', 'PgDn'],
            ['~\n`', '!\n1', '@\n2', '#\n3', '$\n4', '%\n5', '^\n6', '&\n7', '*\n8', '(\n9', ')\n0', '_\n-', '+\n=', 'Backspace', 'Num Lock', '/', '*', '-'],
            ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '{\n[', '}\n]', '|\n\\', ' 7\nHome', '8\n↑', '9\nPgUp', '+'],
            ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ':\n;', '"\n\'', '\nEnter\n', '4\n←', '5\n', '6\n→'],
            ['Shift_L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '<\n,', '>\n.', '?\n/', 'Shift_R', '1\nEnd', '2\n↓', '3\nPgDn', 'KEnter'],
            ['Ctrl', 'Windows', 'Alt_L', 'space', 'Alt_r', 'Fn', 'Menu', 'Ctrl_r', 'up', '0\nIns', ' . '],
            ['Left', 'Down', 'Right']
        ]

        buttons = {}
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
            current_x = X_OFFSET
            current_y = BASE_Y_STEP * i + Y_OFFSET
            last_x_end = X_OFFSET
            for j, key in enumerate(row):
                x1 = BASE_X_STEP * j + X_OFFSET
                y1 = BASE_Y_STEP * i + Y_OFFSET
                w = BUTTON_WIDTH
                h = BUTTON_HEIGHT
                btn = QPushButton(key, keyboard_widget)
                if self.callback_func:
                    # Определяем правильный ключ для сканкода
                    clean_key = key.split('\n')[0].strip()

                    # Специальная обработка клавиш
                    special_keys = {
                        # Numpad клавиши
                        '0': 'KP0', '1': 'KP1', '2': 'KP2', '3': 'KP3', '4': 'KP4',
                        '5': 'KP5', '6': 'KP6', '7': 'KP7', '8': 'KP8', '9': 'KP9',
                        '/': 'KPSLASH', '*': 'KPMULTIPLY', '-': 'KPMINUS', '+': 'KPPLUS',
                        '.': 'KPDOT',
                        # Специальные клавиши
                        'Shift_R': 'RIGHTSHIFT',
                        'Alt_r': 'RIGHTALT',
                        'Ctrl_r': 'RIGHTCTRL',
                        'Shift_L': 'LEFTSHIFT',
                        'Alt_L': 'LEFTALT',
                        'Ctrl': 'LEFTCTRL',
                        'up': 'UP', 'down': 'DOWN', 'left': 'LEFT', 'right': 'RIGHT',
                    }

                    # Если это специальная клавиша, используем правильное имя
                    if clean_key in special_keys:
                        key_for_scancode = special_keys[clean_key]
                    else:
                        key_for_scancode = clean_key

                    btn.clicked.connect(lambda checked, k=key_for_scancode: (self.callback_func(k), self.accept()))
                buttons[btn] = key

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
                            btn.resize(w, h)
                            btn.move(x_pos, y_pos)
                            continue

                if key == '\nEnter\n':
                    w = 140
                    h = BUTTON_HEIGHT * 2 + 5
                    btn.resize(w, h)
                    btn.move(x_pos, y_pos)
                    continue

                if i == 5:
                    if key == "space":
                        w = 300
                        x_pos = x1
                    elif key in ['Alt_r', 'Fn', 'Menu', 'Ctrl_r']:
                        x_pos = x1 + 210
                        w = BUTTON_WIDTH
                    elif key == 'up':
                        x_pos = x1 + 280
                        w = BUTTON_WIDTH
                    elif key == "0\nIns":
                        x_pos = x1 + 420
                        w = 120
                    elif key == ' . ':
                        x_pos = x1 + 490
                        w = BUTTON_WIDTH

                if i == 6:
                    if key in ['Left', 'Down', 'Right']:
                        x_pos = x1 + 770
                        y_pos = y1 - 9
                        w = BUTTON_WIDTH

                btn.resize(w, h)
                btn.move(x_pos, y_pos)

        layout.addWidget(keyboard_widget)

class XemuUltimateEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xemu Master Config Pro")
        self.setFixedSize(1400, 950)

        # Словарь соответствия кнопок геймпада для отображения
        self.button_labels = {
            # Основные кнопки
            "btn_a": "A", "btn_b": "B", "btn_x": "X", "btn_y": "Y",

            # D-PAD (левая крестовина) - теперь это Left Stick в новом layout
            "dpad1_up": "↑", "dpad1_down": "↓", "dpad1_left": "←", "dpad1_right": "→",

            # Left Stick
            "dpad2_up": "↑", "dpad2_down": "↓", "dpad2_left": "←", "dpad2_right": "→",
            "lstick_btn": "LS",

            # Right Stick
            "dpad3_up": "↑", "dpad3_down": "↓", "dpad3_left": "←", "dpad3_right": "→",
            "rstick_btn": "RS",

            # Триггеры
            "ltrigger": "LT", "rtrigger": "RT",

            # Системные кнопки (новые соответствия для нового layout)
            "back": "Back", "start": "Start",
            "guide": "Guide", "white": "LB", "black": "RB",
            "center_abxy": "ABXY", "center_dpad": "D-PAD"
        }

        # Инициализация менеджера логики
        self.config_manager = XemuConfigManager()
        self.config_manager.load_profiles()
        last_profile = self.config_manager.profiles.get("last_profile", "Default")
        # Проверяем, что last_profile не пустой и существует в профилях
        if not last_profile or last_profile not in self.config_manager.profiles:
            last_profile = "Default"
        self.current_profile = last_profile

        self.init_ui()
        self.update_profile_combo()
        self.update_button_labels()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(30, 30, 30, 30)
        main_lay.setSpacing(30)

        # Шапка с неоновым эффектом
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
                border-radius: 20px;
                border: 3px solid #3949ab;
            }
        """)
        header.setFixedHeight(100)

        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(30, 0, 30, 0)

        title_label = QLabel("🎮 <span style='font-size: 28px; color: #ffffff;'>XEMU ULTIMATE CONFIG</span>")
        title_label.setStyleSheet("background: transparent;")
        hlay.addWidget(title_label)
        hlay.addStretch()

        profile_label = QLabel("<span style='color: #bbdefb; font-size: 16px;'>ПРОФИЛЬ:</span>")
        profile_label.setStyleSheet("background: transparent;")
        hlay.addWidget(profile_label)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        self.profile_combo.setStyleSheet("""
            QComboBox {
                background: rgba(25, 25, 35, 0.9);
                color: #ffffff;
                padding: 12px;
                font-size: 15px;
                border-radius: 10px;
                border: 2px solid #5c6bc0;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background: rgba(25, 25, 35, 0.95);
                color: #ffffff;
                selection-background-color: #3949ab;
            }
        """)
        self.profile_combo.currentTextChanged.connect(self.on_profile_select)
        hlay.addWidget(self.profile_combo)

        btn_new = QPushButton("📋 СОЗДАТЬ ПРОФИЛЬ")
        btn_new.setFixedSize(200, 45)
        btn_new.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1976d2, stop:1 #1565c0);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2196f3, stop:1 #1976d2);
            }
        """)
        btn_new.clicked.connect(self.new_profile)
        hlay.addWidget(btn_new)

        btn_default = QPushButton("🔄 ПО УМОЛЧАНИЮ")
        btn_default.setFixedSize(200, 45)
        btn_default.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ff9800, stop:1 #f57c00);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffb74d, stop:1 #ff9800);
            }
        """)
        btn_default.clicked.connect(self.set_default_values)
        hlay.addWidget(btn_default)

        main_lay.addWidget(header)

        # Основная область с геймпадом
        gamepad_container = QWidget()
        gamepad_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 25px;
                border: 3px solid #3949ab;
            }
        """)

        gamepad_lay = QVBoxLayout(gamepad_container)
        gamepad_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Создаем область для геймпада
        self.pad_area = QWidget()
        self.pad_area.setFixedSize(1200, 700)
        self.pad_area.setStyleSheet("background: transparent;")
        gamepad_lay.addWidget(self.pad_area)

        main_lay.addWidget(gamepad_container)

        self.input_btns = {}
        self.build_xbox_layout()

        # Кнопка применения
        btn_apply = QPushButton("🚀 ПРИМЕНИТЬ НАСТРОЙКИ В XEMU")
        btn_apply.setFixedHeight(70)
        btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c853, stop:1 #64dd17);
                color: white;
                font-weight: bold;
                font-size: 18px;
                border-radius: 15px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00e676, stop:1 #76ff03);
            }
        """)
        btn_apply.clicked.connect(self.export_xemu_config)
        main_lay.addWidget(btn_apply)

    def build_xbox_layout(self):
        # Создаем основной layout для геймпада
        main_layout = QVBoxLayout(self.pad_area)
        main_layout.setSpacing(22)  # Уменьшено на 10% (было 25, стало 22)
        main_layout.setContentsMargins(18, 18, 18, 18)  # Уменьшено на 10%

        def create_glow_button(key, text, color=None, size=50, glow_color="#0298ff", text_color="#000000", is_round=True, w=None, h=None):
            """Создает кнопку с эффектом свечения"""
            button_name = self.button_labels.get(key, key)
            btn = GlowButton(button_name, glow_color, self.pad_area)

            # Используем заданные размеры или рассчитываем
            width = w or size
            height = h or (size if size <= 50 else size + 10)

            btn.setFixedSize(width, height)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            radius = "50%" if is_round else "10px"
            display_text_color = "#000080" if (color or '#ffffff') == "#e0e0e0" else text_color
            style = f"""
                QPushButton {{
                    background-color: {color or '#ffffff'};
                    color: {display_text_color};
                    border: 3px solid #666666;
                    border-radius: {radius};
                    font-weight: bold;
                    font-size: 10px;
                    text-align: center;
                    padding: 2px;
                }}
                QPushButton:hover {{
                    border-color: {glow_color};
                }}
            """
            if color:
                text_color_style = "#000080" if color == "#e0e0e0" else "#ffffff"
                style = f"""
                    QPushButton {{
                        background-color: {color};
                        color: {text_color_style};
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 10px;
                        text-align: center;
                        padding: 2px;
                    }}
                """
            btn.setStyleSheet(style)
            btn.shadow_effect.setColor(QColor(glow_color))
            btn.clicked.connect(lambda: self.show_kb(key))
            self.input_btns[key] = btn

            return btn

        def _get_grid_pos(pos):
            """Получить позицию в сетке 3x3 для крестовины"""
            positions = {
                'up': (0, 1), 'left': (1, 0), 'center': (1, 1),
                'right': (1, 2), 'down': (2, 1)
            }
            return positions[pos]

        def create_dpad(labels, title=None):
            """Крестовина 3x3 с возможным заголовком"""
            grid = QGridLayout()
            grid.setSpacing(6)

            if title:
                lbl = QLabel(title)
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setStyleSheet("""
                    font-weight: bold;
                    color: #ffffff;
                    font-size: 12px;
                    margin-bottom: 5px;
                """)
                grid.addWidget(lbl, 0, 0, 1, 3)
                offset = 1
            else:
                offset = 0

            # Создаем кнопки крестовины
            for pos, (key, label) in labels.items():
                if pos == 'center':
                    if title == "ABXY":
                        # Для ABXY центра создаем неактивную кнопку с меткой
                        btn = QPushButton(label)
                        btn.setFixedSize(45, 45)
                        btn.setStyleSheet("""
                            QPushButton {
                                background-color: #666;
                                color: white;
                                border-radius: 50%;
                                font-weight: bold;
                                font-size: 10px;
                            }
                        """)
                        btn.setEnabled(False)  # Неактивная кнопка
                    else:
                        btn = create_glow_button(key, label, "#9e9e9e", 45, "#9e9e9e", "#000", True)
                else:
                    btn = create_glow_button(key, label, "#e0e0e0", 50, "#03a9f4", "#000080", True)

                grid.addWidget(btn, offset + _get_grid_pos(pos)[0], _get_grid_pos(pos)[1])

            container = QWidget()
            container.setLayout(grid)
            return container

        # ───────────── TOP SYSTEM ZONE - White/Guide/Start/Back ─────────────
        top_system = QHBoxLayout()
        top_system.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_system.addWidget(create_glow_button("guide", "Guide", "#1e90ff", 60, "#1e90ff", "#ffffff", True, 80, 80))
        top_system.addWidget(create_glow_button("back", "Back", "#9c27b0", 50, "#9c27b0", "#ffffff", False))
        top_system.addWidget(create_glow_button("start", "Start", "#9c27b0", 50, "#9c27b0", "#ffffff", False))

        # ───────────── TOP ZONE - LB/LT и RB/RT ─────────────
        top = QHBoxLayout()

        left_top = QVBoxLayout()
        left_top.addWidget(create_glow_button("white", "LB", "#666", 50, "#666", "#ffffff", False))
        left_top.addWidget(create_glow_button("ltrigger", "LT", "#ff5722", 50, "#ff5722", "#ffffff", False))

        right_top = QVBoxLayout()
        right_top.addWidget(create_glow_button("black", "RB", "#666", 50, "#666", "#ffffff", False))
        right_top.addWidget(create_glow_button("rtrigger", "RT", "#ff5722", 50, "#ff5722", "#ffffff", False))

        top.addLayout(left_top)
        top.addStretch()
        top.addLayout(right_top)

        # ───────────── BOTTOM ZONE - Крестовины ─────────────
        bottom = QVBoxLayout()
        bottom.setSpacing(13)  # Уменьшено на 10% (было 20, стало 13)

        # Верхний ряд: D-PAD и Right Stick
        top_row = QHBoxLayout()
        top_row.setSpacing(170)  # Уменьшено на 10% (было 200, стало 170)

        dpad = create_dpad({
            "up": ("dpad1_up", "↑"),
            "down": ("dpad1_down", "↓"),
            "left": ("dpad1_left", "←"),
            "right": ("dpad1_right", "→"),
            "center": ("center_dpad", "D-PAD")
        }, "D-PAD")

        right_stick = create_dpad({
            "up": ("dpad3_up", "↑"),
            "down": ("dpad3_down", "↓"),
            "left": ("dpad3_left", "←"),
            "right": ("dpad3_right", "→"),
            "center": ("rstick_btn", "RS")
        }, "Right Stick")

        top_row.addWidget(dpad)
        top_row.addWidget(right_stick)

        # Нижний ряд: Left Stick и ABXY
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(68)  # Уменьшено на 10% (было 80, стало 68)

        left_stick = create_dpad({
            "up": ("dpad2_up", "↑"),
            "down": ("dpad2_down", "↓"),
            "left": ("dpad2_left", "←"),
            "right": ("dpad2_right", "→"),
            "center": ("lstick_btn", "LS")
        }, "Left Stick")

        abxy = create_dpad({
            "up": ("btn_y", "Y"),
            "down": ("btn_a", "A"),
            "left": ("btn_x", "X"),
            "right": ("btn_b", "B"),
            "center": ("center_abxy", "ABXY")  # Метка для центра
        }, "ABXY")

        bottom_row.addWidget(left_stick)
        bottom_row.addWidget(abxy)

        bottom.addLayout(top_row)
        bottom.addLayout(bottom_row)

        # ───────────── ASSEMBLE ─────────────
        main_layout.addLayout(top_system)  # Системные кнопки теперь сверху
        main_layout.addLayout(top)
        main_layout.addStretch()
        main_layout.addLayout(bottom)
        main_layout.addStretch()

    def show_kb(self, key):
        def callback(k):
            scancode = self.config_manager.scancodes.get(k.upper(), 0)
            self.config_manager.update_mapping(self.current_profile, key, scancode)
            self.update_button_label(key, k)
        kb = VirtualKeyboard(self, callback)
        kb.exec()

    def update_button_labels(self):
        if self.current_profile not in self.config_manager.profiles:
            # Если профиль не существует, показываем только названия кнопок
            for key, btn in self.input_btns.items():
                btn.setText(self.button_labels.get(key, key))
            return

        mapping = self.config_manager.profiles[self.current_profile]["mapping"]
        for key, btn in self.input_btns.items():
            button_name = self.button_labels.get(key, key)
            if key in mapping and mapping[key] != 0:
                scancode = mapping[key]
                key_name = next((k for k, v in self.config_manager.scancodes.items() if v == scancode), "???")
                btn.setText(f"{button_name}\n({key_name})")
            else:
                btn.setText(button_name)

    def update_button_label(self, key, val):
        btn = self.input_btns.get(key)
        if btn:
            button_name = self.button_labels.get(key, key)
            if val and val != "---":
                btn.setText(f"{button_name}\n({val})")
            else:
                btn.setText(button_name)

    def update_profile_combo(self):
        # Отключаем сигнал на время обновления, чтобы избежать нежелательных вызовов
        self.profile_combo.currentTextChanged.disconnect(self.on_profile_select)

        self.profile_combo.clear()
        for profile in self.config_manager.profiles:
            if profile != "last_profile":
                self.profile_combo.addItem(profile)

        # Устанавливаем текущий профиль, если он существует в списке
        if self.current_profile in [self.profile_combo.itemText(i) for i in range(self.profile_combo.count())]:
            self.profile_combo.setCurrentText(self.current_profile)
        else:
            # Если текущий профиль не найден, устанавливаем Default
            self.current_profile = "Default"
            self.profile_combo.setCurrentText(self.current_profile)

        # Включаем сигнал обратно
        self.profile_combo.currentTextChanged.connect(self.on_profile_select)

    def on_profile_select(self, text):
        if text and text in self.config_manager.profiles and text != "last_profile" and text != self.current_profile:
            self.current_profile = text
            self.update_button_labels()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "Создать профиль", "Имя профиля:")
        if ok and name:
            self.config_manager.new_profile(name)
            self.update_profile_combo()
            self.profile_combo.setCurrentText(name)
            self.current_profile = name
            self.update_button_labels()

    def set_default_values(self):
        """Устанавливает дефолтные значения для текущего профиля"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Подтверждение",
                                   f"Установить значения по умолчанию для профиля '{self.current_profile}'?\nЭто заменит все текущие настройки.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.set_default_mapping(self.current_profile)
            self.update_button_labels()
            QMessageBox.information(self, "Готово", "Значения по умолчанию установлены!")

    def export_xemu_config(self):
        # Сначала сохраняем выбранный профиль как последний
        self.config_manager.set_last_profile(self.current_profile)

        # Проверяем, что все кнопки настроены
        is_valid, message = self.config_manager.validate_mapping_complete(self.current_profile)
        if not is_valid:
            QMessageBox.warning(self, "Не настроена кнопка",
                              f"{message}\n\nПожалуйста, настройте эту кнопку перед сохранением.")
            return

        # Путь к основному конфигурационному файлу XEMU
        config_file = "/home/egor/.local/share/xemu/xemu/xemu.toml"

        print(f"Обновляю файл настроек XEMU: {config_file}")

        # Проверяем, существует ли файл
        if os.path.exists(config_file):
            print(f"Найден файл настроек XEMU: {config_file}")
        else:
            QMessageBox.warning(self, "Файл не найден",
                              f"Файл настроек XEMU не найден: {config_file}\n\nВозможно, XEMU еще не был запущен или директория изменилась.")
            return

        # Создаем резервную копию
        backup_file = config_file + ".backup"
        try:
            shutil.copy2(config_file, backup_file)
            print(f"Создана резервная копия: {backup_file}")
        except Exception as e:
            print(f"Не удалось создать резервную копию: {e}")

        # Экспортируем конфигурацию
        try:
            self.config_manager.export_xemu_config(config_file)
            QMessageBox.information(self, "Успешно", "Конфигурация XEMU обновлена!\n\nВсе настройки сохранены в правильной последовательности.")
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = XemuUltimateEditor()
    win.show()
    sys.exit(app.exec())