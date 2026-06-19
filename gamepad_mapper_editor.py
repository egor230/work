import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QCheckBox, QMessageBox, QInputDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from Gui_Editor_settings_for_Xbox360 import MainWindow, VirtualKeyboard, KEY_MAPPER
from эмуляция геймпада Xbox 360 import GamepadEmulator

class GamepadMapperEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor_controller = None
        self.profile_name = ""
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        title_label = QLabel("Gamepad Mapper Editor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        profile_controls = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_select)
        profile_controls.addWidget(QLabel("Profile:"))
        profile_controls.addWidget(self.profile_combo)

        create_btn = QPushButton("New")
        create_btn.clicked.connect(self._new_profile)
        profile_controls.addWidget(create_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_profile)
        profile_controls.addWidget(delete_btn)

        profile_controls.addStretch()
        main_layout.addLayout(profile_controls)

        self.keymap_table = QTableWidget()
        self.keymap_table.setColumnCount(2)
        self.keymap_table.setHorizontalHeaderLabels(["Button", "Key"])
        self.keymap_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.keymap_table.verticalHeader().setVisible(False)
        self.keymap_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.keymap_table)

        keymap_button_layout = QHBoxLayout()
        self.current_key_label = QLabel("Press a key to assign...")
        keymap_button_layout.addWidget(self.current_key_label)

        assign_btn = QPushButton("Assign Key")
        assign_btn.clicked.connect(self._start_key_assignment)
        keymap_button_layout.addWidget(assign_btn)

        keymap_button_layout.addStretch()
        main_layout.addLayout(keymap_button_layout)

        self.setLayout(main_layout)
        self._refresh_profiles()

    def set_controller(self, controller):
        self.editor_controller = controller
        self._refresh_profile_combo()

    def _refresh_profiles(self):
        if not self.editor_controller:
            return
        self.profile_combo.clear()
        self.editor_controller.load_profiles()
        if self.editor_controller.current_profile:
            self.profile_combo.addItems(self.editor_controller.current_profile.keys())

    def _on_profile_select(self):
        if not self.editor_controller:
            return
        self.editor_controller.load_profile(self.profile_combo.currentText())
        self._refresh_bindings()

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Enter profile name:")
        if ok and name:
            self.editor_controller.save_profile(name)
            self._refresh_profiles()

    def _delete_profile(self):
        if not self.editor_controller.current_profile or self.profile_combo.currentIndex() == 0:
            return
        self.editor_controller.delete_profile(self.profile_combo.currentText())
        self._refresh_profiles()

    def _refresh_bindings(self):
        if not self.editor_controller.current_profile:
            self.keymap_table.setRowCount(0)
            return

        binding_data = self.editor_controller.current_profile
        self.keymap_table.setRowCount(len(binding_data["keys"]))

        zones_data = self.editor_controller.get_zones_data() if hasattr(self.editor_controller, 'get_zones_data') else []

        for row, (button_name, key_value) in enumerate(binding_data["keys"].items()):
            self.keymap_table.setItem(row, 0, QTableWidgetItem(button_name))

            key_item = QTableWidgetItem(self._format_key_display(key_value))
            key_item.setData(Qt.ItemDataRole.UserRole, key_value)
            self.keymap_table.setItem(row, 1, key_item)

    def _format_key_display(self, key_value):
        if not key_value:
            return "None"
        try:
            xenia_val = KEY_MAPPER.display_to_xenia_value(key_value)
            return xenia_val
        except:
            return key_value

    def _start_key_assignment(self):
        self._assign_key_mode = True

    def update_emulator_mapping(self):
        if not self.editor_controller or not self.editor_controller.current_profile:
            return
        self.editor_controller.update_emulator_mapping(self.profile_combo.currentText())

    def closeEvent(self, event):
        self.editor_controller.stop_emulator()
        event.accept()
