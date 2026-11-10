import sys
import os
import json
import subprocess
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QMessageBox, QStatusBar,
    QListWidget, QListWidgetItem, QProgressBar, QAbstractItemView,
    QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPalette, QColor

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAVE_MULTIMEDIA = True
except Exception:
    HAVE_MULTIMEDIA = False

VIDEO_FILTERS = (
    "Видео (*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.flv *.ts *.wmv);"
    "*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.flv *.ts *.wmv;"
    "Все файлы (*)_*"
)
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".ts", ".wmv"}


def _find_videos(folder: str) -> List[str]:
    """Находит в папке все видеофайлы и возвращает их пути, отсортированные по имени."""
    out = []
    d = Path(folder)
    if not d.is_dir():
        return out
    for item in sorted(d.iterdir()):
        if item.is_file() and item.suffix.lower() in VIDEO_EXTS:
            out.append(str(item))
    return out


def _even(v: int) -> int:
    return int(v) + 1 if int(v) % 2 else int(v)


def _probe(path: str) -> dict:
    """Пробует разрешение, fps, наличие звука и длительность одного видео."""
    cmd = ["ffprobe", "-v", "error",
           "-show_entries", "stream=width,height,r_frame_rate,codec_type,duration:format=duration",
           "-of", "json", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe не читает: {path}\n{r.stderr.strip()}")
    data = json.loads(r.stdout)
    w, h, fps, dur = 1920, 1080, 30.0, None
    has_audio = False
    for s in data.get("streams", []):
        ctype = s.get("codec_type")
        if ctype == "video":
            w = s.get("width") or w
            h = s.get("height") or h
            try:
                num, den = (s.get("r_frame_rate") or "30/1").split("/")
                fps = int(num) / max(1, int(den))
            except (ValueError, ZeroDivisionError):
                fps = 30.0
            if s.get("duration"):
                dur = float(s["duration"])
        elif ctype == "audio":
            has_audio = True
    if dur is None and data.get("format", {}).get("duration"):
        dur = float(data["format"]["duration"])
    return {"w": w, "h": h, "fps": fps, "audio": has_audio, "dur": dur}


class FfmpegWorker(QThread):
    progress = pyqtSignal(int)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, cmd: List[str], total_us: int):
        super().__init__()
        self.cmd = cmd
        self.total_us = total_us

    def run(self):
        try:
            with subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ) as proc:
                for line in proc.stdout:
                    s = line.strip()
                    if s.startswith("out_time_us="):
                        try:
                            val = int(s.split("=")[1])
                            if self.total_us > 0:
                                self.progress.emit(min(100, int(val * 100 // self.total_us)))
                        except ValueError:
                            pass
                    elif s == "progress=end" and self.total_us > 0:
                        self.progress.emit(100)
                err = proc.stderr.read()
                proc.wait()
                if proc.returncode != 0:
                    self.failed.emit((err or "").strip()[-1500:])
                else:
                    self.finished_ok.emit()
        except Exception as e:
            self.failed.emit(str(e))


class VideoMerger(QWidget):
    """Объединение нескольких видео в одно: очередь, сортировка, предпросмотр, FFmpeg."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Объединить видео")
        self.setGeometry(660, 120, 720, 820)
        self.worker = None
        self.last_dir = os.getcwd()

        self.apply_light_theme()

        self.lbl_queue = QLabel("Очередь видео (стрелками менять порядок):")
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setMinimumHeight(180)

        self.btn_add = QPushButton("Добавить видео")
        self.btn_add.clicked.connect(self.add_videos)
        self.btn_folder = QPushButton("Выбрать папку с видео")
        self.btn_folder.clicked.connect(self.select_video_folder)
        self.btn_up = QPushButton("Вверх")
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down = QPushButton("Вниз")
        self.btn_down.clicked.connect(self.move_down)
        self.btn_remove = QPushButton("Удалить")
        self.btn_remove.clicked.connect(self.remove_selected)

        row_add = QHBoxLayout()
        row_add.addWidget(self.btn_add)
        row_add.addWidget(self.btn_folder)

        row_move = QHBoxLayout()
        row_move.addWidget(self.btn_up)
        row_move.addWidget(self.btn_down)
        row_move.addWidget(self.btn_remove)
        row_move.addStretch(1)

        self.lbl_sort = QLabel("Сортировка:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Как добавлено (не трогать)", "as_is")
        self.sort_combo.addItem("По имени (по алфавиту)", "name_asc")
        self.sort_combo.addItem("По имени (обратный порядок)", "name_desc")
        self.sort_combo.addItem("По размеру (сначала мелкие)", "size_asc")
        self.sort_combo.addItem("По размеру (сначала крупные)", "size_desc")
        self.sort_combo.addItem("По дате (новые сверху)", "date_new")
        self.sort_combo.addItem("По дате (старые сверху)", "date_old")
        self.sort_combo.activated.connect(self.on_sort)

        if HAVE_MULTIMEDIA:
            self.player = QMediaPlayer(self)
            self.audio_out = QAudioOutput(self)
            self.player.setAudioOutput(self.audio_out)
            self.video_widget = QVideoWidget(self)
            self.video_widget.setFixedSize(360, 200)
            self.player.setVideoOutput(self.video_widget)
            self.btn_play = QPushButton("Запустить")
            self.btn_pause = QPushButton("Пауза")
            self.btn_stop = QPushButton("Стоп")
            self.btn_play.clicked.connect(self.play_preview)
            self.btn_pause.clicked.connect(self.pause_preview)
            self.btn_stop.clicked.connect(self.stop_preview)
            preview_layout = QVBoxLayout()
            preview_layout.addWidget(QLabel("Предпросмотр (выбери видео из списка):"))
            preview_layout.addWidget(self.video_widget)
            ctl = QHBoxLayout()
            ctl.addWidget(self.btn_play)
            ctl.addWidget(self.btn_pause)
            ctl.addWidget(self.btn_stop)
            ctl.addStretch(1)
            preview_layout.addLayout(ctl)
            self.list.currentItemChanged.connect(self.on_preview_select)
        else:
            self.player = None
            preview_layout = QVBoxLayout()
            preview_layout.addWidget(QLabel("Предпросмотр недоступен (нет QtMultimedia)"))
            preview_layout.addStretch(1)

        self.lbl_out = QLabel("Папка «Вывод»:")
        self.out_dir = QLineEdit(os.path.join(os.getcwd(), "Вывод"))
        self.btn_out_dir = QPushButton("Выбрать")
        self.btn_out_dir.clicked.connect(self.select_out_dir)

        out_dir_row = QHBoxLayout()
        out_dir_row.addWidget(self.out_dir)
        out_dir_row.addWidget(self.btn_out_dir)

        self.lbl_name = QLabel("Имя объединённого файла:")
        self.out_name = QLineEdit("combined.mp4")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.combine)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Готово")

        sort_row = QHBoxLayout()
        sort_row.addWidget(self.lbl_sort)
        sort_row.addWidget(self.sort_combo)

        layout = QVBoxLayout()
        layout.addWidget(self.lbl_queue)
        layout.addWidget(self.list)
        layout.addLayout(row_add)
        layout.addLayout(row_move)
        layout.addLayout(sort_row)
        layout.addLayout(preview_layout)
        layout.addWidget(self.lbl_out)
        layout.addLayout(out_dir_row)
        layout.addWidget(self.lbl_name)
        layout.addWidget(self.out_name)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.merge_btn)
        layout.addWidget(self.status_bar)
        self.setLayout(layout)

    def apply_light_theme(self):
        app = QApplication.instance()
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Button, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)

    def add_videos(self):
        cmd = ["zenity", "--file-selection", "--multiple", f"--file-filter={VIDEO_FILTERS}"]
        if os.path.isdir(self.last_dir):
            cmd.append(f"--filename={self.last_dir}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return
        files = [p for p in r.stdout.splitlines() if p.strip()]
        self._add_paths(files)

    def select_video_folder(self):
        cmd = ["zenity", "--file-selection", "--directory"]
        if os.path.isdir(self.last_dir):
            cmd.append(f"--filename={self.last_dir}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return
        folder = r.stdout.strip()
        if not folder:
            return
        found = _find_videos(folder)
        if not found:
            QMessageBox.information(self, "Нет видео", f"В папке не найдено видео:\n{folder}")
            self.refresh_status()
            return
        self.last_dir = folder
        if not self.out_dir.text().strip():
            self.out_dir.setText(str(Path(folder) / "Вывод"))
        self._add_paths(found)

    def _add_paths(self, paths):
        existing = set(os.path.normpath(x) for x in self.ordered_paths())
        added = 0
        for f in paths:
            p = Path(f)
            if not p.is_file():
                continue
            key = os.path.normpath(str(p))
            if key in existing:
                continue
            existing.add(key)
            item = QListWidgetItem(p.name)
            item.setToolTip(str(p))
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.list.addItem(item)
            added += 1
        self.refresh_status()
        if added:
            self.status_bar.showMessage(f"Добавлено: {added}")

    def ordered_paths(self) -> List[str]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())]

    def on_sort(self, index):
        mode = self.sort_combo.itemData(index)
        if mode and mode != "as_is":
            self.apply_sort(mode)

    def apply_sort(self, mode):
        self.list.blockSignals(True)
        try:
            items = [self.list.takeItem(0) for _ in range(self.list.count())]
        finally:
            pass

        def keyf(it):
            p = Path(it.data(Qt.ItemDataRole.UserRole))
            try:
                st = p.stat()
            except OSError:
                st = None
            if mode in ("name_asc", "name_desc"):
                return p.name.lower()
            if mode in ("size_asc", "size_desc"):
                return st.st_size if st else 0
            if mode in ("date_new", "date_old"):
                return st.st_mtime if st else 0
            return ""

        rev = mode in ("name_desc", "size_desc", "date_new")
        items.sort(key=keyf, reverse=rev)
        for it in items:
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.refresh_status()

    def on_preview_select(self, current, previous):
        if not self.player:
            return
        path = current.data(Qt.ItemDataRole.UserRole) if current else None
        if path and os.path.isfile(path):
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()

    def play_preview(self):
        if self.player:
            self.player.play()

    def pause_preview(self):
        if self.player:
            self.player.pause()

    def stop_preview(self):
        if self.player:
            self.player.stop()

    def move_up(self):
        row = self.list.currentRow()
        if row > 0:
            item = self.list.takeItem(row)
            self.list.insertItem(row - 1, item)
            self.list.setCurrentRow(row - 1)

    def move_down(self):
        row = self.list.currentRow()
        if row < self.list.count() - 1:
            item = self.list.takeItem(row)
            self.list.insertItem(row + 1, item)
            self.list.setCurrentRow(row + 1)

    def remove_selected(self):
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def select_out_dir(self):
        cmd = ["zenity", "--file-selection", "--directory"]
        cur = self.out_dir.text().strip()
        if cur and os.path.isdir(cur):
            cmd.append(f"--filename={cur}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            self.out_dir.setText(r.stdout.strip())

    def refresh_status(self):
        self.status_bar.showMessage(f"В очереди: {self.list.count()}")

    def combine(self):
        paths = self.ordered_paths()
        if len(paths) < 2:
            QMessageBox.critical(self, "Ошибка", "Добавьте хотя бы 2 видео для объединения.")
            return
        if self.player:
            self.player.stop()
        out_dir = self.out_dir.text().strip() or os.path.join(os.getcwd(), "Вывод")
        name = self.out_name.text().strip() or "combined.mp4"
        if not name.lower().endswith(".mp4"):
            name += ".mp4"
        out_path = Path(out_dir) / name
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не создана папка Вывод:\n{e}")
            return
        self.build_and_run(paths, str(out_path))

    def build_and_run(self, paths, out_path):
        self.merge_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Собираю информацию о видео...")
        QApplication.processEvents()
        try:
            info = [_probe(p) for p in paths]
        except Exception as e:
            self.merge_btn.setEnabled(True)
            self.status_bar.showMessage("Ошибка")
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать видео:\n{e}")
            return

        tw = _even(max(i["w"] for i in info))
        th = _even(max(i["h"] for i in info))
        out_fps = max(1, round(max(i["fps"] for i in info)))
        total_us = int(sum(i["dur"] or 0 for i in info) * 1_000_000)

        missing_dur = [p for p, i in zip(paths, info) if not i["audio"] and not i["dur"]]
        if missing_dur:
            self.merge_btn.setEnabled(True)
            self.status_bar.showMessage("Ошибка")
            QMessageBox.critical(
                self, "Ошибка",
                "Не удалось определить длительность видео без звука:\n" +
                "\n".join(os.path.basename(x) for x in missing_dur)
            )
            return

        sources = []
        segments = []
        for i, (p, inf) in enumerate(zip(paths, info)):
            sources.append(
                f"[{i}:v:0]scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={out_fps},"
                f"format=yuv420p,settb=AVTB[v{i}]"
            )
            if inf["audio"]:
                sources.append(
                    f"[{i}:a:0]aresample=48000,aformat=channel_layouts=stereo,"
                    f"asetpts=PTS-STARTPTS[a{i}]"
                )
            else:
                dur = f"{inf['dur']:.6f}".rstrip("0").rstrip(".") or "0"
                sources.append(
                    f"anullsrc=r=48000:cl=stereo[s{i}];"
                    f"[s{i}]atrim=duration={dur},asetpts=PTS-STARTPTS[a{i}]"
                )
            segments.append(f"[v{i}][a{i}]")
        filter_complex = ";".join(sources + ["".join(segments) + f"concat=n={len(paths)}:v=1:a=1[vout][aout]"])

        args = []
        for p in paths:
            args += ["-i", p]
        cmd = ["ffmpeg", "-y", "-hide_banner"] + args + [
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            "-loglevel", "error", "-progress", "pipe:1",
            out_path,
        ]

        self.worker = FfmpegWorker(cmd, total_us)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_ok.connect(lambda: self.on_done(out_path))
        self.worker.failed.connect(self.on_fail)
        self.status_bar.showMessage("Объединяю видео...")
        self.worker.start()

    def on_done(self, out_path):
        self.merge_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_bar.showMessage("Готово")
        QMessageBox.information(self, "Готово", f"Видео объединено.\nФайл:\n{out_path}")

    def on_fail(self, err):
        self.merge_btn.setEnabled(True)
        self.status_bar.showMessage("Ошибка")
        QMessageBox.critical(self, "Ошибка", "FFmpeg не смог объединить видео:\n\n" + (err or "неизвестная ошибка")[-1000:])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoMerger()
    window.show()
    sys.exit(app.exec())
