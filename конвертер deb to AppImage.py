import sys
import subprocess
import os
import shutil
import stat
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DebToAppImageThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, deb_path, output_dir):
        super().__init__()
        self.deb_path = deb_path
        self.output_dir = output_dir
        self.work_dir = None
        self.appdir_path = None

    def run(self):
        try:
            # Проверка наличия нужных инструментов
            if not shutil.which('dpkg-deb'):
                self.log_signal.emit("❌ Не найден dpkg-deb. Установи: sudo apt install dpkg")
                self.finished_signal.emit(False)
                return

            if not shutil.which('ar'):
                self.log_signal.emit("❌ Не найден ar. Установи: sudo apt install binutils")
                self.finished_signal.emit(False)
                return

            # Скачиваем appimagetool, если его нет
            appimagetool = self._ensure_appimagetool()
            if not appimagetool:
                self.finished_signal.emit(False)
                return

            self.log_signal.emit(f"📦 Обрабатываю: {os.path.basename(self.deb_path)}")

            # Создаём временную папку
            self.work_dir = tempfile.mkdtemp(prefix='deb2appimage_')
            self.log_signal.emit(f"📁 Временная папка: {self.work_dir}")

            # Извлекаем control-информацию (для имени, версии, описания)
            control_dir = os.path.join(self.work_dir, 'control')
            os.makedirs(control_dir, exist_ok=True)
            self._run_cmd(['dpkg-deb', '-e', self.deb_path, control_dir])

            # Читаем метаданные из control файла
            meta = self._parse_control(os.path.join(control_dir, 'control'))
            pkg_name = meta.get('Package', 'app')
            pkg_version = meta.get('Version', '1.0')
            pkg_desc = meta.get('Description', pkg_name)
            pkg_arch = meta.get('Architecture', 'amd64')

            self.log_signal.emit(f"📋 Пакет: {pkg_name} v{pkg_version} ({pkg_arch})")

            # Создаём AppDir структуру
            self.appdir_path = os.path.join(self.work_dir, f'{pkg_name}.AppDir')
            os.makedirs(self.appdir_path, exist_ok=True)

            # Извлекаем содержимое deb пакета в AppDir
            self.log_signal.emit("📤 Извлекаю содержимое пакета...")
            self._run_cmd(['dpkg-deb', '-x', self.deb_path, self.appdir_path])

            # Определяем главный исполняемый файл
            exec_path = self._find_executable(self.appdir_path, meta)
            if not exec_path:
                self.log_signal.emit("❌ Не удалось найти исполняемый файл в пакете")
                self.finished_signal.emit(False)
                return

            self.log_signal.emit(f"🎯 Исполняемый файл: {exec_path}")

            # Создаём .desktop файл, если его нет
            self._ensure_desktop_file(self.appdir_path, pkg_name, pkg_desc, exec_path)

            # Копируем зависимости (библиотеки)
            self.log_signal.emit("🔗 Собираю зависимости...")
            self._bundle_dependencies(self.appdir_path, exec_path)

            # Создаём AppRun (точку входа)
            self._create_apprun(self.appdir_path, exec_path)

            # Определяем имя выходного файла
            output_name = f"{pkg_name}-{pkg_version}-{pkg_arch}.AppImage"
            output_path = os.path.join(self.output_dir, output_name)

            # Упаковываем в AppImage
            self.log_signal.emit("📦 Упаковываю в AppImage...")
            env = os.environ.copy()
            env['ARCH'] = pkg_arch if pkg_arch != 'all' else 'x86_64'

            result = subprocess.run(
                [appimagetool, self.appdir_path, output_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            for line in result.stdout.splitlines():
                self.log_signal.emit(line)

            if result.returncode == 0 and os.path.exists(output_path):
                # Делаем исполняемым
                os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                self.log_signal.emit(f"✅ Успешно создано: {output_name}")
                self.log_signal.emit(f"📊 Размер: {size_mb:.1f} МБ")
                self.log_signal.emit(f"🚀 Запуск: ./{output_name}")
                self.finished_signal.emit(True)
            else:
                self.log_signal.emit("❌ Ошибка при создании AppImage")
                self.finished_signal.emit(False)

        except Exception as e:
            self.log_signal.emit(f"❌ Критическая ошибка: {e}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False)
        finally:
            # Удаляем временную папку
            if self.work_dir and os.path.exists(self.work_dir):
                try:
                    shutil.rmtree(self.work_dir)
                    self.log_signal.emit("🧹 Временные файлы удалены")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Не удалось удалить временные файлы: {e}")

    def _ensure_appimagetool(self):
        """Скачивает appimagetool, если его нет в системе"""
        # Сначала ищем в системе
        if shutil.which('appimagetool'):
            return shutil.which('appimagetool')

        # Ищем в домашней папке
        local_path = os.path.expanduser('~/.local/bin/appimagetool')
        if os.path.exists(local_path):
            return local_path

        self.log_signal.emit("⬇️ appimagetool не найден, скачиваю...")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        url = 'https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage'
        try:
            subprocess.run(
                ['wget', '-q', '--show-progress', '-O', local_path, url],
                check=True
            )
            os.chmod(local_path, os.stat(local_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self.log_signal.emit(f"✅ appimagetool скачан в {local_path}")
            return local_path
        except Exception as e:
            self.log_signal.emit(f"❌ Не удалось скачать appimagetool: {e}")
            self.log_signal.emit("💡 Установи вручную: sudo apt install appimagetool")
            return None

    def _run_cmd(self, cmd):
        """Запускает команду и логирует вывод"""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.splitlines():
                self.log_signal.emit(f"  {line}")
        if result.returncode != 0 and result.stderr:
            self.log_signal.emit(f"⚠️ {result.stderr.strip()}")
        return result

    def _parse_control(self, control_file):
        """Парсит control-файл deb пакета"""
        meta = {}
        if not os.path.exists(control_file):
            return meta
        try:
            with open(control_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if ':' in line:
                        key, _, value = line.partition(':')
                        meta[key.strip()] = value.strip()
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка чтения control: {e}")
        return meta

    def _find_executable(self, appdir, meta):
        """Ищет главный исполняемый файл"""
        # Сначала смотрим в control-файле
        exec_field = meta.get('Executable', '') or meta.get('Exec', '')
        if exec_field:
            # Ищем по имени
            for root, _, files in os.walk(appdir):
                for f in files:
                    if f == os.path.basename(exec_field):
                        full = os.path.join(root, f)
                        if os.access(full, os.X_OK):
                            return full

        # Ищем в стандартных местах
        search_dirs = ['usr/bin', 'usr/games', 'usr/sbin', 'opt', 'bin']
        for d in search_dirs:
            full_dir = os.path.join(appdir, d)
            if os.path.exists(full_dir):
                for f in os.listdir(full_dir):
                    full = os.path.join(full_dir, f)
                    if os.path.isfile(full) and os.access(full, os.X_OK):
                        # Проверяем, что это ELF-бинарник, а не скрипт
                        try:
                            with open(full, 'rb') as bf:
                                magic = bf.read(4)
                                if magic == b'\x7fELF':
                                    return full
                        except:
                            continue
        return None

    def _ensure_desktop_file(self, appdir, pkg_name, pkg_desc, exec_path):
        """Создаёт .desktop файл, если его нет"""
        desktop_dir = os.path.join(appdir, 'usr', 'share', 'applications')
        desktop_files = []
        if os.path.exists(desktop_dir):
            desktop_files = [f for f in os.listdir(desktop_dir) if f.endswith('.desktop')]

        if desktop_files:
            # Копируем в корень AppDir
            src = os.path.join(desktop_dir, desktop_files[0])
            dst = os.path.join(appdir, desktop_files[0])
            shutil.copy2(src, dst)
            self.log_signal.emit(f"📄 Используем существующий .desktop: {desktop_files[0]}")
            return

        # Создаём свой .desktop
        self.log_signal.emit("📄 Создаю .desktop файл...")
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={pkg_name}
Comment={pkg_desc}
Exec={os.path.basename(exec_path)}
Icon={pkg_name}
Categories=Utility;
"""
        desktop_path = os.path.join(appdir, f'{pkg_name}.desktop')
        with open(desktop_path, 'w', encoding='utf-8') as f:
            f.write(desktop_content)

    def _bundle_dependencies(self, appdir, exec_path):
        """Копирует разделяемые библиотеки в AppDir"""
        lib_dir = os.path.join(appdir, 'usr', 'lib')
        os.makedirs(lib_dir, exist_ok=True)

        try:
            result = subprocess.run(
                ['ldd', exec_path],
                capture_output=True, text=True
            )
            libs_copied = 0
            for line in result.stdout.splitlines():
                if '=>' in line:
                    parts = line.split('=>')
                    if len(parts) >= 2:
                        path_part = parts[1].strip().split()[0]
                        if path_part and os.path.exists(path_part):
                            # Не копируем системные библиотеки (glibc, ld-linux)
                            if any(x in path_part for x in ['ld-linux', 'libc.so', 'libm.so',
                                                            'libpthread', 'libdl.so', 'librt.so']):
                                continue
                            dst = os.path.join(lib_dir, os.path.basename(path_part))
                            if not os.path.exists(dst):
                                try:
                                    shutil.copy2(path_part, dst)
                                    libs_copied += 1
                                except Exception as e:
                                    self.log_signal.emit(f"⚠️ Не удалось скопировать {path_part}: {e}")

            self.log_signal.emit(f"📚 Скопировано библиотек: {libs_copied}")
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка при сборе зависимостей: {e}")

    def _create_apprun(self, appdir, exec_path):
        """Создаёт AppRun - точку входа"""
        apprun_path = os.path.join(appdir, 'AppRun')
        exec_basename = os.path.basename(exec_path)

        # Относительный путь от корня AppDir
        rel_path = os.path.relpath(exec_path, appdir)

        content = f"""#!/bin/bash
HERE="$(dirname "$(readlink -f "${{0}}")")"
export LD_LIBRARY_PATH="${{HERE}}/usr/lib/:${{HERE}}/lib/:${{LD_LIBRARY_PATH}}"
export PATH="${{HERE}}/usr/bin/:${{HERE}}/bin/:${{PATH}}"
export XDG_DATA_DIRS="${{HERE}}/usr/share/:${{XDG_DATA_DIRS}}"
exec "${{HERE}}/{rel_path}" "$@"
"""
        with open(apprun_path, 'w') as f:
            f.write(content)
        os.chmod(apprun_path, os.stat(apprun_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.log_signal.emit("🚀 AppRun создан")


class SimpleDebToAppImage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('DEB → AppImage Converter')
        self.setFixedSize(500, 400)

        layout = QVBoxLayout()

        self.btn_select = QPushButton('Выбрать .deb пакет')
        self.btn_select.clicked.connect(self.select_deb)
        layout.addWidget(self.btn_select)

        self.status_label = QLabel('Пакет не выбран')
        layout.addWidget(self.status_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.btn_start = QPushButton('Создать AppImage')
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self.start_process)
        layout.addWidget(self.btn_start)

        self.setLayout(layout)

    def select_deb(self):
        """Используем zenity для выбора .deb файла"""
        cmd = ['zenity', '--file-selection', '--file-filter=DEB пакеты | *.deb',
               '--title=Выберите .deb пакет']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.deb_path = result.stdout.strip()
            self.status_label.setText(f'Выбрано: {os.path.basename(self.deb_path)}')
            self.btn_start.setEnabled(True)

    def start_process(self):
        """Выбор места сохранения и запуск конвертации"""
        # Предлагаем имя по умолчанию на основе имени пакета
        default_name = os.path.basename(self.deb_path).replace('.deb', '.AppImage')
        cmd = ['zenity', '--file-selection', '--save', '--confirm-overwrite',
               f'--filename={default_name}', '--title=Сохранить AppImage как']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            output_path = result.stdout.strip()
            # appimagetool сам добавит .AppImage, если нужно
            if not output_path.endswith('.AppImage'):
                output_path += '.AppImage'
            self.output_dir = os.path.dirname(output_path)
            self.output_name = os.path.basename(output_path)

            self.btn_start.setEnabled(False)
            self.log_output.clear()

            self.worker = DebToAppImageThread(self.deb_path, self.output_dir)
            self.worker.log_signal.connect(self.log_output.append)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()

    def on_finished(self, success):
        self.btn_start.setEnabled(True)
        if success:
            QMessageBox.information(self, 'Готово',
                                    f'AppImage успешно создан!\nФайл: {self.output_name}')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = SimpleDebToAppImage()
    win.show()
    sys.exit(app.exec())