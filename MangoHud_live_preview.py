#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MangoHud_live_preview.py
# Живой предпросмотр настроек MangoHud для PortProton.
#
# Заменяет кнопку "Предпросмотр" (184) во вкладке MangoHud (gui_mangohud):
# вместо pw_mangohud_preview (vkcube в фореграунде, без live-обновления)
# открывается это GTK-окно. vkcube крутится В ФОНЕ с MANGOHUD_CONFIGFILE,
# MangoHud следит за файлом через inotify (notify.cpp) и применяет
# изменения на лету. Окно при этом не закрывается.
#
# Принцип (проверено по исходникам MangoHud 0.8.4 из папки "Custom wine"):
#   - MANGOHUD_CONFIG ставить НЕЛЬЗЯ — она перекроет файл при перечитывании;
#   - файл конфига должен существовать ДО старта vkcube;
#   - формат файла: одна опция на строку (parseConfigLine).
#
# Запуск:
#   python3 MangoHud_live_preview.py [--ppdb /path/to/game.exe.ppdb]
#
# Поведение:
#   * на старте читает MANGOHUD_CONFIG и FPS_LIMIT (env -> .ppdb -> дефолт);
#   * кнопка "Сохранить" пишет MANGOHUD_CONFIG/FPS_LIMIT/PW_MANGOHUD в .ppdb
#     и печатает в stdout строки "MANGOHUD_CONFIG=..." и "FPS_LIMIT=...";
#   * кнопка "Отмена"/крестик — ничего не пишет и не печатает.
#   Нужен рабочий Vulkan-драйвер, дисплей и PyGObject (python3-gi).

import argparse
import glob
import os
import re
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

# ----------------------------------------------------------------------------
# Пути PortProton (портативные плагины: vkcube, libMangoHud.so, манифесты слоёв)
# ----------------------------------------------------------------------------
PORT_WINE_PATH = os.environ.get("PORT_WINE_PATH", "/home/egor/PortProton")

DEFAULT_MANGOHUD_CONFIG = (
    "arch,cpu_mhz,cpu_temp,engine_version,gamemode,gpu_core_clock,"
    "gpu_mem_clock,gpu_name,gpu_temp,ram,resolution,vkbasalt,vram,"
    "vulkan_driver,wine,winesync"
)


def find_plugins_path():
    cands = sorted(
        glob.glob(os.path.join(PORT_WINE_PATH, "data", "tmp", "plugins_v*")),
        reverse=True,
    )
    if cands:
        return cands[0]
    return os.path.join(PORT_WINE_PATH, "data", "tmp", "plugins_v20")


PW_PLUGINS_PATH = os.environ.get("PW_PLUGINS_PATH", find_plugins_path())
VKCUBE = os.path.join(PW_PLUGINS_PATH, "portable", "bin", "vkcube")
VK_LAYER_PATH = os.path.join(
    PW_PLUGINS_PATH, "portable", "share", "vulkan", "implicit_layer.d"
)
LIB_DIRS = (
    os.path.join(PW_PLUGINS_PATH, "portable", "lib", "lib64"),
    os.path.join(PW_PLUGINS_PATH, "portable", "lib", "lib32"),
)

USER = os.environ.get("USER", "egor")
PREVIEW_CONF = os.environ.get(
    "MANGOHUD_PREVIEW_CONF", f"/tmp/PortProton_{USER}/mangohud_preview.conf"
)

# ----------------------------------------------------------------------------
# Список опций — тот же, что во вкладке MangoHud у PortProton (LIST_MH)
# ----------------------------------------------------------------------------
MANGOHUD_OPTIONS = (
    "ARCH BATTERY BATTERY_ICON BATTERY_TIME BATTERY_WATT CORE_BARS CORE_LOAD "
    "CPU_MHZ CPU_POWER CPU_TEMP DEVICE_BATTERY_ICON ENGINE_SHORT_NAMES "
    "ENGINE_VERSION EXEC_NAME FCAT FPS_METRICS FRAME_COUNT FRAMETIME FULL "
    "GAMEMODE GPU_CORE_CLOCK GPU_FAN GPU_JUNCTION_TEMP GPU_MEM_CLOCK "
    "GPU_MEM_TEMP GPU_NAME GPU_POWER GPU_TEMP GPU_VOLTAGE HISTOGRAM HORIZONTAL "
    "HORIZONTAL_STRETCH HUD_COMPACT HUD_NO_MARGIN IO_READ IO_WRITE NO_DISPLAY "
    "NO_SMALL_FONT PROCMEM PROCMEM_SHARED PROCMEM_VIRT RAM RESOLUTION "
    "SHOW_FPS_LIMIT SWAP TEMP_FAHRENHEIT THROTTLING_STATUS THROTTLING_STATUS_GRAPH "
    "TIME VERSION VKBASALT VRAM VULKAN_DRIVER WINE WINESYNC"
).split()

FPS_LIMITS = ("30", "40", "45", "48", "60", "75", "90", "120", "144", "165", "175", "240")


# ----------------------------------------------------------------------------
# Чтение/запись .ppdb (формат: строки "export KEY="value"", значение экранировано)
# ----------------------------------------------------------------------------
def _unescape(value):
    return value.replace("\\\\", "\\").replace('\\"', '"')


def read_db_values(ppdb):
    db = {}
    try:
        with open(ppdb, "r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                ln = raw.strip()
                m = re.match(r"^export\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)$", ln)
                if not m:
                    continue
                key, val = m.group(1), m.group(2).strip()
                if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                    val = val[1:-1]
                db[key] = _unescape(val)
    except OSError:
        pass
    return db


def set_db_value(ppdb, key, value):
    esc = value.replace("\\", "\\\\").replace('"', '\\"')
    new_line = 'export %s="%s"' % (key, esc)
    try:
        with open(ppdb, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    pat = re.compile(r"^export\s+%s=.*$" % re.escape(key))
    replaced = False
    for i, ln in enumerate(lines):
        if pat.match(ln.strip()):
            lines[i] = new_line
            replaced = True
            break
    if not replaced:
        lines.append(new_line)
    try:
        with open(ppdb, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def del_db_value(ppdb, key):
    pat = re.compile(r"^export\s+%s=.*$" % re.escape(key))
    try:
        with open(ppdb, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    lines = [ln for ln in lines if not pat.match(ln.strip())]
    try:
        with open(ppdb, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def get_layer_names():
    """Читает имена слоёв MangoHud из манифестов (для VK_INSTANCE_LAYERS)."""
    names = []
    for manifest in ("MangoHud64.json", "MangoHud32.json"):
        path = os.path.join(VK_LAYER_PATH, manifest)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        m = re.search(r'"name"\s*:\s*"([^"]+)"', text)
        if m:
            names.append(m.group(1))
    return names


class MangoHudPreview(Gtk.Window):
    def __init__(self, ppdb=None):
        super().__init__(title="MangoHud — живой предпросмотр (PortProton)")
        self.set_default_size(960, 680)
        self.set_border_width(8)
        self.vkcube = None
        self.vkcube_watch = None
        self.checkboxes = {}
        self.fps_boxes = {}
        self._loading = True
        self._fps_only = False
        self.ppdb = ppdb
        self.db = read_db_values(ppdb) if ppdb else {}

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        # --- Верхняя панель: запуск/остановка vkcube ---
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.btn_start = Gtk.Button(label="Старт предпросмотра (vkcube)")
        self.btn_start.connect("clicked", self.on_start)
        self.btn_stop = Gtk.Button(label="Стоп предпросмотра")
        self.btn_stop.set_sensitive(False)
        self.btn_stop.connect("clicked", self.on_stop)
        btn_row.pack_start(self.btn_start, False, False, 0)
        btn_row.pack_start(self.btn_stop, False, False, 0)
        vbox.pack_start(btn_row, False, False, 0)

        # --- Свиток с чекбоксами опций MangoHud ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        grid = Gtk.Grid(column_spacing=14, row_spacing=2)
        for i, opt in enumerate(MANGOHUD_OPTIONS):
            cb = Gtk.CheckButton(label=opt.lower().replace("_", " "))
            cb.set_tooltip_text(opt.lower())
            cb.connect("toggled", self.on_option_toggled, opt)
            self.checkboxes[opt] = cb
            grid.attach(cb, i % 4, i // 4, 1, 1)
        scrolled.add(grid)
        vbox.pack_start(scrolled, True, True, 0)

        # --- Нижняя панель: лимит FPS и размер шрифта ---
        fps_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fps_row.pack_start(Gtk.Label(label="Лимит FPS (L_SHIFT+F1):"),
                           False, False, 0)
        for rate in FPS_LIMITS:
            cb = Gtk.CheckButton(label=rate)
            cb.set_tooltip_text("fps_limit=" + rate)
            cb.connect("toggled", self.on_option_toggled, "fps_limit")
            self.fps_boxes[rate] = cb
            fps_row.pack_start(cb, False, False, 0)
        vbox.pack_start(fps_row, False, False, 0)

        font_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        font_row.pack_start(Gtk.Label(label="Размер шрифта (0 = авто):"),
                            False, False, 0)
        self.font_spin = Gtk.SpinButton.new_with_range(0, 100, 1)
        self.font_spin.set_value(0)
        self.font_spin.connect("value-changed", self.on_option_toggled, "font_size")
        font_row.pack_start(self.font_spin, False, False, 0)
        vbox.pack_start(font_row, False, False, 0)

        # --- Кнопки Сохранить / Отмена ---
        act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_save = Gtk.Button(label="Сохранить и вернуться")
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self.on_save)
        btn_cancel = Gtk.Button(label="Отмена")
        btn_cancel.connect("clicked", self.on_cancel)
        act_row.pack_end(btn_save, False, False, 0)
        act_row.pack_end(btn_cancel, False, False, 0)
        vbox.pack_start(act_row, False, False, 0)

        # --- Строка статуса ---
        self.status = Gtk.Label(label="", xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
        vbox.pack_start(self.status, False, False, 0)

        self.connect("delete-event", self.on_cancel)
        self.load_existing_config()
        self._loading = False
        self.write_config()

    # ------------------------------------------------------------------
    # Стартовое состояние и сборка конфига
    # ------------------------------------------------------------------
    def load_existing_config(self):
        initial = os.environ.get("MANGOHUD_CONFIG", "") or self.db.get(
            "MANGOHUD_CONFIG", ""
        )
        if not initial:
            initial = DEFAULT_MANGOHUD_CONFIG

        fps = os.environ.get("FPS_LIMIT", "") or self.db.get("FPS_LIMIT", "")
        if fps:
            for rate in fps.split("+"):
                if rate in self.fps_boxes:
                    self.fps_boxes[rate].set_active(True)

        seen = set()
        for item in initial.split(","):
            item = item.strip().lower()
            if not item:
                continue
            if "=" in item:
                key, val = item.split("=", 1)
                if key == "fps_limit":
                    for rate in val.split("+"):
                        if rate in self.fps_boxes:
                            self.fps_boxes[rate].set_active(True)
                elif key == "font_size":
                    try:
                        self.font_spin.set_value(float(val))
                    except ValueError:
                        pass
                continue
            if item == "fps_only":
                self._fps_only = True
                continue
            seen.add(item)
        for opt, cb in self.checkboxes.items():
            cb.set_active(opt.lower() in seen)

    def build_config_lines(self):
        if self._fps_only:
            return ["fps_only"]

        parts = [o.lower() for o in MANGOHUD_OPTIONS if self.checkboxes[o].get_active()]

        fps = [r for r in FPS_LIMITS if self.fps_boxes[r].get_active()]
        if fps:
            if "show_fps_limit" not in parts:
                parts.append("show_fps_limit")
            parts.append("fps_limit=" + "+".join(fps))

        font_size = int(self.font_spin.get_value())
        if font_size <= 0:
            font_size = self.auto_font_size()
        if font_size > 0:
            parts.append("font_size=%d" % font_size)

        if "fps_only" in parts:
            parts = ["fps_only"]
        return parts

    def auto_font_size(self):
        try:
            screen = Gdk.Screen.get_default()
            if screen is not None:
                height = screen.get_height()
                if height > 0:
                    return max(10, height // 45)
        except Exception:
            pass
        return 0

    def write_config(self):
        os.makedirs(os.path.dirname(PREVIEW_CONF), exist_ok=True)
        lines = self.build_config_lines()
        with open(PREVIEW_CONF, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        self.status.set_text(
            "Конфиг: " + (", ".join(lines) if lines else "(пусто)")
            + "\nФайл: " + PREVIEW_CONF
            + ("\n.ppdb: " + self.ppdb if self.ppdb else "")
        )

    def on_option_toggled(self, _widget, _opt=None):
        if self._loading:
            return
        self.write_config()

    # ------------------------------------------------------------------
    # Сохранить / Отмена
    # ------------------------------------------------------------------
    def on_save(self, _btn):
        lines = self.build_config_lines()
        new_config = ",".join(lines)
        fps_selected = [r for r in FPS_LIMITS if self.fps_boxes[r].get_active()]
        new_fps = "+".join(fps_selected) if fps_selected else ""

        if self.ppdb:
            set_db_value(self.ppdb, "MANGOHUD_CONFIG", new_config)
            set_db_value(self.ppdb, "PW_MANGOHUD", "1")
            if new_fps:
                set_db_value(self.ppdb, "FPS_LIMIT", new_fps)
            else:
                del_db_value(self.ppdb, "FPS_LIMIT")
            # Чтобы gui_mangohud (рекурсивная вкладка) показал новые значения
            print("MANGOHUD_CONFIG=" + new_config)
            print("FPS_LIMIT=" + new_fps)

        self.stop_vkcube()
        Gtk.main_quit()

    def on_cancel(self, _win=None, _event=None):
        self.stop_vkcube()
        Gtk.main_quit()

    # ------------------------------------------------------------------
    # Управление vkcube
    # ------------------------------------------------------------------
    def on_start(self, _btn):
        self.write_config()  # файл должен существовать ДО старта vkcube
        if self.vkcube is not None and self.vkcube.poll() is None:
            self.status.set_text(self.status.get_text() + "\n[ vkcube уже запущен ]")
            return
        if not os.path.isfile(VKCUBE):
            self.show_error("vkcube не найден: " + VKCUBE)
            return

        env = os.environ.copy()
        # ВАЖНО: без MANGOHUD_CONFIG — иначе она перекроет файл при перечитывании
        env.pop("MANGOHUD_CONFIG", None)
        env["MANGOHUD_CONFIGFILE"] = PREVIEW_CONF
        env["MANGOHUD"] = "1"
        env["VK_ADD_IMPLICIT_LAYER_PATH"] = VK_LAYER_PATH
        env["VK_ADD_LAYER_PATH"] = VK_LAYER_PATH
        layer_names = get_layer_names()
        if layer_names:
            env["VK_INSTANCE_LAYERS"] = ":".join(layer_names)
        env["LD_LIBRARY_PATH"] = ":".join(
            d for d in (env.get("LD_LIBRARY_PATH", ""), *LIB_DIRS) if d
        )

        try:
            self.vkcube = subprocess.Popen([VKCUBE], env=env)
        except OSError as exc:
            self.show_error("Не удалось запустить vkcube: %s" % exc)
            return

        self.btn_start.set_sensitive(False)
        self.btn_stop.set_sensitive(True)
        self.vkcube_watch = GLib.timeout_add(1000, self.check_vkcube)
        self.status.set_text(self.status.get_text() + "\n[ vkcube запущен ]")

    def check_vkcube(self):
        if self.vkcube is None:
            return False
        code = self.vkcube.poll()
        if code is not None:
            self.status.set_text(self.status.get_text() + "\n[ vkcube завершён ]")
            self.btn_start.set_sensitive(True)
            self.btn_stop.set_sensitive(False)
            self.vkcube = None
            if self.vkcube_watch is not None:
                GLib.source_remove(self.vkcube_watch)
                self.vkcube_watch = None
            return False
        return True

    def on_stop(self, _btn):
        self.stop_vkcube()

    def stop_vkcube(self):
        if self.vkcube is None:
            return
        try:
            self.vkcube.terminate()
            try:
                self.vkcube.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.vkcube.kill()
        except Exception:
            pass
        self.vkcube = None
        self.btn_start.set_sensitive(True)
        self.btn_stop.set_sensitive(False)

    def show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()


def main():
    parser = argparse.ArgumentParser(description="MangoHud live preview (PortProton)")
    parser.add_argument("--ppdb", default=None, help="path to .ppdb file")
    parser.add_argument("--no-vkcube", action="store_true",
                        help="не запускать vkcube автоматически")
    args = parser.parse_args()

    win = MangoHudPreview(ppdb=args.ppdb)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    if not args.no_vkcube:
        GLib.idle_add(win.on_start, None)
    Gtk.main()


if __name__ == "__main__":
    main()
