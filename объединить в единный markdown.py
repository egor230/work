import sys
import subprocess
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QVBoxLayout, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor


class MarkdownMerger(QWidget):
    """Объединение .md файлов из выбранной папки в один документ."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Markdown Merger")
        self.setGeometry(650, 300, 550, 220)

        self.apply_light_theme()

        # Виджеты для выбора папки с .md файлами
        self.src_label = QLabel("Папка с .md файлами:")
        self.src_path = QLineEdit()
        self.select_src_btn = QPushButton("Выбрать папку")
        self.select_src_btn.clicked.connect(self.select_src_dir)

        # Виджеты для выбора выходной папки
        self.dst_label = QLabel("Папка для сохранения:")
        self.dst_path = QLineEdit()
        self.select_dst_btn = QPushButton("Выбрать папку")
        self.select_dst_btn.clicked.connect(self.select_dst_dir)

        # Кнопка запуска объединения
        self.merge_btn = QPushButton("Объединить")
        self.merge_btn.clicked.connect(self.merge_files)

        # Статус-бар
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Готово")

        # Лэйауты
        src_layout = QHBoxLayout()
        src_layout.addWidget(self.src_path)
        src_layout.addWidget(self.select_src_btn)

        dst_layout = QHBoxLayout()
        dst_layout.addWidget(self.dst_path)
        dst_layout.addWidget(self.select_dst_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.src_label)
        layout.addLayout(src_layout)
        layout.addWidget(self.dst_label)
        layout.addLayout(dst_layout)
        layout.addWidget(self.merge_btn)
        layout.addWidget(self.status_bar)

        self.setLayout(layout)

    def apply_light_theme(self):
        """Светлая тема через QPalette."""
        app = QApplication.instance()
        app.setStyle('Fusion')

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.Button, QColor(220, 220, 220))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

        app.setPalette(palette)

    def select_src_dir(self):
        """Выбор исходной папки через zenity (с учётом уже указанной папки назначения)."""
        dst = self.dst_path.text()
        cmd_args = ['zenity', '--file-selection', '--directory']
        if dst and os.path.isdir(dst):
            cmd_args.append(f'--filename={dst}')

        cmd = subprocess.run(cmd_args, capture_output=True, text=True)
        if cmd.returncode == 0:
            self.src_path.setText(cmd.stdout.strip())

    def select_dst_dir(self):
        """Выбор папки назначения через zenity (с учётом уже указанной исходной папки)."""
        src = self.src_path.text()
        cmd_args = ['zenity', '--file-selection', '--directory']
        if src and os.path.isdir(src):
            cmd_args.append(f'--filename={src}')

        cmd = subprocess.run(cmd_args, capture_output=True, text=True)
        if cmd.returncode == 0:
            self.dst_path.setText(cmd.stdout.strip())

    def merge_files(self):
        """Основная логика: поиск .md файлов (включая имена с пробелами и нелатинскими символами),
        объединение с заголовками и разделителями."""
        src_dir = self.src_path.text().strip()
        dst_dir = self.dst_path.text().strip()

        if not src_dir or not dst_dir:
            QMessageBox.critical(self, "Ошибка", "Укажите обе директории.")
            return

        src_path = Path(src_dir)
        if not src_path.is_dir():
            QMessageBox.critical(self, "Ошибка", f"Папка не найдена: {src_dir}")
            return

        # Создаём выходную папку, если её нет
        dst_path = Path(dst_dir)
        dst_path.mkdir(parents=True, exist_ok=True)

        # Находим все .md файлы (без учёта регистра) в указанной папке, исключая поддиректории
        md_files = []
        for item in src_path.iterdir():
            if item.is_file() and item.suffix.lower() == '.md':
                md_files.append(item)

        if not md_files:
            self.status_bar.showMessage("Не найдено .md файлов")
            QMessageBox.information(
                self, "Готово",
                f"В папке\n{src_dir}\nне найдено ни одного .md файла."
            )
            return

        # Сортируем по имени файла (лексикографически)
        md_files.sort(key=lambda p: p.name)

        out_file = dst_path / "all_outfiles.md"
        merged_count = 0
        total = len(md_files)

        try:
            with open(out_file, "w", encoding="utf-8") as out:
                for idx, file_path in enumerate(md_files, 1):
                    # Обновляем статус-бар
                    progress_text = f"Обработка {idx} из {total}: {file_path.name}"
                    self.status_bar.showMessage(progress_text)
                    QApplication.instance().processEvents()

                    # Разделитель между файлами (кроме первого)
                    if idx > 1:
                        out.write("\n\n---\n\n")

                    # Заголовок с именем исходного файла
                    out.write(f"# {file_path.name}\n\n")

                    # Чтение содержимого с поддержкой разных кодировок
                    content = self._read_md_file(file_path)
                    if content is not None:
                        out.write(content)
                        merged_count += 1
                    else:
                        out.write(f"> **Ошибка чтения файла:** не удалось прочитать {file_path.name}\n")

            self.status_bar.showMessage(f"Объединено {merged_count} из {total} файлов")
            QMessageBox.information(
                self, "Готово",
                f"Объединено {merged_count} файл(ов) из {total}.\nРезультат:\n{out_file}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось записать итоговый файл:\n{e}")

    def _read_md_file(self, file_path: Path) -> str | None:
        """Читает .md файл, убирая лишние пустые строки в конце.
        При ошибке кодировки пробует другие популярные кодировки."""
        encodings = ['utf-8', 'cp1251', 'latin-1']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                # Убираем символы перевода строки в конце, но не внутри
                content = content.rstrip('\n')
                # Добавляем финальный перевод строки для корректного отделения от следующего файла
                return content + '\n'
            except UnicodeDecodeError:
                continue
            except Exception:
                return None
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MarkdownMerger()
    window.show()
    sys.exit(app.exec())