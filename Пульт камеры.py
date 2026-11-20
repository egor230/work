#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Графический пульт управления камерой iPhone.

Окно с кнопками:
  - Горизонтально / Вертикально
  - Поворот на 90/180 градусов и сброс
  - Включение/выключение вырезания водяной надписи
  - Перезапуск и остановка потока

Видео показывается прямо в этом окне — отдельный плеер не нужен.
"""

import os
import queue
import subprocess
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

BASE = Path(__file__).resolve().parent.parent.parent
BRIDGE = BASE / "IP Camera Lite - iPhone webcam.sh"
RUNTIME = Path("/tmp/opencode/iphone-cam")
VF_FILE = RUNTIME / "vf.txt"

PREVIEW_W, PREVIEW_H = 640, 360
FRAME_BYTES = PREVIEW_W * PREVIEW_H * 3


class CameraPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Пульт камеры iPhone")
        root.geometry("700x700")
        root.resizable(False, False)

        self.orient = tk.StringVar(value="landscape")
        self.rotation = tk.IntVar(value=0)   # 0, 90, -90, 180
        self.clean = tk.BooleanVar(value=True)
        self.stretch = tk.BooleanVar(value=False)  # растянуть кадр на всё окно без полос

        self.frame_queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.preview_proc = None
        self.photo = None
        self.busy = False
        self.frame_w, self.frame_h = PREVIEW_W, PREVIEW_H
        self.frame_bytes = FRAME_BYTES

        self._build_ui()
        # Предпросмотр запустится сам, когда мост будет готов (см. _run_bridge).
        self.apply_settings(start_bridge=True)
        self.root.after(60, self._ui_tick)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        self.video_label = tk.Label(top, background="black")
        self.video_label.pack()

        self.status = ttk.Label(
            self.root, text="Запуск…", anchor="w", foreground="#2c6e49",
            padding=(12, 4)
        )
        self.status.pack(fill="x")

        controls = ttk.Frame(self.root, padding=(10, 4, 10, 10))
        controls.pack(fill="both", expand=True)

        grp1 = ttk.LabelFrame(controls, text="Расположение кадра", padding=8)
        grp1.pack(fill="x", pady=4)
        ttk.Button(grp1, text="Горизонтально", width=18,
                   command=lambda: self.set_orient("landscape")).pack(side="left", padx=4)
        ttk.Button(grp1, text="Вертикально", width=18,
                   command=lambda: self.set_orient("portrait")).pack(side="left", padx=4)

        grp2 = ttk.LabelFrame(controls, text="Поворот", padding=8)
        grp2.pack(fill="x", pady=4)
        ttk.Button(grp2, text="Влево 90", width=12,
                   command=lambda: self.set_rotation(90)).pack(side="left", padx=4)
        ttk.Button(grp2, text="Вправо 90", width=12,
                   command=lambda: self.set_rotation(-90)).pack(side="left", padx=4)
        ttk.Button(grp2, text="180", width=12,
                   command=lambda: self.set_rotation(180)).pack(side="left", padx=4)
        ttk.Button(grp2, text="Сброс", width=12,
                   command=lambda: self.set_rotation(0)).pack(side="left", padx=4)

        grp3 = ttk.LabelFrame(controls, text="Кадр", padding=8)
        grp3.pack(fill="x", pady=4)
        self.clean_btn = ttk.Button(grp3, text="", width=22,
                                    command=self.toggle_clean)
        self.clean_btn.pack(side="left", padx=4)
        self.stretch_btn = ttk.Button(grp3, text="", width=22,
                                      command=self.toggle_stretch)
        self.stretch_btn.pack(side="left", padx=4)

        grp4 = ttk.Frame(controls, padding=8)
        grp4.pack(fill="x", pady=4)
        ttk.Button(grp4, text="Перезапустить поток", width=24,
                   command=self.restart).pack(side="left", padx=4)
        ttk.Button(grp4, text="Остановить", width=18,
                   command=self.stop_bridge).pack(side="left", padx=4)
        ttk.Button(grp4, text="Выход", width=12,
                   command=self.on_close).pack(side="left", padx=4)

        self._update_clean_button()

    def _update_clean_button(self):
        self.clean_btn.configure(
            text="Надпись УБРАНА" if self.clean.get() else "Надпись ВИДНА"
        )
        self.stretch_btn.configure(
            text="Растянуть ВКЛ" if self.stretch.get() else "Растянуть ВЫКЛ"
        )

    # ---------------------------------------------------------------- filter
    def build_filter(self) -> str:
        parts = []
        if self.clean.get():
            # маленький кадр в правом верхнем углу, где нет строки с текстом
            parts += ["crop=475:233:907:165", "transpose=2"]
        r = self.rotation.get()
        if r == 90:
            parts.append("transpose=2")
        elif r == -90:
            parts.append("transpose=1")
        elif r == 180:
            parts += ["hflip", "vflip"]

        if self.orient.get() == "portrait":
            w, h = 720, 1280
        else:
            w, h = 1280, 720

        if self.stretch.get():
            # Полное заполнение кадра без тёмных полос (пропорции искажаются).
            parts.append("scale=%d:%d" % (w, h))
        else:
            parts += [
                "scale=%d:%d:force_original_aspect_ratio=decrease" % (w, h),
                "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:black" % (w, h),
            ]
        parts.append("format=yuyv422")
        return ",".join(parts)

    def apply_settings(self, start_bridge=True):
        vf = self.build_filter()
        try:
            RUNTIME.mkdir(parents=True, exist_ok=True)
            VF_FILE.write_text(vf, encoding="utf-8")
        except OSError as exc:
            self._set_status("Не удалось записать фильтр: " + str(exc), error=True)
            return

        self.preview_filter = vf
        if start_bridge:
            self.stop_preview()
            self._set_status("Перезапускаю поток…")
            threading.Thread(target=self._run_bridge, args=("start",), daemon=True).start()
        else:
            self._set_status("Настройки сохранены")

    def _run_bridge(self, action: str):
        try:
            result = subprocess.run(
                [str(BRIDGE), action],
                capture_output=True, text=True, timeout=40
            )
            msg = (result.stdout or result.stderr or "").strip().splitlines()
            self.root.after(0, lambda: self._set_status(
                (msg[0] if msg else "Готово") + " | " + self.build_filter()
            ))
            if action == "start":
                self.root.after(0, self.start_preview)
        except Exception as exc:
            self.root.after(0, lambda: self._set_status(
                "Ошибка моста: " + str(exc), error=True))

    def _set_status(self, text, error=False):
        self.status.configure(
            text=text,
            foreground="#b00020" if error else "#2c6e49"
        )

    # ---------------------------------------------------------------- actions
    def set_orient(self, value):
        self.orient.set(value)
        self.apply_settings()

    def set_rotation(self, value):
        self.rotation.set(value)
        self.apply_settings()

    def toggle_clean(self):
        self.clean.set(not self.clean.get())
        self._update_clean_button()
        self.apply_settings()

    def toggle_stretch(self):
        self.stretch.set(not self.stretch.get())
        self._update_clean_button()
        self.apply_settings()

    def restart(self):
        self.apply_settings(start_bridge=True)

    def stop_bridge(self):
        self._run_bridge("stop")

    # ---------------------------------------------------------------- preview
    def stop_preview(self):
        self.stop_event.set()
        if self.preview_proc and self.preview_proc.poll() is None:
            self.preview_proc.terminate()
            try:
                self.preview_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.preview_proc.kill()
        self.preview_proc = None

    def start_preview(self):
        if self.preview_proc and self.preview_proc.poll() is None:
            return
        # Размер предпросмотра следует за ориентацией кадра — тогда внутри
        # окна нет чёрных полос.
        if self.orient.get() == "portrait":
            self.frame_w, self.frame_h = 270, 480
        else:
            self.frame_w, self.frame_h = 640, 360
        self.frame_bytes = self.frame_w * self.frame_h * 3
        vf = "scale=%d:%d" % (self.frame_w, self.frame_h)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "v4l2", "-i", "/dev/video2",
            "-vf", vf,
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ]
        self.stop_event.clear()
        self.preview_proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=self.frame_bytes
        )
        threading.Thread(target=self._preview_loop, daemon=True).start()

    def _read_exact(self, pipe, size):
        buf = bytearray()
        while len(buf) < size:
            chunk = pipe.read(size - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def _preview_loop(self):
        proc = self.preview_proc
        while not self.stop_event.is_set() and proc and proc.poll() is None:
            data = self._read_exact(proc.stdout, self.frame_bytes)
            if data is None:
                break
            img = Image.frombytes("RGB", (self.frame_w, self.frame_h), data)
            while not self.frame_queue.empty():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    break
            self.frame_queue.put(img)

    def _ui_tick(self):
        try:
            img = self.frame_queue.get_nowait()
        except queue.Empty:
            img = None
        if img is not None:
            self.photo = ImageTk.PhotoImage(img)
            self.video_label.configure(image=self.photo)
        self.root.after(60, self._ui_tick)

    def on_close(self):
        self.stop_preview()
        self.root.destroy()


def main():
    root = tk.Tk()
    CameraPanel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
