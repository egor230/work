#!/usr/bin/env python3
"""
Graphical launcher for GameScope 3.16+ and MangoHud.
PyQt6 + JSON config in the same directory.

Three tabs:
  1 — MangoHud (settings + preview/run with MangoHud only)
  2 — GameScope (settings + preview/run with GameScope only)
  3 — Combined (all settings + combined preview/run + save JSON button)

All settings are synchronised between tabs via a shared data model.
"""

import sys
import os
import json
from functools import partial
from PyQt6.QtCore import QTimer

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QSpinBox,
    QDoubleSpinBox, QFormLayout, QGridLayout, QScrollArea,
    QStyleFactory,
)
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QFont, QPalette, QColor

CONFIG_FILE = "MangoHud_Gamescope_config.json"

# ---------- MangoHud toggle fields (from PortProton) ---------- #
MH_TOGGLES = [
    ("fps",                 "FPS"),
    ("frametime",           "Время кадра (frametime)"),
    ("frame_count",         "Счётчик кадров (frame_count)"),
    ("full",                "Все метрики (full)"),
    ("cpu_temp",            "Температура CPU (cpu_temp)"),
    ("cpu_mhz",             "Частота CPU (cpu_mhz)"),
    ("cpu_power",           "Мощность CPU (cpu_power)"),
    ("core_load",           "Загрузка на ядро (core_load)"),
    ("core_bars",           "Полосы ядер (core_bars)"),
    ("gpu_temp",            "Температура GPU (gpu_temp)"),
    ("gpu_junction_temp",   "Температура контакта GPU (gpu_junction_temp)"),
    ("gpu_core_clock",      "Частота GPU (gpu_core_clock)"),
    ("gpu_mem_clock",       "Частота памяти GPU (gpu_mem_clock)"),
    ("gpu_mem_temp",        "Температура памяти GPU (gpu_mem_temp)"),
    ("gpu_name",            "Название GPU (gpu_name)"),
    ("gpu_power",           "Мощность GPU (gpu_power)"),
    ("gpu_voltage",         "Напряжение GPU (gpu_voltage)"),
    ("gpu_fan",             "Вентилятор GPU (gpu_fan)"),
    ("vram",                "VRAM (vram)"),
    ("ram",                 "RAM (ram)"),
    ("procmem",             "Память процесса resident (procmem)"),
    ("procmem_shared",      "Память процесса shared (procmem_shared)"),
    ("procmem_virt",        "Память процесса virtual (procmem_virt)"),
    ("swap",                "Swap (swap)"),
    ("resolution",          "Разрешение (resolution)"),
    ("engine_version",      "Версия движка (engine_version)"),
    ("engine_short_names",  "Короткие названия движков (engine_short_names)"),
    ("vulkan_driver",       "Драйвер Vulkan (vulkan_driver)"),
    ("wine",                "Версия Wine (wine)"),
    ("winesync",            "Синхронизация Wine (winesync)"),
    ("gamemode",            "GameMode (gamemode)"),
    ("vkbasalt",            "vkBasalt (vkbasalt)"),
    ("arch",                "Архитектура 32/64 (arch)"),
    ("exec_name",           "Имя процесса (exec_name)"),
    ("battery",             "Заряд батареи (battery)"),
    ("battery_icon",        "Иконка батареи (battery_icon)"),
    ("battery_time",        "Время от батареи (battery_time)"),
    ("battery_watt",        "Мощность батареи (battery_watt)"),
    ("device_battery_icon", "Иконка батареи устр-ва (device_battery_icon)"),
    ("io_read",             "Чтение IO (io_read)"),
    ("io_write",            "Запись IO (io_write)"),
    ("time",                "Время (time)"),
    ("version",             "Версия MangoHud (version)"),
    ("show_fps_limit",      "Показать лимит FPS (show_fps_limit)"),
    ("throttling_status",   "Троттлинг GPU (throttling_status)"),
    ("throttling_status_graph", "График троттлинга (throttling_status_graph)"),
    ("histogram",           "Гистограмма (histogram)"),
    ("horizontal",          "Горизонтальный режим (horizontal)"),
    ("horizontal_stretch",  "Растяжение гор. (horizontal_stretch)"),
    ("hud_compact",         "Компактный HUD (hud_compact)"),
    ("hud_no_margin",       "Без отступов (hud_no_margin)"),
    ("no_display",          "Скрыть HUD (no_display)"),
    ("no_small_font",       "Крупный шрифт (no_small_font)"),
    ("temp_fahrenheit",     "Фаренгейт (temp_fahrenheit)"),
    ("fps_metrics",         "Метрики FPS avg (fps_metrics)"),
    ("fcat",                "FCAT (fcat)"),
]

MH_FIXED_FIELDS = ["enabled", "position", "fps_only", "colour_overrides", "fps_limit"]

GS_FIELDS = [
    "enabled", "width", "height", "out_width", "out_height",
    "refresh", "borderless", "fullscreen", "force_fullscreen",
    "filter", "sharpness", "scaler", "max_scale_factor",
    "framerate_limit", "adaptive_sync", "mangoapp",
    "backend", "grab_keyboard", "force_grab_cursor",
    "expose_wayland", "mouse_sensitivity", "prefer_vk_device",
    "hdr_enabled", "hdr_itm_enable", "sdr_gamut_wideness",
    "hdr_sdr_content_nits", "hdr_itm_sdr_nits", "hdr_itm_target_nits",
    "force_composition", "hdr_force_support", "hdr_force_output",
    "hdr_force_heatmap", "realtime_scheduling",
]

# ---------- Defaults ---------- #

DEFAULT_MH = {
    "enabled": False,
    "position": "top-left",
    "fps_only": False,
    "colour_overrides": "",
    "fps_limit": 0,
}
# Default all toggles to False except the most common ones
for key, _ in MH_TOGGLES:
    DEFAULT_MH[key] = key in ("fps", "gpu_temp", "vram", "ram", "frametime", "cpu_temp")

DEFAULT_GS = {
    "enabled": False,
    "width": 1280, "height": 720,
    "out_width": 0, "out_height": 0,
    "refresh": 0, "borderless": True, "fullscreen": False,
    "force_fullscreen": False,
    "filter": "None (linear)", "sharpness": 10, "scaler": "Default",
    "max_scale_factor": 0.0,
    "framerate_limit": 0, "adaptive_sync": False, "mangoapp": False,
    "backend": "Auto", "grab_keyboard": False, "force_grab_cursor": False,
    "expose_wayland": False, "mouse_sensitivity": 1.0, "prefer_vk_device": "",
    "hdr_enabled": False, "hdr_itm_enable": False, "sdr_gamut_wideness": 0.5,
    "hdr_sdr_content_nits": 400, "hdr_itm_sdr_nits": 0, "hdr_itm_target_nits": 0,
    "force_composition": False, "hdr_force_support": False,
    "hdr_force_output": False, "hdr_force_heatmap": False,
    "realtime_scheduling": False,
}


def _set_widget_value(w, value):
    if isinstance(w, QCheckBox):
        w.setChecked(bool(value))
    elif isinstance(w, QSpinBox):
        w.setValue(int(value))
    elif isinstance(w, QDoubleSpinBox):
        w.setValue(float(value))
    elif isinstance(w, QComboBox):
        idx = w.findText(str(value))
        if idx >= 0:
            w.setCurrentIndex(idx)
    elif isinstance(w, QLineEdit):
        w.setText(str(value))
    else:
        try:
            w.setText(str(value))
        except AttributeError:
            pass


def _get_widget_value(w):
    if isinstance(w, QCheckBox):
        return w.isChecked()
    elif isinstance(w, QSpinBox):
        return w.value()
    elif isinstance(w, QDoubleSpinBox):
        return w.value()
    elif isinstance(w, QComboBox):
        return w.currentText()
    elif isinstance(w, QLineEdit):
        return w.text()
    return None


class GameScopeMangoHudApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameScope и MangoHud — Настройки")
        self.setMinimumSize(860, 780)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(script_dir, CONFIG_FILE)

        self._data = {"mangohud": dict(DEFAULT_MH), "gamescope": dict(DEFAULT_GS)}
        self._syncing = False
        self._preview_process = None
        self._preview_mode = None

        # Debounce timer for restarting preview (увеличил до 300 мс)
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(300)
        self._restart_timer.timeout.connect(self._do_restart_preview)

        self._cube_geom = None  # saved vkcube window {x, y, w, h}

        # Проверка наличия xdotool
        self._xdotool_available = self._check_xdotool()
        if not self._xdotool_available:
            print("WARNING: xdotool not found. Window position will not be restored.")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)

        self._build_tabs(main_layout)
        self._read_config()
        self._sync_all_widgets()
        # Restore window geometry (after UI is built)
        self._restore_window()

    # ---------- Проверка xdotool ---------- #
    def _check_xdotool(self):
        try:
            import subprocess
            subprocess.run(["xdotool", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    # ---------- Tabs ---------- #

    def _build_tabs(self, parent):
        self.tabs = QTabWidget()

        self._mh_w1 = {}
        self.tabs.addTab(self._build_tab("mh"), "Только MangoHud")

        self._gs_w2 = {}
        self.tabs.addTab(self._build_tab("gs"), "Только GameScope")

        self._mh_w3 = {}
        self._gs_w3 = {}
        self.tabs.addTab(self._build_tab("both"), "Совместный")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        parent.addWidget(self.tabs, stretch=1)

    # ---------- Build one tab ---------- #

    def _build_tab(self, mode):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        il = QVBoxLayout(inner)
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        # -- MangoHud section -- #
        if mode in ("mh", "both"):
            g = QGroupBox("MangoHud (наложение)")
            g_layout = QVBoxLayout(g)
            self._build_mh_ui(g_layout, mode)
            il.addWidget(g)

        # -- GameScope section -- #
        if mode in ("gs", "both"):
            g = QGroupBox("GameScope (микрокомпозитор)")
            g_layout = QVBoxLayout(g)
            self._build_gs_ui(g_layout, mode)
            il.addWidget(g)

        il.addStretch()

        # -- Launch area -- #
        sep = QGroupBox("Запуск")
        sl = QVBoxLayout(sep)
        sl.addWidget(QLabel("Готовая команда:"))
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setFont(QFont("Monospace", 10))
        preview.setMaximumHeight(80)
        sl.addWidget(preview)

        br = QHBoxLayout()
        pb = QPushButton("Предпросмотр с vkcube")
        pb.setToolTip("Запустить vkcube с текущими настройками")
        br.addWidget(pb)
        sb = QPushButton("Стоп")
        sb.setVisible(False)
        br.addWidget(sb)
        br.addStretch()
        sl.addLayout(br)

        # Save button on its own row, only on Combined tab
        if mode == "both":
            sr = QHBoxLayout()
            sr.addStretch()
            self.save_btn = QPushButton("Сохранить настройки в JSON")
            self.save_btn.setToolTip(f"Сохранить текущие настройки в {CONFIG_FILE}")
            self.save_btn.setStyleSheet("padding:5px 16px;")
            self.save_btn.clicked.connect(self._save_explicit)
            sr.addWidget(self.save_btn)
            sl.addLayout(sr)
        layout.addWidget(sep)

        # Store per-tab references
        setattr(self, f"_pv_{mode}", preview)
        setattr(self, f"_pb_{mode}", pb)
        setattr(self, f"_sb_{mode}", sb)

        cb = partial(self._preview_vkcube, mode)
        pb.clicked.connect(cb)
        sb.clicked.connect(partial(self._stop_preview, mode))

        return widget

    # ---------- MangoHud UI ---------- #

    def _build_mh_ui(self, parent_layout, mode):
        target = self._mh_w3 if mode == "both" else self._mh_w1

        form = QFormLayout()

        chk_en = QCheckBox("Включить наложение MangoHud")
        chk_en.setToolTip("Показывать поверхность с метриками поверх приложения")
        form.addRow(chk_en)
        target["enabled"] = chk_en

        cmb_pos = QComboBox()
        cmb_pos.addItems(["top-left", "top-right", "bottom-left", "bottom-right"])
        cmb_pos.setToolTip("Угол экрана для отображения наложения")
        form.addRow("Положение:", cmb_pos)
        target["position"] = cmb_pos

        chk_fpo = QCheckBox("Компактный режим (fps_only — только FPS)")
        chk_fpo.setToolTip("Показывать только счётчик FPS, скрыть все остальные метрики")
        form.addRow("Режим:", chk_fpo)
        target["fps_only"] = chk_fpo

        # FPS limit
        fps_row = QHBoxLayout()
        spn_fps_lim = QSpinBox()
        spn_fps_lim.setRange(0, 999); spn_fps_lim.setValue(0)
        spn_fps_lim.setSpecialValueText("Выкл")
        spn_fps_lim.setToolTip("Лимит FPS через MangoHud (fps_limit)")
        fps_row.addWidget(spn_fps_lim)
        fps_row.addWidget(QLabel("FPS"))
        form.addRow("Лимит FPS (MangoHud):", fps_row)
        target["fps_limit"] = spn_fps_lim

        # Toggles in a grid (4 columns)
        tg = QGroupBox("Отображаемые метрики")
        tg_grid = QGridLayout(tg)
        toggles = {}
        for i, (key, label) in enumerate(MH_TOGGLES):
            chk = QCheckBox(label)
            chk.setToolTip(f"Показывать {label.split('(')[-1].rstrip(')')}")
            tg_grid.addWidget(chk, i // 4, i % 4)
            toggles[key] = chk
        target["toggles"] = toggles
        form.addRow(tg)

        txt_col = QLineEdit()
        txt_col.setPlaceholderText("background=#000000,text_color=#ffffff")
        txt_col.setToolTip("Переопределение цветов (background, text_color и т.д.)")
        form.addRow("Цвета:", txt_col)
        target["colour_overrides"] = txt_col

        parent_layout.addLayout(form)

        # Connect signals
        chk_en.stateChanged.connect(lambda: self._on_changed("mh"))
        cmb_pos.currentTextChanged.connect(lambda _: self._on_changed("mh"))
        chk_fpo.stateChanged.connect(lambda: self._on_changed("mh"))
        spn_fps_lim.valueChanged.connect(lambda: self._on_changed("mh"))
        txt_col.textChanged.connect(lambda: self._on_changed("mh"))
        for chk in toggles.values():
            chk.stateChanged.connect(lambda: self._on_changed("mh"))

    # ---------- GameScope UI ---------- #

    def _build_gs_ui(self, parent_layout, mode):
        target = self._gs_w3 if mode == "both" else self._gs_w2

        form = QFormLayout()

        chk_en = QCheckBox("Включить микрокомпозитор GameScope")
        chk_en.setToolTip("GameScope создаёт отдельное игровое окружение")
        form.addRow(chk_en)
        target["enabled"] = chk_en

        # Display
        dg = QGroupBox("Экран")
        dl = QFormLayout(dg)
        r1 = QHBoxLayout()
        spn_w = QSpinBox(); spn_w.setRange(1, 7680); spn_w.setValue(1280)
        spn_w.setToolTip("Ширина игрового разрешения (-w)")
        spn_h = QSpinBox(); spn_h.setRange(1, 4320); spn_h.setValue(720)
        spn_h.setToolTip("Высота игрового разрешения (-h)")
        r1.addWidget(QLabel("Ш:")); r1.addWidget(spn_w); r1.addWidget(QLabel("В:")); r1.addWidget(spn_h)
        dl.addRow("Разрешение игры (-w -h):", r1)
        target["width"] = spn_w; target["height"] = spn_h

        r2 = QHBoxLayout()
        spn_ow = QSpinBox(); spn_ow.setRange(0, 7680); spn_ow.setValue(0)
        spn_ow.setSpecialValueText("Авто"); spn_ow.setToolTip("Ширина выходного разрешения (-W)")
        spn_oh = QSpinBox(); spn_oh.setRange(0, 4320); spn_oh.setValue(0)
        spn_oh.setSpecialValueText("Авто"); spn_oh.setToolTip("Высота выходного разрешения (-H)")
        r2.addWidget(QLabel("Ш:")); r2.addWidget(spn_ow); r2.addWidget(QLabel("В:")); r2.addWidget(spn_oh)
        dl.addRow("Выходное разрешение (-W -H):", r2)
        target["out_width"] = spn_ow; target["out_height"] = spn_oh

        spn_rr = QSpinBox(); spn_rr.setRange(0, 480); spn_rr.setValue(0)
        spn_rr.setSpecialValueText("По умолч."); spn_rr.setToolTip("Частота обновления (-r)")
        dl.addRow("Частота обновления (-r):", spn_rr)
        target["refresh"] = spn_rr

        nr = QHBoxLayout()
        chk_bl = QCheckBox("Без рамки (-b)"); chk_bl.setChecked(True)
        chk_bl.setToolTip("Окно без рамки")
        chk_fs = QCheckBox("Полный экран (-f)")
        chk_fs.setToolTip("Полноэкранный режим")
        chk_ffs = QCheckBox("Принудит. fullscreen (--force-windows-fullscreen)")
        chk_ffs.setToolTip("Принудительно развернуть окна внутри GameScope на весь экран")
        nr.addWidget(chk_bl); nr.addWidget(chk_fs); nr.addWidget(chk_ffs)
        dl.addRow("Режим окна:", nr)
        target["borderless"] = chk_bl; target["fullscreen"] = chk_fs
        target["force_fullscreen"] = chk_ffs
        form.addRow(dg)

        # Upscaling
        ug = QGroupBox("Масштабирование / Фильтр")
        ul = QFormLayout(ug)
        cmb_flt = QComboBox()
        cmb_flt.addItems(["None (linear)", "Nearest", "FSR", "NIS", "Pixel"])
        cmb_flt.setToolTip("Фильтр масштабирования (-F)")
        ul.addRow("Фильтр (-F):", cmb_flt)
        target["filter"] = cmb_flt
        spn_shp = QSpinBox(); spn_shp.setRange(0, 20); spn_shp.setValue(10)
        spn_shp.setToolTip("Резкость FSR/NIS (0=макс, 20=мин)")
        ul.addRow("Резкость (--sharpness):", spn_shp)
        target["sharpness"] = spn_shp
        cmb_scl = QComboBox()
        cmb_scl.addItems(["Default", "Auto", "Integer", "Fit", "Fill", "Stretch"])
        cmb_scl.setToolTip("Режим масштабирования (-S)")
        ul.addRow("Масштабирование (-S):", cmb_scl)
        target["scaler"] = cmb_scl
        dsp_msf = QDoubleSpinBox()
        dsp_msf.setRange(0.0, 100.0); dsp_msf.setValue(0.0)
        dsp_msf.setSpecialValueText("Выкл"); dsp_msf.setSingleStep(0.5)
        dsp_msf.setToolTip("Макс. масштаб (-m, 0.0 = выкл)")
        ul.addRow("Макс. масштаб (-m):", dsp_msf)
        target["max_scale_factor"] = dsp_msf
        form.addRow(ug)

        # Performance
        pg = QGroupBox("Производительность / FPS")
        pl = QFormLayout(pg)
        spn_fl = QSpinBox(); spn_fl.setRange(0, 999); spn_fl.setValue(0)
        spn_fl.setSpecialValueText("Выкл"); spn_fl.setToolTip("Лимит FPS через --framerate-limit")
        pl.addRow("Лимит FPS (--framerate-limit):", spn_fl)
        target["framerate_limit"] = spn_fl
        chk_as = QCheckBox("Адаптивная синхронизация / VRR (--adaptive-sync)")
        chk_as.setToolTip("FreeSync / G-Sync")
        pl.addRow(chk_as)
        target["adaptive_sync"] = chk_as
        chk_ma = QCheckBox("Встроенный mangoapp (--mangoapp)")
        chk_ma.setToolTip("Использовать встроенный оверлей mangoapp вместо MangoHud")
        pl.addRow(chk_ma)
        target["mangoapp"] = chk_ma
        form.addRow(pg)

        # Advanced
        ag = QGroupBox("Дополнительно")
        al = QFormLayout(ag)
        cmb_bk = QComboBox()
        cmb_bk.addItems(["Auto", "DRM", "SDL", "Wayland", "Headless"])
        cmb_bk.setToolTip("Бэкенд рендеринга (--backend)")
        al.addRow("Бэкенд (--backend):", cmb_bk)
        target["backend"] = cmb_bk

        adv_chks = QHBoxLayout()
        chk_gk = QCheckBox("Захват клавиатуры (-g)"); chk_gk.setToolTip("Захватить ввод с клавиатуры")
        chk_fgc = QCheckBox("Force grab cursor (--force-grab-cursor)")
        chk_fgc.setToolTip("Всегда использовать относительный режим мыши")
        chk_ew = QCheckBox("Expose Wayland (--expose-wayland)")
        chk_ew.setToolTip("Разрешить клиентам Wayland подключаться")
        chk_rt = QCheckBox("Realtime (--rt)")
        chk_rt.setToolTip("Планирование реального времени для GameScope")
        adv_chks.addWidget(chk_gk); adv_chks.addWidget(chk_fgc)
        adv_chks.addWidget(chk_ew); adv_chks.addWidget(chk_rt)
        al.addRow(adv_chks)
        target["grab_keyboard"] = chk_gk
        target["force_grab_cursor"] = chk_fgc
        target["expose_wayland"] = chk_ew
        target["realtime_scheduling"] = chk_rt

        dsp_ms = QDoubleSpinBox()
        dsp_ms.setRange(0.0, 20.0); dsp_ms.setValue(1.0)
        dsp_ms.setSingleStep(0.1); dsp_ms.setDecimals(1)
        dsp_ms.setToolTip("Чувствительность мыши (-s)")
        al.addRow("Чувствительность мыши (-s):", dsp_ms)
        target["mouse_sensitivity"] = dsp_ms

        txt_vk = QLineEdit()
        txt_vk.setPlaceholderText("1002:7300 (vendor:device)")
        txt_vk.setToolTip("Предпочитаемое Vulkan-устройство")
        al.addRow("Предп. Vulkan устройство:", txt_vk)
        target["prefer_vk_device"] = txt_vk

        # HDR group
        hg = QGroupBox("HDR")
        hl = QFormLayout(hg)
        chk_hdr = QCheckBox("Включить HDR (--hdr-enabled)")
        chk_hdr.setToolTip("Включить HDR-вывод")
        hl.addRow(chk_hdr)
        target["hdr_enabled"] = chk_hdr
        chk_hdr_itm = QCheckBox("SDR→HDR ITM (--hdr-itm-enabled)")
        chk_hdr_itm.setToolTip("Обратное тональное отображение SDR→HDR")
        hl.addRow(chk_hdr_itm)
        target["hdr_itm_enable"] = chk_hdr_itm
        hdr_nits1 = QSpinBox(); hdr_nits1.setRange(0, 10000); hdr_nits1.setValue(400)
        hdr_nits1.setToolTip("Яркость SDR контента в нитах (--hdr-sdr-content-nits)")
        hl.addRow("SDR контент (ниты):", hdr_nits1)
        target["hdr_sdr_content_nits"] = hdr_nits1
        hdr_nits2 = QSpinBox(); hdr_nits2.setRange(0, 1000); hdr_nits2.setValue(0)
        hdr_nits2.setSpecialValueText("Выкл")
        hdr_nits2.setToolTip("SDR ниты для ITM (--hdr-itm-sdr-nits)")
        hl.addRow("ITM SDR ниты:", hdr_nits2)
        target["hdr_itm_sdr_nits"] = hdr_nits2
        hdr_nits3 = QSpinBox(); hdr_nits3.setRange(0, 10000); hdr_nits3.setValue(0)
        hdr_nits3.setSpecialValueText("Выкл")
        hdr_nits3.setToolTip("Целевая яркость ITM (--hdr-itm-target-nits)")
        hl.addRow("ITM цель (ниты):", hdr_nits3)
        target["hdr_itm_target_nits"] = hdr_nits3
        dsp_sgw = QDoubleSpinBox()
        dsp_sgw.setRange(0.0, 1.0); dsp_sgw.setValue(0.5)
        dsp_sgw.setSingleStep(0.1); dsp_sgw.setDecimals(1)
        dsp_sgw.setToolTip("Ширина гаммы SDR (--sdr-gamut-wideness)")
        hl.addRow("Ширина гаммы SDR:", dsp_sgw)
        target["sdr_gamut_wideness"] = dsp_sgw

        # HDR debug toggles
        hdr_debug_row = QHBoxLayout()
        chk_fc = QCheckBox("Force composition (--force-composition)")
        chk_fc.setToolTip("Отключить прямой вывод на экран")
        chk_hfs = QCheckBox("Force HDR support")
        chk_hfs.setToolTip("(--hdr-debug-force-support)")
        chk_hfo = QCheckBox("Force HDR output")
        chk_hfo.setToolTip("(--hdr-debug-force-output)")
        chk_hfh = QCheckBox("HDR heatmap")
        chk_hfh.setToolTip("(--hdr-debug-heatmap)")
        hdr_debug_row.addWidget(chk_fc); hdr_debug_row.addWidget(chk_hfs)
        hdr_debug_row.addWidget(chk_hfo); hdr_debug_row.addWidget(chk_hfh)
        hl.addRow(hdr_debug_row)
        target["force_composition"] = chk_fc
        target["hdr_force_support"] = chk_hfs
        target["hdr_force_output"] = chk_hfo
        target["hdr_force_heatmap"] = chk_hfh

        form.addRow(ag)
        form.addRow(hg)

        parent_layout.addLayout(form)

        # Connect signals
        chk_en.stateChanged.connect(lambda: self._on_changed("gs"))
        spn_w.valueChanged.connect(lambda: self._on_changed("gs"))
        spn_h.valueChanged.connect(lambda: self._on_changed("gs"))
        spn_ow.valueChanged.connect(lambda: self._on_changed("gs"))
        spn_oh.valueChanged.connect(lambda: self._on_changed("gs"))
        spn_rr.valueChanged.connect(lambda: self._on_changed("gs"))
        chk_bl.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_fs.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_ffs.stateChanged.connect(lambda: self._on_changed("gs"))
        cmb_flt.currentTextChanged.connect(lambda _: self._on_changed("gs"))
        spn_shp.valueChanged.connect(lambda: self._on_changed("gs"))
        cmb_scl.currentTextChanged.connect(lambda _: self._on_changed("gs"))
        dsp_msf.valueChanged.connect(lambda: self._on_changed("gs"))
        spn_fl.valueChanged.connect(lambda: self._on_changed("gs"))
        chk_as.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_ma.stateChanged.connect(lambda: self._on_changed("gs"))
        cmb_bk.currentTextChanged.connect(lambda _: self._on_changed("gs"))
        chk_gk.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_fgc.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_ew.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_rt.stateChanged.connect(lambda: self._on_changed("gs"))
        dsp_ms.valueChanged.connect(lambda: self._on_changed("gs"))
        txt_vk.textChanged.connect(lambda: self._on_changed("gs"))
        chk_hdr.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_hdr_itm.stateChanged.connect(lambda: self._on_changed("gs"))
        hdr_nits1.valueChanged.connect(lambda: self._on_changed("gs"))
        hdr_nits2.valueChanged.connect(lambda: self._on_changed("gs"))
        hdr_nits3.valueChanged.connect(lambda: self._on_changed("gs"))
        dsp_sgw.valueChanged.connect(lambda: self._on_changed("gs"))
        chk_fc.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_hfs.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_hfo.stateChanged.connect(lambda: self._on_changed("gs"))
        chk_hfh.stateChanged.connect(lambda: self._on_changed("gs"))

    # ---------- Sync ---------- #

    def _on_changed(self, section):
        if self._syncing:
            return
        idx = self.tabs.currentIndex()
        mh_w = None; gs_w = None
        if idx == 0: mh_w = self._mh_w1
        elif idx == 1: gs_w = self._gs_w2
        elif idx == 2: mh_w = self._mh_w3; gs_w = self._gs_w3

        if section == "mh" and mh_w is not None:
            d = self._data["mangohud"]
            for key in MH_FIXED_FIELDS:
                w = mh_w.get(key)
                if w: d[key] = _get_widget_value(w)
            toggles = mh_w.get("toggles", {})
            for key, chk in toggles.items():
                d[key] = chk.isChecked()

        if section == "gs" and gs_w is not None:
            for key in GS_FIELDS:
                w = gs_w.get(key)
                if w: self._data["gamescope"][key] = _get_widget_value(w)

        self._save_config()

        if self._preview_process is not None:
            self._restart_timer.start()

        self._update_previews()

    def _sync_all_widgets(self):
        self._syncing = True

        # MH
        for target in [self._mh_w1, self._mh_w3]:
            if not target: continue
            d = self._data["mangohud"]
            for key in MH_FIXED_FIELDS:
                w = target.get(key)
                if w: _set_widget_value(w, d.get(key, DEFAULT_MH.get(key)))
            toggles = target.get("toggles", {})
            for key, chk in toggles.items():
                chk.setChecked(d.get(key, False))

        # GS
        for target in [self._gs_w2, self._gs_w3]:
            if not target: continue
            d = self._data["gamescope"]
            for key in GS_FIELDS:
                w = target.get(key)
                if w: _set_widget_value(w, d.get(key, DEFAULT_GS.get(key)))

        self._syncing = False
        self._update_previews()

    # ---------- Command builders ---------- #

    def _mh_config_string(self) -> str:
        """Build the MangoHud config string from current data model."""
        d = self._data["mangohud"]
        items = [f"position={d.get('position', 'top-left')}"]

        if d.get("fps_only"):
            items.append("fps_only")
            items.append("fps")
        else:
            for key, _ in MH_TOGGLES:
                if d.get(key, False):
                    items.append(key)

        colours = d.get("colour_overrides", "").strip()
        if colours:
            items.append(colours)

        fps_lim = d.get("fps_limit", 0)
        if fps_lim > 0:
            items.append(f"fps_limit={fps_lim}")

        return ",".join(items)

    def _build_mh_env(self):
        d = self._data["mangohud"]
        if not d.get("enabled"):
            return []
        return [
            "MANGOHUD=1",
            "VK_INSTANCE_LAYERS=VK_LAYER_MANGOHUD_overlay",
            f"MANGOHUD_CONFIG=\"{self._mh_config_string()}\"",
        ]

    def _build_gs_args(self):
        d = self._data["gamescope"]
        if not d.get("enabled"):
            return []
        args = []
        args.extend(["-w", str(d.get("width", 1280))])
        args.extend(["-h", str(d.get("height", 720))])
        ow = d.get("out_width", 0); oh = d.get("out_height", 0)
        if ow > 0: args.extend(["-W", str(ow)])
        if oh > 0: args.extend(["-H", str(oh)])
        rr = d.get("refresh", 0)
        if rr > 0: args.extend(["-r", str(rr)])
        if d.get("borderless", True): args.append("-b")
        if d.get("fullscreen", False): args.append("-f")
        if d.get("force_fullscreen", False): args.append("--force-windows-fullscreen")

        fv = {"None (linear)": "linear", "Nearest": "nearest",
              "FSR": "fsr", "NIS": "nis", "Pixel": "pixel"}.get(d.get("filter"))
        if fv:
            args.extend(["-F", fv])
            if d.get("filter") in ("FSR", "NIS"):
                args.extend(["--sharpness", str(d.get("sharpness", 10))])
        sv = {"Default": None, "Auto": "auto", "Integer": "integer",
              "Fit": "fit", "Fill": "fill", "Stretch": "stretch"}.get(d.get("scaler"))
        if sv: args.extend(["-S", sv])

        msf = d.get("max_scale_factor", 0.0)
        if msf > 0.0: args.extend(["-m", f"{msf:.1f}"])

        fl = d.get("framerate_limit", 0)
        if fl > 0: args.extend(["--framerate-limit", str(fl)])
        if d.get("adaptive_sync"): args.append("--adaptive-sync")
        if d.get("mangoapp"): args.append("--mangoapp")

        bv = {"Auto": None, "DRM": "drm", "SDL": "sdl",
              "Wayland": "wayland", "Headless": "headless"}.get(d.get("backend"))
        if bv: args.extend(["--backend", bv])
        if d.get("grab_keyboard"): args.append("-g")
        if d.get("force_grab_cursor"): args.append("--force-grab-cursor")
        if d.get("expose_wayland"): args.append("--expose-wayland")
        if d.get("realtime_scheduling"): args.append("--rt")

        ms = d.get("mouse_sensitivity", 1.0)
        if abs(float(ms) - 1.0) > 0.01:
            args.extend(["-s", f"{ms:.1f}"])
        vk_dev = d.get("prefer_vk_device", "").strip()
        if vk_dev: args.extend(["--prefer-vk-device", vk_dev])

        # HDR
        if d.get("hdr_enabled"): args.append("--hdr-enabled")
        if d.get("hdr_itm_enable"): args.append("--hdr-itm-enabled")
        sgw = d.get("sdr_gamut_wideness", 0.5)
        if abs(float(sgw) - 0.5) > 0.01:
            args.extend(["--sdr-gamut-wideness", f"{sgw:.1f}"])
        hsn = d.get("hdr_sdr_content_nits", 400)
        if int(hsn) != 400:
            args.extend(["--hdr-sdr-content-nits", str(hsn)])
        isn = d.get("hdr_itm_sdr_nits", 0)
        if int(isn) > 0:
            args.extend(["--hdr-itm-sdr-nits", str(isn)])
        itn = d.get("hdr_itm_target_nits", 0)
        if int(itn) > 0:
            args.extend(["--hdr-itm-target-nits", str(itn)])
        if d.get("force_composition"): args.append("--force-composition")
        if d.get("hdr_force_support"): args.append("--hdr-debug-force-support")
        if d.get("hdr_force_output"): args.append("--hdr-debug-force-output")
        if d.get("hdr_force_heatmap"): args.append("--hdr-debug-heatmap")

        return args

    def _build_command(self, mode, target):
        env = self._build_mh_env() if mode in ("mh", "both") else []
        gs_args = self._build_gs_args() if mode in ("gs", "both") else []
        parts = []
        if gs_args:
            parts.append(f"gamescope {' '.join(gs_args)} --")
        parts.append(target)
        cmd = " ".join(parts)
        env_str = " ".join(env)
        return f"{env_str} {cmd}" if env_str else cmd

    # ---------- ИСПРАВЛЕННЫЕ ФУНКЦИИ для сохранения/восстановления позиции ---------- #

    def _save_cube_geom(self):
        """Сохраняет текущую позицию окна vkcube с помощью xdotool."""
        if not self._xdotool_available:
            return
        try:
            import subprocess
            # Ищем окно по имени (обычно "vkcube"), если не найдено, пробуем по классу
            output = subprocess.check_output(
                ["xdotool", "search", "--name", "vkcube"],
                timeout=2, stderr=subprocess.DEVNULL
            ).decode().strip()
            if not output:
                # fallback на класс
                output = subprocess.check_output(
                    ["xdotool", "search", "--class", "vkcube"],
                    timeout=2, stderr=subprocess.DEVNULL
                ).decode().strip()
            if not output:
                print("xdotool: окно vkcube не найдено для сохранения позиции")
                return
            wid = output.split("\n")[0]
            geo = subprocess.check_output(
                ["xdotool", "getwindowgeometry", wid], timeout=2
            ).decode()
            x = y = w = h = None
            for line in geo.split("\n"):
                if "Position:" in line:
                    parts = line.split(":")[1].strip().split(",")
                    x, y = int(parts[0]), int(parts[1])
                if "Geometry:" in line:
                    parts = line.split(":")[1].strip().split("x")
                    w, h = int(parts[0]), int(parts[1])
            if None not in (x, y, w, h):
                self._cube_geom = {"x": x, "y": y, "w": w, "h": h}
                print(f"Сохранена позиция vkcube: x={x}, y={y}, w={w}, h={h}")
            else:
                print("xdotool: не удалось распарсить геометрию окна")
        except Exception as e:
            print(f"_save_cube_geom ошибка: {e}")

    def _restore_cube_geom(self):
        """Восстанавливает сохранённую позицию окна vkcube (с повторными попытками)."""
        if not self._xdotool_available or self._cube_geom is None:
            return
        try:
            import subprocess, time
            # Пытаемся найти окно до 15 раз с паузой 0.3 с
            for attempt in range(15):
                time.sleep(0.3)
                # сначала по имени, потом по классу
                output = subprocess.check_output(
                    ["xdotool", "search", "--name", "vkcube"],
                    timeout=1, stderr=subprocess.DEVNULL
                ).decode().strip()
                if not output:
                    output = subprocess.check_output(
                        ["xdotool", "search", "--class", "vkcube"],
                        timeout=1, stderr=subprocess.DEVNULL
                    ).decode().strip()
                if output:
                    wid = output.split("\n")[0]
                    subprocess.run(
                        ["xdotool", "windowmove", wid,
                         str(self._cube_geom["x"]), str(self._cube_geom["y"])],
                        timeout=2, check=True
                    )
                    print(f"Восстановлена позиция vkcube: x={self._cube_geom['x']}, y={self._cube_geom['y']}")
                    return
            print("xdotool: окно vkcube не появилось в течение ~4.5 секунд, позиция не восстановлена")
        except Exception as e:
            print(f"_restore_cube_geom ошибка: {e}")

    # ---------- Preview / Run ---------- #

    def _update_previews(self):
        for mode in ("mh", "gs", "both"):
            pv = getattr(self, f"_pv_{mode}", None)
            if pv is not None:
                pv.setText(self._build_command(mode, "vkcube"))

    def _on_tab_changed(self, idx):
        self._sync_all_widgets()
        self._update_previews()

    def _start_preview(self, mode):
        cmd = self._build_command(mode, "vkcube")
        if not cmd:
            QMessageBox.information(self, "Предпросмотр", "Включите MangoHud или GameScope.")
            return
        print(f"Preview start [{mode}]: {cmd}")
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        p.finished.connect(lambda: self._on_preview_finished())
        p.errorOccurred.connect(lambda err: print(f"Preview error: {err}"))
        p.start("bash", ["-c", cmd])
        self._preview_process = p
        self._preview_mode = mode
        pb = getattr(self, f"_pb_{mode}", None)
        sb = getattr(self, f"_sb_{mode}", None)
        if pb: pb.setEnabled(False)
        if sb: sb.setVisible(True)

    def _preview_vkcube(self, mode):
        self._start_preview(mode)

    def _do_restart_preview(self):
        mode = self._preview_mode
        if mode is None:
            return
        # Сначала сохраняем текущую позицию окна (если оно существует)
        self._save_cube_geom()
        # Останавливаем старый процесс
        self._stop_all_previews()
        # Запускаем новый
        self._start_preview(mode)
        # Восстанавливаем позицию (с повторными попытками)
        self._restore_cube_geom()

    def _stop_preview(self, mode):
        if self._preview_process is not None:
            self._preview_process.kill()
            self._preview_process.waitForFinished(2000)
        self._preview_process = None
        self._preview_mode = None
        self._restart_timer.stop()
        self._on_preview_finished()

    def _stop_all_previews(self):
        if self._preview_process is not None:
            self._preview_process.kill()
            self._preview_process.waitForFinished(2000)
        self._preview_process = None
        self._preview_mode = None
        self._restart_timer.stop()

    def _on_preview_finished(self):
        self._preview_process = None
        self._preview_mode = None
        self._restart_timer.stop()
        for m in ("mh", "gs", "both"):
            pb = getattr(self, f"_pb_{m}", None)
            sb = getattr(self, f"_sb_{m}", None)
            if pb: pb.setEnabled(True)
            if sb: sb.setVisible(False)

    def closeEvent(self, event):
        self._save_window()
        self._save_config()
        self._stop_all_previews()
        super().closeEvent(event)

    def _save_window(self):
        """Save window geometry into _data so it persists in JSON."""
        self._data["_window_geometry"] = {
            "x": self.x(), "y": self.y(),
            "w": self.width(), "h": self.height(),
            "maximized": self.isMaximized(),
        }

    def _restore_window(self):
        """Restore window geometry from _data."""
        g = self._data.get("_window_geometry")
        if g:
            if g.get("maximized"):
                self.showMaximized()
            else:
                self.setGeometry(g.get("x", 100), g.get("y", 100),
                                 g.get("w", 860), g.get("h", 780))

    def _save_explicit(self):
        self._save_config()
        QMessageBox.information(self, "Сохранено",
                                f"Настройки сохранены в файл:\n{self.config_path}")

    # ---------- JSON ---------- #

    def _read_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for section, defaults in [("mangohud", DEFAULT_MH), ("gamescope", DEFAULT_GS)]:
                saved = raw.get(section, {})
                for k, default_val in defaults.items():
                    if k in saved:
                        self._data[section][k] = saved[k]
            # Also load toggles from saved mangohud
            for key, _ in MH_TOGGLES:
                if key in raw.get("mangohud", {}):
                    self._data["mangohud"][key] = raw["mangohud"][key]
            _ = raw.get("target_app")  # ignore legacy field)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_config(self):
        if self._syncing:
            return
        mh_data = dict(self._data["mangohud"])
        gs_data = dict(self._data["gamescope"])
        data = {
            "mangohud": mh_data,
            "gamescope": gs_data,
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка записи конфига: {e}")


# ---------- Entry ---------- #

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(0xF0, 0xF0, 0xF0))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(0x00, 0x00, 0x00))
    pal.setColor(QPalette.ColorRole.Base, QColor(0xFF, 0xFF, 0xFF))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(0xE0, 0xE0, 0xE0))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(0xFF, 0xFF, 0xFF))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(0x00, 0x00, 0x00))
    pal.setColor(QPalette.ColorRole.Text, QColor(0x00, 0x00, 0x00))
    pal.setColor(QPalette.ColorRole.Button, QColor(0xE0, 0xE0, 0xE0))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(0x00, 0x00, 0x00))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(0xFF, 0x00, 0x00))
    pal.setColor(QPalette.ColorRole.Link, QColor(0x00, 0x00, 0xFF))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(0x00, 0x7A, 0xCC))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    app.setPalette(pal)
    window = GameScopeMangoHudApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()