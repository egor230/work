#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты запоминания позиции чтения для каждого документа."""
import importlib.util
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

import pymupdf
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-positions-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
RECENT = TMP / 'recent.txt'
m.RECENT_FILE = str(RECENT)
UNCUGHT = []
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=8):
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 90), 'READ %d' % (i + 1), fontsize=22)
    d.save(str(path))
    d.close()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf1 = TMP / 'book1.pdf'
        cls.pdf2 = TMP / 'book2.pdf'
        make_pdf(cls.pdf1)
        make_pdf(cls.pdf2)

    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        RECENT.unlink(missing_ok=True)
        UNCUGHT.clear()

    def tearDown(self):
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    def window(self):
        w = m.MainWindow()
        pump(3)
        return w

    def open(self, w, path):
        w.open_file(str(path))
        pump(5)
        return w.current_tab()


class TestPositions(Base):
    def test_position_saved_to_file(self):
        w = self.window()
        tab = self.open(w, self.pdf1)
        tab.goto(3)
        pump(2)
        w.remember_position(tab)
        data = __import__('json').loads(Path(m.POSITIONS_FILE).read_text(encoding='utf-8'))
        self.assertEqual(data[str(self.pdf1)]['page'], 3)
        w.close()

    def test_position_restored_on_reopen(self):
        w = self.window()
        tab = self.open(w, self.pdf1)
        tab.goto(4)
        pump(2)
        w.remember_position(tab)
        w.close()

        w2 = self.window()
        tab2 = self.open(w2, self.pdf1)
        self.assertEqual(tab2.page, 4)
        w2.close()

    def test_each_document_remembers_its_own_page(self):
        w = self.window()
        t1 = self.open(w, self.pdf1)
        t1.goto(1)
        w.remember_position(t1)
        t2 = self.open(w, self.pdf2)
        t2.goto(5)
        w.remember_position(t2)
        w.close()

        w2 = self.window()
        self.assertEqual(self.open(w2, self.pdf1).page, 1)
        self.assertEqual(self.open(w2, self.pdf2).page, 5)
        w2.close()

    def test_zoom_and_rotation_restored(self):
        w = self.window()
        tab = self.open(w, self.pdf1)
        tab.set_zoom(1.7)
        tab.rotate(90)
        pump(2)
        w.remember_position(tab)
        w.close()

        w2 = self.window()
        tab2 = self.open(w2, self.pdf1)
        self.assertAlmostEqual(tab2.zoom, 1.7, places=2)
        self.assertEqual(tab2.rotation, 90)
        w2.close()

    def test_scroll_position_restored(self):
        w = self.window()
        tab = self.open(w, self.pdf1)
        tab.set_zoom(2.0)
        pump(2)
        bar = tab.view.verticalScrollBar()
        span = bar.maximum() - bar.minimum()
        self.assertGreater(span, 0)
        bar.setValue(bar.minimum() + int(span * 0.6))
        w.remember_position(tab)
        w.close()

        w2 = self.window()
        tab2 = self.open(w2, self.pdf1)
        bar2 = tab2.view.verticalScrollBar()
        span2 = bar2.maximum() - bar2.minimum()
        self.assertAlmostEqual((bar2.value() - bar2.minimum()) / span2, 0.6,
                               delta=0.05)
        w2.close()

    def test_no_saved_position_starts_at_page_one(self):
        w = self.window()
        tab = self.open(w, self.pdf1)
        self.assertEqual(tab.page, 0)
        w.close()


class TestPositionsAndAutostart(Base):
    def test_autostart_opens_where_user_stopped(self):
        RECENT.write_text(str(self.pdf1) + '\n', encoding='utf-8')
        w = self.window()
        tab = self.open(w, self.pdf1)
        tab.goto(6)
        pump(2)
        w.remember_position(tab)
        w.close()

        w2 = self.window()
        w2.open_last_recent()
        pump(5)
        self.assertEqual(w2.current_tab().doc.path, str(self.pdf1))
        self.assertEqual(w2.current_tab().page, 6)
        w2.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
