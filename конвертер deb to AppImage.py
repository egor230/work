import sys
import subprocess
import os
import shutil
import stat
import tempfile
import urllib.request
import gzip
import re
import glob
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QMessageBox, QTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DebToAppImageThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # (успех, путь к AppImage)

    APPIMAGETOOL_URL = 'https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage'
    UBUNTU_BASE = 'http://archive.ubuntu.com/ubuntu/'

    # Кодовые имена по номеру версии Ubuntu из Version: пакета
    CODENAME_BY_RELEASE = {
        '16.04': 'xenial', '18.04': 'bionic', '20.04': 'focal',
        '22.04': 'jammy', '24.04': 'noble', '24.10': 'oracular',
        '25.04': 'plucky', '25.10': 'questing',
    }

    def __init__(self, deb_path, output_dir, output_name=None, remove_deb=True):
        super().__init__()
        self.deb_path = deb_path
        self.output_dir = output_dir
        self.output_name = output_name
        self.remove_deb = remove_deb
        self.work_dir = None
        self.appdir_path = None
        self.cache_root = os.path.expanduser('~/.cache/deb2appimage')

    def run(self):
        try:
            # Проверка наличия нужных инструментов
            if not shutil.which('dpkg-deb'):
                self.log_signal.emit("❌ Не найден dpkg-deb. Установи: sudo apt install dpkg")
                self.finished_signal.emit(False, '')
                return

            if not shutil.which('ar'):
                self.log_signal.emit("❌ Не найден ar. Установи: sudo apt install binutils")
                self.finished_signal.emit(False, '')
                return

            # Скачиваем appimagetool, если его нет
            appimagetool = self._ensure_appimagetool()
            if not appimagetool:
                self.finished_signal.emit(False, '')
                return

            self._check_fuse()

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

            # dpkg-deb -x может потерять execute-биты (их делает postinst, который мы не запускаем) —
            # например, bundled JRE: без +x на java AppImage не запустится
            self._restore_exec_bits(self.appdir_path)

            # Определяем главный исполняемый файл (первичное приближение)
            exec_path = self._find_executable(self.appdir_path, meta)

            # Создаём .desktop файл, если его нет (пока без нормализации — нужно прочитать исходный Exec)
            desktop_file = self._ensure_desktop_file(self.appdir_path, pkg_name, pkg_desc, exec_path)

            # Если .desktop указывает точку входа внутри AppDir — доверяем ему, он точнее
            desk_exec = self._exec_from_desktop(desktop_file, self.appdir_path)
            if desk_exec:
                exec_path = desk_exec
                self.log_signal.emit(f"📄 Точка входа по .desktop: {os.path.relpath(exec_path, self.appdir_path)}")

            if not exec_path:
                self.log_signal.emit("❌ Не удалось найти исполняемый файл в пакете. "
                                     "Скорее всего, этот пакет не содержит приложение (только конфиги/библиотеки).")
                self.finished_signal.emit(False, '')
                return

            self.log_signal.emit(f"🎯 Исполняемый файл: {exec_path}")

            # Иконку в корень AppDir (свежий appimagetool без неё роняет сборку)
            self._ensure_icon(self.appdir_path, desktop_file)

            # Приводим .desktop к виду, который понимает appimagetool
            self._normalize_desktop(desktop_file)

            # Копируем зависимости (библиотеки), которые есть в системе
            self.log_signal.emit("🔗 Собираю зависимости...")
            self._bundle_dependencies(self.appdir_path, exec_path)

            # ГЛАВНОЕ: недостающие библиотеки (libmlt.so.6 и т.п.) качаем из архива Ubuntu
            # Обычный ldd-копировщик их пропускает, и AppImage падает при запуске.
            self._resolve_missing_dependencies(self.appdir_path, meta)

            # Копируем Qt5-платформенные плагины и QML-модули (ldd их не видит)
            self._copy_qt_assets(self.appdir_path)

            # Специфичные иконки приложения из системных тем (kdenlive-show-* и т.п.)
            self._copy_app_icons(self.appdir_path, pkg_name)

            # Создаём AppRun (точку входа) с правильным окружением
            self._create_apprun(self.appdir_path, exec_path)

            # Имя выходного файла: то, которое выбрал пользователь, или по метаданным
            if not self.output_name:
                self.output_name = f"{pkg_name}-{pkg_version}-{pkg_arch}.AppImage"
            output_path = os.path.join(self.output_dir, self.output_name)

            # Удаляем старый файл, если он уже есть (appimagetool иначе не перезапишет)
            if os.path.exists(output_path):
                os.remove(output_path)

            # Упаковываем в AppImage
            self.log_signal.emit("📦 Упаковываю в AppImage...")
            env = os.environ.copy()
            # appimagetool ожидает свои названия архитектур (x86_64/aarch64), а не deb-ные
            arch_map = {'amd64': 'x86_64', 'x86_64': 'x86_64', 'all': 'x86_64',
                        'i386': 'i686', 'i686': 'i686', 'arm64': 'aarch64',
                        'aarch64': 'aarch64'}
            env['ARCH'] = arch_map.get(pkg_arch, pkg_arch)

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
                self.log_signal.emit(f"✅ Успешно создано: {self.output_name} ({size_mb:.1f} МБ)")
                self.log_signal.emit(f"🚀 Запуск: ./{self.output_name}")

                # Удаляем deb-пакет из системы, если он больше не нужен
                if self.remove_deb:
                    self._remove_deb(pkg_name)

                self.finished_signal.emit(True, output_path)
            else:
                self.log_signal.emit("❌ Ошибка при создании AppImage (пакет в системе НЕ удалён)")
                self.finished_signal.emit(False, '')

        except Exception as e:
            self.log_signal.emit(f"❌ Критическая ошибка: {e}")
            import traceback
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit(False, '')
        finally:
            # Удаляем временную папку
            if self.work_dir and os.path.exists(self.work_dir):
                try:
                    shutil.rmtree(self.work_dir)
                    self.log_signal.emit("🧹 Временные файлы удалены")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Не удалось удалить временные файлы: {e}")

    # ------------------------------------------------------------------ #
    #  Загрузки
    # ------------------------------------------------------------------ #
    def _download(self, url, dst, timeout=180):
        """Скачивает URL с User-Agent'ом на диск.Возвращает True при успехе."""
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(dst, 'wb') as out:
                shutil.copyfileobj(resp, out)
            return os.path.getsize(dst) > 0
        except Exception as e:
            self.log_signal.emit(f"⚠️ Не удалось скачать {url}: {e}")
            try:
                if os.path.exists(dst):
                    os.remove(dst)
            except OSError:
                pass
            return False

    def _codename_for(self, meta):
        """Определяет кодовое имя дистрибутива по версии deb-пакета."""
        ver = meta.get('Version', '')
        for rel, codename in self.CODENAME_BY_RELEASE.items():
            if rel in ver:
                return codename
        # fallback: кодовое имя хост-системы
        try:
            with open('/etc/os-release', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('UBUNTU_CODENAME='):
                        return line.split('=', 1)[1].strip().strip('"')
        except OSError:
            pass
        return 'focal'

    def _load_repo_index(self, codename):
        """Грузит (и кэширует) Contents-amd64.gz и Packages индексы архива Ubuntu."""
        cache = os.path.join(self.cache_root, codename)
        os.makedirs(cache, exist_ok=True)
        contents = os.path.join(cache, 'Contents-amd64.gz')
        packages = os.path.join(cache, 'Packages_all.txt')

        if not os.path.exists(contents):
            self.log_signal.emit("📇 Скачиваю индекс файлов архива Ubuntu (Contents, ~40 МБ)...")
            if not self._download(self.UBUNTU_BASE + f'dists/{codename}/Contents-amd64.gz', contents):
                return None, None

        if not os.path.exists(packages):
            self.log_signal.emit("📇 Скачиваю индексы пакетов (Packages)...")
            all_text = []
            for comp in ('main', 'universe'):
                xz = os.path.join(cache, f'Packages_{comp}.xz')
                if not os.path.exists(xz):
                    if not self._download(
                            self.UBUNTU_BASE + f'dists/{codename}/{comp}/binary-amd64/Packages.xz', xz):
                        return None, None
                try:
                    with __import__('lzma').open(xz, 'rt', encoding='utf-8', errors='ignore') as f:
                        all_text.append(f.read())
                except Exception:
                    return None, None
            with open(packages, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(all_text))
        else:
            with open(packages, encoding='utf-8', errors='ignore') as f:
                return self._parse_contents(contents), self._parse_packages_text(f.read())

        with open(packages, encoding='utf-8', errors='ignore') as f:
            return self._parse_contents(contents), self._parse_packages_text(f.read())

    def _parse_contents(self, path):
        """Карта: имя файла/путь -> список пакетов."""
        mapping = {}
        try:
            with gzip.open(path, 'rt', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if '\t' not in line:
                        continue
                    file_path, pkg_field = line.rstrip('\n').split('\t', 1)
                    names = [p.rsplit('/', 1)[-1].strip() for p in pkg_field.split(',')]
                    mapping[os.path.basename(file_path)] = names
                    mapping[file_path] = names
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка чтения Contents: {e}")
        return mapping

    def _parse_packages_text(self, text):
        """Карта: имя пакета -> (версия, путь к .deb)."""
        result = {}
        for block in text.split('\n\n'):
            pm = re.search(r'^Package: (.+)$', block, re.M)
            fm = re.search(r'^Filename: (.+)$', block, re.M)
            vm = re.search(r'^Version: (.+)$', block, re.M)
            if pm and fm:
                result[pm.group(1).strip()] = (
                    vm.group(1).strip() if vm else '', fm.group(1).strip())
        return result

    # ------------------------------------------------------------------ #
    #  Разрешение недостающих библиотек
    # ------------------------------------------------------------------ #
    def _is_elf(self, path):
        try:
            with open(path, 'rb') as f:
                return f.read(4) == b'\x7fELF'
        except OSError:
            return False

    def _missing_libs(self, appdir):
        """Возвращает set soname'ов, которые ldd не смог найти."""
        env = os.environ.copy()
        lib_dirs = [
            os.path.join(appdir, 'usr/lib'),
            os.path.join(appdir, 'usr/lib/x86_64-linux-gnu'),
            os.path.join(appdir, 'usr/lib/x86_64-linux-gnu/mlt'),
            os.path.join(appdir, 'lib'),
        ]
        env['LD_LIBRARY_PATH'] = ':'.join(lib_dirs) + ':' + env.get('LD_LIBRARY_PATH', '')
        missing = set()
        for root, _dirs, files in os.walk(appdir):
            for fn in files:
                full = os.path.join(root, fn)
                if not self._is_elf(full):
                    continue
                try:
                    res = subprocess.run(['ldd', full], env=env, capture_output=True,
                                         text=True, timeout=25)
                except Exception:
                    continue
                for line in res.stdout.splitlines():
                    m = re.search(r'(\S+\.so(?:\.\d+)*)\s+=>\s+not found', line)
                    if m:
                        missing.add(m.group(1))
                    elif '=>' not in line:
                        m2 = re.match(r'\s*(\S+\.so(?:\.\d+)*)\s*$', line)
                        if m2 and 'linux-vdso' not in m2.group(1) and 'ld-linux' not in m2.group(1):
                            missing.add(m2.group(1))
        return missing

    def _resolve_missing_dependencies(self, appdir, meta):
        """Рекурсивно скачивает .deb'ы с недостающими библиотеками и распаковывает в AppDir."""
        codename = self._codename_for(meta)
        file2pkgs, pkg2file = self._load_repo_index(codename)
        if not file2pkgs or not pkg2file:
            self.log_signal.emit("⚠️ Не удалось загрузить индексы Ubuntu — пропускаю разрешение зависимостей")
            return

        deb_cache = os.path.join(self.cache_root, codename, 'debs')
        os.makedirs(deb_cache, exist_ok=True)
        extracted = set()
        added_mlt = False

        def fetch(pkg, reason=''):
            nonlocal added_mlt
            if pkg in extracted or pkg not in pkg2file:
                return False
            ver, filename = pkg2file[pkg]
            local = os.path.join(deb_cache, os.path.basename(filename))
            if not os.path.exists(local):
                self.log_signal.emit(f"  ⬇️ {pkg} ({ver}) {reason}")
                if not self._download(self.UBUNTU_BASE + filename, local, timeout=300):
                    return False
            try:
                subprocess.run(['dpkg-deb', '-x', local, appdir], check=True,
                               capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                self.log_signal.emit(f"  ⚠️ Не удалось распаковать {pkg}: {e}")
                return False
            extracted.add(pkg)
            if pkg.startswith('libmlt'):
                added_mlt = True
            return True

        for iteration in range(1, 13):
            missing = self._missing_libs(appdir)
            if not missing:
                self.log_signal.emit("✅ Все библиотеки найдены в AppDir")
                break
            self.log_signal.emit(f"🔎 Поиск зависимостей (проход {iteration}): не найдено {len(missing)}")
            added = False
            for soname in sorted(missing):
                pkgs = file2pkgs.get(soname, [])
                if not pkgs:
                    self.log_signal.emit(f"  ⚠️ Не найден пакет для {soname} — пропускаю")
                    continue
                # предпочитаем обычные пакеты вместо -dev
                candidates = [p for p in pkgs if not p.endswith('-dev')] or pkgs
                chosen = next((p for p in candidates if p in pkg2file), candidates[0])
                if fetch(chosen, f"(для {soname})"):
                    added = True
                    self.log_signal.emit(f"  ➕ {chosen}: {soname}")
            if not added:
                self.log_signal.emit("⚠️ Дальше разрешить зависимости не удалось")
                break

        if extracted:
            self.log_signal.emit(f"📚 Дополнительно распаковано пакетов: {len(extracted)} "
                                 f"({', '.join(sorted(extracted))})")

        # Сопутствующие данные/утилиты MLT (ldd их не покажет, но они нужны для работы)
        if added_mlt:
            for extra in ('libmlt-data', 'melt', 'ffmpeg'):
                if extra in pkg2file:
                    fetch(extra, "(данные/утилиты MLT)")

    def _copy_qt_assets(self, appdir):
        """Копирует Qt5-плагины и QML-модули хоста (ldd их не перечисляет)."""
        target_plugins = os.path.join(appdir, 'usr/lib/x86_64-linux-gnu/qt5/plugins')
        target_qml = os.path.join(appdir, 'usr/lib/x86_64-linux-gnu/qt5/qml')
        src_roots = ['/usr/lib/x86_64-linux-gnu/qt5', '/usr/lib/qt5', '/usr/lib/x86_64-linux-gnu/qt6']

        for src_root in src_roots:
            if not os.path.isdir(src_root):
                continue
            src_plugins = os.path.join(src_root, 'plugins')
            if os.path.isdir(src_plugins):
                try:
                    shutil.copytree(src_plugins, target_plugins, dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns('*.debug'))
                    self.log_signal.emit("🧩 Скопированы Qt-плагины")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Не удалось скопировать Qt-плагины: {e}")
            src_qml = os.path.join(src_root, 'qml')
            if os.path.isdir(src_qml):
                try:
                    shutil.copytree(src_qml, target_qml, dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns('*.debug'))
                    self.log_signal.emit("🧩 Скопированы QML-модули")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ Не удалось скопировать QML-модули: {e}")
            break  # берём первый найденный корень, чтобы не смешивать Qt5 и Qt6

    def _copy_app_icons(self, appdir, pkg_name):
        """Копирует темы иконок (breeze/hicolor), чтобы QML/KDE находили иконки действий."""
        dest_root = os.path.join(appdir, 'usr/share/icons')
        os.makedirs(dest_root, exist_ok=True)
        copied = 0
        for theme in ('breeze', 'breeze-dark', 'hicolor'):
            src = os.path.join('/usr/share/icons', theme)
            if not os.path.isdir(src):
                continue
            dst = os.path.join(dest_root, theme)
            try:
                before = sum(len(files) for _r, _d, files in os.walk(dst)) if os.path.isdir(dst) else 0
                shutil.copytree(src, dst, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns('*.cache'))
                after = sum(len(files) for _r, _d, files in os.walk(dst))
                copied += after - before
            except Exception as e:
                self.log_signal.emit(f"⚠️ Не удалось скопировать тему иконок {theme}: {e}")
        if copied:
            self.log_signal.emit(f"🎨 Скопировано иконок из системных тем: {copied}")

    # ------------------------------------------------------------------ #
    #  Вспомогательные методы (pacеметалл, иконки, прочее)
    # ------------------------------------------------------------------ #
    def _ensure_appimagetool(self):
        """Находит или скачивает appimagetool"""
        # Сначала ищем в системе
        if shutil.which('appimagetool'):
            return shutil.which('appimagetool')

        # Ищем в домашней папке (проверяя, что файл не битый)
        local_path = os.path.expanduser('~/.local/bin/appimagetool')
        if os.path.isfile(local_path) and self._is_valid_appimagetool(local_path):
            return local_path

        # Ищем рядом с .deb файлом и рядом со скриптом (у тебя appimagetool лежит рядом с deb)
        for cand in (os.path.join(os.path.dirname(os.path.abspath(self.deb_path)), 'appimagetool'),
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appimagetool')):
            if os.path.isfile(cand) and self._is_valid_appimagetool(cand):
                self.log_signal.emit(f"🔎 Нашёл appimagetool рядом: {cand}")
                return cand

        self.log_signal.emit("⬇️ appimagetool не найден, скачиваю...")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Пробуем несколько способов (curl → wget → python → apt)
        if self._download_url_to(local_path, 'curl') \
                or self._download_url_to(local_path, 'wget') \
                or self._download_url_python(local_path):
            if self._is_valid_appimagetool(local_path):
                os.chmod(local_path, os.stat(local_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                self.log_signal.emit(f"✅ appimagetool скачан в {local_path}")
                return local_path
            self.log_signal.emit("⚠️ Скачанный файл повреждён (не похож на appimagetool), удаляю...")
            try:
                os.remove(local_path)
            except OSError:
                pass

        # Последняя надежда: пакетная система
        self.log_signal.emit("📦 Пробую установить через apt-get...")
        res = self._run_privileged(['apt-get', 'install', '-y', 'appimagetool'])
        if res.returncode == 0 and shutil.which('appimagetool'):
            self.log_signal.emit("✅ appimagetool установлен через apt")
            return shutil.which('appimagetool')

        self.log_signal.emit("❌ Не удалось получить appimagetool автоматически.")
        self.log_signal.emit("💡 Как установить вручную:")
        self.log_signal.emit(f"   1. Скачать: {self.APPIMAGETOOL_URL}")
        self.log_signal.emit("   2. Выбери сохранённый файл в диалоге или положи его в ~/.local/bin/appimagetool")
        self.log_signal.emit("   3. ИЛИ (если доступен в репозиториях твоего дистрибутива): sudo apt install appimagetool")
        self.log_signal.emit("   4. ИЛИ установи расширение/прокси, если GitHub недоступен в твоём регионе")
        return None

    def _download_url_to(self, dst, tool):
        """Скачивает URL утилитой curl или wget"""
        if not shutil.which(tool):
            return False
        cmd = ([tool, '-L', '-f', '-s', '-o', dst, self.APPIMAGETOOL_URL] if tool == 'curl'
               else [tool, '-L', '-q', '-O', dst, self.APPIMAGETOOL_URL])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return res.returncode == 0
        except Exception:
            return False

    def _download_url_python(self, dst):
        """Скачивает через urllib (учитывает прокси из переменных окружения)"""
        try:
            req = urllib.request.Request(
                self.APPIMAGETOOL_URL,
                headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'}
            )
            with urllib.request.urlopen(req, timeout=300) as resp, open(dst, 'wb') as f:
                shutil.copyfileobj(resp, f)
            return True
        except Exception:
            return False

    def _is_valid_appimagetool(self, path):
        """Проверяет, что файл похож на настоящий appimagetool (не HTML-ошибка)"""
        try:
            if os.path.getsize(path) < 100_000:
                return False
            with open(path, 'rb') as f:
                head = f.read(256)
            if head.lstrip().startswith(b'<?xml') or head.lstrip().lower().startswith(b'<html'):
                return False
            return True
        except OSError:
            return False

    def _run_privileged(self, args):
        """Запускает команду с правами root (sudo без пароля → pkexec → sudo с паролем)"""
        if os.geteuid() == 0:
            return subprocess.run(args, capture_output=True, text=True)
        # 1) sudo без запроса пароля (включён NOPASSWD или пароль ещё в кэше)
        res = subprocess.run(['sudo', '-n'] + args, capture_output=True, text=True)
        if res.returncode == 0:
            return res
        # 2) графический запрос пароля через polkit
        if shutil.which('pkexec'):
            abs_args = [a if os.path.isabs(a) else shutil.which(a) or a for a in args]
            res2 = subprocess.run(['pkexec'] + abs_args, capture_output=True, text=True, timeout=300)
            if res2.returncode == 0:
                return res2
        # 3) обычный sudo (попросит пароль в терминале, если приложение запущено из него)
        return subprocess.run(['sudo'] + args, capture_output=True, text=True)

    def _remove_deb(self, pkg_name):
        """Удаляет установленный deb-пакет из системы (только после успешной конвертации)"""
        self.log_signal.emit(f"🧽 Пакет больше не нужен — удаляю {pkg_name} из системы...")
        check = subprocess.run(['dpkg', '-s', pkg_name], capture_output=True, text=True)
        if check.returncode != 0 or 'Status: install' not in (check.stdout or ''):
            self.log_signal.emit(f"ℹ️ Пакет {pkg_name} не установлен в системе — удалять нечего")
            return

        res = self._run_privileged(['apt-get', 'remove', '-y', pkg_name])
        if res.returncode == 0:
            self.log_signal.emit(f"✅ Пакет {pkg_name} удалён из системы")
        else:
            self.log_signal.emit(f"⚠️ Не удалось удалить пакет {pkg_name} автоматически.")
            self.log_signal.emit(f"   Удали вручную: sudo apt remove {pkg_name}")

    def _check_fuse(self):
        """appimagetool создаёт AppImage через FUSE — предупреждаем, если его нет"""
        if os.path.exists('/dev/fuse'):
            return
        self.log_signal.emit("⚠️ Не найден /dev/fuse — создание AppImage может не получиться.")
        self.log_signal.emit("   Если будет ошибка mount: sudo apt install fuse3, "
                             "затем: sudo usermod -aG fuse $USER (и перелогинься)")

    def _restore_exec_bits(self, appdir):
        """Возвращает execute-биты ELF-файлам, у которых deb/debian их снял."""
        fixed = 0
        for root, _dirs, files in os.walk(appdir):
            for f in files:
                full = os.path.join(root, f)
                try:
                    st = os.stat(full)  # следует по symlink'ам
                except OSError:
                    continue
                if not (st.st_mode & stat.S_IXUSR):
                    try:
                        with open(full, 'rb') as fh:
                            is_elf = fh.read(4) == b'\x7fELF'
                    except OSError:
                        continue
                    if is_elf:
                        os.chmod(full, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                        fixed += 1
        if fixed:
            self.log_signal.emit(f"🔧 Вернул execute-биты {fixed} ELF-файлам (в пакете они были без +x)")

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
        """Ищет главный исполняемый файл (ELF-бинарник или скрипт)"""
        # Сначала смотрим в control-файле
        exec_field = meta.get('Executable', '') or meta.get('Exec', '')
        if exec_field:
            for root, _, files in os.walk(appdir):
                for f in files:
                    if f == os.path.basename(exec_field):
                        full = os.path.join(root, f)
                        if os.access(full, os.X_OK):
                            return full

        # Ищем в стандартных местах + opt/ (большие Electron/Java-приложения)
        search_dirs = ['usr/bin', 'usr/games', 'usr/sbin', 'bin']
        opt_dir = os.path.join(appdir, 'opt')
        if os.path.isdir(opt_dir):
            for entry in sorted(os.listdir(opt_dir)):
                base = os.path.join(opt_dir, entry)
                for sub in (base, os.path.join(base, 'bin')):
                    if os.path.isdir(sub):
                        search_dirs.append(sub)

        # Ранжируем: ELF-бинарник > скрипт в opt/ > другой скрипт
        ranked = []
        seen = set()
        for d in search_dirs:
            full_dir = os.path.join(appdir, d)
            if not os.path.isdir(full_dir):
                continue
            for f in sorted(os.listdir(full_dir)):
                full = os.path.join(full_dir, f)
                if full in seen or not (os.path.isfile(full) and os.access(full, os.X_OK)):
                    continue
                seen.add(full)
                try:
                    with open(full, 'rb') as bf:
                        is_elf = bf.read(4) == b'\x7fELF'
                except OSError:
                    is_elf = False
                rel = os.path.relpath(full, appdir)
                rank = 0 if is_elf else (1 if rel.startswith('opt') else 2)
                ranked.append((rank, full))

        if ranked:
            ranked.sort(key=lambda t: t[0])
            if ranked[0][0] > 0:
                self.log_signal.emit("ℹ️ Найден исполняемый скрипт (не ELF-бинарник) — он будет точкой входа")
            return ranked[0][1]
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
            return dst

        # Создаём свой .desktop
        self.log_signal.emit("📄 Создаю .desktop файл...")
        desktop_content = f"""[Desktop Entry]
Type=Application
Name={pkg_name}
Comment={pkg_desc}
Exec=AppRun
Icon={pkg_name}
Categories=Utility;
"""
        desktop_path = os.path.join(appdir, f'{pkg_name}.desktop')
        with open(desktop_path, 'w', encoding='utf-8') as f:
            f.write(desktop_content)
        return desktop_path

    def _normalize_desktop(self, desktop_path):
        """Адаптирует .desktop под appimagetool: Exec=AppRun, Icon=<имя>, чистит устаревшие ключи"""
        try:
            with open(desktop_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().splitlines()
            icon_val = None
            for line in lines:
                if line.lower().startswith('icon='):
                    icon_val = line.split('=', 1)[1].strip().split(':')[0]
                    break
            icon_line = ''
            if icon_val:
                name = os.path.basename(icon_val)
                stem = name.rsplit('.', 1)[0] if name.lower().endswith(('.png', '.svg', '.xpm')) else name
                icon_line = f'Icon={stem}'
            out = []
            for line in lines:
                k = line.lower()
                if k.startswith('exec='):
                    out.append('Exec=AppRun')
                elif k.startswith('icon='):
                    if icon_line:
                        out.append(icon_line)
                elif k.startswith(('encoding=', 'path=')):
                    continue  # устаревшие ключи — только шум в логах
                else:
                    out.append(line)
            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(out) + '\n')
        except Exception:
            pass

    def _exec_from_desktop(self, desktop_file, appdir):
        """Разрешает исходный Exec= из .desktop на файл внутри AppDir"""
        exec_val = None
        try:
            with open(desktop_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.lower().startswith('exec='):
                        exec_val = line.split('=', 1)[1].strip().split()[0]
                        break
        except Exception:
            return None
        if not exec_val or exec_val == 'AppRun':
            return None
        if os.path.isabs(exec_val):
            cand = os.path.join(appdir, os.path.relpath(exec_val, '/'))
        else:
            cand = os.path.join(appdir, exec_val)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
        base = os.path.basename(exec_val)
        for root, _dirs, files in os.walk(appdir):
            if base in files:
                return os.path.join(root, base)
        return None

    def _ensure_icon(self, appdir, desktop_file):
        """Гарантирует иконку в корне AppDir — свежий appimagetool без неё роняет сборку."""
        icon_val = None
        try:
            with open(desktop_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.lower().startswith('icon='):
                        icon_val = line.split('=', 1)[1].strip().split(':')[0]
                        break
        except Exception:
            return
        if not icon_val:
            icon_val = os.path.splitext(os.path.basename(desktop_file))[0]
            self.log_signal.emit(f"⚠️ В .desktop нет Icon= — использую имя: {icon_val}")

        base = os.path.basename(icon_val)
        stem = base.rsplit('.', 1)[0] if base.lower().endswith(('.png', '.svg', '.xpm')) else base
        candidates = tuple(c.lower() for c in (f'{stem}.png', f'{stem}.svg', f'{stem}.xpm'))

        for ext in ('.png', '.svg', '.xpm'):
            if os.path.exists(os.path.join(appdir, stem + ext)):
                self.log_signal.emit(f"🖼️ Иконка в корне AppDir: {stem + ext}")
                return

        found = []
        for root, _dirs, files in os.walk(appdir):
            for f in files:
                if f.lower() in candidates:
                    found.append(os.path.join(root, f))

        if not found:
            esc = glob.escape(stem)
            for pattern in (f'/usr/share/icons/*/*/apps/{esc}.*',
                            f'/usr/share/icons/*/apps/{esc}.*',
                            f'/usr/share/icons/hicolor/*/{esc}.*',
                            f'/usr/share/pixmaps/{esc}.*'):
                for p in glob.glob(pattern):
                    if os.path.isfile(p) and os.path.basename(p).lower() in candidates:
                        found.append(p)

        if not found:
            for root, _dirs, files in os.walk(appdir):
                rel = os.path.relpath(root, appdir)
                if rel.startswith(('usr/share/icons', 'opt')):
                    found.extend(os.path.join(root, f) for f in files
                                 if f.lower() in ('icon.png', 'icon.svg', 'icon.xpm'))

        if found:
            try:
                found.sort(key=lambda p: (0 if p.lower().endswith('.png') else 1,
                                          -os.path.getsize(p)))
            except OSError:
                pass
            best = found[0]
            ext = os.path.splitext(best)[1].lower() or '.png'
            dst = os.path.join(appdir, stem + ext)
            if os.path.abspath(best) != os.path.abspath(dst):
                shutil.copy2(best, dst)
            self.log_signal.emit(f"🖼️ Иконка в корне AppDir: {os.path.basename(dst)} (из {best})")
            return

        dst = os.path.join(appdir, stem + '.png')
        try:
            self._generate_placeholder_png(dst, 256)
            self.log_signal.emit(f"⚠️ Иконка {icon_val} не найдена — создана заглушка {stem}.png "
                                 "(при желании замени её на настоящую иконку 256x256)")
        except Exception as e:
            self.log_signal.emit(f"⚠️ Не удалось создать иконку-заглушку: {e}")

    def _generate_placeholder_png(self, path, size=256):
        """Создаёт валидный 256x256 PNG-градиент без внешних библиотек (только zlib/struct)."""
        import struct
        import zlib
        r, g, b = 38, 78, 120

        def chunk(tag, data):
            return (struct.pack('>I', len(data)) + tag + data
                    + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

        raw = bytearray()
        for y in range(size):
            raw.append(0)  # фильтр 'None'
            t = y / max(1, size - 1)
            rr = int(r + (255 - r) * t * 0.35)
            gg = int(g + (255 - g) * t * 0.35)
            bb = int(b + (255 - b) * t * 0.35)
            raw.extend(bytes((rr, gg, bb, 255)) * size)

        png = (b'\x89PNG\r\n\x1a\n'
               + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
               + chunk(b'IEND', b''))
        with open(path, 'wb') as f:
            f.write(png)

    def _bundle_dependencies(self, appdir, exec_path):
        """Копирует разделяемые библиотеки в AppDir"""
        lib_dir = os.path.join(appdir, 'usr', 'lib')
        os.makedirs(lib_dir, exist_ok=True)

        try:
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = os.path.join(appdir, 'usr/lib') + ':' + \
                                     os.path.join(appdir, 'usr/lib/x86_64-linux-gnu') + ':' + \
                                     env.get('LD_LIBRARY_PATH', '')
            result = subprocess.run(['ldd', exec_path], capture_output=True, text=True, env=env)
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

            self.log_signal.emit(f"📚 Скопировано библиотек из системы: {libs_copied}")
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка при сборе зависимостей: {e}")

    def _create_apprun(self, appdir, exec_path):
        """Создаёт AppRun с переменными окружения, необходимыми Qt/MLT/KDE"""
        apprun_path = os.path.join(appdir, 'AppRun')
        rel_path = os.path.relpath(exec_path, appdir)

        content = f"""#!/bin/bash
HERE="$(dirname "$(readlink -f "${{0}}")")"

# Библиотеки: копированные из системы + докачанные из архива Ubuntu
APPDIR_LIBS="${{HERE}}/usr/lib:${{HERE}}/usr/lib/x86_64-linux-gnu:${{HERE}}/lib"
if [ -d "${{HERE}}/usr/lib/x86_64-linux-gnu/mlt" ]; then
    APPDIR_LIBS="${{APPDIR_LIBS}}:${{HERE}}/usr/lib/x86_64-linux-gnu/mlt"
fi
export LD_LIBRARY_PATH="${{APPDIR_LIBS}}${{LD_LIBRARY_PATH:+:${{LD_LIBRARY_PATH}}}}"

# Qt-плагины и QML (ldd их не видит)
if [ -d "${{HERE}}/usr/lib/x86_64-linux-gnu/qt5/plugins" ]; then
    export QT_PLUGIN_PATH="${{HERE}}/usr/lib/x86_64-linux-gnu/qt5/plugins${{QT_PLUGIN_PATH:+:${{QT_PLUGIN_PATH}}}}"
fi
if [ -d "${{HERE}}/usr/lib/x86_64-linux-gnu/qt5/qml" ]; then
    export QML2_IMPORT_PATH="${{HERE}}/usr/lib/x86_64-linux-gnu/qt5/qml${{QML2_IMPORT_PATH:+:${{QML2_IMPORT_PATH}}}}"
fi

# Данные приложения и MLT
export XDG_DATA_DIRS="${{HERE}}/usr/share${{XDG_DATA_DIRS:+:${{XDG_DATA_DIRS}}}}"
export XDG_CONFIG_DIRS="${{HERE}}/usr/share${{XDG_CONFIG_DIRS:+:${{XDG_CONFIG_DIRS}}}}"
if [ -d "${{HERE}}/usr/share/mlt" ]; then
    export MLT_DATA="${{HERE}}/usr/share/mlt"
fi
if [ -d "${{HERE}}/usr/lib/x86_64-linux-gnu/mlt" ]; then
    export MLT_REPOSITORY="${{HERE}}/usr/lib/x86_64-linux-gnu/mlt"
fi

# Локализация
export TEXTDOMAINDIR="${{HERE}}/usr/share/locale${{TEXTDOMAINDIR:+:${{TEXTDOMAINDIR}}}}"

# Утилиты (ffmpeg, melt) внутри AppDir
export PATH="${{HERE}}/usr/bin:${{HERE}}/bin:${{PATH}}"

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
        self.setFixedSize(500, 440)

        layout = QVBoxLayout()

        self.btn_select = QPushButton('Выбрать .deb пакет')
        self.btn_select.clicked.connect(self.select_deb)
        layout.addWidget(self.btn_select)

        self.status_label = QLabel('Пакет не выбран')
        layout.addWidget(self.status_label)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.chk_remove = QCheckBox('Удалить .deb пакет из системы после успешной конвертации')
        self.chk_remove.setChecked(True)
        layout.addWidget(self.chk_remove)

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
            if not output_path.endswith('.AppImage'):
                output_path += '.AppImage'
            self.output_dir = os.path.dirname(output_path)
            self.output_name = os.path.basename(output_path)

            self.btn_start.setEnabled(False)
            self.log_output.clear()

            self.worker = DebToAppImageThread(
                self.deb_path, self.output_dir,
                output_name=self.output_name,
                remove_deb=self.chk_remove.isChecked()
            )
            self.worker.log_signal.connect(self.log_output.append)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()

    def on_finished(self, success, output_path):
        self.btn_start.setEnabled(True)
        if success:
            msg = f'AppImage успешно создан!\nФайл: {os.path.basename(output_path)}'
            if self.chk_remove.isChecked():
                msg += '\n\nСтатус удаления пакета из системы — в журнале выше.'
            QMessageBox.information(self, 'Готово', msg)
        else:
            QMessageBox.critical(self, 'Ошибка',
                                 'Конвертация не удалась. Подробности — в журнале выше.')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = SimpleDebToAppImage()
    win.show()
    sys.exit(app.exec())
