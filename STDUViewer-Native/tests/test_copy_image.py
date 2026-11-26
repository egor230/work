#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты вкладки «Недавние документы», копирования текста и сохранения картинок.

Запуск:
    xvfb-run -a -s "-screen 0 1400x900x24" python3 tests/test_copy_image.py
"""
import importlib.util
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

import pymupdf
from PyQt5.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QPoint, QPointF, Qt
from PyQt5.QtGui import QColor, QImage, QMouseEvent
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-copy-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
UNCUGHT = []
SAVE = {'path': ''}

m.QMessageBox.information = staticmethod(lambda *a, **k: None)
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (SAVE['path'], ''))


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def make_pdf(path):
    d = pymupdf.open()
    p = d.new_page(width=595, height=842)
    p.insert_text((72, 100), 'HELLO SELECTION WORLD', fontsize=20)
    p.insert_text((72, 160), 'SECOND LINE OF TEXT', fontsize=20)
    # Маленькая красная картинка в координатах (200,200)-(300,300).
    img = QImage(40, 40, QImage.Format_RGB32)
    img.fill(QColor('red'))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, 'PNG')
    buf.close()
    p.insert_image(pymupdf.Rect(200, 200, 300, 300), stream=bytes(ba))
    p2 = d.new_page(width=595, height=842)
    p2.insert_text((72, 100), 'PAGE TWO TEXT', fontsize=20)
    d.save(str(path))
    d.close()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'copy.pdf'
        make_pdf(cls.pdf)

    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        UNCUGHT.clear()
        SAVE['path'] = ''
        self.w = m.MainWindow()
        pump(3)
        self.w.open_file(str(self.pdf))
        pump(5)
        self.tab = self.w.current_tab()
        self.label = self.tab.view.label

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    def drag(self, p1, p2):
        p1, p2 = QPointF(*p1), QPointF(*p2)
        self.label.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, p1, Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        self.label.mouseMoveEvent(QMouseEvent(
            QEvent.MouseMove, p2, Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        self.label.mouseReleaseEvent(QMouseEvent(
            QEvent.MouseButtonRelease, p2, Qt.LeftButton,
            Qt.NoButton, Qt.NoModifier))
        pump(2)


class TestRecentTab(Base):
    def test_recent_documents_tab_is_active(self):
        self.assertEqual(self.w.nav.currentWidget(), self.w.recent_list)
        self.assertEqual(self.w.nav.tabText(self.w.nav.currentIndex()),
                         'Недавние документы')


class TestTextCopy(Base):
    def test_copy_page_text(self):
        self.w.copy_page_text()
        pump(2)
        text = QApplication.clipboard().text()
        self.assertIn('HELLO SELECTION WORLD', text)
        self.assertIn('SECOND LINE OF TEXT', text)

    def test_copy_all_text(self):
        self.w.copy_all_text()
        pump(2)
        text = QApplication.clipboard().text()
        self.assertIn('HELLO SELECTION WORLD', text)
        self.assertIn('PAGE TWO TEXT', text)

    def test_drag_selects_text_and_copies_it(self):
        # Строка «HELLO SELECTION WORLD» находится примерно в (72..270, 85..110).
        self.drag((72, 82), (275, 112))
        self.assertIn('HELLO SELECTION', self.tab._selected_text)
        self.assertIn('HELLO SELECTION', QApplication.clipboard().text())

    def test_selection_when_page_is_rotated(self):
        self.tab.rotate(90)
        pump(3)
        # При повороте 90°: X = 842 - y, Y = x (z = 1).
        self.drag((731, 72), (758, 272))
        self.assertIn('HELLO SELECTION', self.tab._selected_text)

    def test_ctrl_c_copies_selection(self):
        self.drag((72, 82), (275, 112))
        QApplication.clipboard().clear()
        self.w.setFocus()
        pump(1)
        self.w.copy_text()
        pump(2)
        self.assertIn('HELLO SELECTION', QApplication.clipboard().text())

    def test_ctrl_c_without_selection_copies_page(self):
        QApplication.clipboard().clear()
        self.w.setFocus()
        pump(1)
        self.w.copy_text()
        pump(2)
        self.assertIn('HELLO SELECTION WORLD', QApplication.clipboard().text())


class TestImageSave(Base):
    def test_image_region_found_under_cursor(self):
        image = self.tab.image_at(QPoint(250, 250))
        self.assertIsNotNone(image, 'картинка под курсором не найдена')
        pno, xref = image
        self.assertEqual(pno, 0)
        self.assertGreater(xref, 0)

    def test_copy_image_to_clipboard(self):
        image = self.tab.image_at(QPoint(250, 250))
        self.assertIsNotNone(image)
        ok = self.tab.copy_image(*image)
        pump(2)
        self.assertTrue(ok)
        self.assertFalse(QApplication.clipboard().image().isNull())

    def test_save_image_to_disk(self):
        image = self.tab.image_at(QPoint(250, 250))
        self.assertIsNotNone(image)
        out = TMP / 'saved_picture.png'
        SAVE['path'] = str(out)
        self.tab.save_image(*image)
        pump(2)
        self.assertTrue(out.exists(), 'файл картинки не создан')
        self.assertGreater(out.stat().st_size, 100)
        img = QImage(str(out))
        self.assertFalse(img.isNull())

    def test_no_image_region_on_text_only_page(self):
        self.tab.goto(1)
        pump(3)
        self.assertIsNone(self.tab.image_at(QPoint(250, 250)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
