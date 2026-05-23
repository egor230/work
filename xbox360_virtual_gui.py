import sys
import json
import threading
import subprocess
from evdev import InputDevice, categorize, ecodes, list_devices
import uinput

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

# ================= CONFIG =================
CONFIG_FILE = "profiles.json"

DEFAULT_PROFILE = {
    "A": "KEY_SPACE",
    "B": "KEY_LEFTCTRL",
    "X": "KEY_Q",
    "Y": "KEY_E",
    "LB": "KEY_Z",
    "RB": "KEY_C",
    "START": "KEY_ENTER",
    "BACK": "KEY_ESC"
}

# ================= GAMEPAD =================

class VirtualGamepad:
    def __init__(self):
        self.device = uinput.Device([
            uinput.BTN_SOUTH,  # A
            uinput.BTN_EAST,   # B
            uinput.BTN_NORTH,  # X
            uinput.BTN_WEST,   # Y
            uinput.BTN_TL,
            uinput.BTN_TR,
            uinput.BTN_START,
            uinput.BTN_SELECT,
        ])

    def press(self, btn):
        self.device.emit(btn, 1)

    def release(self, btn):
        self.device.emit(btn, 0)

# ================= MAIN APP =================

class XboxEmulator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("🎮 Xbox 360 Emulator (Linux)")
        self.resize(600, 500)

        self.gamepad = VirtualGamepad()
        self.mapping = DEFAULT_PROFILE.copy()
        self.running = False

        self.init_ui()
        self.load_profiles()

    def init_ui(self):
        layout = QVBoxLayout()

        self.profile_box = QComboBox()
        layout.addWidget(self.profile_box)

        btn_save = QPushButton("💾 Сохранить профиль")
        btn_save.clicked.connect(self.save_profile)
        layout.addWidget(btn_save)

        btn_load = QPushButton("📂 Загрузить профиль")
        btn_load.clicked.connect(self.load_selected_profile)
        layout.addWidget(btn_load)

        self.grid = QGridLayout()
        self.inputs = {}

        buttons = ["A","B","X","Y","LB","RB","START","BACK"]

        for i, btn in enumerate(buttons):
            label = QLabel(btn)
            combo = QComboBox()

            keys = [k for k in dir(ecodes) if k.startswith("KEY_")]
            combo.addItems(keys)

            combo.setCurrentText(self.mapping[btn])

            combo.currentTextChanged.connect(
                lambda text, b=btn: self.update_mapping(b, text)
            )

            self.inputs[btn] = combo

            self.grid.addWidget(label, i, 0)
            self.grid.addWidget(combo, i, 1)

        layout.addLayout(self.grid)

        self.status = QLabel("⏹ Остановлено")
        layout.addWidget(self.status)

        btn_start = QPushButton("▶ Старт")
        btn_start.clicked.connect(self.start)
        layout.addWidget(btn_start)

        btn_stop = QPushButton("⏹ Стоп")
        btn_stop.clicked.connect(self.stop)
        layout.addWidget(btn_stop)

        btn_xenia = QPushButton("🚀 Запустить Xenia")
        btn_xenia.clicked.connect(self.run_xenia)
        layout.addWidget(btn_xenia)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    # ================= LOGIC =================

    def update_mapping(self, btn, key):
        self.mapping[btn] = key

    def start(self):
        self.running = True
        self.status.setText("🟢 Работает")
        threading.Thread(target=self.listen, daemon=True).start()

    def stop(self):
        self.running = False
        self.status.setText("🔴 Остановлено")

    def listen(self):
        devices = [InputDevice(path) for path in list_devices()]

        keyboard = None
        for dev in devices:
            if "keyboard" in dev.name.lower():
                keyboard = dev
                break

        if not keyboard:
            self.status.setText("❌ Клавиатура не найдена")
            return

        key_state = {}

        while self.running:
            for event in keyboard.read_loop():
                if not self.running:
                    break

                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    code = ecodes.KEY[event.code]

                    for btn, mapped_key in self.mapping.items():
                        if code == mapped_key:

                            ubtn = self.get_uinput_button(btn)

                            if key_event.keystate == 1:
                                self.gamepad.press(ubtn)
                            elif key_event.keystate == 0:
                                self.gamepad.release(ubtn)

    def get_uinput_button(self, btn):
        return {
            "A": uinput.BTN_SOUTH,
            "B": uinput.BTN_EAST,
            "X": uinput.BTN_NORTH,
            "Y": uinput.BTN_WEST,
            "LB": uinput.BTN_TL,
            "RB": uinput.BTN_TR,
            "START": uinput.BTN_START,
            "BACK": uinput.BTN_SELECT,
        }[btn]

    # ================= PROFILES =================

    def load_profiles(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                self.profiles = json.load(f)
        except:
            self.profiles = {"default": DEFAULT_PROFILE}

        self.profile_box.clear()
        self.profile_box.addItems(self.profiles.keys())

    def save_profile(self):
        name = self.profile_box.currentText()

        self.profiles[name] = self.mapping.copy()

        with open(CONFIG_FILE, "w") as f:
            json.dump(self.profiles, f, indent=4)

        self.status.setText("✅ Профиль сохранён")

    def load_selected_profile(self):
        name = self.profile_box.currentText()
        self.mapping = self.profiles[name]

        for btn, combo in self.inputs.items():
            combo.setCurrentText(self.mapping[btn])

        self.status.setText("📂 Профиль загружен")

    # ================= XENIA =================

    def run_xenia(self):
        try:
            subprocess.Popen(["./xenia_edge_linux.AppImage"])
            self.status.setText("🚀 Xenia запущен")
        except Exception as e:
            self.status.setText(f"❌ Ошибка запуска: {e}")

# ================= RUN =================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = XboxEmulator()
    win.show()
    sys.exit(app.exec())