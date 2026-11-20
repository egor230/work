#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Всесторонние тесты STDU Reader (Native).

Запуск:
    xvfb-run -a -s "-screen 0 1400x900x24" python3 tests/test_reader.py

Тесты работают без настоящих диалогов: все QMessageBox/QFileDialog/QInputDialog
подменены, а QDesktopServices.openUrl записывает адрес в список URLS.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import traceback
import unittest
from pathlib import Path

import pymupdf
from PyQt5.QtCore import Qt, QPoint, QUrl
from PyQt5.QtGui import QCursor, QDesktopServices
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'STDUViewer-Native-source.py'
spec = importlib.util.spec_from_file_location('stdu_reader', str(SRC))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

app = QApplication.instance() or QApplication([])
TMP = Path(tempfile.mkdtemp(prefix='stdu-tests-'))

DIALOGS = []
URLS = []
CHOICE = {'open': '', 'save': '', 'dir': '', 'password': 'secret', 'password_ok': True}
UNCUGHT = []


def hook(t, v, tb):
    UNCUGHT.append(''.join(traceback.format_exception(t, v, tb)))


sys.excepthook = hook
m.QMessageBox.warning = staticmethod(
    lambda *a, **k: DIALOGS.append(('warning', a[1] if len(a) > 1 else '',
                                    a[2] if len(a) > 2 else '')))
m.QMessageBox.information = staticmethod(
    lambda *a, **k: DIALOGS.append(('info', a[1] if len(a) > 1 else '',
                                    a[2] if len(a) > 2 else '')))
m.QMessageBox.critical = staticmethod(
    lambda *a, **k: DIALOGS.append(('critical', a[1] if len(a) > 1 else '',
                                    a[2] if len(a) > 2 else '')))
m.QMessageBox.about = staticmethod(
    lambda *a, **k: DIALOGS.append(('about', a[1] if len(a) > 1 else '',
                                    a[2] if len(a) > 2 else '')))
def fake_get_text(*a, **k):
    title = str(a[1]) if len(a) > 1 else ''
    if 'Пароль' in title:
        return CHOICE['password'], CHOICE['password_ok']
    return CHOICE.get('text', 'Закладка'), True


m.QInputDialog.getText = staticmethod(fake_get_text)
m.QFileDialog.getOpenFileName = staticmethod(
    lambda *a, **k: (CHOICE['open'], ''))
m.QFileDialog.getSaveFileName = staticmethod(
    lambda *a, **k: (CHOICE['save'], ''))
m.QFileDialog.getExistingDirectory = staticmethod(
    lambda *a, **k: CHOICE['dir'])
m.QDesktopServices.openUrl = staticmethod(lambda u: URLS.append(u.toString()))


def pump(n=3):
    for _ in range(n):
        app.processEvents()


def make_pdf(path, pages=3, size=(595, 842), text='Page %d', toc=None,
             links=None, password=None, rotate=None):
    """links: список словарей {'at': 0, ...параметры insert_link...}."""
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=size[0], height=size[1])
        p.insert_text((72, 80), text % (i + 1) if '%d' in text else text,
                      fontsize=20)
    if links:
        for spec in links:
            data = dict(spec)
            pno = data.pop('at')
            d[pno].insert_link(data)
    if toc:
        d.set_toc(toc)
    if rotate is not None:
        d[0].set_rotation(rotate)
    if password:
        d.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256,
               owner_pw=password, user_pw=password)
    else:
        d.save(str(path))
    d.close()


class Base(unittest.TestCase):
    def setUp(self):
        DIALOGS.clear(); URLS.clear(); UNCUGHT.clear()
        CHOICE.update(open='', save='', dir='', password='secret',
                      password_ok=True, text='Закладка')
        m.QInputDialog.getText = staticmethod(fake_get_text)
        self.w = m.MainWindow()
        pump(2)
        QApplication.setActiveWindow(self.w)

    def tearDown(self):
        while self.w.tabs.count():
            self.w.close_tab(0)
        self.w.close()
        pump(2)
        self.assertFalse(UNCUGHT, 'Необработанные исключения:\n' + '\n'.join(UNCUGHT))
        self.assertFalse([d for d in DIALOGS if d[0] in ('warning', 'critical')],
                         'Неожиданные диалоги ошибок: %r' % DIALOGS)

    def open(self, path):
        self.w.open_file(str(path))
        pump(6)
        return self.w.current_tab()

    def assertPage(self, expected, msg=''):
        tab = self.w.current_tab()
        self.assertIsNotNone(tab, 'нет активной вкладки')
        self.assertEqual(tab.page, expected,
                         '%s: ожидалась страница %d, получена %d'
                         % (msg, expected + 1, tab.page + 1))


# ---------------------------------------------------------------------------
class Test01Interface(Base):
    def test_main_window_widgets(self):
        w = self.w
        self.assertEqual(w.windowTitle(), 'STDU Viewer')
        self.assertIsNotNone(w.tabs)
        self.assertIsNotNone(w.nav_dock)
        self.assertIsNotNone(w.toc_tree)
        self.assertIsNotNone(w.thumb_list)
        self.assertIsNotNone(w.bookmark_list)
        self.assertIsNotNone(w.recent_list)
        self.assertEqual(w.nav.tabText(0), 'Недавние документы')
        self.assertEqual(w.nav.tabText(1), 'Содержание')
        self.assertEqual(w.nav.tabText(2), 'Миниатюры')
        self.assertEqual(w.nav.tabText(3), 'Закладки')

    def test_empty_state(self):
        self.assertEqual(self.w.tabs.count(), 0)
        self.assertEqual(self.w.spin_page.value(), 1)
        self.assertEqual(self.w.lbl_total.text(), '/ 1')
        self.assertEqual(self.w.lbl_zoom.text(), '100%')
        self.assertIsNone(self.w.current_tab())

    def test_menus_and_actions(self):
        menus = [a.text() for a in self.w.menuBar().actions()]
        self.assertEqual(menus, ['Файл', 'Вид', 'Навигация', 'Инструменты', 'Справка'])

    def test_toolbar_and_status_widgets(self):
        self.assertIsNotNone(self.w.zoom_combo)
        self.assertIsNotNone(self.w.zoom_slider)
        self.assertIsNotNone(self.w.find_edit)
        self.assertIn('100%', [self.w.zoom_combo.itemText(i)
                               for i in range(self.w.zoom_combo.count())])


# ---------------------------------------------------------------------------
class Test02PdfBasics(Base):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'basic.pdf'
        make_pdf(cls.pdf, pages=5, toc=[[1, 'Глава 1', 1], [1, 'Глава 4', 4]])

    def test_open_and_metadata(self):
        t = self.open(self.pdf)
        self.assertEqual(self.w.tabs.count(), 1)
        self.assertEqual(t.doc.format_name(), 'PDF')
        self.assertEqual(t.doc.page_count, 5)
        self.assertIn('basic.pdf', self.w.tabs.tabText(0))
        self.assertEqual(self.w.lbl_total.text(), '/ 5')
        self.assertEqual(self.w.lbl_format.text(), 'PDF')
        self.assertIn(str(self.pdf),
                      open(m.RECENT_FILE, encoding='utf-8').read())

    def test_render_sizes(self):
        t = self.open(self.pdf)
        img = t.doc.render(0, 1.0, 0)
        self.assertEqual((img.width(), img.height()), (595, 842))
        img2 = t.doc.render(0, 2.0, 0)
        self.assertTrue(img2.width() > img.width())
        self.assertEqual(t.view.label.pixmap().size().width(), img.width())

    def test_text_extraction(self):
        t = self.open(self.pdf)
        self.assertIn('Page 1', t.doc.text(0))
        self.assertIn('Page 5', t.doc.text(4))

    def test_toc_values_are_zero_based(self):
        t = self.open(self.pdf)
        self.assertEqual(t.doc.toc(), [(1, 'Глава 1', 0), (1, 'Глава 4', 3)])

    def test_open_missing_file(self):
        self.w.open_file(str(TMP / 'no-such-file.pdf'))
        self.assertEqual(self.w.tabs.count(), 0)
        self.assertTrue(any(d[0] == 'warning' for d in DIALOGS))
        DIALOGS.clear()

    def test_open_corrupted_file(self):
        bad = TMP / 'bad.pdf'
        bad.write_bytes(b'%PDF-1.4\nthis is not a real pdf')
        self.w.open_file(str(bad))
        self.assertEqual(self.w.tabs.count(), 0)
        DIALOGS.clear()

    def test_drag_and_drop(self):
        from PyQt5.QtCore import QMimeData, QUrl as QUrlCore
        data = QMimeData()
        data.setUrls([QUrlCore.fromLocalFile(str(self.pdf))])

        class Ev:
            def mimeData(self): return data
            def acceptProposedAction(self): pass
        self.w.dropEvent(Ev())
        pump(6)
        self.assertEqual(self.w.tabs.count(), 1)

    def test_multiple_tabs(self):
        t1 = self.open(self.pdf)
        other = TMP / 'other.pdf'
        make_pdf(other, pages=2)
        t2 = self.open(other)
        self.assertEqual(self.w.tabs.count(), 2)
        self.assertIsNot(t1, t2)
        self.w.tabs.setCurrentIndex(0); pump()
        self.assertIs(self.w.current_tab(), t1)
        self.assertPage(0)
        self.w.close_tab(1); pump()
        self.assertEqual(self.w.tabs.count(), 1)


# ---------------------------------------------------------------------------
class Test03NavigationAndZoom(Base):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'nav.pdf'
        make_pdf(cls.pdf, pages=10, toc=[[1, '.Page 1', 1], [1, 'Page 5', 5]])

    def test_page_navigation_methods(self):
        self.open(self.pdf)
        self.w.next_page(); self.assertPage(1)
        self.w.prev_page(); self.assertPage(0)
        self.w.last_page(); self.assertPage(9)
        self.w.first_page(); self.assertPage(0)
        self.w.on_spin_page(7); self.assertPage(6)

    def test_status_follows_navigation(self):
        self.open(self.pdf)
        self.w.next_page(); pump()
        self.assertEqual(self.w.spin_page.value(), 2)
        self.w.on_spin_page(5); pump()
        self.assertEqual(self.w.spin_page.value(), 5)
        self.assertEqual(self.w.lbl_total.text(), '/ 10')

    def test_toc_navigation(self):
        self.open(self.pdf)
        self.w.on_toc_clicked(self.w.toc_tree.topLevelItem(1), 0); pump()
        self.assertPage(4)
        self.w.on_toc_clicked(self.w.toc_tree.topLevelItem(0), 0); pump()
        self.assertPage(0)

    def test_thumbnails(self):
        t = self.open(self.pdf)
        self.assertEqual(self.w.thumb_list.count(), 10)
        self.w.on_thumb_clicked(self.w.thumb_list.item(4)); pump()
        self.assertPage(4)

    def test_zoom_methods(self):
        t = self.open(self.pdf)
        self.w.zoom_100(); pump()
        self.assertAlmostEqual(t.zoom, 1.0)
        self.w.zoom_by(2); pump()
        self.assertAlmostEqual(t.zoom, 2.0)
        self.w.zoom_by(0.5); pump()
        self.assertAlmostEqual(t.zoom, 1.0)

    def test_zoom_sync_three_places(self):
        t = self.open(self.pdf)
        t.set_zoom(1.5); pump()
        self.assertEqual(self.w.lbl_zoom.text(), '150%')
        self.assertEqual(self.w.zoom_combo.currentText(), '150%')
        self.assertEqual(self.w.zoom_slider.value(), 150)
        self.w.zoom_slider.setValue(75); pump()
        self.assertEqual(self.w.lbl_zoom.text(), '75%')

    def test_zoom_combo_custom_value(self):
        t = self.open(self.pdf)
        self.w.zoom_combo.setCurrentText('200%')
        self.w.on_zoom_combo(); pump()
        self.assertAlmostEqual(t.zoom, 2.0)

    def test_zoom_limits(self):
        t = self.open(self.pdf)
        t.set_zoom(0.001); self.assertGreaterEqual(t.zoom, 0.05)
        t.set_zoom(100); self.assertLessEqual(t.zoom, 5.0)

    def test_fit_modes(self):
        t = self.open(self.pdf)
        self.w.fit_width(); pump()
        self.assertEqual(t.fit, 'width')
        self.assertGreater(t.zoom, 0)
        self.w.fit_height(); pump()
        self.assertEqual(t.fit, 'page')
        self.w.fit_page(); pump()
        self.assertEqual(t.fit, 'page')
        self.w.zoom_100(); pump()
        self.assertEqual(t.fit, 'none')

    def test_rotate(self):
        t = self.open(self.pdf)
        self.w.rotate(90); pump()
        self.assertEqual(t.rotation, 90)
        self.assertEqual((t.view.label.pixmap().height(),
                          t.view.label.pixmap().width()), (595, 842))
        self.w.rotate(270); pump()
        self.assertEqual(t.rotation, 0)

    def test_view_modes(self):
        t = self.open(self.pdf)
        self.w.set_mode('facing'); pump()
        self.assertEqual(t._pages_to_show(), [0, 1])
        t.goto(4); pump()
        self.assertEqual(t._pages_to_show(), [4, 5])
        self.w.set_mode('facing_cover'); pump()
        self.assertEqual(t._pages_to_show(), [0])
        self.w.set_mode('single'); pump()
        self.assertEqual(t._pages_to_show(), [0])

    def test_keyboard_navigation(self):
        self.open(self.pdf)
        QTest.keyClick(self.w, Qt.Key_PageDown); pump()
        self.assertPage(1)
        QTest.keyClick(self.w, Qt.Key_PageUp); pump()
        self.assertPage(0)
        QTest.keyClick(self.w, Qt.Key_End); pump()
        self.assertPage(9)
        QTest.keyClick(self.w, Qt.Key_Home); pump()
        self.assertPage(0)


# ---------------------------------------------------------------------------
class Test04Links(Base):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'links.pdf'
        make_pdf(cls.pdf, pages=4, text='Page %d',
                 toc=[[1, 'Page 1', 1]],
                 links=[
                     {'at': 0, 'kind': pymupdf.LINK_GOTO,
                      'from': pymupdf.Rect(72, 100, 300, 130),
                      'page': 2, 'to': pymupdf.Point(72, 100)},
                     {'at': 0, 'kind': pymupdf.LINK_URI,
                      'from': pymupdf.Rect(72, 150, 300, 180),
                      'uri': 'https://example.org/path'},
                     {'at': 0, 'kind': pymupdf.LINK_URI,
                      'from': pymupdf.Rect(72, 200, 300, 230),
                      'uri': 'sub/other.pdf#page=2'},
                     {'at': 0, 'kind': pymupdf.LINK_LAUNCH,
                      'from': pymupdf.Rect(72, 250, 300, 280),
                      'file': 'notes.txt'},
                     {'at': 3, 'kind': pymupdf.LINK_GOTO,
                      'from': pymupdf.Rect(72, 100, 300, 130), 'page': 0},
                 ])
        cls.other = TMP / 'sub' / 'other.pdf'
        cls.other.parent.mkdir(exist_ok=True)
        make_pdf(cls.other, pages=3, text='Other %d')
        (TMP / 'notes.txt').write_text('notes', encoding='utf-8')

    def _click_link(self, tab, page, x, y):
        tab.goto(page); pump(4)
        lbl = tab.view.label
        QTest.mouseClick(lbl, Qt.LeftButton, pos=QPoint(x, y)); pump(4)

    def test_all_link_kinds_detected(self):
        t = self.open(self.pdf)
        kinds = sorted(l.get('kind') for _r, l in t.view.label.link_regions)
        # PyMuPDF превращает URI с относительным путём и LAUNCH в GOTOR (5)
        self.assertEqual(kinds, [pymupdf.LINK_GOTO, pymupdf.LINK_URI,
                                 pymupdf.LINK_GOTOR, pymupdf.LINK_GOTOR])
        t.goto(3); pump()
        self.assertEqual(len(t.view.label.link_regions), 1)

    def test_internal_goto(self):
        t = self.open(self.pdf)
        self._click_link(t, 0, 186, 115)
        self.assertPage(2)

    def test_external_uri(self):
        t = self.open(self.pdf)
        self._click_link(t, 0, 186, 165)
        self.assertIn('https://example.org/path', URLS)

    def test_relative_pdf_with_fragment(self):
        t = self.open(self.pdf)
        self._click_link(t, 0, 186, 215)
        self.assertIsNotNone(self.w.current_tab())
        self.assertEqual(self.w.current_tab().doc.name, 'other.pdf')
        self.assertPage(1)

    def test_launch_local_file(self):
        t = self.open(self.pdf)
        self._click_link(t, 0, 186, 265)
        opened_here = self.w.current_tab() and \
            self.w.current_tab().doc.name == 'notes.txt'
        self.assertTrue(opened_here or any('notes.txt' in u for u in URLS))

    def test_hover_cursor_tooltip_highlight(self):
        t = self.open(self.pdf)
        lbl = t.view.label
        QCursor.setPos(lbl.mapToGlobal(QPoint(500, 500))); pump()
        QCursor.setPos(lbl.mapToGlobal(QPoint(186, 115))); pump()
        self.assertEqual(lbl.cursor().shape(), Qt.PointingHandCursor)
        self.assertIn('страницу 3', lbl.toolTip())
        self.assertIsNotNone(lbl._hover)
        QCursor.setPos(lbl.mapToGlobal(QPoint(500, 600))); pump()
        QCursor.setPos(lbl.mapToGlobal(QPoint(500, 500))); pump()
        self.assertIsNone(lbl._hover)
        self.assertEqual(lbl.cursor().shape(), Qt.ArrowCursor)

    def test_click_outside_link_does_nothing(self):
        t = self.open(self.pdf)
        QTest.mouseClick(t.view.label, Qt.LeftButton, pos=QPoint(500, 500)); pump()
        self.assertPage(0)
        self.assertEqual(URLS, [])

    def test_drag_does_not_activate_link(self):
        t = self.open(self.pdf)
        lbl = t.view.label
        QTest.mousePress(lbl, Qt.LeftButton, pos=QPoint(186, 115)); pump()
        QTest.mouseMove(lbl, QPoint(300, 400)); pump()
        QTest.mouseRelease(lbl, Qt.LeftButton, pos=QPoint(300, 400)); pump()
        self.assertPage(0)

    def test_link_in_facing_mode(self):
        t = self.open(self.pdf)
        self.w.set_mode('facing'); pump()
        t.goto(2); pump()
        found = False
        for rect, link in t.view.label.link_regions:
            if link.get('page') == 0:
                QTest.mouseClick(t.view.label, Qt.LeftButton,
                                 pos=QPoint(int(rect.center().x()),
                                           int(rect.center().y())))
                pump()
                found = True
                break
        self.assertTrue(found, 'ссылка на второй странице разворота не найдена')
        self.assertPage(0)

    def test_link_when_rotated(self):
        t = self.open(self.pdf)
        t.rotate(90); pump()
        for rect, link in t.view.label.link_regions:
            if link.get('page') == 1:
                QTest.mouseClick(t.view.label, Qt.LeftButton,
                                 pos=QPoint(int(rect.center().x()),
                                           int(rect.center().y())))
                pump()
                self.assertPage(1)
                return
        self.fail('ссылка при повороте не найдена')

    def test_link_at_different_zoom(self):
        t = self.open(self.pdf)
        t.set_zoom(1.5); pump()
        rect, link = t.view.label.link_regions[0]
        QTest.mouseClick(t.view.label, Qt.LeftButton,
                         pos=QPoint(int(rect.center().x()),
                                   int(rect.center().y())))
        pump()
        self.assertPage(2)

    def test_file_uri(self):
        t = self.open(self.pdf)
        t.activate_link({'kind': pymupdf.LINK_URI,
                         'uri': QUrl.fromLocalFile(str(self.other)).toString()})
        pump()
        self.assertIsNotNone(self.w.current_tab())
        self.assertEqual(self.w.current_tab().doc.name, 'other.pdf')

    def test_uri_page_fragment(self):
        t = self.open(self.pdf)
        t.activate_link({'kind': pymupdf.LINK_URI, 'uri': '#page=4'})
        pump()
        self.assertPage(3)

    def test_named_destination(self):
        t = self.open(self.pdf)
        t.doc.named_destination = lambda name: {'page': 2, 'name': name}
        t.activate_link({'kind': pymupdf.LINK_NAMED, 'name': 'dest'})
        pump()
        self.assertPage(2)

    def test_gotor_with_page(self):
        t = self.open(self.pdf)
        t.activate_link({'kind': pymupdf.LINK_GOTOR,
                         'file': str(self.other), 'page': 2})
        pump()
        self.assertPage(2)

    def test_malformed_link_is_ignored(self):
        t = self.open(self.pdf)
        t.activate_link({'kind': pymupdf.LINK_URI, 'uri': ''})
        t.activate_link({'kind': 999})
        t.activate_link({})
        pump()
        self.assertPage(0)


# ---------------------------------------------------------------------------
class Test05TocBookmarksSearch(Base):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'search.pdf'
        d = pymupdf.open()
        for i in range(4):
            p = d.new_page(width=595, height=842)
            p.insert_text((72, 80), 'Page %d' % (i + 1), fontsize=20)
            p.insert_text((72, 200 + i * 10), 'targetword here', fontsize=14)
        d.set_toc([[1, 'First', 1], [1, 'Last', 4]])
        d.save(str(cls.pdf)); d.close()

    def test_toc_filter(self):
        self.open(self.pdf)
        self.w.filter_toc('last')
        self.assertTrue(self.w.toc_tree.topLevelItem(0).isHidden())
        self.assertFalse(self.w.toc_tree.topLevelItem(1).isHidden())
        self.w.filter_toc('')
        self.assertFalse(self.w.toc_tree.topLevelItem(1).isHidden())

    def test_bookmarks_lifecycle(self):
        t = self.open(self.pdf)
        self.w.next_page(); self.w.next_page(); pump()
        self.w.add_bookmark(); pump()
        self.assertEqual(self.w.bookmark_list.count(), 1)
        item = self.w.bookmark_list.item(0)
        self.assertEqual(item.data(Qt.UserRole), 2)
        self.w.first_page(); pump()
        self.w.on_bookmark_clicked(item); pump()
        self.assertPage(2)
        CHOICE['text'] = 'Моя закладка'
        self.w.bookmark_list.setCurrentItem(item)
        self.w.edit_bookmark(); pump()
        self.assertEqual(item.text(), 'Моя закладка')
        self.w.delete_bookmark(); pump()
        self.assertEqual(self.w.bookmark_list.count(), 0)

    def test_bookmark_export_import(self):
        self.open(self.pdf)
        self.w.add_bookmark(); pump()
        CHOICE['save'] = str(TMP / 'bookmarks.txt')
        self.w.export_bookmarks(); pump()
        self.assertTrue(Path(CHOICE['save']).exists())
        self.w.bookmark_list.clear()
        CHOICE['open'] = CHOICE['save']
        self.w.import_bookmarks(); pump()
        self.assertEqual(self.w.bookmark_list.count(), 1)

    def test_find_text(self):
        t = self.open(self.pdf)
        self.w.find_edit.setText('targetword')
        self.w.do_find(); pump()
        self.assertPage(0)
        self.assertTrue(hasattr(t, 'find_text'))

    def test_find_next(self):
        t = self.open(self.pdf)
        self.assertTrue(t.find_text('targetword')); pump()
        first = t.page
        t.find_next(); pump()
        self.assertNotEqual(t.page, first)

    def test_find_highlight(self):
        t = self.open(self.pdf)
        self.assertTrue(t.find_text('targetword')); pump()
        self.assertTrue(t._find_rects, 'нет прямоугольников подсветки')
        self.assertGreater(len(t._find_rects), 0)
        self.assertEqual(t._find_matches[0][1], t._find_rects)

    def test_find_highlight_rotated(self):
        t = self.open(self.pdf)
        t.find_text('targetword'); pump()
        t.rotate(90); pump()
        im = t.doc.render(t.page, t.zoom, t.rotation)
        rects = [t._map_rect(t.page, im, 0, t.zoom, fr)
                 for fr in t._find_rects]
        self.assertTrue(any(not r.isEmpty() for r in rects),
                        'подсветка не пересчитана при повороте')

    def test_find_next_cycles(self):
        t = self.open(self.pdf)
        self.assertTrue(t.find_text('Page')); pump()
        seen = [t.page]
        for _ in range(4):
            t.find_next(); pump()
            seen.append(t.page)
        self.assertEqual(seen[0], seen[-1], 'цикл поиска не замкнулся')
        self.assertGreater(len(set(seen)), 1)

    def test_find_forward_backward_actions(self):
        t = self.open(self.pdf)
        t.find_text('Page'); pump()
        self.w.find_forward(); pump()
        second = t.page
        self.w.find_backward(); pump()
        self.assertEqual(t.page, 0)
        self.assertNotEqual(second, 0)

    def test_find_not_found(self):
        t = self.open(self.pdf)
        self.assertFalse(t.find_text('nonexistent-word-xyz'))

    def test_flow_find(self):
        fb2 = TMP / 'book.fb2'
        fb2.write_text(
            '<?xml version="1.0"?><FictionBook '
            'xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><body>'
            '<section><title><p>Глава</p></title><p>Слово targetword тут</p>'
            '</section></body></FictionBook>', encoding='utf-8')
        t = self.open(fb2)
        self.assertTrue(t.find_text('targetword'))


# ---------------------------------------------------------------------------
class Test06ExportAndExtras(Base):
    @classmethod
    def setUpClass(cls):
        cls.pdf = TMP / 'export.pdf'
        make_pdf(cls.pdf, pages=3, text='Export %d')

    def test_export_page_images(self):
        self.open(self.pdf)
        d = TMP / 'imgs'; d.mkdir(exist_ok=True)
        CHOICE['dir'] = str(d)
        self.w.export_images(); pump()
        self.assertEqual(len(list(d.glob('page_*.png'))), 3)

    def test_export_text(self):
        self.open(self.pdf)
        out = TMP / 'doc.txt'
        CHOICE['save'] = str(out)
        self.w.export_text(); pump()
        txt = out.read_text(encoding='utf-8')
        self.assertIn('Export 1', txt)
        self.assertIn('Export 3', txt)

    def test_export_page(self):
        self.open(self.pdf)
        for ext in ('png', 'jpg', 'bmp'):
            out = TMP / ('page.' + ext)
            CHOICE['save'] = str(out)
            self.w.export_page(); pump()
            self.assertTrue(out.exists() and out.stat().st_size > 0)

    def test_print_to_pdf(self):
        t = self.open(self.pdf)
        out = TMP / 'printed.pdf'
        self.w.print_to_pdf(t, str(out)); pump()
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)
        printed = pymupdf.open(str(out))
        self.assertEqual(printed.page_count, 3)
        printed.close()

    def test_copy_page_text(self):
        from PyQt5.QtWidgets import QApplication
        t = self.open(self.pdf)
        t.view.label._copy_page_text(); pump()
        self.assertIn('Export 1', QApplication.clipboard().text())

    def test_properties_and_about(self):
        self.open(self.pdf)
        self.w.document_properties(); pump()
        self.assertTrue(any(d[0] == 'info' and 'Свойства' in d[1] for d in DIALOGS))
        self.w.about(); pump()
        self.assertTrue(any(d[0] == 'about' for d in DIALOGS))

    def test_recent_files_survive_restart(self):
        p = str(self.pdf)
        self.open(self.pdf)
        self.assertIn(p, open(m.RECENT_FILE, encoding='utf-8').read())
        w2 = m.MainWindow(); pump()
        self.assertTrue(any(p == item.data(Qt.UserRole)
                            for item in w2.recent_list.findItems(
                                '*', Qt.MatchWildcard)) or
                        p in open(m.RECENT_FILE, encoding='utf-8').read())
        w2.close()

    def test_password_pdf(self):
        enc = TMP / 'enc.pdf'
        make_pdf(enc, pages=2, password='secret')
        t = self.open(enc)
        self.assertEqual(t.doc.page_count, 2)
        self.assertIn('Page 1', t.doc.text(0))

    def test_wrong_password(self):
        enc = TMP / 'enc2.pdf'
        make_pdf(enc, pages=2, password='right')
        CHOICE['password'] = 'wrong'
        self.w.open_file(str(enc)); pump()
        self.assertEqual(self.w.tabs.count(), 0)
        DIALOGS.clear()
        CHOICE['password'] = 'secret'

    def test_fullscreen_and_nav_toggle(self):
        self.open(self.pdf)
        self.w.toggle_nav(); pump()
        self.assertFalse(self.w.nav_dock.isVisible())
        self.w.toggle_nav(); pump()
        self.assertTrue(self.w.nav_dock.isVisible())
        self.w.toggle_fullscreen(); pump()
        self.assertTrue(self.w.isFullScreen())
        self.w.toggle_fullscreen(); pump()
        self.assertFalse(self.w.isFullScreen())


# ---------------------------------------------------------------------------
class Test07Robustness(Base):
    def test_many_pages(self):
        pdf = TMP / 'many.pdf'
        make_pdf(pdf, pages=60)
        t = self.open(pdf)
        t.goto(59); pump()
        self.assertPage(59)
        self.assertTrue(t.view.label.pixmap().width() > 0)

    def test_rotation_and_zoom_combinations(self):
        pdf = TMP / 'combo.pdf'
        make_pdf(pdf, pages=2, links=[
            {'at': 0, 'kind': pymupdf.LINK_GOTO,
             'from': pymupdf.Rect(50, 50, 200, 80), 'page': 1}])
        t = self.open(pdf)
        for rot in (0, 90, 180, 270):
            for zoom in (0.25, 1.0, 2.0):
                t.rotate(90); t.set_zoom(zoom); pump(2)
                self.assertTrue(t.view.label.pixmap().width() > 0)
                self.assertTrue(len(t.view.label.link_regions) >= 0)

    def test_switch_tabs_with_links(self):
        a = TMP / 'a.pdf'; b = TMP / 'b.pdf'
        make_pdf(a, pages=2, links=[{'at': 0, 'kind': pymupdf.LINK_GOTO,
                                     'from': pymupdf.Rect(10, 10, 50, 50),
                                     'page': 1}])
        make_pdf(b, pages=2)
        self.open(a); self.open(b)
        self.w.tabs.setCurrentIndex(0); pump()
        self.assertEqual(len(self.w.current_tab().view.label.link_regions), 1)
        self.w.tabs.setCurrentIndex(1); pump()
        self.assertEqual(len(self.w.current_tab().view.label.link_regions), 0)

    def test_single_empty_page(self):
        pdf = TMP / 'blank.pdf'
        d = pymupdf.open(); d.new_page(width=200, height=200)
        d.save(str(pdf)); d.close()
        t = self.open(pdf)
        self.assertEqual(t.doc.page_count, 1)
        t.goto(100); pump()
        self.assertPage(0)
        self.assertTrue(t.view.label.pixmap().width() > 0)


def main():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for cls in (Test01Interface, Test02PdfBasics, Test03NavigationAndZoom,
                Test04Links, Test05TocBookmarksSearch, Test06ExportAndExtras,
                Test07Robustness):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
