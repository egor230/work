#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты глобального ползунка документа.

Ползунок должен охватывать ВСЕ страницы документа: перетаскивание его
переводит на нужную страницу (и нужное место внутри неё), а не просто
прокручивает текущую страницу.

Запуск:
    xvfb-run -a -s "-screen 0 1400x900x24" python3 tests/test_docscroll.py
"""
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
TMP = Path(tempfile.mkdtemp(prefix='stdu-docscroll-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
m.RECENT_FILE = str(TMP / 'recent.txt')
UNCUGHT = []
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=10):
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 90), 'PAGE %d' % (i + 1), fontsize=22)
    d.save(str(path))
    d.close()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'docscroll.pdf'
        make_pdf(cls.pdf)
        cls.single = TMP / 'single.pdf'
        make_pdf(cls.single, pages=1)

    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        UNCUGHT.clear()
        self.w = m.MainWindow()
        pump(3)
        self.w.open_file(str(self.pdf))
        pump(5)
        self.tab = self.w.current_tab()
        self.tab.set_zoom(2.0)
        pump(3)

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    @property
    def bar(self):
        return self.tab.view.docbar


class TestDocScroll(Base):
    def test_docbar_is_visible_and_native_is_hidden(self):
        self.assertTrue(self.tab.view.docbar.isVisible())
        self.assertFalse(self.tab.view.verticalScrollBar().isVisible())

    def test_range_covers_every_page(self):
        n = self.tab.doc.page_count
        self.assertEqual(self.bar.minimum(), 0)
        self.assertEqual(self.bar.maximum(), n * m.PAGE_SCROLL_UNITS - 1)
        self.assertEqual(self.bar.pageStep(), m.PAGE_SCROLL_UNITS)

    def test_drag_to_middle_of_page(self):
        target_page = 4
        value = target_page * m.PAGE_SCROLL_UNITS + m.PAGE_SCROLL_UNITS // 2
        self.bar.setValue(value)
        pump(3)
        self.assertEqual(self.tab.page, target_page)
        native = self.tab.view._native_bar()
        self.assertGreater(native.value(), native.maximum() * 0.4)
        self.assertLess(native.value(), native.maximum() * 0.6)

    def test_drag_to_last_page(self):
        self.bar.setValue(self.bar.maximum())
        pump(3)
        self.assertEqual(self.tab.page, self.tab.doc.page_count - 1)

    def test_drag_to_second_page(self):
        self.bar.setValue(m.PAGE_SCROLL_UNITS + 10)
        pump(3)
        self.assertEqual(self.tab.page, 1)

    def test_goto_moves_docbar(self):
        self.tab.goto(7)
        pump(3)
        self.assertGreaterEqual(self.bar.value(), 7 * m.PAGE_SCROLL_UNITS)
        self.assertLess(self.bar.value(), 8 * m.PAGE_SCROLL_UNITS)

    def test_native_scroll_moves_docbar_within_page(self):
        start = self.bar.value()
        native = self.tab.view._native_bar()
        native.setValue(native.maximum())
        pump(3)
        self.assertGreater(self.bar.value(), start)
        self.assertLess(self.bar.value(), (self.tab.page + 1) * m.PAGE_SCROLL_UNITS)

    def test_groove_click_moves_one_page(self):
        self.tab.goto(2)
        pump(2)
        value = self.bar.value() + self.bar.pageStep()
        self.bar.setValue(value)
        pump(3)
        self.assertEqual(self.tab.page, 3)

    def test_works_with_continuous_disabled(self):
        self.w.toggle_continuous(False)
        self.bar.setValue(6 * m.PAGE_SCROLL_UNITS + 100)
        pump(3)
        self.assertEqual(self.tab.page, 6)

    def test_facing_mode_range_still_maps_pages(self):
        self.w.set_mode('facing')
        pump(3)
        self.assertEqual(self.bar.maximum(),
                         self.tab.doc.page_count * m.PAGE_SCROLL_UNITS - 1)
        self.bar.setValue(5 * m.PAGE_SCROLL_UNITS)
        pump(3)
        self.assertEqual(self.tab.page, 5)

    def test_rotation_keeps_mapping(self):
        self.tab.rotate(90)
        pump(3)
        self.bar.setValue(8 * m.PAGE_SCROLL_UNITS + 250)
        pump(3)
        self.assertEqual(self.tab.page, 8)

    def test_high_zoom_keeps_mapping(self):
        self.tab.set_zoom(4.0)
        pump(3)
        self.bar.setValue(3 * m.PAGE_SCROLL_UNITS + 900)
        pump(3)
        self.assertEqual(self.tab.page, 3)
        native = self.tab.view._native_bar()
        self.assertGreater(native.value(), native.maximum() * 0.8)

    def test_drag_cancels_smooth_scroll(self):
        native = self.tab.view._native_bar()
        self.tab.view._animate_scroll(native.maximum())
        pump(2)
        self.assertIsNotNone(self.tab.view._scroll_anim)
        self.bar.setValue(2 * m.PAGE_SCROLL_UNITS)
        pump(3)
        self.assertIsNone(self.tab.view._scroll_anim)

    def test_position_survives_docbar_drag(self):
        self.bar.setValue(5 * m.PAGE_SCROLL_UNITS + 300)
        pump(3)
        self.w.remember_position(self.tab)
        self.w.close()

        w2 = m.MainWindow()
        pump(3)
        w2.open_file(str(self.pdf))
        pump(5)
        tab2 = w2.current_tab()
        self.assertEqual(tab2.page, 5)
        self.assertGreaterEqual(tab2.view.docbar.value(),
                                5 * m.PAGE_SCROLL_UNITS)
        w2.close()


class TestSinglePage(Base):
    def test_single_page_document(self):
        self.w.open_file(str(self.single))
        pump(4)
        tab = self.w.current_tab()
        self.assertEqual(tab.doc.page_count, 1)
        self.assertEqual(tab.view.docbar.maximum(), m.PAGE_SCROLL_UNITS - 1)
        tab.view.docbar.setValue(tab.view.docbar.maximum())
        pump(3)
        self.assertEqual(tab.page, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
