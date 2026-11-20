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

import json
import os
import queue
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

BASE = Path(__file__).resolve().parent.parent.parent
BRIDGE = BASE / "IP Camera Lite - iPhone webcam.sh"
RUNTIME = Path("/tmp/opencode/iphone-cam")
VF_FILE = RUNTIME / "vf.txt"
SETTINGS_FILE = Path(__file__).resolve().parent / "camera_settings.json"

PREVIEW_W, PREVIEW_H = 640, 360
FRAME_BYTES = PREVIEW_W * PREVIEW_H * 3


class CameraPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Пульт камеры iPhone")
        root.geometry("700x900")
        root.resizable(True, True)

        self.orient = tk.StringVar(value="landscape")
        self.rotation = tk.IntVar(value=0)   # 0, 90, -90, 180
        self.clean = tk.BooleanVar(value=True)
        self.stretch = tk.BooleanVar(value=False)  # растянуть кадр на всё окно без полос
        self.audio = tk.BooleanVar(value=True)     # передавать звук iPhone в виртуальный микрофон
        self.recording = False
        self.record_file = None
        self.record_dir = Path("/mnt/807EB5FA7EB5E954/видео")

        self.load_settings()

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
        self.root.bind("r", lambda _event: self.toggle_recording())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------------------------------------------- настройки
    def load_settings(self):
        """Восстанавливаем последние настройки из JSON рядом с программой."""
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.orient.set(data.get("orient", self.orient.get()))
        self.rotation.set(int(data.get("rotation", self.rotation.get())))
        self.clean.set(bool(data.get("clean", self.clean.get())))
        self.stretch.set(bool(data.get("stretch", self.stretch.get())))
        self.audio.set(bool(data.get("audio", self.audio.get())))

    def save_settings(self):
        data = {
            "orient": self.orient.get(),
            "rotation": self.rotation.get(),
            "clean": self.clean.get(),
            "stretch": self.stretch.get(),
            "audio": self.audio.get(),
        }
        try:
            SETTINGS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

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
        controls.pack(fill="x")

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
        self.audio_btn = ttk.Button(grp3, text="", width=20,
                                    command=self.toggle_audio)
        self.audio_btn.pack(side="left", padx=4)

        grp_rec = ttk.LabelFrame(controls, text="Запись видео", padding=8)
        grp_rec.pack(fill="x", pady=4)
        self.record_btn = ttk.Button(grp_rec, text="Начать запись", width=22,
                                     command=self.toggle_recording)
        self.record_btn.pack(side="left", padx=4)
        ttk.Label(grp_rec, text="файлы сохраняются в /mnt/807EB5FA7EB5E954/видео").pack(side="left")

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
        self.audio_btn.configure(
            text="Звук ВКЛ" if self.audio.get() else "Звук ВЫКЛ"
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
        self.save_settings()
        vf = self.build_filter()
        try:
            RUNTIME.mkdir(parents=True, exist_ok=True)
            VF_FILE.write_text(vf, encoding="utf-8")
        except OSError as exc:
            self._set_status("Не удалось записать фильтр: " + str(exc), error=True)
            return

        self.preview_filter = vf
        try:
            RUNTIME.mkdir(parents=True, exist_ok=True)
            (RUNTIME / "audio.txt").write_text(
                "on" if self.audio.get() else "off", encoding="utf-8"
            )
        except OSError:
            pass

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

    def toggle_audio(self):
        self.audio.set(not self.audio.get())
        self._update_clean_button()
        self.apply_settings()
        if self.audio.get():
            self._set_status(
                "Звук включён. В Zoom выберите микрофон 'iPhone Mic' "
                "(или 'Монитор iPhone Mic')."
            )

    def toggle_recording(self):
        self.recording = not self.recording
        self.record_btn.configure(
            text="Остановить запись" if self.recording else "Начать запись"
        )
        self.stop_preview()
        self.start_preview()
        if self.recording and self.record_file:
            self._set_status("Идёт запись: " + self.record_file)
        elif not self.recording:
            self._set_status("Запись сохранена: " + str(self.record_file))

    def restart(self):
        self.apply_settings(start_bridge=True)

    def stop_bridge(self):
        self._run_bridge("stop")

    # ---------------------------------------------------------------- preview
    def stop_preview(self):
        self.stop_event.set()
        proc = self.preview_proc
        if proc and proc.poll() is None:
            # SIGINT заставляет ffmpeg корректно закрыть MP4 (иначе файл битый).
            try:
                proc.send_signal(signal.SIGINT)
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.preview_proc = None

    def content_size(self):
        """Размер полезной картинки внутри /dev/video2 (без чёрных полей)."""
        if self.stretch.get():
            return None
        if self.clean.get():
            w, h = 233, 475
        else:
            w, h = 1440, 1080
        if self.rotation.get() in (90, -90):
            w, h = h, w
        return w, h

    def start_preview(self):
        if self.preview_proc and self.preview_proc.poll() is None:
            return
        # Размер предпросмотра следует за ориентацией кадра — тогда внутри
        # окна нет чёрных полос.
        if self.orient.get() == "portrait":
            dev_w, dev_h = 720, 1280
            max_w, max_h = 360, 480
        else:
            dev_w, dev_h = 1280, 720
            max_w, max_h = 640, 480

        content = self.content_size()
        if content is None:  # «Растянуть» — картинка уже заполняет устройство
            self.frame_w, self.frame_h = (
                (360, 640) if self.orient.get() == "portrait" else (640, 360)
            )
        else:
            cw0, ch0 = content
            ratio = min(max_w / cw0, max_h / ch0)
            self.frame_w = int(cw0 * ratio)
            self.frame_h = int(ch0 * ratio)
            self.frame_w -= self.frame_w % 2
            self.frame_h -= self.frame_h % 2
        self.frame_bytes = self.frame_w * self.frame_h * 3

        # Мост добавляет чёрные поля в /dev/video2 для Zoom.
        # В окне вырезаем их и масштабируем БЕЗ искажения пропорций.
        crop_part = ""
        if content is not None:
            cw0, ch0 = content
            ratio = min(dev_w / cw0, dev_h / ch0)
            cw, ch = int(cw0 * ratio), int(ch0 * ratio)
            cw -= cw % 2
            ch -= ch % 2
            cx, cy = (dev_w - cw) // 2, (dev_h - ch) // 2
            crop_part = "crop=%d:%d:%d:%d," % (cw, ch, cx, cy)
        vf = crop_part + "scale=%d:%d" % (self.frame_w, self.frame_h)

        if self.recording:
            try:
                self.record_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.record_file = str(self.record_dir / ("iphone_%s.ts" % stamp))
            except OSError as exc:
                self.recording = False
                self.record_file = None
                self.root.after(0, lambda: self._set_status(
                    "Не удалось создать папку записи: " + str(exc), error=True))

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "v4l2", "-i", "/dev/video2",
        ]
        if self.recording and self.record_file:
            fc = (
                "[0:v]%ssplit[a][b];"
                "[a]scale=%d:%d[pv];"
                "[b]null[rec]"
            ) % (crop_part, self.frame_w, self.frame_h)
            cmd += [
                "-filter_complex", fc,
                "-map", "[pv]", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
                "-map", "[rec]", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-r", "25", "-f", "mpegts", self.record_file,
            ]
        else:
            cmd += ["-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]

        self.stop_event.clear()
        err_log = open("/tmp/opencode/iphone-cam/preview_err.log", "ab")
        self.preview_proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=err_log, bufsize=self.frame_bytes
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
