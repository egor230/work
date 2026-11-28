#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты плавной (без рывков) прокрутки колесом мыши.

Запуск:
    xvfb-run -a -s "-screen 0 1400x900x24" python3 tests/test_smooth.py
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
TMP = Path(tempfile.mkdtemp(prefix='stdu-smooth-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
m.RECENT_FILE = str(TMP / 'recent.txt')
UNCUGHT = []
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=3):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=8):
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=595, height=842)
        for j in range(45):
            p.insert_text((72, 55 + 17 * j),
                          'Page %d line %d — текст для прокрутки' % (i + 1, j),
                          fontsize=10)
    d.save(str(path))
    d.close()


def wheel_event(dy, pixel=False):
    if pixel:
        return QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, dy),
                           QPoint(0, 0), Qt.NoButton, Qt.NoModifier,
                           Qt.NoScrollPhase, False)
    return QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, 0),
                       QPoint(0, dy), Qt.NoButton, Qt.NoModifier,
                       Qt.NoScrollPhase, False)


def ticks(view, limit=100, collect=False):
    """Прокрутить до остановки; при collect — вернуть шаги за каждый тик."""
    steps = []
    for _ in range(limit):
        if not view._scroll_timer.isActive():
            break
        before = view._native_bar().value()
        page_before = view.tab.page
        view._scroll_tick()
        if collect:
            steps.append((view._native_bar().value() - before,
                          view.tab.page != page_before))
    pump(2)
    return steps


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'smooth.pdf'
        make_pdf(cls.pdf)

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
        self.view = self.tab.view
        self.bar = self.view._native_bar()

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))


class TestAccumulation(Base):
    def test_fast_wheels_accumulate_instead_of_restarting(self):
        for _ in range(4):
            self.view.wheelEvent(wheel_event(-120))
        self.assertGreater(self.view._scroll_target, 400)
        ticks(self.view)
        self.assertGreater(self.bar.value(), 400)
        self.assertEqual(self.tab.page, 0)

    def test_motion_has_no_large_jumps(self):
        for _ in range(3):
            self.view.wheelEvent(wheel_event(-120))
        steps = ticks(self.view, collect=True)
        moves = [abs(s[0]) for s in steps if abs(s[0]) > 0]
        self.assertGreater(len(moves), 4)
        self.assertLess(max(moves), 120, 'за один тик страница не должна прыгать')
        # Первый и последний шаги маленькие (разгон/торможение) — их не считаем.
        middle = [x for x in moves if x >= 5]
        self.assertLess(max(middle) / max(1, min(middle)), 12)

    def test_wheel_direction_reverses_target(self):
        self.view.wheelEvent(wheel_event(-120))
        first = self.view._scroll_target
        self.view.wheelEvent(wheel_event(60))
        self.assertLess(self.view._scroll_target, first)
        ticks(self.view)

    def test_trackpad_pixel_delta_is_used(self):
        self.view.wheelEvent(wheel_event(-24, pixel=True))
        self.assertEqual(self.view._scroll_target, 24)
        ticks(self.view)


class TestPageTransitions(Base):
    def test_down_transition_stitches_pages_and_keeps_offset(self):
        self.bar.setValue(self.bar.maximum())
        self.view.wheelEvent(wheel_event(-120))
        self.view._scroll_tick()
        self.assertIsNotNone(self.view._transition,
                             'на границе нужно сшить две страницы, а не подменить')
        self.assertEqual(len(self.tab._pages), 2)
        steps = ticks(self.view, collect=True)
        self.assertEqual(self.tab.page, 1)
        self.assertLessEqual(self.bar.value(), 120)
        changed = [s for s in steps if s[1]]
        self.assertEqual(len(changed), 1,
                           'за один переход страница меняется ровно один раз')

    def test_up_transition_returns_to_previous_page(self):
        self.tab.goto(3)
        pump(2)
        self.bar.setValue(self.bar.minimum())
        self.view.wheelEvent(wheel_event(120))
        self.view._scroll_tick()
        self.assertIsNotNone(self.view._transition)
        ticks(self.view)
        self.assertEqual(self.tab.page, 2)
        self.assertGreater(self.bar.value(), self.bar.maximum() - 160)

    def test_reverse_cancels_stitched_canvas(self):
        self.bar.setValue(self.bar.maximum())
        self.view.wheelEvent(wheel_event(-120))
        self.view._scroll_tick()
        self.assertIsNotNone(self.view._transition)
        self.view.wheelEvent(wheel_event(240))
        ticks(self.view)
        self.assertIsNone(self.view._transition)
        self.assertEqual(self.tab.page, 0)
        self.assertEqual(len(self.tab._pages), 1)

    def test_several_pages_in_one_spin(self):
        self.bar.setValue(self.bar.maximum())
        for _ in range(4):
            self.view.wheelEvent(wheel_event(-120))
        ticks(self.view)
        self.assertEqual(self.tab.page, 1)
        self.assertIsNone(self.view._transition)
        self.assertLess(self.bar.value(), self.bar.maximum())

    def test_facing_mode_turns_one_spread(self):
        self.w.set_mode('facing')
        pump(3)
        self.bar.setValue(self.bar.maximum())
        self.view.wheelEvent(wheel_event(-120))
        ticks(self.view)
        self.assertEqual(self.tab.page, 2)
        self.assertIsNone(self.view._transition)
        self.assertEqual(self.tab._pages_to_show(), [2, 3])

    def test_continuous_disabled_never_stitches(self):
        self.w.toggle_continuous(False)
        self.bar.setValue(self.bar.maximum())
        self.view.wheelEvent(wheel_event(-120))
        ticks(self.view)
        self.assertEqual(self.tab.page, 0)
        self.assertIsNone(self.view._transition)

    def test_neighbor_pages_are_cached(self):
        self.tab._prefetch_timer.stop()
        calls = []
        original = self.tab.doc.render

        def counted(index, zoom, rotation):
            calls.append(index)
            return original(index, zoom, rotation)

        self.tab.doc.render = counted
        try:
            self.tab.make_transition(1)
            n = len(calls)
            self.tab.make_transition(1)
            self.assertEqual(len(calls), n,
                             'соседняя страница не должна перерисовываться')
        finally:
            self.tab.doc.render = original


if __name__ == '__main__':
    unittest.main(verbosity=2)
