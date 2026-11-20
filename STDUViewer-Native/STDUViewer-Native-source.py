#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STDU Reader — нативный Linux-ридер с интерфейсом в стиле STDU Viewer.
Работает без Wine. Поддерживает PDF, DjVu, EPUB, FB2, MOBI/AZW, XPS,
TIFF/изображения, комиксы (CBZ/CBR), DOCX/ODT/RTF, HTML, Markdown, TXT.
"""
import os
import re
import sys
import io
import zipfile
import tempfile
import subprocess
import shutil
import html as html_mod
from html.parser import HTMLParser
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QSize, QTimer, QUrl, QFileInfo, pyqtSignal, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QImage, QPixmap, QIcon, QFont, QTransform, QPainter, QColor,
    QKeySequence, QStandardItem, QCursor, QPalette, QBrush, QPen,
    QDesktopServices,
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QToolBar, QMenuBar, QMenu,
    QAction, QDockWidget, QTreeWidget, QTreeWidgetItem, QListWidget,
    QListWidgetItem, QScrollArea, QLabel, QVBoxLayout, QHBoxLayout,
    QStatusBar, QSpinBox, QSlider, QLineEdit, QFileDialog, QMessageBox,
    QSplitter, QTextBrowser, QAbstractItemView, QFrame, QSizePolicy,
    QStyle, QToolButton, QInputDialog, QComboBox,
)
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

import pymupdf as fitz

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.jpe', '.jfif', '.tif', '.tiff',
              '.gif', '.bmp', '.webp', '.ico', '.pcx', '.dcx', '.psd',
              '.ppm', '.pgm', '.pbm', '.wmf', '.emf'}
COMIC_EXTS = {'.cbz', '.cbr', '.zip', '.rar'}
EBOOK_EXTS = {'.epub', '.mobi', '.azw', '.azw3', '.prc', '.fb2'}
TEXT_EXTS = {'.txt', '.tcr', '.md', '.markdown', '.html', '.htm', '.xhtml',
             '.docx', '.odt', '.rtf', '.rst'}
CONVERT_EXTS = {'.xps', '.ps', '.eps', '.oxps'}
PDF_EXTS = {'.pdf'}
DJVU_EXTS = {'.djvu', '.djv'}
JBIG2_EXTS = {'.jb2', '.jbig2'}
PALM_EXTS = {'.pdb', '.wwf'}

# Значок оригинала (тот же .ico, что и у STDU Viewer под Wine)
ICON_FILE = os.environ.get(
    'STDU_ICON',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'STDUViewerApp.ico'))
RECENT_FILE = os.path.expanduser('~/.local/share/stdu-reader/recent.txt')

ALL_FILTER = ("Все поддерживаемые (*.pdf *.djvu *.djv *.epub *.fb2 *.mobi *.azw "
              "*.azw3 *.prc *.xps *.oxps *.ps *.eps *.tif *.tiff *.png *.jpg "
              "*.jpeg *.gif *.bmp *.webp *.cbz *.cbr *.zip *.rar *.txt *.md "
              "*.html *.htm *.docx *.odt *.rtf);;PDF (*.pdf);;DjVu (*.djvu *.djv);;"
              "EPUB (*.epub);;FB2 (*.fb2);;MOBI/AZW (*.mobi *.azw *.azw3);;"
              "Изображения (*.png *.jpg *.jpeg *.tif *.tiff *.gif *.bmp *.webp);;"
              "Комиксы (*.cbz *.cbr *.zip *.rar);;Текст (*.txt *.md *.html *.docx *.odt *.rtf)")


# ---------------------------------------------------------------------------
# Документы (бэкенды форматов)
# ---------------------------------------------------------------------------
class DocBase:
    kind = 'pages'

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)

    def close(self):
        pass

    @property
    def page_count(self):
        return 0

    def render(self, index, zoom=1.0, rotation=0):
        return QImage()

    def text(self, index):
        return ''

    def text_rect(self, index, rect):
        """Текст внутри прямоугольника в координатах страницы."""
        return self.text(index)

    def image_regions(self, index):
        """Список (прямоугольник, xref) изображений на странице."""
        return []

    def toc(self):
        return []

    def html(self):
        return ''

    def format_name(self):
        return Path(self.path).suffix.lstrip('.').upper()

    # --- hyperlinks --------------------------------------------------
    def page_size(self, index):
        """Размер страницы в пунктах (ширина, высота)."""
        return 0.0, 0.0

    def links(self, index):
        """Список ссылок со страницы (словари в формате PyMuPDF)."""
        return []

    def search(self, index, text):
        """Прямоугольники всех вхождений текста на странице."""
        return []

    def named_destination(self, name):
        """Разрешить именованный пункт назначения."""
        return None


class PdfDoc(DocBase):
    def __init__(self, path, password=''):
        super().__init__(path)
        self.doc = fitz.open(path)
        self.needs_pass = bool(getattr(self.doc, 'needs_pass', False))

    def authenticate(self, password):
        return self.doc.authenticate(password)

    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass

    @property
    def page_count(self):
        return len(self.doc)

    def render(self, index, zoom=1.0, rotation=0):
        page = self.doc[index]
        # Сглаживание (суперсэмплинг): при малом/среднем масштабе рисуем страницу
        # с запасом и уменьшаем её качественным фильтром. Так текст и тонкие
        # линии не превращаются в «лестницу»; при крупном масштабе запас не нужен.
        z = max(0.05, zoom)
        oversample = 2.0 if z < 1.5 else 1.0
        pix = page.get_pixmap(matrix=fitz.Matrix(z * oversample, z * oversample),
                              alpha=False)
        fmt = QImage.Format_RGB888 if pix.n == 3 else QImage.Format_RGBA8888
        img = QImage(pix.samples, pix.width, pix.height, pix.n * pix.width, fmt).copy()
        if oversample != 1.0:
            img = img.scaled(max(1, round(pix.width / oversample)),
                             max(1, round(pix.height / oversample)),
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if rotation:
            img = img.transformed(QTransform().rotate(rotation),
                                  Qt.SmoothTransformation)
        return img

    def text(self, index):
        try:
            return self.doc[index].get_text()
        except Exception:
            return ''

    def text_rect(self, index, rect):
        try:
            return self.doc[index].get_textbox(rect)
        except Exception:
            return self.text(index)

    def image_regions(self, index):
        """Прямоугольники и xref изображений — нужны для контекстного меню."""
        try:
            out = []
            for info in self.doc[index].get_image_info(xrefs=True):
                box = info.get('bbox')
                if box:
                    out.append((fitz.Rect(box), info.get('xref', 0)))
            return out
        except Exception:
            return []

    def toc(self):
        try:
            # PyMuPDF возвращает номера страниц с единицы, в программе же
            # страницы индексируются с нуля — сразу приводим к внутреннему виду.
            return [(lvl, title, max(0, page - 1))
                    for lvl, title, page in self.doc.get_toc()]
        except Exception:
            return []

    def page_size(self, index):
        try:
            r = self.doc[index].rect
            return r.width, r.height
        except Exception:
            return 0.0, 0.0

    def links(self, index):
        try:
            return self.doc[index].get_links()
        except Exception:
            return []

    def search(self, index, text):
        try:
            return [r for r in self.doc[index].search_for(text)]
        except Exception:
            return []

    def named_destination(self, name):
        try:
            names = self.doc.resolve_names()
            if isinstance(names, dict):
                item = names.get(name)
                return item if isinstance(item, dict) else None
            for item in names or []:
                if isinstance(item, dict) and item.get('name') == name:
                    return item
        except Exception:
            pass
        return None


class DjvuDoc(DocBase):
    def __init__(self, path):
        super().__init__(path)
        out = subprocess.check_output(['djvused', path, '-e', 'n'],
                                      stderr=subprocess.DEVNULL).decode('utf-8', 'ignore')
        m = re.search(r'\d+', out)
        self._n = int(m.group()) if m else 1

    @property
    def page_count(self):
        return self._n

    def render(self, index, zoom=1.0, rotation=0):
        scale = max(25, int(round(100 * zoom)))
        data = subprocess.check_output(
            ['ddjvu', '-format=ppm', '-page=%d' % (index + 1),
             '-scale=%d' % scale, self.path, '-'],
            stderr=subprocess.DEVNULL)
        m = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s', data)
        if not m:
            return QImage()
        w, h = int(m.group(1)), int(m.group(2))
        img = QImage(data[m.end():], w, h, 3 * w, QImage.Format_RGB888).copy()
        if rotation:
            img = img.transformed(QTransform().rotate(rotation))
        return img

    def text(self, index):
        try:
            return subprocess.check_output(
                ['djvutxt', '--page=%d' % (index + 1), self.path],
                stderr=subprocess.DEVNULL).decode('utf-8', 'ignore')
        except Exception:
            return ''


class ImageDoc(DocBase):
    """Одна или несколько страниц-изображений (в т.ч. многокадровый TIFF/GIF)."""

    def __init__(self, path, files=None):
        super().__init__(path)
        self._files = files
        self._images = []
        if files is None:
            self._load_file(path)
        else:
            for f in files:
                self._load_file(f)

    def _load_file(self, path):
        from PIL import Image, ImageSequence
        try:
            im = Image.open(path)
            for frame in ImageSequence.Iterator(im):
                frame = frame.convert('RGB')
                w, h = frame.size
                q = QImage(frame.tobytes(), w, h, 3 * w, QImage.Format_RGB888).copy()
                self._images.append(q)
        except Exception as e:
            print('image load error:', e, file=sys.stderr)

    @property
    def page_count(self):
        return len(self._images)

    def render(self, index, zoom=1.0, rotation=0):
        if index >= len(self._images):
            return QImage()
        img = self._images[index]
        if zoom != 1.0:
            img = img.scaled(int(img.width() * zoom), int(img.height() * zoom),
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if rotation:
            img = img.transformed(QTransform().rotate(rotation),
                                  Qt.SmoothTransformation)
        return img

    def format_name(self):
        if self._files:
            return 'CBZ/CBR'
        return super().format_name()


class ConvertedImageDoc(DocBase):
    """Формат, который внешняя утилита конвертирует в изображение."""

    def __init__(self, path, commands, fmt):
        super().__init__(path)
        self._tmp = tempfile.mkdtemp(prefix='stduconv-')
        self._fmt = fmt
        out = os.path.join(self._tmp, 'page.png')
        last = None
        for cmd in commands:
            try:
                subprocess.check_call(cmd(path, out),
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, timeout=60)
                if os.path.isfile(out) and os.path.getsize(out) > 0:
                    self._img = ImageDoc(out)
                    return
            except Exception as e:
                last = e
        shutil.rmtree(self._tmp, ignore_errors=True)
        raise RuntimeError(str(last) if last else 'conversion failed')

    @property
    def page_count(self):
        return self._img.page_count

    def render(self, index, zoom=1.0, rotation=0):
        return self._img.render(index, zoom, rotation)

    def format_name(self):
        return self._fmt

    def close(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


class FlowDoc(DocBase):
    """Текстовый поток: HTML + оглавление."""
    kind = 'flow'

    def __init__(self, path, content_html, toc=None, fmt=None):
        super().__init__(path)
        self._html = content_html
        self._toc = toc or []
        self._fmt = fmt

    @property
    def page_count(self):
        return 1

    def html(self):
        return self._html

    def toc(self):
        return self._toc

    def format_name(self):
        return self._fmt or super().format_name()

    def render(self, index, zoom=1.0, rotation=0):
        return QImage()


# ---------------------------------------------------------------------------
# Построители текстовых форматов
# ---------------------------------------------------------------------------
def wrap_html(body, title=''):
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title>'
            '<style>body{font-family:"DejaVu Serif",serif;font-size:14px;'
            'color:#111;background:#fff;margin:28px 36px;line-height:1.55;}'
            'h1,h2,h3{font-family:"DejaVu Sans",sans-serif;color:#1a3c6e;}'
            'img{max-width:95%%;} p{margin:0 0 0.8em;}</style></head><body>%s</body></html>'
            % (html_mod.escape(title), body))


def build_epub(path):
    import ebooklib
    from ebooklib import epub
    book = epub.read_epub(path)
    parts = []
    names = []
    images = {}
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_IMAGE:
            try:
                import base64
                mime = item.media_type or 'image/png'
                b64 = base64.b64encode(item.get_content()).decode('ascii')
                images[item.get_name()] = 'data:%s;base64,%s' % (mime, b64)
            except Exception:
                pass
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        try:
            txt = item.get_content().decode('utf-8', 'ignore')
        except Exception:
            continue
        for name, uri in images.items():
            txt = txt.replace(os.path.basename(name), uri)
        parts.append(txt)
        names.append(item.get_name())

    toc = []

    def walk(items, level=1):
        for it in items:
            if isinstance(it, tuple):
                sec, children = it
                walk([sec], level)
                walk(children, level + 1)
            elif hasattr(it, 'title'):
                title = it.title or ''
                href = ''
                if hasattr(it, 'href'):
                    href = it.href
                elif getattr(it, 'link', None):
                    href = getattr(it.link, 'href', '')
                toc.append((level, title, href))
                if getattr(it, 'children', None):
                    walk(it.children, level + 1)

    try:
        walk(book.toc)
    except Exception:
        pass

    # Все файлы книги склеены в один HTML, поэтому ссылки оглавления
    # (chap1.xhtml#section) нужно превратить в реальные якоря QTextBrowser.
    anchors = {}
    for _level, _title, href in toc:
        if not href:
            continue
        file_name, sep, fragment = href.partition('#')
        base = os.path.basename(file_name)
        name = fragment if sep and fragment else base
        anchors.setdefault(base, set()).add(name)

    wrapped = []
    for name, txt in zip(names, parts):
        base = os.path.basename(name)
        tags = ''.join('<a name="%s"></a>' % html_mod.escape(a)
                       for a in sorted(anchors.get(base, set()) | {base}))
        wrapped.append('<div>%s%s</div>' % (tags, txt))

    norm_toc = []
    for level, title, href in toc:
        if href:
            file_name, sep, fragment = href.partition('#')
            href = fragment if sep and fragment else os.path.basename(file_name)
        norm_toc.append((level, title, href))
    return wrap_html('\n'.join(wrapped)), norm_toc


def build_mobi(path):
    import mobi
    result = mobi.extract(path)
    filepath, directory = result if isinstance(result, tuple) else (result, None)
    files = []
    if directory and os.path.isdir(directory):
        for root, _dirs, names in os.walk(directory):
            for n in names:
                if n.lower().endswith(('.html', '.htm', '.xhtml')):
                    files.append(os.path.join(root, n))
    if filepath and os.path.isfile(filepath) and filepath not in files:
        files.insert(0, filepath)
    parts = []
    for f in sorted(set(files)):
        try:
            parts.append(open(f, 'r', encoding='utf-8', errors='ignore').read())
        except Exception:
            pass
    if not parts and filepath and os.path.isfile(filepath):
        parts.append(open(filepath, 'rb').read().decode('utf-8', 'ignore'))
    title = Path(path).stem
    return wrap_html('\n'.join(parts), title), []


def build_fb2(path):
    from lxml import etree
    tree = etree.parse(path)
    root = tree.getroot()
    binaries = {}
    for b in root.iter():
        if etree.QName(b).localname == 'binary' and b.get('id'):
            import base64
            binaries[b.get('id')] = 'data:%s;base64,%s' % (
                b.get('content-type', 'image/jpeg'),
                base64.b64encode((b.text or '').encode()).decode('ascii'))

    out = []
    toc = []
    body = None
    for el in root.iter():
        if etree.QName(el).localname == 'body':
            body = el
            break
    if body is None:
        return wrap_html('<p>Пустой FB2</p>'), []

    def inline(el):
        name = etree.QName(el).localname
        txt = el.text or ''
        tail = el.tail or ''
        if name in ('strong', 'b'):
            s = '<b>%s</b>' % html_mod.escape(txt)
        elif name in ('emphasis', 'i'):
            s = '<i>%s</i>' % html_mod.escape(txt)
        elif name == 'image':
            ref = ''
            for k, v in el.attrib.items():
                if etree.QName(k).localname in ('href', 'type') and '#' in str(v):
                    ref = str(v).split('#')[-1]
            s = '<img src="%s"/>' % binaries.get(ref, '') if ref else ''
        else:
            s = html_mod.escape(txt)
        for child in el:
            s += inline(child)
        return s + html_mod.escape(tail)

    for sec in body:
        lname = etree.QName(sec).localname
        if lname != 'section':
            continue
        title_el = None
        for ch in sec:
            if etree.QName(ch).localname == 'title':
                title_el = ch
                break
        if title_el is not None:
            text = ''.join(title_el.itertext()).strip()
            anchor = 'sec%d' % len(toc)
            out.append('<h2 id="%s">%s</h2>' % (anchor, html_mod.escape(text)))
            toc.append((1, text, anchor))
        for ch in sec:
            n = etree.QName(ch).localname
            if n == 'title':
                continue
            if n == 'p':
                out.append('<p>%s</p>' % inline(ch))
            elif n == 'image':
                ref = ''
                for k, v in ch.attrib.items():
                    if etree.QName(k).localname in ('href', 'type') and '#' in str(v):
                        ref = str(v).split('#')[-1]
                out.append('<p><img src="%s"/></p>' % binaries.get(ref, ''))
            elif n == 'section':
                t = ''.join(ch.itertext()).strip()[:80]
                out.append('<h3>%s</h3>' % html_mod.escape(t))
                for p in ch:
                    if etree.QName(p).localname == 'p':
                        out.append('<p>%s</p>' % inline(p))
    if not out:
        out = ['<p>%s</p>' % html_mod.escape(''.join(body.itertext())[:20000])]
    return wrap_html('\n'.join(out), Path(path).stem), toc


def build_plain(path):
    ext = Path(path).suffix.lower()
    with open(path, 'rb') as fh:
        raw = fh.read().decode('utf-8', 'ignore')
    if ext in ('.html', '.htm', '.xhtml'):
        return raw, []
    if ext == '.txt':
        body = '<pre style="white-space:pre-wrap;font-family:DejaVu Serif,serif;font-size:14px">%s</pre>' % html_mod.escape(raw)
        return wrap_html(body, Path(path).stem), []
    # pandoc: markdown / rst / docx / odt / rtf -> html
    try:
        out = subprocess.check_output(
            ['pandoc', '--wrap=none', '-t', 'html5', path],
            stderr=subprocess.DEVNULL, timeout=60).decode('utf-8', 'ignore')
        return wrap_html(out, Path(path).stem), []
    except Exception:
        body = '<pre style="white-space:pre-wrap">%s</pre>' % html_mod.escape(raw)
        return wrap_html(body, Path(path).stem), []


class ConvertedPdfDoc(PdfDoc):
    """Документ, сконвертированный в PDF (XPS/PS/EPS)."""

    def __init__(self, path, pdf_path, tmpdir):
        super().__init__(pdf_path)
        self.path = path
        self._tmpdir = tmpdir

    def format_name(self):
        return Path(self.path).suffix.lstrip('.').upper()

    def close(self):
        super().close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)


def build_converted(path):
    tmp = tempfile.mkdtemp(prefix='stdux-')
    pdf = os.path.join(tmp, 'converted.pdf')
    ext = Path(path).suffix.lower()
    try:
        if ext in ('.xps', '.oxps'):
            subprocess.check_call(['mutool', 'convert', '-o', pdf, path],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.check_call(['gs', '-q', '-dNOPAUSE', '-dBATCH',
                                   '-sDEVICE=pdfwrite', '-sOutputFile=' + pdf, path],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.isfile(pdf):
            raise RuntimeError('conversion failed')
        return ConvertedPdfDoc(path, pdf, tmp)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def open_document(path):
    ext = Path(path).suffix.lower()
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    # FB2 внутри ZIP
    if ext == '.zip' and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            fb2 = [n for n in z.namelist() if n.lower().endswith('.fb2')]
            if fb2:
                tmp = tempfile.mkdtemp(prefix='stdufb2-')
                z.extract(fb2[0], tmp)
                h, toc = build_fb2(os.path.join(tmp, fb2[0]))
                d = FlowDoc(path, h, toc, 'FB2')
                d._tmpdir = tmp
                return d

    if ext in PDF_EXTS:
        return PdfDoc(path)
    if ext in DJVU_EXTS:
        return DjvuDoc(path)
    if ext in CONVERT_EXTS:
        return build_converted(path)
    if ext in JBIG2_EXTS:
        return ConvertedImageDoc(path, [
            lambda p, o: ['mutool', 'draw', '-o', o, p],
            lambda p, o: ['convert', p, o],
        ], 'JBIG2')
    if ext in PALM_EXTS:
        try:
            h, toc = build_mobi(path)
            return FlowDoc(path, h, toc, 'PalmDoc')
        except Exception:
            h, toc = build_plain(path)
            return FlowDoc(path, h, toc, 'PalmDoc')
    if ext in COMIC_EXTS:
        tmp = tempfile.mkdtemp(prefix='stducomic-')
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as z:
                    z.extractall(tmp)
            else:
                subprocess.check_call(['unrar', 'x', '-o+', path, tmp],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            files = []
            for root, _dirs, names in os.walk(tmp):
                for n in names:
                    if Path(n).suffix.lower() in IMAGE_EXTS:
                        files.append(os.path.join(root, n))
            files.sort(key=lambda p: [int(t) if t.isdigit() else t.lower()
                                      for t in re.split(r'(\d+)', p)])
            if not files:
                raise RuntimeError('no images in archive')
            d = ImageDoc(path, files)
            d._tmpdir = tmp
            return d
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    if ext in IMAGE_EXTS:
        try:
            return ImageDoc(path)
        except Exception:
            if shutil.which('convert'):
                return ConvertedImageDoc(path, [
                    lambda p, o: ['convert', p, o],
                ], ext.lstrip('.').upper())
            raise
    if ext == '.epub':
        h, toc = build_epub(path)
        return FlowDoc(path, h, toc, 'EPUB')
    if ext in ('.mobi', '.azw', '.azw3', '.prc'):
        h, toc = build_mobi(path)
        return FlowDoc(path, h, toc, 'MOBI')
    if ext == '.fb2':
        h, toc = build_fb2(path)
        return FlowDoc(path, h, toc, 'FB2')
    if ext in TEXT_EXTS:
        h, toc = build_plain(path)
        return FlowDoc(path, h, toc, ext.lstrip('.').upper())
    # неизвестный формат: пробуем как изображение, потом как текст
    try:
        return ImageDoc(path)
    except Exception:
        h, toc = build_plain(path)
        return FlowDoc(path, h, toc, 'TEXT')


# ---------------------------------------------------------------------------
# Виджеты
# ---------------------------------------------------------------------------
def link_tooltip(link):
    """Подсказка для ссылки PDF."""
    kind = link.get('kind', fitz.LINK_NONE)
    if kind == fitz.LINK_URI:
        return link.get('uri', '') or 'Ссылка'
    if kind == fitz.LINK_GOTO:
        try:
            return 'Перейти на страницу %d' % (int(link.get('page', 0)) + 1)
        except Exception:
            return 'Перейти на страницу'
    if kind == fitz.LINK_NAMED:
        return 'Перейти: %s' % (link.get('name', '') or 'раздел')
    if kind in (fitz.LINK_GOTOR, fitz.LINK_LAUNCH):
        return link.get('file', '') or link.get('uri', '') or 'Открыть файл'
    return 'Ссылка'


class PageLabel(QLabel):
    """Метка со страницей: отслеживает наведение и нажатия на ссылки PDF."""

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.tab = view.tab
        self.link_regions = []      # список (QRectF, dict-ссылка)
        self._pressed = None
        self._hover = None
        self._selecting = False
        self._sel_start = None
        self._sel_end = None
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

    def set_links(self, regions):
        self.link_regions = list(regions or [])
        if self._hover is not None:
            self._hover = None
            self.unsetCursor()
            self.setToolTip('')
        self.update()

    def _hit(self, pos):
        point = QPointF(pos)
        # Поздние регионы (поверх предыдущих) имеют приоритет.
        for rect, link in reversed(self.link_regions):
            if rect.contains(point):
                return link
        return None

    def clear_selection(self):
        self._selecting = False
        self._sel_start = self._sel_end = None
        self.tab._selected_text = ''
        self.update()

    def selection_rect(self):
        if self._sel_start is None or self._sel_end is None:
            return QRectF()
        return QRectF(self._sel_start, self._sel_end).normalized()

    def mouseMoveEvent(self, event):
        if self._selecting and (event.buttons() & Qt.LeftButton):
            self._sel_end = event.pos()
            self.update()
        link = self._hit(event.pos())
        if link is not self._hover:
            self._hover = link
            if link is not None:
                self.setCursor(Qt.PointingHandCursor)
                self.setToolTip(link_tooltip(link))
            else:
                self.unsetCursor()
                self.setToolTip('')
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover is not None:
            self._hover = None
            self.unsetCursor()
            self.setToolTip('')
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = event.pos()
            self._sel_start = event.pos()
            self._sel_end = event.pos()
            self._selecting = True
            self.tab._selected_text = ''
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed is not None:
            pressed = self._pressed
            self._pressed = None
            self._selecting = False
            if (pressed - event.pos()).manhattanLength() <= 4:
                # Короткий клик — переход по ссылке, выделение сбрасываем.
                self._sel_start = self._sel_end = None
                link = self._hit(event.pos())
                if link is not None:
                    self.tab.activate_link(link)
                    return
            else:
                # Протаскивание — выделяем текст и сразу кладём в буфер обмена.
                rect = self.selection_rect()
                text = self.tab.text_in_rect(rect)
                if text.strip():
                    self.tab._selected_text = text
                    QApplication.clipboard().setText(text)
        self.update()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.tab._selected_text:
            menu.addAction('Копировать выделенный текст',
                           self._copy_selection)
        menu.addAction('Копировать текст страницы', self._copy_page_text)
        menu.addAction('Копировать весь документ', self._copy_all_text)

        # Изображение под курсором: копируем в буфер или сохраняем на диск.
        image = self.tab.image_at(event.pos())
        if image is not None:
            pno, xref = image
            menu.addSeparator()
            menu.addAction('Копировать изображение',
                           lambda: self.tab.copy_image(pno, xref))
            menu.addAction('Сохранить изображение как...',
                           lambda: self.tab.save_image(pno, xref))

        hovered = self._hit(event.pos())
        if hovered is not None:
            address = link_tooltip(hovered)
            menu.addSeparator()
            menu.addAction('Копировать адрес ссылки: %s' % address,
                           lambda: QApplication.clipboard().setText(address))
            menu.addAction('Перейти по ссылке',
                           lambda: self.tab.activate_link(hovered))
        menu.exec_(event.globalPos())

    def _copy_selection(self):
        self.tab.copy_selection()

    def _copy_page_text(self):
        text = self.tab.page_text()
        if text:
            QApplication.clipboard().setText(text)

    def _copy_all_text(self):
        text = self.tab.all_text()
        if text:
            QApplication.clipboard().setText(text)

    def paintEvent(self, event):
        super().paintEvent(event)
        selection = self.selection_rect()
        if self._hover is None and selection.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if not selection.isEmpty():
            painter.fillRect(selection, QColor(30, 100, 200, 70))
            painter.setPen(QPen(QColor(20, 80, 180), 1, Qt.SolidLine))
            painter.drawRect(selection)
        if self._hover is not None:
            for rect, link in self.link_regions:
                if link is self._hover:
                    painter.fillRect(rect, QColor(30, 100, 200, 40))
                    painter.setPen(QPen(QColor(30, 100, 200), 1, Qt.DashLine))
                    painter.drawRect(rect)
                    break
        painter.end()


class PageView(QScrollArea):
    """Прокручиваемая область со страницей.

    Помимо обычной прокрутки внутри страницы поддерживается *непрерывный
    просмотр*: когда колесо дошло до нижнего/верхнего края страницы,
    автоматически открывается следующая/предыдущая страница, и прокрутка
    продолжается уже на ней. Благодаря этому весь документ можно листать
    одним непрерывным движением колеса, не нажимая «Вперёд/Назад».
    """

    def __init__(self, tab):
        super().__init__()
        self.tab = tab
        self.setAlignment(Qt.AlignCenter)
        self.setBackgroundRole(QPalette.Dark)
        self.setViewportMargins(0, 0, 0, 0)
        self.label = PageLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setBackgroundRole(QPalette.Dark)
        self.setWidget(self.label)
        self.setWidgetResizable(False)
        self.verticalScrollBar().setSingleStep(48)
        self._scroll_anim = None

    # -- служебные методы прокрутки ------------------------------------
    def _stop_anim(self):
        if self._scroll_anim is not None:
            if self._scroll_anim.state() == QPropertyAnimation.Running:
                self._scroll_anim.stop()
            self._scroll_anim = None

    def _animate_scroll(self, target):
        """Плавная (сглаженная) прокрутка к заданному положению ползунка."""
        bar = self.verticalScrollBar()
        target = max(bar.minimum(), min(bar.maximum(), int(target)))
        self._stop_anim()
        if target == bar.value():
            return
        self._scroll_anim = QPropertyAnimation(bar, b'value', self)
        self._scroll_anim.setDuration(200)
        self._scroll_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()

    def scroll_to_top(self):
        self._stop_anim()
        self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())

    def scroll_to_bottom(self):
        self._stop_anim()
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def set_image(self, qimage, links=None):
        self.label.clear_selection()
        self.label.set_links(links or [])
        if qimage.isNull():
            self.label.clear()
            return
        self.label.setPixmap(QPixmap.fromImage(qimage))
        self.label.resize(self.label.pixmap().size())

    # -- колесо мыши ----------------------------------------------------
    def wheelEvent(self, event):
        # Ctrl + колесо — масштабирование (как в оригинале).
        if event.modifiers() & Qt.ControlModifier:
            delta = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
            self.tab.set_zoom(self.tab.zoom * delta)
            event.accept()
            return

        dy = event.angleDelta().y()
        if dy == 0:
            super().wheelEvent(event)
            return

        bar = self.verticalScrollBar()
        step = abs(dy) or 120
        down = dy < 0        # в Qt отрицательный angleDelta — прокрутка вниз

        # seamless-режим выключен: просто плавно листаем текущую страницу.
        continuous = getattr(self.tab, 'continuous', True)
        pages = self.tab.doc.page_count
        can_turn = continuous and pages > 1

        if down:
            room = bar.maximum() - bar.value()
            if room > step or not can_turn or self.tab.page >= pages - 1:
                self._animate_scroll(bar.value() + step)
                event.accept()
                return
            # Дошли до низа — переходим на следующую страницу и переносим
            # оставшийся «хвост» прокрутки на неё, чтобы листание было непрерывным.
            overflow = max(0, step - room)
            self.tab.next_page()
            self.scroll_to_top()
            if overflow:
                bar.setValue(min(overflow, bar.maximum()))
        else:
            room = bar.value() - bar.minimum()
            if room > step or not can_turn or self.tab.page <= 0:
                self._animate_scroll(bar.value() - step)
                event.accept()
                return
            overflow = max(0, step - room)
            self.tab.prev_page()
            self.scroll_to_bottom()
            if overflow:
                bar.setValue(max(bar.minimum(), bar.maximum() - overflow))
        event.accept()


class DocumentTab(QWidget):
    pageChanged = pyqtSignal(int)

    def __init__(self, doc, main_window):
        super().__init__()
        self.doc = doc
        self.mw = main_window
        self.page = 0
        self.zoom = 1.0
        self.rotation = 0
        self.fit = 'none'
        self.mode = 'single'   # single | facing | facing_cover
        self.continuous = getattr(main_window, 'continuous', True)
        self._closed = False
        self._dirty = False
        self._find_text = ''
        self._find_matches = []   # [(страница, [прямоугольники])]
        self._find_index = -1
        self._find_rects = []     # подсветка на текущей странице
        self._selected_text = ''  # текст, выделенный мышью на странице
        self._pages, self._imgs, self._offsets, self._z = [], [], [], 1.0
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._refit_after_resize)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if doc.kind == 'flow':
            self.browser = QTextBrowser()
            self.browser.setOpenExternalLinks(True)
            self.browser.setStyleSheet('QTextBrowser{background:#fff;border:none;}')
            self.browser.setHtml(doc.html())
            lay.addWidget(self.browser)
            self.view = None
        else:
            self.view = PageView(self)
            lay.addWidget(self.view)
            self.browser = None

        QTimer.singleShot(0, self.render)

    def _pages_to_show(self):
        n = self.doc.page_count
        if self.mode == 'single' or n <= 1:
            return [self.page]
        if self.mode == 'facing_cover' and self.page == 0:
            return [0]
        start = self.page if self.page % 2 == 0 else self.page - 1
        if self.mode == 'facing_cover':
            start = self.page if self.page == 0 else self.page
        return [i for i in (start, start + 1) if i < n]

    def render(self):
        if self.doc.kind == 'flow':
            return
        w = self.viewport_width()
        h = self.viewport_height()
        z = self.zoom
        if self.fit == 'width' or self.fit == 'page':
            probe = self.doc.render(self.page, 1.0, self.rotation)
            if not probe.isNull():
                if self.fit == 'width':
                    z = max(0.05, (w - 24) / (probe.width() * len(self._pages_to_show())))
                else:
                    z = max(0.05, min((w - 24) / (probe.width() * len(self._pages_to_show())),
                                      (h - 24) / probe.height()))
                # Расчётный масштаб должен стать текущим: иначе строка состояния
                # и последующие операции показывают/используют старое значение.
                z = max(0.05, min(5.0, z))
                self.zoom = z

        pages, imgs = [], []
        for i in self._pages_to_show():
            im = self.doc.render(i, z, self.rotation)
            if not im.isNull():
                pages.append(i)
                imgs.append(im)
        if not imgs:
            self.view.set_image(QImage(), [])
            self.pageChanged.emit(self.page)
            return

        # Собираем разворот и запоминаем горизонтальное смещение каждой страницы —
        # оно нужно, чтобы наложить ссылки на правильное место картинки.
        offsets, x = [], 0
        for im in imgs:
            offsets.append(x)
            x += im.width() + 8
        if len(imgs) == 1:
            canvas = imgs[0]
        else:
            total_w = x - 8
            total_h = max(im.height() for im in imgs)
            canvas = QImage(total_w, total_h, QImage.Format_RGB32)
            canvas.fill(QColor('#808080'))
            p = QPainter(canvas)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            for im, ox in zip(imgs, offsets):
                p.drawImage(ox, 0, im)
            p.end()

        if self._find_rects:
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            for pno, im, ox in zip(pages, imgs, offsets):
                if pno == self.page:
                    for fr in self._find_rects:
                        rect = self._map_rect(pno, im, ox, z, fr)
                        if not rect.isEmpty():
                            painter.fillRect(rect, QColor(255, 215, 0, 110))
            painter.end()

        # Запоминаем геометрию текущей отрисовки: по ней выделение текста и
        # контекстное меню переводят пиксели картинки обратно в точки страницы.
        self._pages, self._imgs, self._offsets, self._z = pages, imgs, offsets, z
        self.view.set_image(canvas, self._link_regions(pages, imgs, offsets, z))
        self.pageChanged.emit(self.page)

    def _map_rect(self, pno, im, ox, z, fr):
        """Одна область из координат страницы в пиксели картинки."""
        pw, ph = self.doc.page_size(pno)
        if pw <= 0 or ph <= 0:
            pw, ph = im.width() / z, im.height() / z
        base_w, base_h = pw * z, ph * z
        try:
            x0, y0, x1, y1 = fr.x0 * z, fr.y0 * z, fr.x1 * z, fr.y1 * z
        except Exception:
            return QRectF()
        # Программа может дополнительно поворачивать уже отрисованную
        # картинку — переносим прямоугольник вместе с ней.
        rot = self.rotation % 360
        if rot == 90:
            x0, y0, x1, y1 = base_h - y1, x0, base_h - y0, x1
        elif rot == 180:
            x0, y0, x1, y1 = base_w - x1, base_h - y1, base_w - x0, base_h - y0
        elif rot == 270:
            x0, y0, x1, y1 = y0, base_w - x1, y1, base_w - x0
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        rect = QRectF(x0 + ox, y0, x1 - x0, y1 - y0)
        return rect.intersected(QRectF(ox, 0, im.width(), im.height()))

    def _link_regions(self, pages, imgs, offsets, z):
        """Переводит ссылки PDF из координат страницы в пиксели картинки."""
        regions = []
        for pno, im, ox in zip(pages, imgs, offsets):
            for link in self.doc.links(pno):
                fr = link.get('from')
                if fr is None:
                    continue
                rect = self._map_rect(pno, im, ox, z, fr)
                if not rect.isEmpty():
                    regions.append((rect, link))
        return regions

    # -- выделение и копирование текста / изображений -------------------
    def _pixel_to_point(self, x, y):
        """Пиксель картинки → (номер страницы, X, Y) в точках PDF."""
        z = self._z or self.zoom or 1.0
        for pno, im, ox in zip(self._pages, self._imgs, self._offsets):
            if x < ox or x > ox + im.width() or y < 0 or y > im.height():
                continue
            lx, ly = x - ox, y
            pw, ph = self.doc.page_size(pno)
            if pw <= 0 or ph <= 0:
                pw, ph = im.width() / z, im.height() / z
            base_w, base_h = pw * z, ph * z
            rot = self.rotation % 360
            # Обратное преобразование к повороту из _map_rect().
            if rot == 90:
                bx, by = ly, base_h - lx
            elif rot == 180:
                bx, by = base_w - lx, base_h - ly
            elif rot == 270:
                bx, by = base_w - ly, lx
            else:
                bx, by = lx, ly
            return pno, bx / z, by / z
        return None

    def text_in_rect(self, rect):
        """Текст внутри прямоугольника, заданного в пикселях картинки."""
        corners = [self._pixel_to_point(rect.left(), rect.top()),
                   self._pixel_to_point(rect.right(), rect.top()),
                   self._pixel_to_point(rect.left(), rect.bottom()),
                   self._pixel_to_point(rect.right(), rect.bottom())]
        if any(c is None for c in corners):
            return ''
        seen = []
        for c in corners:
            if c[0] not in seen:
                seen.append(c[0])
        parts = []
        for pno in seen:
            pts = [c for c in corners if c[0] == pno]
            x0, x1 = min(c[1] for c in pts), max(c[1] for c in pts)
            y0, y1 = min(c[2] for c in pts), max(c[2] for c in pts)
            if x1 - x0 < 1 or y1 - y0 < 1:
                continue
            try:
                text = self.doc.text_rect(pno, fitz.Rect(x0, y0, x1, y1))
                if text:
                    parts.append(text)
            except Exception:
                pass
        return '\n'.join(parts)

    def page_text(self):
        try:
            return self.doc.text(self.page) or ''
        except Exception:
            return ''

    def all_text(self):
        if self.browser is not None:
            return self.browser.toPlainText()
        parts = []
        for i in range(self.doc.page_count):
            try:
                parts.append(self.doc.text(i) or '')
            except Exception:
                pass
        return '\n\n'.join(parts)

    def copy_selection(self):
        """Ctrl+C: выделенный фрагмент, а если выделения нет — текст страницы."""
        text = self._selected_text or self.page_text()
        if text:
            QApplication.clipboard().setText(text)
        return text

    def image_at(self, pos):
        """ Возвращает (страница, xref) под курсором или None. """
        point = self._pixel_to_point(pos.x(), pos.y())
        if not point:
            return None
        pno, x, y = point
        for rect, xref in self.doc.image_regions(pno):
            if rect.contains(fitz.Point(x, y)):
                return pno, xref
        # Для чистых изображений (PNG, TIFF, CBZ, DjVu) картинка — вся страница.
        ext = Path(self.doc.path).suffix.lower()
        if ext in (IMAGE_EXTS | COMIC_EXTS | CONVERT_EXTS | DJVU_EXTS):
            return pno, None
        return None

    def _image_qimage(self, pno, xref=None):
        if xref:
            try:
                info = self.doc.doc.extract_image(xref)
                img = QImage.fromData(info['image'])
                if not img.isNull():
                    return img, (info.get('ext') or 'png').lower()
            except Exception:
                pass
        return self.doc.render(pno, 1.0, 0), 'png'

    def copy_image(self, pno, xref=None):
        img, _ext = self._image_qimage(pno, xref)
        if img.isNull():
            return False
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(QPixmap.fromImage(img))
        clipboard.setImage(img)
        return True

    def save_image(self, pno, xref=None):
        img, ext = self._image_qimage(pno, xref)
        if img.isNull():
            return
        filt = 'Изображения (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;Все файлы (*)'
        path, _f = QFileDialog.getSaveFileName(
            self.mw, 'Сохранить изображение', 'image.' + ext, filt)
        if not path:
            return
        if not Path(path).suffix:
            path += '.' + ext
        if xref:
            try:
                info = self.doc.doc.extract_image(xref)
                with open(path, 'wb') as fh:
                    fh.write(info['image'])
                return
            except Exception:
                pass
        img.save(path)

    # -- гиперссылки ----------------------------------------------------
    def activate_link(self, link):
        """Обрабатывает переход по ссылке PDF."""
        kind = link.get('kind', fitz.LINK_NONE)
        if kind == fitz.LINK_GOTO or kind == fitz.LINK_NAMED:
            if kind == fitz.LINK_NAMED:
                dest = self.doc.named_destination(link.get('name', ''))
                if not dest:
                    return
                pno = dest.get('page', -1)
            else:
                pno = link.get('page', -1)
            try:
                pno = int(pno)
            except Exception:
                return
            if 0 <= pno < self.doc.page_count:
                self.goto(pno)
            return

        if kind == fitz.LINK_GOTOR or kind == fitz.LINK_LAUNCH:
            target = link.get('file') or link.get('uri') or ''
            if target:
                self._open_target(target, link.get('page'))
            return

        if kind == fitz.LINK_URI:
            self._open_target(link.get('uri', ''), None)

    def _open_target(self, target, page=None):
        if not target:
            return
        # Фрагмент внутри того же документа: #page=5 (нумерация с единицы).
        if target.startswith('#'):
            m = re.search(r'page=(\d+)', target, re.IGNORECASE)
            if m:
                self.goto(int(m.group(1)) - 1)
            return

        local = target
        if target.startswith('file://'):
            local = QUrl(target).toLocalFile()
        elif '://' in target or target.lower().startswith(('mailto:', 'tel:')):
            QDesktopServices.openUrl(QUrl(target))
            return

        # Относительный путь считаем от папки текущего документа.
        if not os.path.isabs(local):
            local = os.path.join(os.path.dirname(os.path.abspath(self.doc.path)), local)
        local = os.path.normpath(local)
        fragment = None
        if '#' in local and not os.path.exists(local):
            local, fragment = local.split('#', 1)
        if os.path.isfile(local):
            if page is None and fragment:
                m = re.search(r'page=(\d+)', fragment, re.IGNORECASE)
                if m:
                    page = int(m.group(1)) - 1
            if Path(local).suffix.lower() in (PDF_EXTS | DJVU_EXTS | IMAGE_EXTS |
                                              COMIC_EXTS | EBOOK_EXTS | TEXT_EXTS |
                                              CONVERT_EXTS):
                self.mw.open_file(local)
                if page is not None:
                    tab = self.mw.current_tab()
                    if tab:
                        tab.goto(page)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(local))
        else:
            # Ссылка может быть обычным веб-адресом без схемы в старых PDF.
            QDesktopServices.openUrl(QUrl(target))

    def viewport_width(self):
        return self.view.width() if self.view else 800

    def viewport_height(self):
        return self.view.height() if self.view else 600

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # При изменении размера окна режимы «По ширине / По высоте / По странице»
        # должны пересчитывать масштаб — иначе страница остаётся старого размера.
        if self.view is not None and self.fit != 'none':
            self._fit_timer.start(120)

    def _refit_after_resize(self):
        if self._closed or self.view is None or self.fit == 'none':
            return
        try:
            self.render()
            self.mw.update_status()
        except Exception:
            pass   # документ мог быть закрыт, пока таймер ожидал срабатывания

    def prepare_close(self):
        """Останавливает отложенные операции перед закрытием документа."""
        self._closed = True
        self._fit_timer.stop()
        if self.view is not None:
            self.view._stop_anim()

    def goto(self, index):
        n = self.doc.page_count
        if n == 0:
            return
        index = max(0, min(n - 1, index))
        if index == self.page and not self._dirty:
            return
        self.page = index
        self.render()
        if self.view:
            self.view.scroll_to_top()
        self._dirty = False

    def set_mode(self, mode):
        self.mode = mode
        self.page = 0
        self.render()
        if self.view:
            self.view.scroll_to_top()

    def next_page(self):
        step = 2 if self.mode in ('facing', 'facing_cover') and self.doc.page_count > 1 else 1
        self.goto(self.page + step)

    def prev_page(self):
        step = 2 if self.mode in ('facing', 'facing_cover') and self.doc.page_count > 1 else 1
        self.goto(self.page - step)

    def set_zoom(self, z, fit='none'):
        self.zoom = max(0.05, min(5.0, z))
        self.fit = fit
        self.render()
        self.mw.update_status()

    def rotate(self, delta):
        self.rotation = (self.rotation + delta) % 360
        self.render()

    def find_text(self, text):
        """Ищет все совпадения и показывает первое с подсветкой."""
        self._find_text = text or ''
        self._find_rects = []
        if not text:
            self._find_matches = []
            self._find_index = -1
            return False
        if self.browser:
            found = bool(self.browser.find(text))
            self._find_matches = [(0, [])] if found else []
            self._find_index = 0 if found else -1
            return found

        pat = re.compile(re.escape(text), re.IGNORECASE)
        matches = []
        for i in range(self.doc.page_count):
            rects = self.doc.search(i, text)
            try:
                in_text = bool(rects) or bool(pat.search(self.doc.text(i)))
            except Exception:
                in_text = bool(rects)
            if in_text:
                matches.append((i, rects))
        self._find_matches = matches
        if not matches:
            self._find_index = -1
            return False
        self._find_index = 0
        self._show_match()
        return True

    def find_next(self, step=1):
        """Переход к следующему/предыдущему совпадению (по циклу)."""
        if self.browser:
            return bool(self.browser.find(self._find_text))
        if not self._find_matches:
            return False
        self._find_index = (self._find_index + step) % len(self._find_matches)
        self._show_match()
        return True

    def _show_match(self):
        pno, rects = self._find_matches[self._find_index]
        self._find_rects = rects
        self.page = pno
        self._dirty = True
        self.render()
        # Подводим найденный фрагмент к верху видимой области, чтобы подсветка
        # не осталась за пределами экрана на длинной странице.
        if self.view and rects:
            try:
                top = min(r.y0 for r in rects)
                bar = self.view.verticalScrollBar()
                self.view._animate_scroll(max(bar.minimum(), int(top) - 80))
            except Exception:
                pass
        self.mw.update_status()

    def scroll_to_anchor(self, anchor):
        if self.browser:
            self.browser.scrollToAnchor(anchor)


# ---------------------------------------------------------------------------
# Главное окно
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('STDU Viewer')
        if os.path.exists(ICON_FILE):
            self.setWindowIcon(QIcon(ICON_FILE))
        else:
            self.setWindowIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.recent = []
        try:
            if os.path.exists(RECENT_FILE):
                with open(RECENT_FILE, encoding='utf-8') as fh:
                    self.recent = [l.strip() for l in fh
                                   if l.strip() and os.path.isfile(l.strip())]
        except Exception:
            pass
        self._tabs = []
        self.continuous = True   # непрерывный просмотр включён по умолчанию

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            'QTabWidget::pane{border:1px solid #a0a0a0;background:#808080;}'
            'QTabBar::tab{background:#e8e8e8;padding:3px 10px;border:1px solid #b0b0b0;}'
            'QTabBar::tab:selected{background:#fff;}')
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self._build_nav_dock()
        self._build_actions()
        self._build_toolbar()
        self._build_statusbar()
        self._rebuild_recent()

        self.setAcceptDrops(True)
        self.resize(1200, 820)
        self.showMaximized()

    # -- UI construction ----------------------------------------------------
    def _build_nav_dock(self):
        dock = QDockWidget('Навигация', self)
        dock.setObjectName('navDock')
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetClosable |
                         QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        self.nav = QTabWidget()
        self.nav.setTabPosition(QTabWidget.South)
        self.nav.setDocumentMode(True)

        toc_widget = QWidget()
        toc_lay = QVBoxLayout(toc_widget)
        toc_lay.setContentsMargins(0, 0, 0, 0)
        toc_lay.setSpacing(2)
        self.toc_search = QLineEdit()
        self.toc_search.setPlaceholderText('Быстрый поиск в содержании')
        self.toc_search.textChanged.connect(self.filter_toc)
        toc_lay.addWidget(self.toc_search)
        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderLabel('Содержание')
        self.toc_tree.itemClicked.connect(self.on_toc_clicked)
        toc_lay.addWidget(self.toc_tree)
        self.nav.addTab(toc_widget, 'Содержание')

        self.recent_list = QListWidget()
        self.recent_list.setToolTip('Недавно открытые документы')
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(
            self.on_recent_context_menu)
        self.recent_list.itemClicked.connect(self.on_recent_clicked)
        self.nav.insertTab(0, self.recent_list, 'Недавние документы')
        self.recent_tab = self.recent_list
        self.toc_tab = toc_widget

        self.thumb_list = QListWidget()
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setIconSize(QSize(96, 128))
        self.thumb_list.setResizeMode(QListWidget.Adjust)
        self.thumb_list.setMovement(QListWidget.Static)
        self.thumb_list.itemClicked.connect(self.on_thumb_clicked)
        self.nav.addTab(self.thumb_list, 'Миниатюры')

        self.bookmark_list = QListWidget()
        self.bookmark_list.itemClicked.connect(self.on_bookmark_clicked)
        self.nav.addTab(self.bookmark_list, 'Закладки')

        # «Недавние документы» должны быть открыты при запуске. insertTab(0)
        # оставляет текущим прежний виджет («Содержание»), поэтому выбираем
        # вкладку явно — после добавления всех вкладок.
        self.nav.setCurrentWidget(self.recent_list)

        # Небольшая кнопка «×» прямо на панели — скрыть одним кликом,
        # независимо от стиля заголовка dock-виджета.
        header = QHBoxLayout()
        header.setContentsMargins(2, 2, 2, 0)
        header.addStretch(1)
        hide_btn = QToolButton()
        hide_btn.setText('×')
        hide_btn.setToolTip('Скрыть панель навигации (F6)')
        hide_btn.setFixedSize(22, 20)
        hide_btn.clicked.connect(self.toggle_nav)
        header.addWidget(hide_btn)
        self._nav_hide_button = hide_btn

        lay.addLayout(header)
        lay.addWidget(self.nav)
        dock.setWidget(inner)
        # Панель можно сунуть почти полностью влево — минимум был 330 px.
        dock.setMinimumWidth(170)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        dock.visibilityChanged.connect(self._on_nav_visibility)
        self.nav_dock = dock

    def _action(self, text, icon=None, shortcut=None, checkable=False, slot=None):
        a = QAction(text, self)
        if icon:
            a.setIcon(icon)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        if slot:
            a.triggered.connect(slot)
        return a

    def _std_icon(self, *names):
        for n in names:
            if hasattr(QStyle, n):
                return self.style().standardIcon(getattr(QStyle, n))
        return QIcon()

    def _build_actions(self):
        mb = self.menuBar()
        open_ico = self._std_icon('SP_DialogOpenButton', 'SP_FileIcon')
        save_ico = self._std_icon('SP_DialogSaveButton', 'SP_DriveFDIcon')
        print_ico = self._std_icon('SP_ComputerIcon', 'SP_PrintIcon')

        m_file = mb.addMenu('Файл')
        m_file.addAction(self._action('Открыть...', open_ico, 'Ctrl+O', slot=self.open_file))
        m_file.addAction(self._action('Закрыть', None, 'Ctrl+W', slot=self.close_current))
        m_file.addSeparator()
        m_file.addAction(self._action('Сохранить копию...', save_ico, slot=self.save_copy))
        m_file.addAction(self._action('Печать...', print_ico, 'Ctrl+P', slot=self.print_current))
        m_file.addSeparator()
        self.export_md_action = self._action(
            'Экспорт в Markdown...', slot=self.export_markdown)
        self.export_docx_action = self._action(
            'Экспорт в DOCX (Word)...', slot=self.export_docx)
        m_file.addAction(self.export_md_action)
        m_file.addAction(self.export_docx_action)
        m_file.addSeparator()
        self.recent_menu = m_file.addMenu('Недавние файлы')
        m_file.addSeparator()
        m_file.addAction(self._action('Выход', None, 'Ctrl+Q', slot=self.close))

        m_view = mb.addMenu('Вид')
        panel_ico = self._std_icon('SP_FileDialogDetailedView',
                                   'SP_ToolBarHorizontalExtensionButton')
        self._panel_action = self._action(
            'Панель навигации', panel_ico, 'F6', checkable=True,
            slot=self.toggle_nav)
        self._panel_action.setChecked(True)
        self._panel_action.setToolTip('Скрыть/показать левую панель (F6)')
        m_view.addAction(self._panel_action)
        m_view.addSeparator()
        m_view.addAction(self._action('Увеличить', None, 'Ctrl++', slot=lambda: self.zoom_by(1.2)))
        m_view.addAction(self._action('Уменьшить', None, 'Ctrl+-', slot=lambda: self.zoom_by(1 / 1.2)))
        m_view.addAction(self._action('По ширине', slot=self.fit_width))
        m_view.addAction(self._action('По высоте', slot=self.fit_height))
        m_view.addAction(self._action('По странице', slot=self.fit_page))
        m_view.addAction(self._action('Масштаб 100%', slot=self.zoom_100))
        m_view.addSeparator()
        self._mode_actions = {}
        for label, mode in (
            ('Режим просмотра: страницами', 'single'),
            ('Режим просмотра: разворотами', 'facing'),
            ('Режим просмотра: разворотами, первая страница отдельно', 'facing_cover'),
        ):
            a = self._action(label, checkable=True, slot=lambda c=False, m=mode: self.set_mode(m))
            self._mode_actions[mode] = a
            m_view.addAction(a)
        self._mode_actions['single'].setChecked(True)
        m_view.addSeparator()
        self._continuous_action = self._action(
            'Непрерывный просмотр', checkable=True, slot=self.toggle_continuous)
        self._continuous_action.setChecked(True)
        m_view.addAction(self._continuous_action)
        m_view.addSeparator()
        m_view.addAction(self._action('Повернуть по часовой стрелке', slot=lambda: self.rotate(90)))
        m_view.addAction(self._action('Повернуть против часовой стрелки', slot=lambda: self.rotate(-90)))
        m_view.addSeparator()
        for label, size in (('Маленькие эскизы', 64), ('Средние эскизы', 96),
                            ('Большие эскизы', 144), ('Огромные эскизы', 200)):
            m_view.addAction(self._action(label, slot=lambda c=False, s=size: self.set_thumb_size(s)))
        m_view.addSeparator()
        self._nav_action = self._action('Скрыть/показать панель навигации', slot=self.toggle_nav)
        m_view.addAction(self._nav_action)
        m_view.addAction(self._action('Во весь экран', shortcut='F11', slot=self.toggle_fullscreen))

        m_nav = mb.addMenu('Навигация')
        m_nav.addAction(self._action('Первая страница', None, 'Home', slot=self.first_page))
        m_nav.addAction(self._action('Предыдущая страница', None, 'PgUp', slot=self.prev_page))
        m_nav.addAction(self._action('Следующая страница', None, 'PgDown', slot=self.next_page))
        m_nav.addAction(self._action('Последняя страница', None, 'End', slot=self.last_page))
        m_nav.addSeparator()
        m_nav.addAction(self._action('Добавить закладку', slot=self.add_bookmark))
        m_nav.addAction(self._action('Удалить закладку', slot=self.delete_bookmark))
        m_nav.addAction(self._action('Редактировать закладку', slot=self.edit_bookmark))
        m_nav.addSeparator()
        m_nav.addAction(self._action('Экспортировать закладки в файл', slot=self.export_bookmarks))
        m_nav.addAction(self._action('Импортировать закладки из файла', slot=self.import_bookmarks))

        m_tools = mb.addMenu('Инструменты')
        m_tools.addAction(self._action('Копировать', None, 'Ctrl+C', slot=self.copy_text))
        m_tools.addAction(self._action('Копировать текст страницы', slot=self.copy_page_text))
        m_tools.addAction(self._action('Копировать весь документ', slot=self.copy_all_text))
        m_tools.addAction(self._action('Сохранить изображение как...', slot=self.save_image_at_cursor))
        m_tools.addSeparator()
        m_tools.addAction(self._action('Поиск', None, 'Ctrl+F', slot=self.focus_find))
        m_tools.addAction(self._action('Следующее совпадение', None, 'F3', slot=self.find_forward))
        m_tools.addAction(self._action('Предыдущее совпадение', None, 'Shift+F3', slot=self.find_backward))
        m_tools.addAction(self._action('Быстрый поиск в содержании', slot=self.focus_toc_search))
        m_tools.addSeparator()
        m_tools.addAction(self._action('Экспортировать текущий документ как набор изображений', slot=self.export_images))
        m_tools.addAction(self._action('Экспортировать текущий документ в текстовый файл', slot=self.export_text))
        m_tools.addAction(self.export_md_action)
        m_tools.addAction(self.export_docx_action)
        m_tools.addAction(self._action('Экспортировать текущую страницу в файл изображения', slot=self.export_page))
        m_tools.addSeparator()
        m_tools.addAction(self._action('Настройки программы', slot=self.settings_dialog))

        m_help = mb.addMenu('Справка')
        m_help.addAction(self._action('Свойства документа', slot=self.document_properties))
        m_help.addAction(self._action('О программе', slot=self.about))

    def _build_toolbar(self):
        tb = QToolBar('Панель инструментов')
        tb.setIconSize(QSize(20, 20))
        tb.setStyleSheet('QToolBar{background:#f0f0f0;border-bottom:1px solid #cfcfcf;spacing:2px;}')
        open_ico = self._std_icon('SP_DialogOpenButton', 'SP_FileIcon')
        save_ico = self._std_icon('SP_DialogSaveButton', 'SP_DriveFDIcon')
        left = self._std_icon('SP_ArrowBack', 'SP_ArrowLeft')
        right = self._std_icon('SP_ArrowForward', 'SP_ArrowRight')
        first = self._std_icon('SP_ArrowUp', 'SP_ArrowLeft')
        last = self._std_icon('SP_ArrowDown', 'SP_ArrowRight')

        tb.addAction(self._action('Открыть', open_ico, slot=self.open_file))
        tb.addAction(self._action('Сохранить копию', save_ico, slot=self.save_copy))
        tb.addAction(self._panel_action)   # кнопка скрытия левой панели
        tb.addSeparator()
        tb.addAction(self._action('Первая', first, slot=self.first_page))
        tb.addAction(self._action('Назад', left, slot=self.prev_page))
        tb.addAction(self._action('Вперёд', right, slot=self.next_page))
        tb.addAction(self._action('Последняя', last, slot=self.last_page))
        tb.addSeparator()
        tb.addAction(self._action('Уменьшить', slot=lambda: self.zoom_by(1 / 1.2)))
        tb.addAction(self._action('1:1', shortcut='Ctrl+0', slot=self.zoom_100))
        tb.addWidget(QLabel('Масштаб:'))
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setMaximumWidth(90)
        for s in ('5%', '25%', '50%', '75%', '100%', '125%', '150%', '200%', '300%', '500%'):
            self.zoom_combo.addItem(s)
        self.zoom_combo.setCurrentText('100%')
        self.zoom_combo.activated.connect(self.on_zoom_combo)
        self.zoom_combo.lineEdit().returnPressed.connect(self.on_zoom_combo)
        tb.addWidget(self.zoom_combo)
        tb.addAction(self._action('Увеличить', slot=lambda: self.zoom_by(1.2)))
        tb.addAction(self._action('По ширине', slot=self.fit_width))
        tb.addAction(self._action('По странице', slot=self.fit_page))
        tb.addSeparator()
        tb.addAction(self._action('Повернуть', slot=lambda: self.rotate(90)))

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText('Поиск...')
        self.find_edit.setMaximumWidth(180)
        self.find_edit.returnPressed.connect(self.do_find)
        tb.addWidget(self.find_edit)
        tb.addAction(self._action('Найти', slot=self.do_find))
        self.addToolBar(tb)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_page = QLabel('Страница:')
        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setMaximumWidth(60)
        self.spin_page.valueChanged.connect(self.on_spin_page)
        self.lbl_total = QLabel('/ 1')
        self.lbl_zoom = QLabel('100%')
        self.lbl_zoom.setMinimumWidth(55)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(5, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(160)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider)
        self.lbl_format = QLabel('')
        sb.addWidget(self.lbl_page)
        sb.addWidget(self.spin_page)
        sb.addWidget(self.lbl_total)
        sb.addPermanentWidget(self.lbl_format)
        sb.addPermanentWidget(QLabel('Масштаб:'))
        sb.addPermanentWidget(self.zoom_slider)
        sb.addPermanentWidget(self.lbl_zoom)

    # -- helpers ------------------------------------------------------------
    def current_tab(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, DocumentTab) else None

    def update_status(self):
        tab = self.current_tab()
        if not tab:
            self.spin_page.setMaximum(1)
            self.spin_page.setValue(1)
            self.lbl_total.setText('/ 1')
            self.lbl_format.setText('')
            self.lbl_zoom.setText('100%')
            self.zoom_combo.blockSignals(True)
            self.zoom_combo.setCurrentText('100%')
            self.zoom_combo.blockSignals(False)
            return
        n = max(1, tab.doc.page_count)
        self.spin_page.blockSignals(True)
        self.spin_page.setMaximum(n)
        self.spin_page.setValue(tab.page + 1)
        self.spin_page.blockSignals(False)
        self.lbl_total.setText('/ %d' % n)
        self.lbl_format.setText(tab.doc.format_name())
        pct = '%d%%' % round(tab.zoom * 100)
        self.lbl_zoom.setText(pct)
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(pct)
        self.zoom_combo.blockSignals(False)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(max(5, min(500, round(tab.zoom * 100))))
        self.zoom_slider.blockSignals(False)
        self.setWindowTitle('%s - STDU Viewer' % tab.doc.name)

    def on_tab_changed(self, idx):
        self._fill_nav()
        self.update_status()

    # -- file operations ----------------------------------------------------
    def open_file(self, path=None):
        if not path:
            path, _f = QFileDialog.getOpenFileName(self, 'Открыть документ', '', ALL_FILTER)
        if not path:
            return
        try:
            doc = open_document(path)
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось открыть файл:\n%s\n\n%s' % (path, e))
            return
        if getattr(doc, 'needs_pass', False):
            pw, ok = QInputDialog.getText(
                self, 'Пароль', "'%s' защищён. Введите пароль:" % doc.name,
                QLineEdit.Password)
            if not ok or not doc.authenticate(pw):
                QMessageBox.warning(self, 'Ошибка', 'Неправильный пароль.')
                doc.close()
                return
        tab = DocumentTab(doc, self)
        tab.pageChanged.connect(self.update_status)
        idx = self.tabs.addTab(tab, doc.name)
        self.tabs.setCurrentIndex(idx)
        self._tabs.append(tab)
        self._fill_nav()
        self.update_status()
        if path in self.recent:
            self.recent.remove(path)
        self.recent.insert(0, path)
        self.recent = self.recent[:12]
        self._rebuild_recent()

    def _rebuild_recent(self):
        self.recent_menu.clear()
        self.recent_list.clear()
        for p in self.recent:
            if not os.path.isfile(p):
                continue
            self.recent_menu.addAction(self._action(
                p, slot=lambda checked=False, p=p: self.open_file(p)))
            it = QListWidgetItem(os.path.basename(p))
            it.setData(Qt.UserRole, p)
            it.setToolTip(p)
            it.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
            self.recent_list.addItem(it)
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(
            self._action('Очистить список', slot=self.clear_recent))
        try:
            os.makedirs(os.path.dirname(RECENT_FILE), exist_ok=True)
            with open(RECENT_FILE, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(self.recent))
        except Exception:
            pass

    def on_recent_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.open_file(path)

    def on_recent_context_menu(self, pos):
        """Правый клик в «Недавних документах»: открыть / удалить / очистить."""
        item = self.recent_list.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            path = item.data(Qt.UserRole)
            menu.addAction('Открыть', lambda: self.open_file(path))
            menu.addAction('Удалить из списка',
                           lambda: self.remove_recent(path))
            menu.addSeparator()
        menu.addAction('Очистить недавние документы', self.clear_recent)
        menu.exec_(self.recent_list.viewport().mapToGlobal(pos))

    def remove_recent(self, path):
        if path in self.recent:
            self.recent.remove(path)
        self._rebuild_recent()

    def clear_recent(self):
        self.recent = []
        self._rebuild_recent()

    def open_last_recent(self):
        """Открывает последний PDF (или любой последний документ) при запуске."""
        candidates = [p for p in self.recent if p and os.path.isfile(p)]
        if not candidates:
            return None
        pdfs = [p for p in candidates
                if Path(p).suffix.lower() in PDF_EXTS]
        target = pdfs[0] if pdfs else candidates[0]
        self.open_file(target)
        return target

    def close_tab(self, idx):
        w = self.tabs.widget(idx)
        if isinstance(w, DocumentTab):
            w.prepare_close()
            try:
                w.doc.close()
            except Exception:
                pass
            if hasattr(w.doc, '_tmpdir'):
                shutil.rmtree(w.doc._tmpdir, ignore_errors=True)
            if w in self._tabs:
                self._tabs.remove(w)
        self.tabs.removeTab(idx)
        self._fill_nav()
        self.update_status()

    def close_current(self):
        if self.tabs.count():
            self.close_tab(self.tabs.currentIndex())

    def save_copy(self):
        tab = self.current_tab()
        if not tab:
            return
        path, _f = QFileDialog.getSaveFileName(self, 'Сохранить копию', tab.doc.name)
        if path:
            try:
                shutil.copyfile(tab.doc.path, path)
            except Exception as e:
                QMessageBox.warning(self, 'Ошибка', str(e))

    def print_current(self):
        tab = self.current_tab()
        if not tab:
            return
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() != QPrintDialog.Accepted:
            return
        self._print_document(tab, printer)

    def print_to_pdf(self, tab, path):
        """Печать документа в PDF-файл (используется и в тестах)."""
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self._print_document(tab, printer)

    def _print_document(self, tab, printer):
        if tab.doc.kind == 'flow':
            tab.browser.print_(printer)
            return
        painter = QPainter(printer)
        rect = painter.viewport()
        for i in range(tab.doc.page_count):
            img = tab.doc.render(i, 1.0, tab.rotation)
            if img.isNull():
                continue
            if i:
                printer.newPage()
            scaled = img.scaled(rect.size(), Qt.KeepAspectRatio,
                                Qt.SmoothTransformation)
            painter.drawImage(rect, scaled)
        painter.end()

    # -- navigation ---------------------------------------------------------
    def first_page(self):
        t = self.current_tab()
        if t:
            t.goto(0)

    def prev_page(self):
        t = self.current_tab()
        if t:
            t.prev_page()

    def next_page(self):
        t = self.current_tab()
        if t:
            t.next_page()

    def last_page(self):
        t = self.current_tab()
        if t:
            t.goto(t.doc.page_count - 1)

    def on_spin_page(self, value):
        t = self.current_tab()
        if t:
            t.goto(value - 1)

    def zoom_by(self, factor):
        t = self.current_tab()
        if t:
            t.set_zoom(t.zoom * factor)

    def on_zoom_slider(self, value):
        t = self.current_tab()
        if t and abs(t.zoom * 100 - value) > 1:
            t.set_zoom(value / 100.0)

    def fit_width(self):
        t = self.current_tab()
        if t:
            w = t.viewport_width() or 800
            probe = t.doc.render(t.page, 1.0, t.rotation)
            z = (w - 24) / probe.width() if not probe.isNull() else 1.0
            t.set_zoom(z, 'width')

    def fit_page(self):
        t = self.current_tab()
        if t:
            w, h = t.viewport_width() or 800, t.viewport_height() or 600
            probe = t.doc.render(t.page, 1.0, t.rotation)
            z = 1.0
            if not probe.isNull():
                z = min((w - 24) / probe.width(), (h - 24) / probe.height())
            t.set_zoom(z, 'page')

    def rotate(self, delta):
        t = self.current_tab()
        if t:
            t.rotate(delta)

    # -- navigation panel ---------------------------------------------------
    def _fill_nav(self):
        self.toc_tree.clear()
        self.thumb_list.clear()
        self.bookmark_list.clear()
        tab = self.current_tab()
        if not tab:
            return
        for level, title, target in tab.doc.toc():
            item = QTreeWidgetItem([str(title)])
            item.setData(0, Qt.UserRole, target)
            self.toc_tree.addTopLevelItem(item)
        if self.toc_tree.topLevelItemCount() == 0:
            for i in range(tab.doc.page_count):
                item = QTreeWidgetItem(['Страница %d' % (i + 1)])
                item.setData(0, Qt.UserRole, i)
                self.toc_tree.addTopLevelItem(item)
        n = tab.doc.page_count
        for i in range(min(n, 40)):
            img = tab.doc.render(i, 0.22, 0)
            if img.isNull():
                continue
            it = QListWidgetItem(QIcon(QPixmap.fromImage(img)), 'Стр. %d' % (i + 1))
            it.setData(Qt.UserRole, i)
            self.thumb_list.addItem(it)

    def on_toc_clicked(self, item, col):
        tab = self.current_tab()
        if not tab:
            return
        target = item.data(0, Qt.UserRole)
        if isinstance(target, int):
            tab.goto(target)
        elif tab.browser and isinstance(target, str) and target:
            tab.scroll_to_anchor(target)

    def on_thumb_clicked(self, item):
        tab = self.current_tab()
        if tab:
            tab.goto(int(item.data(Qt.UserRole)))

    def on_bookmark_clicked(self, item):
        tab = self.current_tab()
        if tab:
            tab.goto(int(item.data(Qt.UserRole)))

    def add_bookmark(self):
        tab = self.current_tab()
        if tab:
            self.bookmark_list.addItem(QListWidgetItem(
                '%s — стр. %d' % (tab.doc.name, tab.page + 1)))
            self.bookmark_list.item(self.bookmark_list.count() - 1).setData(
                Qt.UserRole, tab.page)
            self.nav.setCurrentWidget(self.bookmark_list)

    # -- расширенный функционал (из ресурсов оригинала) ---------------------
    def filter_toc(self, text):
        for i in range(self.toc_tree.topLevelItemCount()):
            it = self.toc_tree.topLevelItem(i)
            it.setHidden(bool(text) and text.lower() not in it.text(0).lower())

    def focus_toc_search(self):
        self.nav.setCurrentWidget(self.toc_tab)
        self.toc_search.setFocus()
        self.toc_search.selectAll()

    def fit_height(self):
        t = self.current_tab()
        if t and t.view:
            probe = t.doc.render(t.page, 1.0, t.rotation)
            h = t.viewport_height() or 600
            z = (h - 24) / probe.height() if not probe.isNull() else 1.0
            t.set_zoom(z, 'page')

    def zoom_100(self):
        t = self.current_tab()
        if t:
            t.set_zoom(1.0)

    def on_zoom_combo(self, *args):
        text = self.zoom_combo.currentText().strip()
        m = re.match(r'(\d+)\s*%?', text)
        if m:
            t = self.current_tab()
            if t:
                t.set_zoom(int(m.group(1)) / 100.0)

    def set_mode(self, mode):
        for k, a in self._mode_actions.items():
            a.setChecked(k == mode)
        t = self.current_tab()
        if t:
            t.set_mode(mode)

    def set_thumb_size(self, size):
        self.thumb_list.setIconSize(QSize(size, int(size * 1.33)))

    def toggle_continuous(self, checked=None):
        """Включает/выключает непрерывный просмотр (листание колесом)."""
        if checked is None:
            checked = not self.continuous
        self.continuous = bool(checked)
        for tab in self._tabs:
            tab.continuous = self.continuous

    def _on_nav_visibility(self, visible):
        """Держит галочку меню и кнопку панели в синхроне с её реальным видом."""
        action = getattr(self, '_panel_action', None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.setText(('Скрыть' if visible else 'Показать') + ' панель навигации')
        action.setToolTip(('Скрыть' if visible else 'Показать') +
                          ' левую панель (F6)')
        action.blockSignals(False)

    def toggle_nav(self, checked=None):
        visible = not self.nav_dock.isVisible()
        self.nav_dock.setVisible(visible)
        self._on_nav_visibility(visible)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def delete_bookmark(self):
        row = self.bookmark_list.currentRow()
        if row >= 0:
            self.bookmark_list.takeItem(row)

    def edit_bookmark(self):
        it = self.bookmark_list.currentItem()
        if not it:
            return
        text, ok = QInputDialog.getText(self, 'Редактировать закладку', 'Название:', text=it.text())
        if ok and text:
            it.setText(text)

    def export_bookmarks(self):
        path, _f = QFileDialog.getSaveFileName(
            self, 'Экспорт закладок', 'bookmarks.txt',
            'Текстовые файлы (*.txt);;XML-файлы (*.xml)')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for i in range(self.bookmark_list.count()):
                    it = self.bookmark_list.item(i)
                    f.write('%s\t%s\n' % (it.text(), it.data(Qt.UserRole)))
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    def import_bookmarks(self):
        path, _f = QFileDialog.getOpenFileName(
            self, 'Импорт закладок', '', 'Текстовые файлы (*.txt);;XML-файлы (*.xml)')
        if not path:
            return
        try:
            for line in open(path, encoding='utf-8', errors='ignore'):
                parts = line.rstrip('\n').split('\t')
                if len(parts) == 2:
                    it = QListWidgetItem(parts[0])
                    it.setData(Qt.UserRole, int(parts[1]))
                    self.bookmark_list.addItem(it)
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    def export_images(self):
        t = self.current_tab()
        if not t or not t.view:
            return
        d = QFileDialog.getExistingDirectory(self, 'Выберите папку для сохранения')
        if not d:
            return
        n = t.doc.page_count
        for i in range(n):
            t.doc.render(i, 1.5, 0).save(os.path.join(d, 'page_%04d.png' % (i + 1)))
        QMessageBox.information(self, 'Готово', 'Экспортировано страниц: %d' % n)

    def export_text(self):
        t = self.current_tab()
        if not t:
            return
        path, _f = QFileDialog.getSaveFileName(
            self, 'Экспорт в текст', t.doc.name + '.txt', 'Текстовые файлы (*.txt)')
        if not path:
            return
        try:
            if t.doc.kind == 'flow':
                txt = re.sub(r'<[^>]+>', '', t.doc.html())
            else:
                txt = '\n\n'.join('--- Страница %d ---\n%s' % (i + 1, t.doc.text(i))
                                  for i in range(t.doc.page_count))
            open(path, 'w', encoding='utf-8').write(txt)
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    # -- экспорт в Markdown / DOCX --------------------------------------
    def _export_html(self, tab):
        """Собирает HTML всего документа — общий источник для MD и DOCX."""
        if tab.doc.kind == 'flow':
            return tab.doc.html() or '<html><body></body></html>'
        parts = ['<!DOCTYPE html><html><head><meta charset="utf-8">'
                 '<title>%s</title></head><body>' % html_mod.escape(tab.doc.name)]
        for i in range(tab.doc.page_count):
            parts.append('<h2>Страница %d</h2>' % (i + 1))
            try:
                text = tab.doc.text(i) or ''
            except Exception:
                text = ''
            lines = []
            for line in text.splitlines():
                if line.strip():
                    lines.append(html_mod.escape(line))
                elif lines:
                    parts.append('<p>%s</p>' % '<br/>'.join(lines))
                    lines = []
            if lines:
                parts.append('<p>%s</p>' % '<br/>'.join(lines))
        parts.append('</body></html>')
        return '\n'.join(parts)

    def _html_to_markdown(self, source):
        if shutil.which('pandoc'):
            try:
                res = subprocess.run(
                    ['pandoc', '-f', 'html', '-t', 'gfm'],
                    input=source.encode('utf-8'), stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=120)
                if res.returncode == 0:
                    return res.stdout.decode('utf-8', 'replace')
            except Exception:
                pass
        try:
            import html2text
            conv = html2text.HTML2Text()
            conv.body_width = 0
            conv.unicode_snob = True
            return conv.handle(source)
        except Exception:
            return re.sub(r'<[^>]+>', '', source)

    def _html_to_docx(self, source, path):
        """Резервный вариант без pandoc: простой HTML-парсер + python-docx."""
        from docx import Document

        class Blocks(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.blocks = []
                self.kind = 'paragraph'
                self.level = 0
                self.buf = []

            def flush(self):
                text = ''.join(self.buf).strip()
                if text:
                    self.blocks.append((self.kind, self.level, text))
                self.buf = []
                self.kind, self.level = 'paragraph', 0

            def handle_starttag(self, tag, attrs):
                if re.fullmatch(r'h[1-6]', tag):
                    self.flush()
                    self.kind, self.level = 'heading', int(tag[1])
                elif tag in ('p', 'div', 'tr', 'br'):
                    self.flush()
                elif tag == 'li':
                    self.flush()
                    self.kind = 'list_item'

            def handle_endtag(self, tag):
                if re.fullmatch(r'h[1-6]', tag) or tag in ('p', 'div', 'li', 'tr'):
                    self.flush()

            def handle_data(self, data):
                self.buf.append(data)

        blocks = Blocks()
        blocks.feed(source)
        blocks.flush()
        doc = Document()
        for kind, level, text in blocks.blocks:
            if kind == 'heading':
                doc.add_heading(text, level=min(level, 9))
            elif kind == 'list_item':
                doc.add_paragraph(text, style='List Bullet')
            else:
                doc.add_paragraph(text)
        doc.save(path)

    def export_markdown(self):
        t = self.current_tab()
        if not t:
            return
        default = Path(t.doc.name).stem + '.md'
        path, _f = QFileDialog.getSaveFileName(
            self, 'Экспорт в Markdown', default,
            'Markdown (*.md);;Текстовые файлы (*.txt)')
        if not path:
            return
        if not Path(path).suffix:
            path += '.md'
        try:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(self._html_to_markdown(self._export_html(t)))
            QMessageBox.information(self, 'Готово', 'Файл сохранён:\n%s' % path)
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    def export_docx(self):
        t = self.current_tab()
        if not t:
            return
        default = Path(t.doc.name).stem + '.docx'
        path, _f = QFileDialog.getSaveFileName(
            self, 'Экспорт в DOCX', default, 'Документ Word (*.docx)')
        if not path:
            return
        if not Path(path).suffix:
            path += '.docx'
        source = self._export_html(t)
        ok = False
        if shutil.which('pandoc'):
            try:
                res = subprocess.run(
                    ['pandoc', '-f', 'html', '-t', 'docx', '-o', path],
                    input=source.encode('utf-8'), stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, timeout=180)
                ok = (res.returncode == 0 and os.path.isfile(path)
                      and os.path.getsize(path) > 0)
            except Exception:
                ok = False
        if not ok:
            try:
                self._html_to_docx(source, path)
            except Exception as e:
                QMessageBox.warning(self, 'Ошибка', str(e))
                return
        QMessageBox.information(self, 'Готово', 'Файл сохранён:\n%s' % path)

    def export_page(self):
        t = self.current_tab()
        if not t or not t.view:
            return
        path, _f = QFileDialog.getSaveFileName(
            self, 'Экспорт страницы', 'page.png', 'PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)')
        if path:
            t.doc.render(t.page, 2.0, t.rotation).save(path)

    def settings_dialog(self):
        QMessageBox.information(
            self, 'Настройки программы',
            'Язык интерфейса и режимы задаются в меню Вид.\n'
            'Шрифты текстовых документов настраиваются через стили Qt.')

    def document_properties(self):
        t = self.current_tab()
        if not t:
            return
        info = QFileInfo(t.doc.path)
        QMessageBox.information(
            self, 'Свойства документа',
            '<b>%s</b><br><br>Путь: %s<br>Формат: %s<br>Страниц: %d<br>Размер: %s' % (
                html_mod.escape(t.doc.name), html_mod.escape(t.doc.path),
                t.doc.format_name(), t.doc.page_count, self._size(info.size())))

    def _size(self, n):
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if n < 1024:
                return '%.1f %s' % (n, unit)
            n /= 1024
        return '%.1f ТБ' % n

    # -- копирование ---------------------------------------------------------
    def copy_text(self):
        """Ctrl+C: не трогаем стандартное копирование из полей ввода."""
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QTextBrowser, QComboBox)):
            if hasattr(focus, 'copy'):
                focus.copy()
            return
        tab = self.current_tab()
        if tab:
            tab.copy_selection()

    def copy_page_text(self):
        tab = self.current_tab()
        if tab:
            text = tab.page_text()
            if text:
                QApplication.clipboard().setText(text)

    def copy_all_text(self):
        tab = self.current_tab()
        if tab:
            text = tab.all_text()
            if text:
                QApplication.clipboard().setText(text)

    def save_image_at_cursor(self):
        tab = self.current_tab()
        if not tab or tab.view is None:
            return
        pos = tab.view.label.mapFromGlobal(QCursor.pos())
        image = tab.image_at(pos)
        if image is None:
            QMessageBox.information(
                self, 'Изображение',
                'Наведите курсор на изображение на странице и повторите действие.')
            return
        pno, xref = image
        tab.save_image(pno, xref)

    # -- find / misc --------------------------------------------------------
    def focus_find(self):
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def do_find(self, next_only=False):
        tab = self.current_tab()
        text = self.find_edit.text().strip()
        if tab and text:
            if next_only and getattr(tab, '_find_matches', None) and \
                    tab._find_text == text:
                found = tab.find_next(1)
            else:
                found = tab.find_text(text)
            self.find_edit.setStyleSheet(
                'background:%s;' % ('#ddffdd' if found else '#ffdddd'))
            QTimer.singleShot(900, lambda: self.find_edit.setStyleSheet(''))

    def find_forward(self):
        tab = self.current_tab()
        if tab:
            tab.find_next(1)
            self.update_status()

    def find_backward(self):
        tab = self.current_tab()
        if tab:
            tab.find_next(-1)
            self.update_status()

    def about(self):
        QMessageBox.about(self, 'О программе',
            '<b>STDU Reader</b><br><br>'
            'Нативный Linux-ридер с интерфейсом в стиле STDU Viewer.<br>'
            'Поддерживает PDF, DjVu, EPUB, FB2, MOBI/AZW, XPS, TIFF,<br>'
            'изображения, CBZ/CBR, DOCX/ODT/RTF, HTML, Markdown, TXT.<br><br>'
            'Работает без Wine.')

    # -- drag & drop / keys -------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_file(url.toLocalFile())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.find_edit.hasFocus():
            self.find_edit.clear()
            return
        super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('STDU Viewer')
    if os.path.exists(ICON_FILE):
        app.setWindowIcon(QIcon(ICON_FILE))
    app.setStyle('Fusion')
    w = MainWindow()
    opened_from_args = False
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if os.path.isfile(arg):
                w.open_file(arg)
                opened_from_args = True
    # Если файл не передан явно — открываем последний документ из списка
    # недавних (предпочтительно PDF), как просил пользователь.
    if not opened_from_args:
        w.open_last_recent()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
