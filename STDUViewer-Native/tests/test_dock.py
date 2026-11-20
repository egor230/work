#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты ширины и кнопок скрытия левой панели."""
import importlib.util
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QMessageBox, QToolButton

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-dock-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
UNCUGHT = []
m.QMessageBox.information = staticmethod(lambda *a, **k: None)
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=3):
    for _ in range(n):
        app.processEvents()


class TestDockPanel(unittest.TestCase):
    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        UNCUGHT.clear()
        self.w = m.MainWindow()
        pump(3)

    def tearDown(self):
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    def test_minimum_width_is_small(self):
        self.assertEqual(self.w.nav_dock.minimumWidth(), 170)
        self.assertLess(self.w.nav_dock.minimumWidth(), 330)

    def test_hide_button_exists(self):
        self.assertIsInstance(self.w._nav_hide_button, QToolButton)
        self.assertEqual(self.w._nav_hide_button.text(), '×')

    def test_hide_button_hides_panel(self):
        self.assertTrue(self.w.nav_dock.isVisible())
        self.w._nav_hide_button.click()
        pump(2)
        self.assertFalse(self.w.nav_dock.isVisible())

    def test_toolbar_toggle_action(self):
        self.assertIsNotNone(self.w._panel_action)
        self.assertEqual(self.w._panel_action.shortcut(), QKeySequence('F6'))
        self.assertTrue(self.w._panel_action.isChecked())
        toolbars = self.w.findChildren(m.QToolBar)
        self.assertTrue(any(self.w._panel_action in tb.actions() for tb in toolbars))

    def test_menu_check_state_follows_visibility(self):
        self.w.toggle_nav()
        pump(2)
        self.assertFalse(self.w._panel_action.isChecked())
        self.w.toggle_nav()
        pump(2)
        self.assertTrue(self.w._panel_action.isChecked())

    def test_visibility_signal_updates_action(self):
        self.w.nav_dock.setVisible(False)
        pump(2)
        self.assertFalse(self.w._panel_action.isChecked())
        self.w.nav_dock.setVisible(True)
        pump(2)
        self.assertTrue(self.w._panel_action.isChecked())


if __name__ == '__main__':
    unittest.main(verbosity=2)
