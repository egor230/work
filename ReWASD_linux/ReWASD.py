#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Сгенерировано сборщиком build_3files.py из оригинальных исходников.
# Логика не изменена — убраны только межмодульные импорты и блоки __main__.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ReWASD Linux — единая программа в визуальном стиле reWASD 9.3.
Дизайн: панели #2E2E33, акцент #F8C000, шрифт Barlow, line-art иллюстрации.
Функционал: эмуляция геймпада (evdev/uinput) + настройки мыши и клавиатуры
из существующих проектов пользователя (mouse/ и Editor_settings_for_Xbox360.py).
"""
import os
import sys
import json
import copy
import traceback
import time as time_module
from pynput import keyboard as pynput_keyboard
import mss
from datetime import datetime
from PIL import Image
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTableWidget, QTableWidgetItem, QCheckBox, QRadioButton,
    QButtonGroup, QSlider, QDialog, QFileDialog, QMessageBox, QScrollArea,
    QProgressBar, QSizePolicy, QHeaderView, QSplitter, QAbstractItemView,
    QStyledItemDelegate, QStyleOptionViewItem, QGraphicsView, QGraphicsScene,
    QGraphicsProxyWidget, QTextEdit, QSystemTrayIcon, QMenu, QInputDialog,
    QFormLayout, QLineEdit,
)
from PyQt6.QtCore import Qt, QSize, QRect, QRectF, QPointF, QPoint, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QPixmap, QFont, QFontMetrics, QIcon, QColor, QPainter, QPen, QBrush, QTextCursor

HERE = Path(__file__).resolve().parent
CORE = HERE  # данные проектов лежат в корне — отдельная папка core/ не нужна
ASSETS = HERE / "assets"
sys.path.insert(0, str(HERE))

# --- функционал из исходных проектов ---
# Импорты из двух других файлов сборки
from appearance import (
    GamepadWidget, InteractiveZone, ZONE_DEFINITIONS, KEY_MAPPER,
    VirtualKeyboard, InteractiveMouse, KeyboardWidget,
)
from library import (LIST_MOUSE_BUTTONS, Worker, GAMEPAD_EC, MouseSettingApp,
                     dict_save, add_text_pytq5, defaut_list_mouse_buttons,
                     cleanup_empty_script_entries, scripts_to_text)

SETTINGS_FILE = HERE / "settings.json"
LOCK_FILE = Path("/tmp/rewasd_linux_single_instance.lock")


def acquire_single_instance():
    """Не дать запуститься второму экземпляру программы.

    Без рекурсии: при битом lock-файле делается ровно одна повторная попытка.
    """
    def _create():
        fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, str(os.getpid()).encode())
        finally:
            os.close(fd)
        return True

    try:
        return _create()
    except FileExistsError:
        try:
            pid = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            pid = None
        if pid is not None:
            try:
                os.kill(pid, 0)  # живой процесс — действительно второй запуск
                return False
            except ProcessLookupError:
                pass            # процесс мёртв — lock устарел
            except PermissionError:
                return False    # процесс есть, сигналы запрещены — не пускаем второй
            except OSError:
                pass
        try:
            LOCK_FILE.unlink(missing_ok=True)  # мёртвый/битый lock — чистим
        except Exception:
            return False                       # не смогли убрать — лучше не запускать
        try:
            return _create()                   # одна повторная попытка
        except FileExistsError:
            return False
        except Exception:
            return True
    except Exception:
        return True  # lock-файл недоступен — не мешаем запуску


def release_single_instance():
    try:
        LOCK_FILE.unlink()
    except Exception:
        pass


def _migrate_json_files():
    """Собрать данные старых JSON в единый settings.json.

    Исходные файлы НЕ удаляются: если пользователь позже правит профиль в
    редакторе Xbox 360, данные остаются доступными для сверки/переноса.
    """
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False) \
            if SETTINGS_FILE.exists() else {}
    except Exception:
        data = {}
    changed = False
    for key, filename in (("mouse_data", "settings control mouse buttons.json"),
                          ("gamepad_data", "editor_for_Xbox360_app_settings.json")):
        if key not in data:
            old = HERE / filename
            if old.exists():
                try:
                    data[key] = json.loads(old.read_text(encoding="utf-8"), strict=False)
                    changed = True
                except Exception:
                    pass
    if changed:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    # Раньше здесь старые JSON удалялись. Из-за этого правки, сделанные в
    # редакторе Xbox 360 после первого запуска, становились недоступны.
    # Оставляем файлы на месте — автоматический импорт по-прежнему только
    # один раз, но исходные данные не теряются.


def _normalize_scripts_file():
    """Однократно убрать старые отступы continuation-строк в скриптах."""
    try:
        if not SETTINGS_FILE.exists():
            return
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False)
        before = json.dumps(data, sort_keys=True, ensure_ascii=False)
        scripts_to_text(data.get("mouse_data", {}))
        after = json.dumps(data, sort_keys=True, ensure_ascii=False)
        if before != after:
            SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    except Exception:
        pass


_migrate_json_files()
_normalize_scripts_file()

GAMEPAD_IMAGE = ASSETS / "gamepad_minimal.png"
SCREENSHOT = HERE / "screenshot.png"
BANNER_SEND_INPUT = ASSETS / "Resources_011.png"
ILLUS_SELECT = ASSETS / "Resources_000.png"
ILLUS_DARK = ASSETS / "Resources_010.png"
PROFILE_SHOT = ASSETS / "Resources_062.png"

ACCENT = "#F8C000"
BLUE = "#09518A"
MUTED = "#999999"

# Клавиши для выпадающих списков
KEY_LIST = sorted(set(list(KEY_MAPPER.default_mapping().values()) + [
    "KEY_SPACE", "KEY_ENTER", "KEY_ESC", "KEY_BACKSPACE", "KEY_TAB",
    "KEY_LEFTSHIFT", "KEY_RIGHTSHIFT", "KEY_LEFTCTRL", "KEY_RIGHTCTRL",
    "KEY_LEFTALT", "KEY_RIGHTALT", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    "KEY_W", "KEY_A", "KEY_S", "KEY_D", "KEY_Q", "KEY_E", "KEY_R", "KEY_F",
    "KEY_1", "KEY_2", "KEY_3", "KEY_4", "KEY_5", "KEY_6", "KEY_7", "KEY_8", "KEY_9", "KEY_0",
    "KEY_KP8", "KEY_KP2", "KEY_KP4", "KEY_KP6", "KEY_KPENTER",
]))
MOUSE_BUTTONS = ["LBUTTON", "RBUTTON", "MBUTTON", "SIDE_BUTTON", "EXTRA_BUTTON",
                 "WHEEL_UP", "WHEEL_DOWN"]
# Порядок кнопок в мышином движке другой: ...MBUTTON, WHEEL_UP, WHEEL_DOWN,
# SIDE1, SIDE2. Без преобразования привязки колеса и боковых кнопок
# записывались не в те слоты.
MOUSE_INDEX_TO_ENGINE = [0, 1, 2, 5, 6, 3, 4]

# Зоны поверх контура геймпада из реWASD (координаты относительно картинки 600x530)
# Зоны подсветки берём из единого списка appearance.py — они совпадают
# с интерактивными зонами и с новым рисунком геймпада.
PAD_ZONES = [tuple(z) for z in ZONE_DEFINITIONS]


class PaddedItemDelegate(QStyledItemDelegate):
    """Небольшой отступ текста ячеек от левой границы колонки."""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        opt.rect.adjust(8, 0, 0, 0)
        super().paint(painter, opt, index)


class PadWidget(GamepadWidget):
    """Геймпад без обрезки: рисунок и зоны масштабируются вместе с окном."""
    def __init__(self, image_path, parent=None):
        super().__init__(image_path, parent)
        self._source_pixmap = QPixmap(image_path)
        # снимаем фиксированный размер, заданный в GamepadWidget
        self.setMinimumSize(300, 200)
        self.setMaximumSize(QSize(16777215, 16777215))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_rect = QRect(0, 0, self.width(), self.height())
        self._zoom = 1.0          # масштаб картинки колесом мыши
        self._pan = QPointF(0, 0)  # смещение картинки при перетаскивании
        self._pan_drag_start = None
        self._pan_start = QPointF(0, 0)

    def _load_and_crop_image(self, path):
        # весь рисунок, без обрезки; дальнейший масштаб — в resizeEvent
        return QPixmap(path)

    def _layout_image(self):
        """Прямоугольник картинки с сохранением пропорций внутри виджета."""
        w, h = self.width(), self.height()
        if self._source_pixmap.isNull() or w <= 0 or h <= 0:
            return QRect(0, 0, max(w, 1), max(h, 1))
        sw, sh = self._source_pixmap.width(), self._source_pixmap.height()
        scale = min(w / sw, h / sh) * self._zoom
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        cx, cy = w / 2 + self._pan.x(), h / 2 + self._pan.y()
        return QRect(int(cx - nw / 2), int(cy - nh / 2), nw, nh)

    def _refresh_image(self):
        self._image_rect = self._layout_image()
        self.bg_pixmap = self._source_pixmap.scaled(
            self._image_rect.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.update()

    def resizeEvent(self, event):
        self._refresh_image()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        # В режиме правки колесо масштабирует картинку (зум к курсору).
        if not self._edit_enabled:
            return super().wheelEvent(event)
        cursor = event.position()
        r = self._image_rect
        nx = (cursor.x() - r.left()) / max(r.width(), 1)
        ny = (cursor.y() - r.top()) / max(r.height(), 1)
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        new_zoom = max(1.0, min(6.0, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        self._zoom = new_zoom
        self._refresh_image()
        r2 = self._image_rect
        self._pan += QPointF(cursor.x() - (r2.left() + nx * r2.width()),
                             cursor.y() - (r2.top() + ny * r2.height()))
        self._refresh_image()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._zone_at(event.position())
            # пустое место — перетаскиваем саму картинку
            if self._edit_enabled and zone is None:
                self._pan_drag_start = event.position()
                self._pan_start = QPointF(self._pan)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_drag_start is not None:
            self._pan_drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        super().mouseReleaseEvent(event)

    def _zone_rect(self, z, rect=None):
        r = rect if rect is not None else self._image_rect
        return QRectF(r.left() + z.rx * r.width(), r.top() + z.ry * r.height(),
                      z.rw * r.width(), z.rh * r.height())

    def _zone_at(self, pos):
        r = self._image_rect
        local = QPointF(pos.x() - r.left(), pos.y() - r.top())
        for z in reversed(self.zones):
            if z.contains(local, r.width(), r.height()):
                return z
        return None

    def mouseMoveEvent(self, event):
        if self._pan_drag_start is not None:
            pos = event.position()
            self._pan = self._pan_start + QPointF(
                pos.x() - self._pan_drag_start.x(),
                pos.y() - self._pan_drag_start.y())
            self._refresh_image()
            return
        if self._edit_mode and self._drag_zone and self._drag_start_pos:
            r = self._image_rect
            pos = event.position()
            dx = (pos.x() - self._drag_start_pos.x()) / max(r.width(), 1)
            dy = (pos.y() - self._drag_start_pos.y()) / max(r.height(), 1)
            z = self._drag_zone
            z.rx = max(0.0, min(1.0 - z.rw, self._drag_start_rx + dx))
            z.ry = max(0.0, min(1.0 - z.rh, self._drag_start_ry + dy))
            self.update()
            return
        super().mouseMoveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._image_rect
        p.drawPixmap(r, self.bg_pixmap)
        for z in self.zones:
            rect = self._zone_rect(z)
            if z.current_binding:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1, Qt.PenStyle.DashLine))
                p.setBrush(QBrush(QColor(255, 255, 255, 15)))
                if z.shape == "ellipse":
                    p.drawEllipse(rect)
                else:
                    p.drawRoundedRect(rect, 4, 4)
                self._paint_label(p, z, rect)
            if z.hovered and not z.pressed:
                self._paint_highlight(p, z, rect, 140, is_hover=True)
                self._paint_label(p, z, rect)
            if z.pressed:
                self._paint_highlight(p, z, rect, 200, is_hover=False)
                self._paint_label(p, z, rect)
        p.end()


class KeyboardImageWidget(QWidget):
    """Клавиатура, вписанная в виджет; кнопки подсвечиваются жёлтым при наведении."""
    def __init__(self, pixmap, buttons, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._buttons = list(buttons)  # [(QRect, текст)] в координатах исходной картинки
        self._hovered = -1
        self._dest = QRect(0, 0, 1, 1)
        self.setMinimumSize(400, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#302E2C;")
        self.setMouseTracking(True)

    def _map_to_source(self, pos):
        r = self._dest
        if r.width() <= 0 or r.height() <= 0:
            return QPointF(-1, -1)
        sw, sh = self._pixmap.width(), self._pixmap.height()
        return QPointF((pos.x() - r.left()) * sw / r.width(),
                       (pos.y() - r.top()) * sh / r.height())

    def mouseMoveEvent(self, event):
        src = self._map_to_source(event.position())
        found = -1
        for i, (rect, _text) in enumerate(self._buttons):
            if rect.contains(src.toPoint()):
                found = i
                break
        if found != self._hovered:
            self._hovered = found
            self.setCursor(Qt.CursorShape.PointingHandCursor if found >= 0
                           else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hovered != -1:
            self._hovered = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#302E2C"))
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            self._dest = QRect(x, y, scaled.width(), scaled.height())
            p.drawPixmap(x, y, scaled)

            if 0 <= self._hovered < len(self._buttons):
                rect, text = self._buttons[self._hovered]
                sw, sh = self._pixmap.width(), self._pixmap.height()
                hi = QRectF(self._dest.left() + rect.left() * self._dest.width() / sw,
                            self._dest.top() + rect.top() * self._dest.height() / sh,
                            rect.width() * self._dest.width() / sw,
                            rect.height() * self._dest.height() / sh)
                # только подсветка существующей клавиши — без новой кнопки и текста
                p.setPen(QPen(QColor("#F8C000"), 2))
                p.setBrush(QBrush(QColor(248, 192, 0, 70)))
                p.drawRoundedRect(hi.adjusted(1, 1, -1, -1), 2, 2)
        p.end()


class ScreenshotWidget(QWidget):
    """Скриншот с выделением oblastи мышью (рамка эмблемы)."""
    selection_changed = pyqtSignal(dict)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap(str(path))
        self._rect = None
        self._drag_start = None
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#1C1C20;")
        self.setMouseTracking(True)

    def set_pixmap(self, path):
        pm = QPixmap(str(path))
        if not pm.isNull():
            self._pixmap = pm
            self._rect = None
            self.update()

    def _display_rect(self):
        if self._pixmap.isNull():
            return QRect(0, 0, max(self.width(), 1), max(self.height(), 1))
        scaled = self._pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        return QRect((self.width() - scaled.width()) // 2,
                     (self.height() - scaled.height()) // 2,
                     scaled.width(), scaled.height())

    def _to_image(self, pos):
        r = self._display_rect()
        x = (pos.x() - r.left()) * self._pixmap.width() / max(r.width(), 1)
        y = (pos.y() - r.top()) * self._pixmap.height() / max(r.height(), 1)
        return QPoint(max(0, min(self._pixmap.width(), int(x))),
                      max(0, min(self._pixmap.height(), int(y))))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._pixmap.isNull():
            self._drag_start = self._to_image(event.position())
            self._rect = QRect(self._drag_start, self._drag_start)
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._rect = QRect(self._drag_start, self._to_image(event.position())).normalized()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_start is not None and self._rect is not None:
            r = self._rect
            if r.width() > 2 and r.height() > 2:
                data = {"left": r.left(), "top": r.top(), "right": r.right(),
                        "bottom": r.bottom(), "width": r.width(), "height": r.height()}
                self.selection_changed.emit(data)
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1C1C20"))
        if not self._pixmap.isNull():
            r = self._display_rect()
            p.drawPixmap(r.left(), r.top(), self._pixmap.scaled(
                r.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            if self._rect is not None:
                ir = self._rect
                disp = QRect(r.left() + int(ir.left() * r.width() / self._pixmap.width()),
                             r.top() + int(ir.top() * r.height() / self._pixmap.height()),
                             max(1, int(ir.width() * r.width() / self._pixmap.width())),
                             max(1, int(ir.height() * r.height() / self._pixmap.height())))
                p.setPen(QPen(QColor("#e74c3c"), 2, Qt.PenStyle.SolidLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(disp)
        p.end()


class KeyboardView(QGraphicsView):
    """Настоящая клавиатура в масштабирующем контейнере: hover работает штатно."""
    def __init__(self, keyboard_widget, parent=None):
        super().__init__(parent)
        self._keyboard = keyboard_widget
        self._scene = QGraphicsScene(self)
        self._proxy = self._scene.addWidget(keyboard_widget)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background:#302E2C; border:0;")
        self.setMinimumSize(400, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self._proxy, Qt.AspectRatioMode.KeepAspectRatio)


def scaled_label(path, w, h):
    lab = QLabel()
    if Path(path).exists():
        pm = QPixmap(str(path))
        if not pm.isNull():
            lab.setPixmap(pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setStyleSheet("background:transparent;")
    return lab


class KeySelectDialog(QDialog):
    """Компактный выбор клавиши в стиле реWASD."""
    def __init__(self, parent=None, current=""):
        super().__init__(parent)
        self.setWindowTitle("Выбор клавиши")
        self.setStyleSheet(open(HERE / "style.qss", encoding="utf-8").read())
        self.chosen = current
        lay = QVBoxLayout(self)
        title = QLabel("ВЫБЕРИТЕ КЛАВИШУ")
        title.setObjectName("h2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)
        grid = QGridLayout()
        common = [k for k in KEY_LIST if len(k) < 12]
        for i, key in enumerate(common):
            b = QPushButton(key.replace("KEY_", ""))
            b.setObjectName("secondary")
            b.setFixedHeight(30)
            b.clicked.connect(lambda _, k=key: self.accept_key(k))
            grid.addWidget(b, i // 8, i % 8)
        wrap = QWidget()
        wrap.setLayout(grid)
        sc = QScrollArea()
        sc.setWidget(wrap)
        sc.setWidgetResizable(True)
        sc.setFixedSize(700, 340)
        lay.addWidget(sc)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignRight)

    def accept_key(self, key):
        self.chosen = key
        self.accept()


class RewasdApp(QMainWindow):
    # Сигнал для доставки глобальных хоткеев из потока pynput в GUI-поток.
    hotkey_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReWASD Linux — Ultimate gaming experience")
        self.setWindowIcon(QIcon(str(ASSETS / "window_icon.png")))
        self.setStyleSheet(open(HERE / "style.qss", encoding="utf-8").read())
        self.worker = None
        self.mouse_window = None
        self.script_editor = None
        self._hotkey_listener = None
        self.data = self.load_settings()
        # Снимок вложенных секций: позволяет не затирать правки, сделанные
        # мышиным движком в отдельном окне, при автосохранении из ReWASD.
        self._loaded_nested = copy.deepcopy({
            k: self.data.get(k) for k in ("mouse_data", "gamepad_data", "macro_data")})
        # Восстанавливаем размер И положение окна с прошлого запуска
        geom = self.data.get("window_geometry")
        if geom and len(geom) == 4:
            self.resize(int(geom[2]), int(geom[3]))
            self.move(int(geom[0]), int(geom[1]))
        else:
            win_size = self.data.get("window_size", [1280, 820])
            self.resize(int(win_size[0]), int(win_size[1]))
        self.init_ui()
        self.apply_data_to_ui()
        self._baseline_data = None
        self._baseline_text = ""
        self._closing = False
        self.mouse_engine = None
        self.start_mouse_engine()
        # Как в оригинальном редакторе: эмуляция геймпада стартует сразу
        self.auto_start_gamepad()
        self.install_hotkeys()

    # ---------- данные ----------
    def load_mouse_profiles(self):
        """Текущие профили и привязки кнопок из программы мыши пользователя.
        Имена профилей — это ЗНАЧЕНИЯ ключа 'paths' из JSON (как в вашей программе)."""
        try:
            root = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False)
            data = root.get("mouse_data", {})
            profiles = [p for p, on in data.get("games_checkmark", {}).items() if on]
            if not profiles:
                profiles = list(data.get("games_checkmark", {}).keys())
            current = data.get("current_app", "")
            bindings = {}
            vals = data.get("key_value", {}).get(current, [])
            for i, btn in enumerate(MOUSE_BUTTONS[:7]):
                if i < len(vals):
                    bindings[btn] = str(vals[i])  # включая пустые значения « » из JSON по умолчанию
            return profiles, current, bindings, data.get("paths", {})
        except Exception:
            return [], "", {}, {}

    def load_gamepad_config(self):
        """Профили геймпада — по именам, из отдельного JSON редактора Xbox 360."""
        try:
            root = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False)
            d = root.get("gamepad_data", {})
            return (d.get("profiles", {}), d.get("last_profile", ""),
                    d.get("trigger_modes", {}),
                    {k: d.get(k) for k in ("mouse_on", "sens", "sens_x", "sens_y", "smooth", "grab")})
        except Exception:
            return {}, "", {}, {}

    def profile_display(self, path, paths=None):
        """Имя профиля мыши — значение из 'paths' JSON; fallback — имя файла."""
        if paths and str(path) in paths:
            return str(paths[str(path)])
        return Path(str(path)).name or str(path)

    def load_settings(self):
        mouse_profiles, mouse_current, mouse_bindings, mouse_paths = self.load_mouse_profiles()
        gp_profiles, gp_last, gp_triggers, gp_common = self.load_gamepad_config()
        default_mouse = {b: (mouse_bindings.get(b) or KEY_LIST[i % len(KEY_LIST)]) for i, b in enumerate(MOUSE_BUTTONS)}
        gp_names = list(gp_profiles.keys()) or ["Default"]
        gp_current = gp_last if gp_last in gp_profiles else gp_names[0]
        default = {
            "profiles": [self.profile_display(p, mouse_paths) for p in mouse_profiles] or
                        ["По умолчанию", "Empty Profile (2)", "Empty Profile (3)"],
            "profile_paths": mouse_profiles,
            "current_profile": max(0, mouse_profiles.index(mouse_current)) if mouse_current in mouse_profiles else 0,
            # геймпад: profiles by NAME (отдельный JSON)
            "gamepad_profile_names": gp_names,
            "gamepad_profiles": gp_profiles,
            "trigger_modes": gp_triggers,
            "current_gamepad_profile": gp_current,
            "gamepad_map": gp_profiles.get(gp_current, KEY_MAPPER.default_mapping()),
            "mouse_map": default_mouse,
            # мышь: удержание / повтор / длительность повтора (по кнопкам)
            "mouse_hold": {b: False for b in MOUSE_BUTTONS},
            "mouse_repeat": {b: False for b in MOUSE_BUTTONS},
            "mouse_repeat_sec": {b: "" for b in MOUSE_BUTTONS},
            "mouse_splitter_sizes": [260, 400],
            "kb_split_sizes": [330, 340],
            "macro_splitter_sizes": [330, 340],
            "macro_data": {},
            "macro_column_widths": [260, 160, 300],
            "kb_column_widths": [560, 417],
            "gamepad_split_sizes": [700, 300],
            "gamepad_zoom": 1.0,
            "gamepad_pan": [0, 0],
            "window_size": [1280, 820],
            "window_geometry": [80, 80, 1280, 820],
            "main_splitter_sizes": [258, 1022],
            "profile_split_sizes": [125, 109],
            "profile_vertical_sizes": [340, 420],
            "mouse_column_widths": [270, 220, 100, 100, 160, 100],
            "sens_x": int(gp_common.get("sens_x") or gp_common.get("sens") or 6),
            "sens_y": int(gp_common.get("sens_y") or gp_common.get("sens") or 6),
            "smooth": bool(gp_common.get("smooth", True)),
            "grab": bool(gp_common.get("grab", False)),
            "mouse_on": bool(gp_common.get("mouse_on", False)),
        }
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                default.update(saved)
            except Exception:
                pass
        # gamepad_data — источник профилей и триггеров. Верхние ключи могли
        # устареть, поэтому сверяем копии. Активные привязки из прошлой сессии
        # сохраняем и записываем в текущий профиль, чтобы ничего не пропало.
        gp = default.get("gamepad_data", {}) or {}
        nested_profiles = gp.get("profiles") or {}
        if nested_profiles:
            default["gamepad_profiles"] = nested_profiles
            if gp.get("trigger_modes") is not None:
                default["trigger_modes"] = gp["trigger_modes"]
            cur = gp.get("last_profile") or default.get("current_gamepad_profile")
            if cur not in nested_profiles:
                cur = default.get("current_gamepad_profile")
            if cur not in nested_profiles:
                cur = next(iter(nested_profiles), "Default")
            default["current_gamepad_profile"] = cur
            default["gamepad_profile_names"] = list(nested_profiles.keys())
            active = default.get("gamepad_map") or {}
            if active:
                nested_profiles[cur] = dict(active)
            default["gamepad_map"] = dict(nested_profiles.get(cur, KEY_MAPPER.default_mapping()))
            gp["last_profile"] = cur
        # «По умолчанию» — обязательный первый профиль; восстанавливаем его,
        # если он пропал из-за старого сохранённого списка.
        profiles = default.get("profiles", [])
        if "По умолчанию" not in profiles:
            profiles.insert(0, "По умолчанию")
            paths = default.get("profile_paths", [])
            if paths:
                paths.insert(0, "C:/Windows/explorer.exe")
            default["current_profile"] = min(
                int(default.get("current_profile", 0)) + 1, len(profiles) - 1)
        return default

    def save_settings(self):
        """Записать текущие данные в JSON.

        Важно: здесь НЕ обновляем снимок настроек. save_settings() вызывают
        многие обработчики (смена профиля, ползунки, разделители, параметры
        геймпада). Если сбрасывать снимок при каждом таком автосохранении, то
        при закрытии окна всегда получается «изменений нет» и диалог
        «Сохранить изменения?» не появляется. Снимок обновляется только при
        открытии окна и при явном подтверждении сохранения в confirm_unsaved().
        """
        try:
            merged = dict(self.data)
            try:
                disk = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False)
            except Exception:
                disk = {}
            keys = ("mouse_data", "gamepad_data", "macro_data")
            loaded = getattr(self, "_loaded_nested", {})
            for key in keys:
                # Секцию не меняли в интерфейсе — берём свежую с диска: её мог
                # записать мышиный движок из своего окна.
                if self.data.get(key) == loaded.get(key) and key in disk:
                    merged[key] = disk[key]
            SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            self._loaded_nested = copy.deepcopy({k: merged.get(k) for k in keys})
            self.status("Настройки сохранены")
        except Exception as e:
            self.status("Ошибка сохранения: " + str(e))

    def _take_baseline(self):
        """Снимок настроек в момент открытия окна — с чем сравнивать при выходе.

        Сравниваем с данными в памяти, а не с файлом: при загрузке часть
        ключей нормализуется (сверка копий gamepad_data), и сравнение с файлом
        давало бы ложный вопрос о сохранении сразу после открытия окна.
        Текст файла запоминается отдельно — для кнопки «Не сохранять».
        """
        try:
            self._baseline_text = SETTINGS_FILE.read_text(encoding="utf-8")
        except Exception:
            self._baseline_text = ""
        self._baseline_data = copy.deepcopy(self.data)

    def has_changes(self):
        """Любое изменение данных/виджетов относительно снимка."""
        if getattr(self, "_baseline_data", None) is None:
            return False
        try:
            current = json.dumps(self.data, sort_keys=True, ensure_ascii=False)
            saved = json.dumps(self._baseline_data, sort_keys=True, ensure_ascii=False)
            return current != saved
        except Exception:
            return False

    def confirm_unsaved(self):
        """Сравнить состояние с JSON и спросить про сохранение при закрытии."""
        if not self.has_changes():
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Выход")
        box.setText("Вы хотите сохранить изменения перед выходом?")
        box.setStandardButtons(QMessageBox.StandardButton.Save |
                               QMessageBox.StandardButton.Discard |
                               QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self.save_settings()
            self._take_baseline()
        else:  # Не сохранять — возвращаем и файл, и данные к состоянию открытия
            # Иначе последующий вызов save_settings() в closeEvent/quit_app
            # записал бы обратно уже изменённые self.data, и «Не сохранять»
            # фактически сохраняла бы правки.
            try:
                self.data = json.loads(json.dumps(self._baseline_data))
                self._loaded_nested = copy.deepcopy({
                    k: self.data.get(k)
                    for k in ("mouse_data", "gamepad_data", "macro_data")})
                SETTINGS_FILE.write_text(self._baseline_text, encoding="utf-8")
            except Exception:
                pass
        return True

    # ---------- каркас ----------
    def init_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # левая панель
        side = QFrame()
        side.setObjectName("sidebar")
        side.setMinimumWidth(180)
        slay = QVBoxLayout(side)
        slay.setContentsMargins(12, 12, 12, 12)
        slay.setSpacing(10)
        # Верхняя часть сайдбара: логотип и навигация
        top_widget = QWidget()
        top_widget.setMinimumHeight(260)
        tlay = QVBoxLayout(top_widget)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(10)
        logo = QLabel("⚡  reWASD")
        logo.setObjectName("appTitle")
        logo.setStyleSheet("color:#F8C000;font-size:22px;font-weight:800;")
        tlay.addWidget(logo)
        sub = QLabel("LINUX EDITION · 9.3")
        sub.setObjectName("appSub")
        tlay.addWidget(sub)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedHeight(252)
        for name in ["Мышь", "Клавиатура", "Геймпад", "Макросы"]:
            self.nav.addItem(QListWidgetItem(name))
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.on_nav)
        tlay.addWidget(self.nav)
        tlay.addStretch()  # лишняя высота — пустое место внизу, а не растяжение текста

        # Нижняя часть: текущий профиль, список и кнопки — ОДИН виджет,
        # его высоту можно менять за границу вертикального разделителя.
        profile_block = QWidget()
        profile_block.setMinimumHeight(190)
        pbl = QVBoxLayout(profile_block)
        pbl.setContentsMargins(0, 0, 0, 0)
        pbl.setSpacing(6)

        label_widget = QWidget()
        lw = QHBoxLayout(label_widget)
        lw.setContentsMargins(0, 0, 0, 0)
        pl = QLabel("ТЕКУЩИЙ ПРОФИЛЬ:")
        pl.setObjectName("muted")
        lw.addWidget(pl)

        self.ms_profile = QComboBox()
        self.ms_profile.addItems(self.data["profiles"])
        self.ms_profile.currentIndexChanged.connect(self.on_profile_combo)
        self.ms_profile.installEventFilter(self)

        self.profile_split = QSplitter(Qt.Orientation.Horizontal)
        self.profile_split.addWidget(label_widget)
        self.profile_split.addWidget(self.ms_profile)
        saved_ps = self.data.get("profile_split_sizes")
        if saved_ps and len(saved_ps) == 2:
            self.profile_split.setSizes([int(saved_ps[0]), int(saved_ps[1])])
        self.profile_split.splitterMoved.connect(self.on_profile_split_moved)
        pbl.addWidget(self.profile_split)

        # Список всех профилей с перемещением вверх/вниз
        self.profile_list = QListWidget()
        self.profile_list.addItems(self.data["profiles"])
        self.profile_list.setCurrentRow(min(self.data.get("current_profile", 0),
                                            len(self.data["profiles"]) - 1))
        self.profile_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.profile_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.profile_list.currentRowChanged.connect(self.on_profile_list_row)
        self.profile_list.itemDoubleClicked.connect(self.rename_profile)
        self.profile_list.model().rowsMoved.connect(self.on_profiles_reordered)
        pbl.addWidget(self.profile_list, 1)

        move_row = QHBoxLayout()
        b_up = QPushButton("▲")
        b_down = QPushButton("▼")
        b_up.clicked.connect(lambda: self.move_profile(-1))
        b_down.clicked.connect(lambda: self.move_profile(1))
        move_row.addWidget(b_up)
        move_row.addWidget(b_down)
        move_row.addStretch()
        pbl.addLayout(move_row)

        self.profile_vertical_split = QSplitter(Qt.Orientation.Vertical)
        self.profile_vertical_split.addWidget(top_widget)
        self.profile_vertical_split.addWidget(profile_block)
        saved_pv = self.data.get("profile_vertical_sizes")
        if saved_pv and len(saved_pv) == 2:
            self.profile_vertical_split.setSizes([int(saved_pv[0]), int(saved_pv[1])])
        self.profile_vertical_split.splitterMoved.connect(self.on_profile_vertical_moved)
        slay.addWidget(self.profile_vertical_split, 1)

        # рабочая область
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(64)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(20, 6, 20, 6)
        tl.addWidget(scaled_label(BANNER_SEND_INPUT, 360, 52))
        title = QLabel("SEND INPUT  →  GAMEPAD / MOUSE / KEYBOARD")
        title.setObjectName("gold")
        tl.addWidget(title)
        tl.addStretch()
        self.btn_add = QPushButton("Добавить")
        self.btn_add.setObjectName("primary")
        self.btn_add.clicked.connect(self.on_add_clicked)
        tl.addWidget(self.btn_add)
        self.btn_del = QPushButton("Удалить")
        self.btn_del.setObjectName("secondary")
        self.btn_del.clicked.connect(self.on_delete_clicked)
        tl.addWidget(self.btn_del)
        right.addWidget(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.page_mouse())
        self.stack.addWidget(self.page_keyboard())
        self.stack.addWidget(self.page_gamepad())
        self.stack.addWidget(self.page_macros())
        right.addWidget(self.stack, 1)

        # Статус-бар («Готово» и индикатор с %) убран из окна.
        # Виджеты оставляем скрытыми: методы status()/эмуляции по-прежнему
        # обращаются к ним, поэтому логика не ломается.
        self.status_label = QLabel(self)
        self.status_label.setVisible(False)
        self.progress = QProgressBar(self)
        self.progress.setVisible(False)
        self.progress.setValue(0)

        # Разделитель: тяни границу меню/контент, чтобы менять ширину меню
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(side)
        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        saved_main = self.data.get("main_splitter_sizes")
        if saved_main and len(saved_main) == 2:
            self.main_splitter.setSizes([int(saved_main[0]), int(saved_main[1])])
        self.main_splitter.splitterMoved.connect(self.on_main_splitter_moved)
        root.addWidget(self.main_splitter)

    # ---------- страницы ----------
    def page_frame(self):
        f = QFrame(); f.setObjectName("page")
        return f

    def page_profiles(self):
        page = self.page_frame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("ПРОФИЛИ")
        h.setObjectName("h1")
        lay.addWidget(h)
        sub = QLabel("Выберите профиль и назначьте управление")
        sub.setObjectName("muted")
        lay.addWidget(sub)
        body = QHBoxLayout()
        body.addWidget(scaled_label(ILLUS_SELECT, 560, 360), 3)
        info = QVBoxLayout()
        info.addWidget(scaled_label(PROFILE_SHOT, 420, 210))
        t = QLabel("SEND INPUT")
        t.setObjectName("gold")
        info.addWidget(t)
        d = QLabel("Нажмите кнопку мыши или клавиатуры, затем выберите\n"
                   "действие геймпада на вкладке «Геймпад».")
        d.setObjectName("muted")
        info.addWidget(d)
        b = QPushButton("Настроить геймпад →")
        b.setObjectName("primary")
        b.clicked.connect(lambda: self.nav.setCurrentRow(1))
        info.addWidget(b, alignment=Qt.AlignmentFlag.AlignLeft)
        body.addLayout(info, 2)
        lay.addLayout(body, 1)
        return page

    def page_gamepad(self):
        page = self.page_frame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 16, 18, 16)
        head = QHBoxLayout()
        h = QLabel("ГЕЙМПАД")
        h.setObjectName("h1")
        head.addWidget(h)
        head.addSpacing(28)
        pl = QLabel("ПРОФИЛЬ ГЕЙМПАДА:")
        pl.setObjectName("muted")
        head.addWidget(pl)
        self.gp_profile = QComboBox()
        self.gp_profile.setFixedWidth(250)
        self.gp_profile.addItems(self.data["gamepad_profile_names"])
        cur = self.data["current_gamepad_profile"]
        if cur in self.data["gamepad_profile_names"]:
            self.gp_profile.setCurrentText(cur)
        self.gp_profile.currentTextChanged.connect(self.on_gamepad_profile)
        head.addWidget(self.gp_profile)
        head.addStretch()
        self.btn_start = QPushButton("▶  Запустить эмуляцию")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self.start_emulation)
        head.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■  Остановить")
        self.btn_stop.setObjectName("secondary")
        self.btn_stop.clicked.connect(self.stop_emulation)
        self.btn_stop.setEnabled(False)
        head.addWidget(self.btn_stop)
        lay.addLayout(head)

        body = QHBoxLayout()
        # Интерактивный контур геймпада: зоны подсвечиваются при наведении
        self.gamepad = PadWidget(str(GAMEPAD_IMAGE))
        self.gamepad.zone_clicked.connect(lambda name: self.status("Геймпад: " + name))

        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        rh = QLabel("НАЗНАЧЕНИЕ КЛАВИШ")
        rh.setObjectName("h2")
        right.addWidget(rh)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        gridw = QWidget()
        grid = QGridLayout(gridw)
        grid.setContentsMargins(4, 4, 4, 4)
        self.gamepad_combos = {}
        for i, z in enumerate(ZONE_DEFINITIONS):
            label, logical = z[0], z[1]
            lb = QLabel(f"{label}  ·  {logical}")
            lb.setObjectName("muted")
            cb = QComboBox()
            cb.addItems(KEY_LIST)
            cb.setMinimumWidth(160)
            cb.currentTextChanged.connect(lambda v, lg=logical: self.on_key_changed(lg, v))
            self.gamepad_combos[logical] = cb
            grid.addWidget(lb, i, 0)
            grid.addWidget(cb, i, 1)
        scroll.setWidget(gridw)
        scroll.setFixedWidth(330)
        right.addWidget(scroll, 1)
        self.log_label = QLabel("Лог эмуляции: ожидание")
        self.log_label.setObjectName("muted")
        self.log_label.setWordWrap(True)
        right.addWidget(self.log_label)

        # Ширина картинки и панели назначения клавиш меняется разделителем
        self.gamepad_split = QSplitter(Qt.Orientation.Horizontal)
        self.gamepad_split.addWidget(self.gamepad)
        self.gamepad_split.addWidget(right_widget)
        saved_gp = self.data.get("gamepad_split_sizes")
        if saved_gp and len(saved_gp) == 2:
            self.gamepad_split.setSizes([int(saved_gp[0]), int(saved_gp[1])])
        else:
            self.gamepad_split.setSizes([700, 300])
        self.gamepad_split.splitterMoved.connect(self.on_gamepad_split_moved)
        body.addWidget(self.gamepad_split)
        lay.addLayout(body, 1)

        # параметры эмуляции — под геймпадом (вкладка «Настройки» убрана)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Чувств. X"))
        self.sx = QSlider(Qt.Orientation.Horizontal); self.sx.setRange(1, 15); self.sx.setFixedWidth(100)
        srow.addWidget(self.sx)
        srow.addWidget(QLabel("Чувств. Y"))
        self.sy = QSlider(Qt.Orientation.Horizontal); self.sy.setRange(1, 15); self.sy.setFixedWidth(100)
        srow.addWidget(self.sy)
        self.chk_mouse_mode = QCheckBox("Мышь")
        self.chk_mouse_mode.setToolTip("Правый стик управляется мышью, как в редакторе Xbox 360")
        self.chk_mouse_mode.toggled.connect(self.on_gamepad_option_changed)
        srow.addWidget(self.chk_mouse_mode)
        self.chk_smooth = QCheckBox("Сглаживание")
        self.chk_smooth.setToolTip("Сглаживание движения мыши по осям правого стика")
        self.chk_smooth.toggled.connect(self.on_gamepad_option_changed)
        srow.addWidget(self.chk_smooth)
        self.chk_grab = QCheckBox("Захват клавиатуры")
        self.chk_grab.setToolTip("Перехват физической клавиатуры через evdev (grab)")
        self.chk_grab.toggled.connect(self.on_gamepad_option_changed)
        srow.addWidget(self.chk_grab)
        # Дребезг: при перетаскивании ползунка valueChanged приходит на каждом
        # шаге. Без задержки каждое движение пересоздавало Worker и UInput.
        self._gp_apply_timer = QTimer(self)
        self._gp_apply_timer.setSingleShot(True)
        self._gp_apply_timer.setInterval(400)
        self._gp_apply_timer.timeout.connect(self._apply_gamepad_options)
        self.sx.valueChanged.connect(self.on_gamepad_option_changed)
        self.sy.valueChanged.connect(self.on_gamepad_option_changed)
        srow.addStretch()
        # Ручная настройка зон: включил — двигаешь зоны и колесом меняешь размер,
        # выключил — новые координаты сохраняются в settings.json.
        self.btn_edit_zones = QPushButton("Редактировать зоны")
        self.btn_edit_zones.setObjectName("secondary")
        self.btn_edit_zones.setCheckable(True)
        self.btn_edit_zones.toggled.connect(self.on_edit_zones)
        srow.addWidget(self.btn_edit_zones)
        lay.addLayout(srow)
        return page

    def page_keyboard(self):
        page = self.page_frame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("КЛАВИАТУРА")
        h.setObjectName("h1")
        lay.addWidget(h)
        sub = QLabel("Виртуальная клавиатура — назначьте клавиши для действий геймпада")
        sub.setObjectName("muted")
        lay.addWidget(sub)
        # Клавиатура из вашего mouse-скрипта — отдельный виджет, который
        # можно тянуть по высоте границей разделителя.
        self.kw = KeyboardWidget(self._on_keyboard_key)
        self.kb_image = KeyboardView(self.kw, self)
        self.kb_table = QTableWidget(len(self.data["gamepad_map"]), 2)
        self.kb_table.setHorizontalHeaderLabels(["Действие", "Клавиша"])
        self.kb_table.verticalHeader().setVisible(False)  # без циферок 1,2,3...
        khdr = self.kb_table.horizontalHeader()
        for c in range(2):
            khdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        kb_widths = self.data.get("kb_column_widths")
        if not kb_widths or len(kb_widths) != 2:
            kb_widths = [560, 417]
        for c, width in enumerate(kb_widths):
            self.kb_table.setColumnWidth(c, int(width))
        self.kb_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        khdr.sectionResized.connect(self.on_kb_column_resized)
        self.kb_buttons = {}
        for i, (logical, key) in enumerate(sorted(self.data["gamepad_map"].items())):
            self.kb_table.setItem(i, 0, QTableWidgetItem(logical))
            b = QPushButton(key.replace("KEY_", ""))
            b.setObjectName("secondary")
            b.clicked.connect(lambda _, lg=logical: self.pick_key(lg))
            self.kb_table.setCellWidget(i, 1, b)
            self.kb_buttons[logical] = b
        self.kb_split = QSplitter(Qt.Orientation.Vertical)
        self.kb_split.addWidget(self.kb_image)
        self.kb_split.addWidget(self.kb_table)
        self.kb_split.setStretchFactor(0, 1)
        self.kb_split.setStretchFactor(1, 1)
        saved_kb = self.data.get("kb_split_sizes")
        if saved_kb and len(saved_kb) == 2:
            self.kb_split.setSizes([int(saved_kb[0]), int(saved_kb[1])])
        self.kb_split.splitterMoved.connect(self.on_kb_split_moved)
        lay.addWidget(self.kb_split, 1)
        row = QHBoxLayout()
        b_open = QPushButton("Полная виртуальная клавиатура")
        b_open.setObjectName("secondary")
        b_open.clicked.connect(self.open_virtual_keyboard)
        row.addWidget(b_open)
        row.addStretch()
        lay.addLayout(row)
        return page

    def page_mouse(self):
        page = self.page_frame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("МЫШЬ")
        h.setObjectName("h1")
        lay.addWidget(h)
        self.mouse_art = InteractiveMouse()
        self.mouse_art.setMinimumHeight(140)
        self.mouse_art.zone_clicked.connect(self.on_mouse_zone)
        self.mouse_art.zone_hovered.connect(self.on_mouse_zone_hover)

        self.mouse_table = QTableWidget(len(MOUSE_BUTTONS), 6)
        pad_delegate = PaddedItemDelegate(self.mouse_table)
        self.mouse_table.setItemDelegateForColumn(0, pad_delegate)
        self.mouse_table.setItemDelegateForColumn(5, pad_delegate)
        self.mouse_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.mouse_table.currentCellChanged.connect(self.on_mouse_table_cell)
        self.mouse_table.setMouseTracking(True)
        self.mouse_table.itemEntered.connect(self.on_mouse_table_entered)
        self.mouse_table.itemClicked.connect(self.on_mouse_table_item_clicked)
        self.mouse_table.viewport().installEventFilter(self)
        self.mouse_table.installEventFilter(self)
        self.mouse_table.setHorizontalHeaderLabels([
            "Кнопка мыши", "Клавиша", "Удерживать", "Повторять", "Время повторения", "Скрипты"
        ])
        # заголовок «Время повторения» выравниваем по левому краю, чтобы не обрезался
        self.mouse_table.horizontalHeaderItem(4).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hdr = self.mouse_table.horizontalHeader()
        # Все колонки можно тянуть мышью за границу; ширины хранятся в JSON.
        saved_widths = self.data.get("mouse_column_widths")
        widths = saved_widths if saved_widths and len(saved_widths) == 6 \
            else [270, 220, 100, 100, 160, 100]
        self._restoring_columns = True
        for c in range(6):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self.mouse_table.setColumnWidth(c, int(widths[c]))
        self._restoring_columns = False
        # Последний столбец «Скрипты» занимает ВСЁ оставшееся место справа —
        # пустого пространства после него быть не должно.
        hdr.setStretchLastSection(True)
        hdr.sectionResized.connect(self.on_mouse_column_resized)
        self.mouse_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        QTimer.singleShot(0, self.normalize_mouse_columns)
        # строки одинаковой высоты и заполняют таблицу без пустого места внизу
        vh = self.mouse_table.verticalHeader()
        vh.setVisible(False)  # убираем циферки 1,2,3... слева от кнопок
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mouse_hold_boxes = {}
        self.mouse_repeat_boxes = {}
        self.mouse_sec_combos = {}
        self.mouse_key_combos = {}
        self.mouse_mode_groups = {}
        for i, btn in enumerate(MOUSE_BUTTONS):
            label = LIST_MOUSE_BUTTONS[i] if i < len(LIST_MOUSE_BUTTONS) else btn
            self.mouse_table.setItem(i, 0, QTableWidgetItem(label))
            cb = QComboBox(); cb.addItems(KEY_LIST)
            key = self.data["mouse_map"].get(btn, "")
            if key:
                if cb.findText(key) < 0:
                    cb.addItem(key)
                cb.setCurrentText(key)
            cb.currentTextChanged.connect(
                lambda v, b=btn, idx=i: self.on_mouse_key_changed(b, idx, v))
            self.mouse_key_combos[btn] = cb
            self.mouse_table.setCellWidget(i, 1, cb)

            # «Удерживать / Повторять» — радиокнопки: только одно положение
            hold_on = bool(self.data.get("mouse_hold", {}).get(btn, False))
            repeat_on = bool(self.data.get("mouse_repeat", {}).get(btn, False)) and not hold_on
            hold = QRadioButton()
            hold.setToolTip("Удерживать нажатой")
            hold.toggled.connect(
                lambda on, b=btn: self.data.setdefault("mouse_hold", {}).__setitem__(b, bool(on)))
            repeat = QRadioButton()
            repeat.setToolTip("Повторять")
            repeat.toggled.connect(
                lambda on, b=btn: self.data.setdefault("mouse_repeat", {}).__setitem__(b, bool(on)))
            group = QButtonGroup(self)
            group.setExclusive(True)
            group.addButton(hold, 0)
            group.addButton(repeat, 1)
            hold.setChecked(hold_on)
            repeat.setChecked(repeat_on)
            self.mouse_mode_groups[btn] = group
            self.mouse_hold_boxes[btn] = hold
            self.mouse_repeat_boxes[btn] = repeat
            # радиокнопки по центру ячейки
            hold_cell = QWidget()
            hold_cell.setLayout(QHBoxLayout())
            hold_cell.layout().setContentsMargins(0, 0, 0, 0)
            hold_cell.layout().addWidget(hold, alignment=Qt.AlignmentFlag.AlignCenter)
            repeat_cell = QWidget()
            repeat_cell.setLayout(QHBoxLayout())
            repeat_cell.layout().setContentsMargins(0, 0, 0, 0)
            repeat_cell.layout().addWidget(repeat, alignment=Qt.AlignmentFlag.AlignCenter)
            self.mouse_table.setCellWidget(i, 2, hold_cell)
            self.mouse_table.setCellWidget(i, 3, repeat_cell)

            sec = QComboBox()
            sec.addItems(["", "5", "10", "20"])  # по умолчанию пусто
            sec.setToolTip("Время повторения")
            sec.setCurrentText(str(self.data.get("mouse_repeat_sec", {}).get(btn, "")))
            sec.currentTextChanged.connect(
                lambda v, b=btn: self.data.setdefault("mouse_repeat_sec", {}).__setitem__(b, v))
            self.mouse_sec_combos[btn] = sec
            self.mouse_table.setCellWidget(i, 4, sec)

            # Столбец «Скрипты» — названия такие же, как в «Кнопка мыши»
            self.mouse_table.setItem(i, 5, QTableWidgetItem(label))
        # Разделитель: тяни границу мышь/таблица мышью — размеры сохраняются в JSON
        self.mouse_table.setMinimumHeight(280)  # шапка таблицы не прячется при перетаскивании
        self.mouse_splitter = QSplitter(Qt.Orientation.Vertical)
        self.mouse_splitter.addWidget(self.mouse_art)
        self.mouse_splitter.addWidget(self.mouse_table)
        self.mouse_splitter.setStretchFactor(0, 1)
        self.mouse_splitter.setStretchFactor(1, 1)
        saved_sizes = self.data.get("mouse_splitter_sizes")
        if saved_sizes and len(saved_sizes) == 2:
            self.mouse_splitter.setSizes([int(saved_sizes[0]), int(saved_sizes[1])])
        self.mouse_splitter.splitterMoved.connect(self.on_mouse_splitter_moved)
        lay.addWidget(self.mouse_splitter, 1)
        return page

    def page_macros(self):
        page = self.page_frame()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("МАКРОСЫ")
        h.setObjectName("h1")
        lay.addWidget(h)
        sub = QLabel("Скриншот и макросы клавиатуры текущего профиля")
        sub.setObjectName("muted")
        lay.addWidget(sub)

        # Верхний виджет — скриншот (как картинка мыши на вкладке «Мышь»)
        self.macro_shot = ScreenshotWidget(SCREENSHOT, self)
        self.macro_shot.selection_changed.connect(self.on_macro_selection)
        saved_shot = self._saved_macro_screenshot()
        if saved_shot and Path(saved_shot).exists():
            self.macro_shot.set_pixmap(saved_shot)
        self.macro_info = QLabel("")
        self.macro_info.setObjectName("muted")
        lay.addWidget(self.macro_info)

        # Нижний виджет — таблица макросов
        self.macro_table = QTableWidget(0, 3)
        self.macro_table.setHorizontalHeaderLabels(["Координаты", "Клавиша", "Скрипт"])
        mh = self.macro_table.horizontalHeader()
        mh.setMinimumSectionSize(60)  # минимум считаем по тексту заголовка ниже
        self.macro_table.horizontalHeaderItem(2).setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for c in range(3):
            mh.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        mh.sectionResized.connect(self.on_macro_column_resized)
        QTimer.singleShot(0, self.normalize_macro_columns)
        self.macro_table.verticalHeader().setVisible(False)
        self.macro_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.macro_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.macro_table.itemClicked.connect(self.on_macro_item_clicked)
        self.macro_table.installEventFilter(self)
        self.refresh_macro_table()

        self.macro_split = QSplitter(Qt.Orientation.Vertical)
        self.macro_split.addWidget(self.macro_shot)
        self.macro_split.addWidget(self.macro_table)
        saved = self.data.get("macro_splitter_sizes")
        if saved and len(saved) == 2:
            self.macro_split.setSizes([int(saved[0]), int(saved[1])])
        self.macro_split.splitterMoved.connect(self.on_macro_split_moved)
        lay.addWidget(self.macro_split, 1)
        return page

    # Устаревший page_settings() удалён: вкладка «Настройки» не показывается,
    # а её дублирующие виджеты (sx/sy/chk_grab/chk_smooth/chk_mouse) могли
    # перезаписать элементы вкладки «Геймпад». Все параметры эмуляции теперь
    # живут на вкладке «Геймпад» и сохраняются в settings.json.

    def start_mouse_engine(self):
        """Поднять скрытый движок мыши/клавиатуры из исходного проекта.
        Окно настроек мыши не показывается — внешний вид программы не меняется."""
        try:
            self.mouse_engine = MouseSettingApp()
            # Скрытый движок не должен показывать свой значок в трее —
            # у программы остаётся только одна иконка.
            extra_tray = getattr(self.mouse_engine, "tray_icon", None)
            if extra_tray is not None:
                extra_tray.hide()
            self.mouse_engine.start_startup_now(dict_save)
        except Exception as exc:
            self.mouse_engine = None
            self.status("Мышиный движок не запущен: " + str(exc)[:120])

    def auto_start_gamepad(self):
        """Автозапуск эмуляции геймпада (как в AppController оригинала)."""
        try:
            self.start_emulation()
        except Exception as exc:
            self.status("Геймпад не запущен: " + str(exc)[:120])

    def take_screenshot(self):
        """F11 — скриншот в папку 'Screenshot_from_games' рядом с программой."""
        folder = HERE / "Screenshot_from_games"
        try:
            folder.mkdir(exist_ok=True)
            profiles = self.data.get("profiles", [])
            row = self.data.get("current_profile", 0)
            profile = profiles[row] if 0 <= row < len(profiles) else "profile"
            safe = "".join(c if (c.isalnum() or c in "-_") else "_"
                           for c in str(profile))
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = folder / (safe + "_" + stamp + ".png")
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[1])
                Image.frombytes("RGB", raw.size, raw.rgb).save(path)
            info = getattr(self, "macro_info", None)
            if info is not None:
                info.setText("Скриншот: " + str(path))
            return path
        except Exception as exc:
            info = getattr(self, "macro_info", None)
            if info is not None:
                info.setText("Ошибка скриншота: " + str(exc)[:90])
            return None

    def install_hotkeys(self):
        """Глобальные F11/End/F3 через pynput + локальные QShortcut."""
        self._last_hotkey = {}
        actions = {
            "f11": self.take_screenshot,
            "f3": lambda: self.btn_edit_zones.setChecked(
                not self.btn_edit_zones.isChecked()),
            "end": self.stop_emulation,
        }
        self._hotkey_actions = actions
        # QTimer, созданный в потоке pynput, никогда не сработает: у этого
        # потока нет event loop. Сигнал с автосоединением сам доставит вызов
        # в GUI-поток через очередь событий Qt.
        self.hotkey_sig.connect(self._on_hotkey)

        def fire(name):
            now = time_module.monotonic()
            if now - self._last_hotkey.get(name, 0) < 0.5:
                return
            self._last_hotkey[name] = now
            self.hotkey_sig.emit(name)

        def on_press(key):
            try:
                name = getattr(key, "name", None) or ""
            except Exception:
                name = ""
            if name in actions:
                fire(name)

        try:
            listener = pynput_keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
            self._hotkey_listener = listener
        except Exception:
            # Глобальный слушатель недоступен (например, Wayland) — остаются
            # локальные QShortcut, работающие при фокусе на окне программы.
            pass

        # Дополнительно — локальные Qt-шорткаты, когда окно в фокусе
        try:
            from PyQt6.QtGui import QShortcut, QKeySequence
            for combo, name in (("F11", "f11"), ("F3", "f3"), ("End", "end")):
                sc = QShortcut(QKeySequence(combo), self)
                sc.activated.connect(lambda n=name: fire(n))
        except Exception:
            pass

    def _on_hotkey(self, name):
        """Выполнение хоткея строго в GUI-потоке."""
        action = getattr(self, "_hotkey_actions", {}).get(name)
        if action is not None:
            action()

    def _stop_hotkey_listener(self):
        listener = getattr(self, "_hotkey_listener", None)
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

    def stop_mouse_engine(self):
        try:
            if self.mouse_engine is not None:
                self.mouse_engine._stop_active_runtime(dict_save)
        except Exception:
            pass

    # ---------- редактор скриптов (функционал исходного проекта) ----------
    def _on_keyboard_key(self, key):
        """Клик по клавише виртуальной клавиатуры — открыть редактор скрипта."""
        self.open_script_editor(key, "keyboard_script")

    def open_script_editor(self, key, section="keyboard_script"):
        """Окно: поле ввода скрипта сверху и клавиатура снизу.
        Нажатие клавиш на клавиатуре вставляет в поле команды xte."""
        if getattr(self, "script_editor", None) is not None:
            try:
                self.script_editor.close()
            except Exception:
                pass
        editor = QMainWindow(self)
        editor.setWindowTitle("Запись макроса для клавиши " + str(key))
        editor.resize(1100, 600)
        central = QWidget()
        editor.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.addWidget(QLabel("Редактор скрипта:"))
        text = QTextEdit()
        lay.addWidget(text)

        res = dict_save.return_jnson()
        app = res.get("current_app", "")
        if section == "keyboard_script":
            content = res.get("keyboard_script", {}).get(app, {}).get("keys", {}).get(key, "")
        else:
            content = res.get("script_mouse", {}).get(app, {}).get(key, "")
        text.setPlainText(content if content else "#!/bin/bash\n")
        cursor = text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        text.setTextCursor(cursor)

        keyboard = KeyboardWidget(lambda k, w=text: add_text_pytq5(k, w))
        lay.addWidget(keyboard)

        editor._script_key = key
        editor._script_section = section
        editor._script_text = text
        editor.closeEvent = lambda ev: self.save_script_editor(editor, ev)
        self.script_editor = editor
        editor.show()

    def save_script_editor(self, editor, event):
        """Сохранить скрипт в JSON исходного проекта и обновить подсветку."""
        try:
            res = dict_save.return_jnson()
            app = res.get("current_app", "")
            content = editor._script_text.toPlainText().strip()
            key, section = editor._script_key, editor._script_section
            if content and content != "#!/bin/bash":
                if section == "keyboard_script":
                    keys = res.setdefault("keyboard_script", {}).setdefault(app, {}).setdefault("keys", {})
                    keys[key] = content
                else:
                    res.setdefault("script_mouse", {}).setdefault(app, {})[key] = content
            else:
                if section == "keyboard_script":
                    keys = res.get("keyboard_script", {}).get(app, {}).get("keys", {})
                    if key in keys:
                        del keys[key]
                else:
                    scripts = res.get("script_mouse", {}).get(app, {})
                    if key in scripts:
                        del scripts[key]
            res = cleanup_empty_script_entries(res)
            scripts_to_text(res)
            dict_save.save_jnson(res)
            # Сначала записываем правку в settings.json, и только потом
            # синхронизируем движок — иначе он перечитал бы старый файл.
            self.data["mouse_data"] = res
            self.save_settings()
            self.sync_engine_settings(source=res)
            self.refresh_script_highlights()
            self.refresh_macro_table()
        except Exception:
            pass
        if self.script_editor is editor:
            self.script_editor = None
        if event is not None:
            event.accept()

    def refresh_script_highlights(self):
        """Клавиши со скриптом — жёлтые; ячейки «Скрипты» — тоже."""
        try:
            res = dict_save.return_jnson()
            app = res.get("current_app", "")
            kb_keys = set(res.get("keyboard_script", {}).get(app, {}).get("keys", {}).keys())
            widgets = [getattr(self, "kw", None), getattr(self, "_virtual_kb_widget", None)]
            for widget in widgets:
                if widget is None:
                    continue
                for btn in widget.findChildren(QPushButton):
                    eff = getattr(btn, "effective_key", None)
                    marked = (eff in kb_keys or
                              btn.text().replace("\n", " ").strip() in kb_keys)
                    btn.setStyleSheet(
                        "background-color:#F8C000; color:#141414;" if marked else "")
            mouse_scripts = res.get("script_mouse", {}).get(app, {})
            table = getattr(self, "mouse_table", None)
            if table is not None:
                for i, name in enumerate(defaut_list_mouse_buttons):
                    if i >= table.rowCount():
                        break
                    item = table.item(i, 5)
                    if item is None:
                        continue
                    item.setBackground(QBrush(QColor("#F8C000")) if mouse_scripts.get(name)
                                       else QBrush(QColor("#222226")))
        except Exception:
            pass

    # ---------- макросы ----------
    def _read_all_settings(self):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"), strict=False)
            # continuation-строки скриптов не должны тащить огромные отступы
            scripts_to_text(data.get("mouse_data", {}))
            return data
        except Exception:
            return {}

    def _write_all_settings(self, root):
        # Берём текущие данные интерфейса и подменяем только вложенные разделы
        # из переданного root — иначе щелчок по кнопке мыши откатывал бы
        # только что изменённое значение старым значением из файла.
        merged = dict(self.data)
        for key in ("mouse_data", "gamepad_data", "macro_data"):
            if key in root:
                merged[key] = root[key]
        SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        self.data = merged

    def _saved_macro_screenshot(self):
        root = self._read_all_settings()
        game = root.get("mouse_data", {}).get("current_app", "")
        return root.get("macro_data", {}).get(game, "")

    def on_macro_selection(self, coords):
        """Сохраняем координаты рамки эмблемы: скриншот — ключ, эмблема — значение."""
        try:
            root = self._read_all_settings()
            macro = root.setdefault("macro_data", {})
            game = root.get("mouse_data", {}).get("current_app", "")
            shot = macro.get(game) or str(SCREENSHOT)
            entry = macro.setdefault(shot, {})
            entry.update(coords)
            self._write_all_settings(root)
            text = "Эмблема: %s,%s – %s,%s (%s×%s)" % (
                coords["left"], coords["top"], coords["right"], coords["bottom"],
                coords["width"], coords["height"])
            self.macro_info.setText(text)
            self.refresh_macro_table()
        except Exception as exc:
            self.macro_info.setText("Ошибка сохранения: " + str(exc)[:80])

    def add_macro_screenshot(self):
        """Кнопка «Добавить» на вкладке «Макросы» — выбор файла изображения."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать скриншот", str(HERE),
            "Изображения (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tif *.tiff);;Все файлы (*)")
        if not path:
            return
        try:
            root = self._read_all_settings()
            game = root.get("mouse_data", {}).get("current_app", "")
            root.setdefault("macro_data", {})[game] = path
            self._write_all_settings(root)
            self.macro_shot.set_pixmap(path)
            self.macro_info.setText("Скриншот: " + path)
            self.refresh_macro_table()
        except Exception as exc:
            self.macro_info.setText("Ошибка: " + str(exc)[:80])

    def delete_macro_selection(self):
        """Удалить текущую координату и красную рамку на скриншоте."""
        item = self.macro_table.currentItem() if hasattr(self, "macro_table") else None
        shot = self._macro_shot_from_item(item)
        try:
            root = self._read_all_settings()
            macro = root.get("macro_data", {})
            if shot:
                macro.pop(shot, None)
                for key, value in list(macro.items()):
                    if isinstance(value, str) and value == shot:
                        del macro[key]
            else:
                game = root.get("mouse_data", {}).get("current_app", "")
                current_shot = macro.get(game, "")
                if current_shot in macro:
                    del macro[current_shot]
                macro.pop(game, None)
            self._write_all_settings(root)
        except Exception:
            pass
        if hasattr(self, "macro_shot"):
            self.macro_shot._rect = None
            self.macro_shot.update()
        if hasattr(self, "macro_info"):
            self.macro_info.setText("")
        self.refresh_macro_table()
        self.status("Координата удалена")

    def on_delete_clicked(self):
        """В Макросах «Удалить» чистит координату, в остальных — профиль."""
        if self.stack.currentIndex() == 3:
            self.delete_macro_selection()
        else:
            self.del_profile()

    def on_add_clicked(self):
        """Верхняя кнопка «Добавить»: в Макросах выбирает скриншот, иначе профиль."""
        if self.stack.currentIndex() == 3:
            self.add_macro_screenshot()
        else:
            self.add_profile()

    def refresh_macro_table(self):
        """Колонки: координаты эмблемы, клавиша, скрипт."""
        table = getattr(self, "macro_table", None)
        if table is None:
            return
        root = self._read_all_settings()
        macro = root.get("macro_data", {})
        rows = [(k, v) for k, v in macro.items() if isinstance(v, dict)]
        table.setRowCount(len(rows))
        for i, (shot, data) in enumerate(rows):
            coords = "%s,%s – %s,%s (%sx%s)" % (
                data.get("left", 0), data.get("top", 0),
                data.get("right", 0), data.get("bottom", 0),
                data.get("width", 0), data.get("height", 0))
            item = QTableWidgetItem(coords)
            item.setData(Qt.ItemDataRole.UserRole, shot)
            table.setItem(i, 0, item)
            table.setItem(i, 1, QTableWidgetItem(data.get("key", "")))
            script = str(data.get("script", "")).replace("\n", " ")
            table.setItem(i, 2, QTableWidgetItem(script[:120]))
    def edit_macro_entry(self, shot):
        """Редактирование клавиши и скрипта для выбранного скриншота."""
        root = self._read_all_settings()
        entry = root.setdefault("macro_data", {}).setdefault(shot, {})
        dlg = QDialog(self)
        dlg.setWindowTitle("Макрос: " + Path(shot).name)
        form = QFormLayout(dlg)
        key = QLineEdit(entry.get("key", ""))
        script = QTextEdit(entry.get("script", ""))
        script.setMinimumHeight(180)
        form.addRow("Клавиша:", key)
        form.addRow("Скрипт:", script)
        row = QHBoxLayout()
        ok = QPushButton("Сохранить")
        cancel = QPushButton("Отмена")
        row.addWidget(ok)
        row.addWidget(cancel)
        form.addRow(row)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry["key"] = key.text().strip()
            entry["script"] = script.toPlainText().strip()
            self._write_all_settings(root)
            self.refresh_macro_table()
    def macro_column_minimums(self):
        """Минимальная ширина колонки — по количеству/ширине символов заголовка."""
        table = getattr(self, "macro_table", None)
        if table is None:
            return [110, 100, 140]
        fm = QFontMetrics(table.font())
        result = []
        for i in range(3):
            item = table.horizontalHeaderItem(i)
            text = item.text() if item is not None else ""
            result.append(max(fm.horizontalAdvance(text) + 36, 90))
        return result

    def normalize_macro_columns(self):
        """Колонки занимают ВСЮ ширину таблицы; ширины сохраняются в JSON."""
        if getattr(self, "_normalizing_macro", False):
            return
        table = getattr(self, "macro_table", None)
        if table is None:
            return
        self._normalizing_macro = True
        try:
            avail = table.viewport().width()
            if avail <= 0:
                return
            mins = self.macro_column_minimums()
            widths = self.data.get("macro_column_widths") or [260, 160, 300]
            widths = [max(int(widths[i]), mins[i]) for i in range(3)]
            if sum(widths) < avail:
                widths[2] += avail - sum(widths)
            elif sum(widths) > avail:
                excess = sum(widths) - avail
                for i in (2, 1, 0):
                    take = min(excess, max(0, widths[i] - mins[i]))
                    widths[i] -= take
                    excess -= take
                    if excess <= 0:
                        break
            self._restoring_macro_cols = True
            for i, w in enumerate(widths):
                table.setColumnWidth(i, int(w))
            self._restoring_macro_cols = False
            # Только подстраи вид под окно; в data ничего не пишем.
        except Exception:
            pass
        finally:
            self._normalizing_macro = False
    def on_macro_column_resized(self, index, old_size, new_size):
        """Все колонки тянутся свободно, но заголовки остаются видимыми."""
        if getattr(self, "_restoring_macro_cols", False):
            return
        try:
            table = self.macro_table
            avail = table.viewport().width()
            if avail <= 0:
                return
            mins = self.macro_column_minimums()
            widths = [max(table.columnWidth(i), mins[i]) for i in range(3)]
            total = sum(widths)
            if total > avail:
                excess = total - avail
                for i in (2, 1, 0):
                    if i == index:
                        continue
                    take = min(excess, max(0, widths[i] - mins[i]))
                    widths[i] -= take
                    excess -= take
                    if excess <= 0:
                        break
                if excess > 0:
                    widths[index] = max(mins[index], widths[index] - excess)
            elif total < avail:
                widths[2] += avail - total
            self._restoring_macro_cols = True
            for i, w in enumerate(widths):
                table.setColumnWidth(i, int(w))
            self._restoring_macro_cols = False
            self.data["macro_column_widths"] = [table.columnWidth(i) for i in range(3)]
            self.save_settings()
        except Exception:
            pass
    def _macro_shot_from_item(self, item):
        if item is None:
            return ""
        shot = item.data(Qt.ItemDataRole.UserRole)
        if not shot:
            it = self.macro_table.item(item.row(), 0)
            shot = it.data(Qt.ItemDataRole.UserRole) if it else ""
        return shot

    def on_macro_item_clicked(self, item):
        """Один клик — как на вкладке «Мышь»: клавиша/скрипт открывают окна."""
        shot = self._macro_shot_from_item(item)
        if not shot:
            return
        col = item.column()
        if col == 1:
            self.pick_macro_key(shot)
        elif col == 2:
            self.open_macro_script_editor(shot)

    def pick_macro_key(self, shot):
        """Та же большая клавиатура, что и у скрипта, но без текстового редактора."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор клавиши")
        dlg.resize(1200, 420)
        lay = QVBoxLayout(dlg)

        def choose(key):
            self.set_macro_key(shot, key)
            dlg.accept()

        lay.addWidget(KeyboardWidget(choose))
        dlg.exec()
    def set_macro_key(self, shot, key):
        try:
            root = self._read_all_settings()
            root.setdefault("macro_data", {}).setdefault(shot, {})["key"] = str(key)
            self._write_all_settings(root)
            self.refresh_macro_table()
        except Exception:
            pass

    def open_macro_script_editor(self, shot):
        """Поле ввода скрипта + клавиатура; команды вставляются кликом по клавишам."""
        root = self._read_all_settings()
        entry = root.setdefault("macro_data", {}).setdefault(shot, {})
        dlg = QDialog(self)
        dlg.setWindowTitle("Редактор скрипта: " + Path(shot).name)
        dlg.resize(1000, 520)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Редактор скрипта:"))
        text = QTextEdit()
        text.setPlainText(entry.get("script", "") or "#!/bin/bash\n")
        lay.addWidget(text)
        kb = KeyboardWidget(lambda k, w=text: add_text_pytq5(k, w))
        lay.addWidget(kb)

        def save(event=None):
            script = text.toPlainText().strip()
            entry["script"] = "" if script == "#!/bin/bash" else script
            self._write_all_settings(root)
            self.refresh_macro_table()
            if event is not None:
                event.accept()
        dlg.closeEvent = save
        dlg.exec()
    def on_macro_split_moved(self):
        try:
            self.data["macro_splitter_sizes"] = list(self.macro_split.sizes())
            self.save_settings()
        except Exception:
            pass

    # ---------- события ----------
    def on_nav(self, idx):
        self.stack.setCurrentIndex(idx)
        # Уходя с вкладки геймпада — выходим из режима редактирования зон
        if idx != 2 and hasattr(self, "btn_edit_zones") \
                and self.btn_edit_zones.isChecked():
            self.btn_edit_zones.setChecked(False)

    def sync_engine_settings(self, restart=True, source=None):
        """Передать движку актуальные данные и перезапустить его рантайм.

        source нужен, когда данные только что изменены в памяти: перечитывание
        файла затерло бы правку, ещё не записанную на диск.
        """
        try:
            if source is None:
                root = self._read_all_settings()
                source = root.get("mouse_data", {})
            dict_save.save_jnson(source)         # память движка, а не только файл
            dict_save.set_cur_app(source.get("current_app", ""))
            if restart and self.mouse_engine is not None:
                self.mouse_engine.prepare(dict_save, force_ui_selection=True)
        except Exception:
            pass

    def _profile_path(self, row):
        """Путь игры, соответствующий профилю с этим номером."""
        paths = self.data.get("profile_paths", [])
        if 0 <= row < len(paths):
            return str(paths[row])
        mouse = self.data.get("mouse_data", {})
        keys = list(mouse.get("games_checkmark", {}).keys())
        if 0 <= row < len(keys):
            return keys[row]
        return ""

    def on_mouse_key_changed(self, btn, index, value):
        """Привязка кнопки мыши пишется в данные ВЫБРАННОГО профиля."""
        self.data["mouse_map"][btn] = value
        try:
            root = self._read_all_settings()
            mouse = root.setdefault("mouse_data", {})
            path = mouse.get("current_app", "")
            vals = mouse.setdefault("key_value", {}).setdefault(path, [])
            need = max(MOUSE_INDEX_TO_ENGINE) + 1
            while len(vals) < need:
                vals.append(" ")
            vals[MOUSE_INDEX_TO_ENGINE[index]] = value
            self._write_all_settings(root)
            self.sync_engine_settings()
        except Exception:
            self.save_settings()

    def apply_mouse_profile(self, row):
        """Загрузить привязки/режимы/скрипты выбранного профиля из JSON мыши."""
        if not (0 <= row < len(self.data.get("profiles", []))):
            return
        path = self._profile_path(row)
        root = self._read_all_settings()
        mouse = root.setdefault("mouse_data", {})
        if path:
            mouse["current_app"] = path
        self._write_all_settings(root)
        self.sync_engine_settings()
        # Подсветить кнопки, у которых в ЭТОМ профиле есть скрипт
        self.refresh_script_highlights()

        vals = mouse.get("key_value", {}).get(path, [])
        for i, btn in enumerate(MOUSE_BUTTONS):
            src = MOUSE_INDEX_TO_ENGINE[i]
            value = str(vals[src]) if src < len(vals) else ""
            self.data["mouse_map"][btn] = value
            cb = self.mouse_key_combos.get(btn)
            if cb is not None:
                if value and cb.findText(value) < 0:
                    cb.addItem(value)
                cb.blockSignals(True)
                cb.setCurrentText(value)
                cb.blockSignals(False)
        self.refresh_macro_table()

    def on_profile(self, row):
        if 0 <= row < len(self.data["profiles"]):
            self.data["current_profile"] = row
            self.sync_profile_combos(row)
            self.apply_mouse_profile(row)

    def on_profile_combo(self, row):
        if 0 <= row < len(self.data["profiles"]):
            self.data["current_profile"] = row
            self.sync_profile_combos(row)
            self.apply_mouse_profile(row)
            self.status("Профиль мыши: " + self.data["profiles"][row])
            self.save_settings()

    def rename_profile(self, item):
        """Двойной клик по профилю — окно с полем ввода нового имени."""
        row = self.profile_list.row(item)
        if not (0 <= row < len(self.data.get("profiles", []))):
            return
        old = self.data["profiles"][row]
        name, ok = QInputDialog.getText(
            self, "Переименовать профиль", "Имя профиля:", text=old)
        if ok and name.strip() and name.strip() != old:
            name = name.strip()
            self.data["profiles"][row] = name
            item.setText(name)
            self.refresh_profile_combos()
            self.save_settings()
            self.status("Профиль переименован: " + name)

    def rename_current_profile(self):
        """Двойной клик по выпадающему списку профиля — переименование."""
        row = self.ms_profile.currentIndex()
        profiles = self.data.get("profiles", [])
        if not (0 <= row < len(profiles)):
            return
        old = profiles[row]
        name, ok = QInputDialog.getText(
            self, "Переименовать профиль", "Имя профиля:", text=old)
        if ok and name.strip() and name.strip() != old:
            name = name.strip()
            profiles[row] = name
            if 0 <= row < self.profile_list.count():
                self.profile_list.item(row).setText(name)
            self.refresh_profile_combos()
            self.save_settings()
            self.status("Профиль переименован: " + name)

    def show_normal(self):
        """Показать окно из трея."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if getattr(self, "_baseline_data", None) is None:
            QTimer.singleShot(150, self._take_baseline)

    def on_profile_list_row(self, row):
        if 0 <= row < len(self.data["profiles"]):
            self.data["current_profile"] = row
            self.sync_profile_combos(row)
            self.apply_mouse_profile(row)
            self.status("Профиль: " + self.data["profiles"][row])

    def on_profile_split_moved(self):
        try:
            self.data["profile_split_sizes"] = list(self.profile_split.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_gamepad_split_moved(self):
        """Ширина картинки геймпада и панели клавиш сохраняется в JSON."""
        try:
            self.data["gamepad_split_sizes"] = list(self.gamepad_split.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_profile_vertical_moved(self):
        """Высота блока профиля сохраняется в settings.json."""
        try:
            self.data["profile_vertical_sizes"] = list(
                self.profile_vertical_split.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_profiles_reordered(self):
        """Порядок профилей изменён перетаскиванием — запомнить и сохранить."""
        names = [self.profile_list.item(i).text()
                 for i in range(self.profile_list.count())]
        if names == self.data.get("profiles"):
            return
        old = self.data.get("profiles", [])
        self.data["profiles"] = names
        paths = self.data.get("profile_paths", [])
        if len(paths) == len(old):
            self.data["profile_paths"] = [
                paths[old.index(n)] if n in old else p for n, p in zip(names, paths)
            ]
        row = self.profile_list.currentRow()
        self.data["current_profile"] = max(0, row)
        self.refresh_profile_combos()
        self.save_settings()

    def move_profile(self, delta):
        """Переместить выбранный профиль вверх/вниз и сохранить порядок."""
        lst = self.profile_list
        row = lst.currentRow()
        new = row + delta
        if row < 0 or not (0 <= new < lst.count()):
            return
        item = lst.takeItem(row)
        lst.insertItem(new, item)
        lst.setCurrentRow(new)
        self.on_profiles_reordered()

    def sync_profile_combos(self, row):
        combo = getattr(self, "ms_profile", None)
        if combo is not None and combo.currentIndex() != row:
            combo.blockSignals(True)
            combo.setCurrentIndex(row)
            combo.blockSignals(False)
        lst = getattr(self, "profile_list", None)
        if lst is not None and lst.currentRow() != row:
            lst.blockSignals(True)
            lst.setCurrentRow(row)
            lst.blockSignals(False)

    def mouse_column_minimums(self):
        """Минимальная ширина колонки — чтобы её заголовок целиком влезал."""
        t = self.mouse_table
        fm = QFontMetrics(t.font())
        result = []
        for i in range(t.columnCount()):
            item = t.horizontalHeaderItem(i)
            text = item.text() if item is not None else ""
            result.append(max(fm.horizontalAdvance(text) + 30, 60))
        return result

    def normalize_mouse_columns(self):
        """Подогнать ширины колонок под таблицу, чтобы не было горизонтальной прокрутки."""
        t = getattr(self, "mouse_table", None)
        if t is None:
            return
        if not self.isVisible():  # окно в трее — размер таблицы ещё не настоящий
            return
        avail = t.viewport().width()
        if avail <= 0:
            return
        widths = [t.columnWidth(i) for i in range(6)]
        minimums = self.mouse_column_minimums()
        for i in range(6):
            if widths[i] < minimums[i]:
                widths[i] = minimums[i]
        total = sum(widths)
        if total > avail:
            excess = total - avail
            for i in (5, 4, 3, 2, 1, 0):
                can = widths[i] - minimums[i]
                if can <= 0:
                    continue
                take = min(excess, can)
                widths[i] -= take
                excess -= take
                if excess <= 0:
                    break
        elif total < avail:
            widths[0] += avail - total  # заполняем место без прокрутки
        if total != avail:
            self._restoring_columns = True
            for i, w in enumerate(widths):
                t.setColumnWidth(i, int(w))
            self._restoring_columns = False
        # Авто-подгонка при показе вкладки НЕ сохраняется как изменение
        # пользователя — иначе окно спрашивает «сохранить?» просто при открытии.

    def on_mouse_column_resized(self, index, old_size, new_size):
        """Тянем колонку: остальные 5 не выходят за окно, а «Скрипты»
        (последняя) занимает всё оставшееся место справа."""
        if getattr(self, "_restoring_columns", False) or index == 5:
            return
        try:
            t = self.mouse_table
            avail = t.viewport().width()
            if avail <= 0:
                return
            mins = self.mouse_column_minimums()
            widths = [t.columnWidth(i) for i in range(6)]
            fixed = sum(widths[:5])
            max_fixed = max(0, avail - mins[5])
            if fixed > max_fixed:
                widths[index] = max(mins[index], widths[index] - (fixed - max_fixed))
            self._restoring_columns = True
            for i in range(5):
                t.setColumnWidth(i, int(widths[i]))
            self._restoring_columns = False
            self.data["mouse_column_widths"] = [t.columnWidth(i) for i in range(6)]
            self.save_settings()  # сразу в JSON, иначе после выхода ширины вернутся
        except Exception:
            pass

    def on_main_splitter_moved(self):
        """Ширина бокового меню сохраняется в settings.json."""
        try:
            self.data["main_splitter_sizes"] = list(self.main_splitter.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_kb_split_moved(self):
        try:
            self.data["kb_split_sizes"] = list(self.kb_split.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_kb_column_resized(self, index, old_size, new_size):
        """Две колонки таблицы клавиатуры: при изменении одной подгоняем вторую."""
        if getattr(self, "_restoring_kb_cols", False):
            return
        try:
            t = self.kb_table
            avail = t.viewport().width()
            widths = [t.columnWidth(i) for i in range(2)]
            mins = [120, 120]
            widths[index] = max(mins[index], widths[index])
            total = sum(widths)
            if avail > 0 and total > avail:
                other = 1 - index
                excess = total - avail
                can = widths[other] - mins[other]
                take = min(excess, max(0, can))
                widths[other] -= take
                excess -= take
                if excess > 0:
                    widths[index] = max(mins[index], widths[index] - excess)
            elif avail > 0 and total < avail:
                widths[1 - index] += avail - sum(widths)
            self._restoring_kb_cols = True
            for i, w in enumerate(widths):
                t.setColumnWidth(i, int(w))
            self._restoring_kb_cols = False
            self.data["kb_column_widths"] = [t.columnWidth(i) for i in range(2)]
        except Exception:
            pass

    def on_edit_zones(self, checked):
        """Включить/выключить ручную правку зон; при выключении сохранить."""
        self.gamepad.set_debug_mode(bool(checked))
        # жёлтая кнопка = режим редактирования включён
        self.btn_edit_zones.setObjectName("primary" if checked else "secondary")
        self.btn_edit_zones.style().polish(self.btn_edit_zones)
        if checked:
            self.status("Редактирование зон: тяни зоны, колесо — размер")
        else:
            try:
                self.data["gamepad_zone_geometry"] = self.gamepad.get_zones_data()
                # сохраняем текущий приближение/сдвиг — картинка останется такой же
                self.data["gamepad_zoom"] = self.gamepad._zoom
                self.data["gamepad_pan"] = [self.gamepad._pan.x(), self.gamepad._pan.y()]
                self.save_settings()
                self.status("Зоны сохранены")
            except Exception:
                self.status("Ошибка сохранения зон")

    def on_mouse_splitter_moved(self):
        """Запоминаем новые размеры панелей — сохранятся в settings.json."""
        try:
            self.data["mouse_splitter_sizes"] = list(self.mouse_splitter.sizes())
            self.save_settings()
        except Exception:
            pass

    def on_mouse_zone(self, label):
        for row in range(self.mouse_table.rowCount()):
            item = self.mouse_table.item(row, 0)
            if item and item.text() == label:
                self.mouse_table.clearSelection()
                item.setSelected(True)  # только название кнопки, не радиокнопки
                self.mouse_table.setCurrentCell(row, 0)
                self.status("Мышь: " + label)
                return

    def on_mouse_zone_hover(self, label):
        """Навели на кнопку мыши — подсвечиваем соответствующую строку таблицы."""
        t = getattr(self, "mouse_table", None)
        if t is None:
            return
        t.blockSignals(True)
        t.clearSelection()
        if not label:
            art = getattr(self, "mouse_art", None)
            if art is not None:
                art.set_external_zone("")
        if label:
            for row in range(t.rowCount()):
                item = t.item(row, 0)
                if item and item.text() == label:
                    item.setSelected(True)  # подсвечиваем только имя кнопки
                    break
        t.blockSignals(False)

    def eventFilter(self, obj, event):
        try:
            t = getattr(self, "mouse_table", None)
            if (t is not None and obj is t.viewport()
                    and event.type() == QEvent.Type.Leave):
                art = getattr(self, "mouse_art", None)
                if art is not None:
                    art.set_external_zone("")
            mt = getattr(self, "macro_table", None)
            if (mt is not None and obj is mt
                    and event.type() == QEvent.Type.Resize):
                QTimer.singleShot(0, self.normalize_macro_columns)
            if (obj is getattr(self, "mouse_table", None)
                    and event.type() == QEvent.Type.Resize):
                QTimer.singleShot(0, self.normalize_mouse_columns)
            if (obj is getattr(self, "ms_profile", None)
                    and event.type() == QEvent.Type.MouseButtonDblClick):
                QTimer.singleShot(0, self.rename_current_profile)
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def on_mouse_table_item_clicked(self, item):
        """Клик по колонке «Скрипты» открывает редактор скрипта кнопки мыши."""
        if item is not None and item.column() == 5 \
                and item.row() < len(defaut_list_mouse_buttons):
            key = defaut_list_mouse_buttons[item.row()]
            self.open_script_editor(key, "script_mouse")

    def on_mouse_table_entered(self, item):
        """Навели на ячейку таблицы — подсвечиваем кнопку на картинке мыши."""
        art = getattr(self, "mouse_art", None)
        if art is None:
            return
        labels = {z[0] for z in InteractiveMouse.ZONES}
        text = item.text() if (item is not None and item.column() in (0, 5)) else ""
        art.set_external_zone(text if text in labels else "")

    def on_mouse_table_cell(self, row, column, previous_row, previous_column):
        """Выбрали строку в таблице — подсвечиваем кнопку на картинке мыши."""
        art = getattr(self, "mouse_art", None)
        if art is None or not (0 <= row < self.mouse_table.rowCount()):
            return
        item = self.mouse_table.item(row, 0)
        art.set_external_zone(item.text() if item else "")

    def on_gamepad_profile(self, name):
        """Профиль геймпада выбирается по имени из JSON редактора Xbox 360."""
        profiles = self.data.get("gamepad_profiles", {})
        if name in profiles:
            self.data["current_gamepad_profile"] = name
            self.data["gamepad_map"] = dict(profiles[name])
            for logical, key in self.data["gamepad_map"].items():
                cb = self.gamepad_combos.get(logical)
                if cb is not None:
                    cb.blockSignals(True)
                    if cb.findText(key) < 0:
                        cb.addItem(key)
                    cb.setCurrentText(key)
                    cb.blockSignals(False)
                b = self.kb_buttons.get(logical)
                if b:
                    b.setText(key.replace("KEY_", ""))
            self.status("Профиль геймпада: " + name)

    def refresh_profile_combos(self):
        combo = getattr(self, "ms_profile", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(self.data["profiles"])
            combo.setCurrentIndex(min(self.data.get("current_profile", 0), len(self.data["profiles"]) - 1))
            combo.blockSignals(False)

    def add_profile(self):
        name = f"Empty Profile ({len(self.data['profiles']) + 1})"
        self.data["profiles"].append(name)
        self.data["current_profile"] = len(self.data["profiles"]) - 1
        self.profile_list.addItem(name)
        self.profile_list.setCurrentRow(self.data["current_profile"])
        self.refresh_profile_combos()
        self.save_settings()

    def del_profile(self):
        row = self.data.get("current_profile", 0)
        if len(self.data["profiles"]) > 1:
            self.data["profiles"].pop(row)
            if "profile_paths" in self.data and row < len(self.data["profile_paths"]):
                self.data["profile_paths"].pop(row)
            self.profile_list.takeItem(row)
            self.data["current_profile"] = max(0, row - 1)
            self.profile_list.setCurrentRow(self.data["current_profile"])
            self.refresh_profile_combos()
            self.save_settings()

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить профиль", str(HERE / "profile.json"), "JSON (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status("Профиль сохранён: " + path)

    def _set_gamepad_binding(self, logical, value):
        """Привязка пишется и в рабочую карту, и в оба хранилища профиля."""
        self.data["gamepad_map"][logical] = value
        profile = self.data.get("current_gamepad_profile")
        for container in (self.data.get("gamepad_profiles", {}),
                          (self.data.get("gamepad_data", {}).get("profiles", {}))):
            if isinstance(container, dict) and profile in container:
                container[profile][logical] = value

    def on_key_changed(self, logical, value):
        self._set_gamepad_binding(logical, value)
        b = self.kb_buttons.get(logical)
        if b:
            b.setText(value.replace("KEY_", ""))

    def pick_key(self, logical):
        dlg = KeySelectDialog(self, self.data["gamepad_map"].get(logical, ""))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._set_gamepad_binding(logical, dlg.chosen)
            self.kb_buttons[logical].setText(dlg.chosen.replace("KEY_", ""))
            cb = self.gamepad_combos.get(logical)
            if cb and dlg.chosen in KEY_LIST:
                cb.setCurrentText(dlg.chosen)

    def open_virtual_keyboard(self):
        """Большая виртуальная клавиатура: клик по клавише открывает редактор скрипта."""
        win = QMainWindow(self)
        win.setWindowTitle("Выбор клавиш")
        win.resize(1340, 430)
        central = QWidget()
        win.setCentralWidget(central)
        lay = QVBoxLayout(central)
        kb = KeyboardWidget(lambda key: self.open_script_editor(key, "keyboard_script"))
        self._virtual_kb_widget = kb
        lay.addWidget(kb)
        self.refresh_script_highlights()
        win.show()
        self._virtual_keyboard_window = win

    def open_mouse_app(self):
        try:
            if self.mouse_window is None:
                from library import MouseSettingApp  # noqa: E402
                self.mouse_window = MouseSettingApp()
            self.mouse_window.show()
            self.mouse_window.raise_()
        except Exception:
            QMessageBox.warning(self, "Мышь", "Не удалось открыть модуль мыши:\n" + traceback.format_exc()[-600:])

    def on_gamepad_option_changed(self, *_args):
        """Отложить применение параметра, чтобы не дёргать движок на каждом тике."""
        timer = getattr(self, "_gp_apply_timer", None)
        if timer is not None:
            timer.start()
        else:
            self._apply_gamepad_options()

    def _apply_gamepad_options(self):
        """Сохранить параметры эмуляции и применить их, если она уже идёт."""
        self.data["sens_x"] = int(self.sx.value())
        self.data["sens_y"] = int(self.sy.value())
        self.data["mouse_on"] = bool(self.chk_mouse_mode.isChecked())
        self.data["smooth"] = bool(self.chk_smooth.isChecked())
        self.data["grab"] = bool(self.chk_grab.isChecked())
        self.save_settings()
        if self.worker and self.worker.isRunning():
            self.start_emulation()

    def start_emulation(self):
        # Как в рабочем редакторе Xbox 360: перед запуском всегда останавливаем
        # прежний поток. Иначе смена профиля, привязки или параметра не
        # применялась бы — start_emulation просто возвращался без перезапуска.
        if self.worker and self.worker.isRunning():
            self.stop_emulation()
        keymap = dict(self.data["gamepad_map"])
        self.apply_data_to_ui(write=False)
        trigger_modes = self.data.get("trigger_modes", {}).get(self.data.get("current_gamepad_profile"), {})
        # Параметры берём из настроек/виджетов — как в рабочем редакторе Xbox 360,
        # а не жёстко True: режим мыши и сглаживание можно выключить.
        self.worker = Worker(keymap, trigger_modes,
                             bool(self.data.get("mouse_on", True)),
                             self.sx.value(), self.sy.value(),
                             bool(self.data.get("smooth", True)),
                             self.chk_grab.isChecked())
        self.worker.status_sig.connect(self.on_worker_status)
        self.worker.error_sig.connect(self.on_worker_error)
        # Сигнал от старого потока может прийти уже после старта нового.
        # Привязываем его к конкретному экземпляру, как в эталонном редакторе.
        self.worker.finished.connect(
            lambda source=self.worker: self._on_worker_finished(source))
        self.worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(10)
        self.status("Эмуляция запускается…")

    def stop_emulation(self):
        if self.worker:
            # Worker.stop() уже делает wait(2000); второе ожидание до 3 с
            # только замораживало GUI при перезапуске.
            try:
                self.worker.stop()
            except Exception:
                pass
        self.on_worker_finished()

    def _on_worker_finished(self, source):
        """Обработать завершение только текущего потока эмуляции."""
        if self.worker is source:
            self.on_worker_finished()

    def on_worker_status(self, msg):
        self.log_label.setText("Лог: " + str(msg)[-300:])
        self.status(str(msg))
        self.progress.setValue(min(90, self.progress.value() + 8))

    def on_worker_error(self, msg):
        self.log_label.setText("ОШИБКА: " + str(msg)[-300:])
        self.status("Ошибка: " + str(msg)[:120])

    def on_worker_finished(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(0)
        self.status("Эмуляция остановлена")

    def status(self, text):
        self.status_label.setText(text)

    def apply_data_to_ui(self, write=True):
        self.refresh_profile_combos()
        self.apply_mouse_profile(int(self.data.get("current_profile", 0)))
        # Автозапуск тоже вызывает этот метод: блокируем сигналы, чтобы
        # восстановление виджетов не сохраняло настройки и не перезапускало Worker.
        gp_widgets = (self.sx, self.sy, self.chk_mouse_mode,
                      self.chk_smooth, self.chk_grab)
        for w in gp_widgets:
            w.blockSignals(True)
        self.sx.setValue(int(self.data.get("sens_x", 6)))
        self.sy.setValue(int(self.data.get("sens_y", 6)))
        self.chk_mouse_mode.setChecked(bool(self.data.get("mouse_on", True)))
        self.chk_smooth.setChecked(bool(self.data.get("smooth", True)))
        self.chk_grab.setChecked(bool(self.data.get("grab", False)))
        for w in gp_widgets:
            w.blockSignals(False)
        # при запуске всегда обычный режим, никогда не редактирование
        if hasattr(self, "btn_edit_zones"):
            self.btn_edit_zones.setChecked(False)
            self.gamepad.set_debug_mode(False)
        # подписи зон на картинке геймпада — текущие привязки
        if hasattr(self, "gamepad"):
            saved_zones = self.data.get("gamepad_zone_geometry")
            if saved_zones:
                self.gamepad.set_zones_data(saved_zones)
            # восстанавливаем масштаб и сдвиг картинки
            try:
                self.gamepad._zoom = float(self.data.get("gamepad_zoom", 1.0))
                pan = self.data.get("gamepad_pan", [0, 0])
                self.gamepad._pan = QPointF(float(pan[0]), float(pan[1]))
                self.gamepad._refresh_image()
            except Exception:
                pass
            self.gamepad.update_all_bindings(self.data.get("gamepad_map", {}))
        # мышь: вернуть флажки «удерживать / повторять» и секунды повтора
        for btn in MOUSE_BUTTONS:
            hold = getattr(self, "mouse_hold_boxes", {}).get(btn)
            repeat = getattr(self, "mouse_repeat_boxes", {}).get(btn)
            sec = getattr(self, "mouse_sec_combos", {}).get(btn)
            hold_on = bool(self.data.get("mouse_hold", {}).get(btn, False))
            repeat_on = bool(self.data.get("mouse_repeat", {}).get(btn, False)) and not hold_on
            if hold is not None:
                hold.setChecked(hold_on)
            if repeat is not None:
                repeat.setChecked(repeat_on)
            if sec is not None:
                sec.setCurrentText(str(self.data.get("mouse_repeat_sec", {}).get(btn, "")))
        for logical, key in self.data["gamepad_map"].items():
            cb = self.gamepad_combos.get(logical)
            if cb and key in KEY_LIST:
                cb.setCurrentText(key)
            b = self.kb_buttons.get(logical)
            if b:
                b.setText(key.replace("KEY_", ""))
        self.refresh_script_highlights()
        self.refresh_macro_table()
        if write:
            pass

    def moveEvent(self, event):
        """Запоминаем положение окна (в файл пишем при выходе)."""
        try:
            self.data["window_geometry"] = [self.x(), self.y(),
                                            self.width(), self.height()]
        except Exception:
            pass
        super().moveEvent(event)

    def resizeEvent(self, event):
        """Запоминаем размер окна (в файл пишем при выходе)."""
        try:
            old = self.data.get("window_geometry", [self.x(), self.y(),
                                                    self.width(), self.height()])
            self.data["window_geometry"] = [old[0], old[1],
                                            self.width(), self.height()]
            self.data["window_size"] = [self.width(), self.height()]
        except Exception:
            pass
        super().resizeEvent(event)

    def quit_app(self):
        """Выход из трея: сначала спросить про изменения, потом завершиться."""
        self._update_geometry_data()
        if not self.confirm_unsaved():
            return
        self._closing = True
        self._stop_hotkey_listener()
        self.stop_emulation()
        self.stop_mouse_engine()
        self.save_settings()
        release_single_instance()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _update_geometry_data(self):
        """Перед проверкой изменений учесть положение/размер окна и зум."""
        try:
            self.data["window_geometry"] = [self.x(), self.y(),
                                            self.width(), self.height()]
            self.data["window_size"] = [self.width(), self.height()]
            self.data["gamepad_zoom"] = self.gamepad._zoom
            self.data["gamepad_pan"] = [self.gamepad._pan.x(), self.gamepad._pan.y()]
        except Exception:
            pass

    def closeEvent(self, event):
        if getattr(self, "_closing", False):
            event.accept()
            return
        self._update_geometry_data()
        if not self.confirm_unsaved():
            event.ignore()
            return
        self._closing = True
        self._stop_hotkey_listener()
        self.stop_emulation()
        self.stop_mouse_engine()
        self.save_settings()
        # os._exit минует finally в main(), поэтому lock снимаем сами.
        release_single_instance()
        super().closeEvent(event)
        # Как в исходном скрипте мыши: гарантированный выход без повторного
        # срабатывания closeEvent (иначе окно подтверждения появляется дважды).
        os._exit(0)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Barlow", 10))

    # Второй экземпляр не запускаем — показываем окно с кнопкой OK.
    if not acquire_single_instance():
        QMessageBox.information(
            None, "ReWASD Linux",
            "Программа уже запущена.\n"
            "Работает только один экземпляр — найдите её иконку в трее.",
            QMessageBox.StandardButton.Ok)
        return 0

    # Главное окно стартует скрытым в трее. При True закрытие любого
    # дополнительного окна (редактор скриптов, клавиатура) завершало бы
    # приложение без stop_emulation/save_settings. Выход только через
    # closeEvent главного окна или пункт трея «Выход».
    app.setQuitOnLastWindowClosed(False)
    w = RewasdApp()
    # Иконка окна — видна на панели задач и в заголовке окна
    w.setWindowIcon(QIcon(str(ASSETS / "window_icon.png")))

    # Иконка в системном трее; при запуске окно не показываем.
    tray = QSystemTrayIcon(QIcon(str(ASSETS / "tray_icon.png")), app)
    tray.setToolTip("ReWASD Linux")
    menu = QMenu()
    menu.addAction("Показать окно").triggered.connect(w.show_normal)
    menu.addSeparator()
    menu.addAction("Выход").triggered.connect(w.quit_app)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: w.show_normal()
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick)
        else None)
    tray.show()
    w.tray = tray

    try:
        code = app.exec()
    finally:
        release_single_instance()
    sys.exit(code)


if __name__ == "__main__":
    main()
