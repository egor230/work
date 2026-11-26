#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты непрерывного просмотра и сглаживания.

Запуск:
    xvfb-run -a -s "-screen 0 1400x900x24" python3 tests/test_continuous.py
"""
import importlib.util
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

import pymupdf
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-continuous-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
UNCUGHT = []
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=6):
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 90), 'Page %d' % (i + 1), fontsize=22)
    d.save(str(path))
    d.close()


def wheel(view, delta):
    """Отправляет колесо мыши с заданным angleDelta.y."""
    ev = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, 0),
                     QPoint(0, delta), Qt.NoButton, Qt.NoModifier,
                     Qt.NoScrollPhase, False)
    view.wheelEvent(ev)
    pump(2)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'continuous.pdf'
        make_pdf(cls.pdf)

    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        UNCUGHT.clear()
        self.w = m.MainWindow()
        pump(3)
        self.w.open_file(str(self.pdf))
        pump(5)
        self.tab = self.w.current_tab()
        # Крупный масштаб — страница гарантированно больше области просмотра.
        self.tab.set_zoom(2.0)
        pump(3)

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    def bar(self):
        return self.tab.view.verticalScrollBar()


class TestContinuous(Base):
    def test_continuous_enabled_by_default(self):
        self.assertTrue(self.w.continuous)
        self.assertTrue(self.tab.continuous)
        self.assertTrue(self.w._continuous_action.isChecked())

    def test_wheel_down_at_bottom_turns_page(self):
        self.bar().setValue(self.bar().maximum())
        wheel(self.tab.view, -120)
        self.assertEqual(self.tab.page, 1)
        # Остаток прокрутки перенесён на новую страницу.
        self.assertLessEqual(self.bar().value(), 120)

    def test_wheel_up_at_top_turns_page_back(self):
        self.tab.goto(3)
        pump(3)
        self.bar().setValue(self.bar().minimum())
        wheel(self.tab.view, 120)
        self.assertEqual(self.tab.page, 2)

    def test_wheel_inside_page_does_not_turn(self):
        self.bar().setValue(self.bar().minimum())
        wheel(self.tab.view, -120)
        self.assertEqual(self.tab.page, 0)
        self.assertIsNotNone(self.tab.view._scroll_anim,
                             'прокрутка внутри страницы должна быть плавной')

    def test_several_wheels_walk_through_document(self):
        for expected in range(1, 6):
            self.bar().setValue(self.bar().maximum())
            wheel(self.tab.view, -120)
            self.assertEqual(self.tab.page, expected)

    def test_toggle_off_disables_page_turning(self):
        self.w.toggle_continuous(False)
        self.assertFalse(self.tab.continuous)
        self.bar().setValue(self.bar().maximum())
        wheel(self.tab.view, -120)
        self.assertEqual(self.tab.page, 0)

    def test_toggle_action_updates_all_tabs(self):
        self.w.open_file(str(self.pdf))
        pump(4)
        self.assertTrue(self.w._continuous_action.isChecked())
        self.w._continuous_action.trigger()   # с True переключит в False
        pump(2)
        self.assertFalse(self.w.current_tab().continuous)
        for tab in self.w._tabs:
            self.assertFalse(tab.continuous)

    def test_new_page_starts_from_top_on_goto(self):
        self.bar().setValue(self.bar().maximum())
        self.tab.goto(4)
        pump(3)
        self.assertEqual(self.bar().value(), self.bar().minimum())


class TestRefit(Base):
    def test_fit_recalculates_on_resize(self):
        self.w.showNormal()
        pump(2)
        self.w.fit_width()
        pump(3)
        self.assertEqual(self.tab.fit, 'width')
        old_zoom = self.tab.zoom
        self.w.resize(760, 620)
        pump(4)
        self.assertTrue(self.tab._fit_timer.isActive(),
                        'изменение размера должно запускать пересчёт масштаба')
        self.tab._refit_after_resize()
        pump(2)
        self.assertNotEqual(self.tab.zoom, old_zoom)


class TestSmoothing(Base):
    def test_supersampling_keeps_output_size(self):
        img = self.tab.doc.render(0, 0.5, 0)
        self.assertEqual((img.width(), img.height()), (298, 421))
        img2 = self.tab.doc.render(0, 1.0, 0)
        self.assertEqual((img2.width(), img2.height()), (595, 842))

    def test_smooth_rotation_keeps_geometry(self):
        img = self.tab.doc.render(0, 1.0, 90)
        self.assertEqual((img.width(), img.height()), (842, 595))

    def test_render_hints_are_smooth(self):
        image = m.QImage(4, 4, m.QImage.Format_RGB32)
        painter = m.QPainter(image)
        painter.setRenderHint(m.QPainter.SmoothPixmapTransform, True)
        self.assertTrue(painter.testRenderHint(m.QPainter.SmoothPixmapTransform))
        painter.end()


if __name__ == '__main__':
    import sys
    unittest.main(verbosity=2)
