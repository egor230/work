#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты автоматического открытия последнего документа при запуске."""
import importlib.util
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

import pymupdf
from PyQt5.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-autostart-'))
UNCUGHT = []
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)
m.QMessageBox.information = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=3):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=2):
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 90), 'AUTO %d' % (i + 1), fontsize=20)
    d.save(str(path))
    d.close()


class Base(unittest.TestCase):
    def setUp(self):
        UNCUGHT.clear()
        self.old_recent_file = m.RECENT_FILE
        m.RECENT_FILE = str(TMP / 'recent.txt')
        self.pdf1 = TMP / 'first.pdf'
        self.pdf2 = TMP / 'last.pdf'
        make_pdf(self.pdf1)
        make_pdf(self.pdf2)

    def tearDown(self):
        m.RECENT_FILE = self.old_recent_file
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))

    def write_recent(self, paths):
        Path(m.RECENT_FILE).write_text('\n'.join(paths), encoding='utf-8')

    def new_window(self):
        w = m.MainWindow()
        pump(3)
        return w


class TestOpenLastRecent(Base):
    def test_opens_last_pdf(self):
        self.write_recent([str(self.pdf1)])
        w = self.new_window()
        target = w.open_last_recent()
        pump(5)
        self.assertEqual(target, str(self.pdf1))
        self.assertEqual(w.current_tab().doc.path, str(self.pdf1))
        w.close()

    def test_prefers_pdf_over_other_recent_files(self):
        txt = TMP / 'notes.txt'
        txt.write_text('hello', encoding='utf-8')
        self.write_recent([str(txt), str(self.pdf1), str(self.pdf2)])
        w = self.new_window()
        target = w.open_last_recent()
        pump(5)
        self.assertEqual(target, str(self.pdf1))
        self.assertEqual(w.current_tab().doc.path, str(self.pdf1))
        w.close()

    def test_missing_files_are_skipped(self):
        self.write_recent([str(TMP / 'gone.pdf'), str(self.pdf2)])
        w = self.new_window()
        target = w.open_last_recent()
        pump(5)
        self.assertEqual(target, str(self.pdf2))
        w.close()

    def test_no_recent_returns_none(self):
        self.write_recent([])
        w = self.new_window()
        self.assertIsNone(w.open_last_recent())
        self.assertEqual(w.tabs.count(), 0)
        w.close()


class TestMainPrecedence(Base):
    def run_main(self, argv):
        calls = []

        class FakeApp:
            def __init__(self, a):
                pass

            def setApplicationName(self, *a):
                pass

            def setWindowIcon(self, *a):
                pass

            def setStyle(self, *a):
                pass

            def exec_(self):
                return 0

        class FakeWindow:
            def __init__(self):
                pass

            def open_file(self, p):
                calls.append(('file', p))

            def open_last_recent(self):
                calls.append(('recent',))
                return None

        old_app, old_win, old_argv = m.QApplication, m.MainWindow, sys.argv
        m.QApplication, m.MainWindow, sys.argv = FakeApp, FakeWindow, argv
        try:
            with self.assertRaises(SystemExit):
                m.main()
        finally:
            m.QApplication, m.MainWindow, sys.argv = old_app, old_win, old_argv
        return calls

    def test_argument_disables_autostart(self):
        calls = self.run_main(['prog', str(self.pdf2)])
        self.assertIn(('file', str(self.pdf2)), calls)
        self.assertNotIn(('recent',), calls)

    def test_no_argument_opens_last_recent(self):
        calls = self.run_main(['prog'])
        self.assertIn(('recent',), calls)
        self.assertNotIn(('file', str(self.pdf2)), calls)


if __name__ == '__main__':
    unittest.main(verbosity=2)
