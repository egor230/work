import sys
import subprocess
import os
import shutil
import stat
import tempfile
import urllib.request
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QMessageBox, QTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DebToAppImageThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # (успех, путь к AppImage)

    APPIMAGETOOL_URL = 'https://github.com/AppImage/AppImageKit/releases/download/13/appimagetool-x86_64.AppImage'

    def __init__(self, deb_path, output_dir, output_name=None, remove_deb=True):
        super().__init__()
        self.deb_path = deb_path
        self.output_dir = output_dir
        self.output_name = output_name
        self.remove_deb = remove_deb
        self.work_dir = None
        self.appdir_path = None

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

            # Копируем зависимости (библиотеки)
            self.log_signal.emit("🔗 Собираю зависимости...")
            self._bundle_dependencies(self.appdir_path, exec_path)

            # Создаём AppRun (точку входа)
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
        """Возвращает execute-биты ELF-файлам, у которых deb/debian их снял.
        Без этого bundled JRE (runtime/bin/java) и подобные бинарники не запустятся."""
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
                        # первый токен — путь (отбрасываем %F, %U и флаги)
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
        # страховка: ищем по имени файла
        base = os.path.basename(exec_val)
        for root, _dirs, files in os.walk(appdir):
            if base in files:
                return os.path.join(root, base)
        return None

    def _ensure_icon(self, appdir, desktop_file):
        """Свежий appimagetool роняет сборку, если иконки нет в корне AppDir.
        Имя файла должно совпадать со stem из Icon= (расширение пробуют сами)."""
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
            return
        base = os.path.basename(icon_val)
        stem = base.rsplit('.', 1)[0] if base.lower().endswith(('.png', '.svg', '.xpm')) else base
        for ext in ('.png', '.svg', '.xpm'):
            if os.path.exists(os.path.join(appdir, stem + ext)):
                return
        # ищем файл с подходящим именем по всему AppDir
        found = []
        for root, _dirs, files in os.walk(appdir):
            for f in files:
                if f.lower() in (f'{stem}.png', f'{stem}.svg', f'{stem}.xpm'):
                    found.append(os.path.join(root, f))
        if not found:
            # страховка: иконка с обычным именем в каталогах иконок или в папке приложения
            for root, _dirs, files in os.walk(appdir):
                rel = os.path.relpath(root, appdir)
                if rel.startswith(('usr/share/icons', 'opt')):
                    found.extend(os.path.join(root, f) for f in files
                                 if f.lower() in ('icon.png', 'icon.svg', 'icon.xpm', f'{stem}.png'))
        if found:
            best = max(found, key=os.path.getsize)
            ext = os.path.splitext(best)[1] or '.png'
            dst = os.path.join(appdir, stem + ext)
            if os.path.abspath(best) != os.path.abspath(dst):
                shutil.copy2(best, dst)
            self.log_signal.emit(f"🖼️ Иконка в корне AppDir: {os.path.basename(dst)}")
        else:
            self.log_signal.emit(f"⚠️ Иконка {icon_val} не найдена в пакете — свежий appimagetool может прервать сборку")

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
