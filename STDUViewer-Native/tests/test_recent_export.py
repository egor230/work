#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты очистки недавних документов и экспорта в Markdown / DOCX."""
import importlib.util
import sys
import tempfile
import traceback
import unittest
import zipfile
from pathlib import Path

import pymupdf
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-export-'))
m.POSITIONS_FILE = str(TMP / 'positions.json')
UNCUGHT = []
SAVE = {'path': ''}

m.QMessageBox.information = staticmethod(lambda *a, **k: None)
m.QMessageBox.warning = staticmethod(lambda *a, **k: None)


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook


def pump(n=3):
    for _ in range(n):
        app.processEvents()


def make_pdf(path):
    d = pymupdf.open()
    for i in range(2):
        p = d.new_page(width=595, height=842)
        p.insert_text((72, 90), 'EXPORT TEST PAGE %d' % (i + 1), fontsize=20)
    d.save(str(path))
    d.close()


def fake_save(*a, **k):
    return SAVE['path'], ''


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'export.pdf'
        make_pdf(cls.pdf)

    def setUp(self):
        Path(m.POSITIONS_FILE).unlink(missing_ok=True)
        UNCUGHT.clear()
        SAVE['path'] = ''
        m.QFileDialog.getSaveFileName = staticmethod(fake_save)
        self.w = m.MainWindow()
        pump(2)
        self.w.open_file(str(self.pdf))
        pump(4)

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))


class TestRecentActions(Base):
    def test_clear_recent(self):
        self.assertTrue(self.w.recent)
        self.w.clear_recent()
        pump(2)
        self.assertEqual(self.w.recent, [])
        self.assertEqual(self.w.recent_list.count(), 0)
        with open(m.RECENT_FILE, encoding='utf-8') as fh:
            content = fh.read()
        self.assertEqual(content, '')

    def test_remove_one_recent(self):
        other = TMP / 'other.pdf'
        make_pdf(other)
        self.w.open_file(str(other))
        pump(3)
        before = len(self.w.recent)
        self.w.remove_recent(str(other))
        pump(2)
        self.assertEqual(len(self.w.recent), before - 1)
        self.assertNotIn(str(other), self.w.recent)

    def test_recent_menu_has_clear_action(self):
        texts = [a.text() for a in self.w.recent_menu.actions()]
        self.assertIn('Очистить список', texts)

    def test_context_menu_policy(self):
        from PyQt5.QtCore import Qt
        self.assertEqual(self.w.recent_list.contextMenuPolicy(),
                         Qt.CustomContextMenu)


class TestExportMarkdown(Base):
    def test_export_markdown_creates_file(self):
        out = TMP / 'result.md'
        SAVE['path'] = str(out)
        self.w.export_markdown()
        pump(2)
        self.assertTrue(out.exists())
        text = out.read_text(encoding='utf-8')
        self.assertIn('EXPORT TEST PAGE 1', text)
        self.assertIn('EXPORT TEST PAGE 2', text)

    def test_markdown_has_page_headings(self):
        out = TMP / 'headings.md'
        SAVE['path'] = str(out)
        self.w.export_markdown()
        pump(2)
        text = out.read_text(encoding='utf-8')
        self.assertIn('Страница 1', text)

    def test_export_markdown_flow_document(self):
        txt = TMP / 'story.txt'
        txt.write_text('Первая строка故事\nВторая строка', encoding='utf-8')
        self.w.open_file(str(txt))
        pump(5)
        tab = self.w.current_tab()
        self.assertEqual(tab.doc.kind, 'flow')
        out = TMP / 'story.md'
        SAVE['path'] = str(out)
        self.w.export_markdown()
        pump(2)
        self.assertTrue(out.exists())
        self.assertIn('Первая строка', out.read_text(encoding='utf-8'))


class TestExportDocx(Base):
    def test_export_docx_creates_valid_file(self):
        out = TMP / 'result.docx'
        SAVE['path'] = str(out)
        self.w.export_docx()
        pump(2)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)
        with zipfile.ZipFile(out) as z:
            self.assertIn('word/document.xml', z.namelist())
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
            self.assertIn('EXPORT TEST PAGE 1', xml)

    def test_fallback_docx_without_pandoc(self):
        out = TMP / 'fallback.docx'
        SAVE['path'] = str(out)
        old_which = m.shutil.which

        def no_pandoc(name):
            return None if name == 'pandoc' else old_which(name)

        m.shutil.which = no_pandoc
        try:
            self.w.export_docx()
            pump(2)
        finally:
            m.shutil.which = old_which
        self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
            self.assertIn('EXPORT TEST PAGE 1', xml)


if __name__ == '__main__':
    unittest.main(verbosity=2)
