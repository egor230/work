import os
import subprocess
import psutil


def get_pid_and_path_window():
    """
    Получаем словарь {pid: linux_path} для всех процессов пользователя.
    Включает Wine/Proton процессы с .exe.
    Расширяет словарь на всех родителей и потомков найденных игровых процессов.
    """
    my_pid = os.getpid()
    data_dict = {}

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            pid = info["pid"]

            if pid == my_pid:
                continue

            cmdline_parts = info["cmdline"] or []

            # --- Читаем /proc/{pid}/cwd ---
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
            except (FileNotFoundError, PermissionError):
                cwd = None

            # --- Читаем /proc/{pid}/exe ---
            try:
                exe_link = os.readlink(f"/proc/{pid}/exe")
            except (FileNotFoundError, PermissionError):
                exe_link = None

            # ========== Определяем, это Wine/Proton-процесс? ==========
            is_wine = False
            if exe_link and (
                'wine-preloader' in exe_link
                or 'wine64-preloader' in exe_link
            ):
                is_wine = True
            elif any('.exe' in arg.lower() for arg in cmdline_parts):
                is_wine = True
            # Proton может маппить .exe напрямую через PE loader
            elif exe_link and exe_link.lower().endswith('.exe'):
                is_wine = True

            resolved_path = None

            # ==================== WINE / PROTON ====================
            if is_wine:
                # Приоритет 1: exe_link уже указывает на .exe (Proton PE mapping)
                if exe_link and exe_link.lower().endswith('.exe') and os.path.isfile(exe_link):
                    resolved_path = exe_link

                # Приоритет 2: ищем .exe в аргументах командной строки
                if not resolved_path:
                    win_exe = None
                    for arg in cmdline_parts:
                        if arg.lower().endswith('.exe'):
                            win_exe = arg
                            break

                    if win_exe:
                        exe_name = os.path.basename(win_exe.replace('\\', '/'))
                        found = False

                        # 2a. Абсолютный Windows-путь (C:\...) — winepath
                        if len(win_exe) >= 2 and win_exe[1] == ':':
                            try:
                                result = subprocess.run(
                                    ['winepath', '-u', win_exe],
                                    capture_output=True, text=True, timeout=3
                                )
                                if result.returncode == 0:
                                    linux_path = result.stdout.strip()
                                    if os.path.isfile(linux_path):
                                        resolved_path = linux_path
                                        found = True
                            except Exception:
                                pass

                            # Fallback: basename в cwd
                            if not found and cwd:
                                candidate = os.path.join(cwd, exe_name)
                                if os.path.isfile(candidate):
                                    resolved_path = candidate
                                    found = True

                        # 2b. Относительный путь (dx11\Game.exe)
                        if not found and cwd:
                            rel = win_exe.replace('\\', '/')
                            candidate = os.path.normpath(os.path.join(cwd, rel))
                            if os.path.isfile(candidate):
                                resolved_path = candidate
                                found = True

                            if not found:
                                candidate = os.path.join(cwd, exe_name)
                                if os.path.isfile(candidate):
                                    resolved_path = candidate
                                    found = True

                        # 2c. Fallback: find
                        if not found and cwd and exe_name:
                            try:
                                result = subprocess.run(
                                    ['find', cwd, '-maxdepth', '4',
                                     '-iname', exe_name, '-type', 'f'],
                                    capture_output=True, text=True, timeout=5
                                )
                                if result.returncode == 0 and result.stdout.strip():
                                    resolved_path = result.stdout.strip().split('\n')[0]
                            except Exception:
                                pass

                if resolved_path:
                    data_dict[pid] = resolved_path

            # ==================== Обычный Linux-процесс ====================
            else:
                if not cmdline_parts:
                    if exe_link:
                        data_dict[pid] = exe_link
                    continue

                relative_exe = cmdline_parts[0].replace("\\", "/")

                if relative_exe.startswith('/'):
                    full_path = relative_exe
                elif cwd and relative_exe:
                    full_path = os.path.normpath(os.path.join(cwd, relative_exe))
                else:
                    full_path = None

                if full_path and os.path.isfile(full_path):
                    data_dict[pid] = full_path
                elif exe_link:
                    data_dict[pid] = exe_link

        except Exception:
            pass

    # ========== Расширяем на родителей и потомков ==========
    expanded = dict(data_dict)
    for game_pid, game_path in list(data_dict.items()):
        try:
            proc = psutil.Process(game_pid)

            # Родители (до init, pid=1)
            parent = proc.parent()
            while parent and parent.pid > 1:
                expanded[parent.pid] = game_path
                parent = parent.parent()

            # Потомки (рекурсивно)
            for child in proc.children(recursive=True):
                expanded[child.pid] = game_path

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return expanded


def get_active_window_pid():
    """
    Получаем PID процесса, владеющего активным X11-окном.
    Три метода для надёжности: xdotool, xprop, wmctrl.
    """
    # ---- Метод 1: xdotool ----
    try:
        result = subprocess.run(
            ['xdotool', 'getactivewindow'],
            capture_output=True, text=True, timeout=3
        )
        window_id = result.stdout.strip()
        if window_id and window_id.isdigit() and int(window_id) > 0:
            result = subprocess.run(
                ['xdotool', 'getwindowpid', window_id],
                capture_output=True, text=True, timeout=3
            )
            pid_str = result.stdout.strip()
            if pid_str and pid_str.isdigit():
                pid = int(pid_str)
                if pid > 1:
                    return pid, 'xdotool'
    except Exception:
        pass

    # ---- Метод 2: xprop (_NET_ACTIVE_WINDOW + _NET_WM_PID) ----
    try:
        result = subprocess.run(
            ['xprop', '-root', '_NET_ACTIVE_WINDOW'],
            capture_output=True, text=True, timeout=3
        )
        # Формат ответа: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x3400003
        for part in result.stdout.split():
            if part.startswith('0x'):
                window_hex = part.lstrip('#')
                result2 = subprocess.run(
                    ['xprop', '-id', window_hex, '_NET_WM_PID'],
                    capture_output=True, text=True, timeout=3
                )
                # Формат: _NET_WM_PID(CARDINAL) = 12345
                for token in result2.stdout.split():
                    if token.isdigit() and int(token) > 1:
                        return int(token), 'xprop'
                break
    except Exception:
        pass

    # ---- Метод 3: wmctrl ----
    try:
        result = subprocess.run(
            ['wmctrl', '-a', ':ACTIVE:', '-p'],
            capture_output=True, text=True, timeout=3
        )
        # Формат: 0x...  -1  hostname  pid  ...  Window Title
        parts = result.stdout.split()
        if len(parts) >= 3:
            pid_str = parts[2]
            if pid_str.isdigit() and int(pid_str) > 1:
                return int(pid_str), 'wmctrl'
    except Exception:
        pass

    return None, None


def resolve_game_pid(window_pid, data_dict):
    """
    По PID от xdotool/xprop находим PID игры в data_dict.
    Обходит дерево процессов ВВЕРХ (родители) и ВНИЗ (потомки),
    а также проверяет СИБЛИНГОВ и всю ветку от каждого предка.

    Для Wine/Proton: xdotool может вернуть PID wine-server или
    wine-preloader. Игровой .exe может быть:
      - прямым родителем/потомком окна
      - СИБЛИНГОМ (другой дочерний процесс того же родителя)
      - КУЗЕНОМ (находиться в другой ветке от общего предка)

    Алгоритм: поднимаемся до корня, собираем ВСЕХ предков,
    затем от КАЖДОГО предка спускаемся вниз по ВСЕМ веткам.
    Это покрывает прямых родителей, потомков, сиблингов и кузенов.
    """
    if not window_pid or not data_dict:
        return None

    # 1. Прямое совпадение
    if window_pid in data_dict:
        return window_pid

    try:
        proc = psutil.Process(window_pid)

        # 2. Быстрая проверка: идём ВВЕРХ по родителям
        parent = proc.parent()
        visited_up = set()
        while parent and parent.pid > 1 and parent.pid not in visited_up:
            visited_up.add(parent.pid)
            if parent.pid in data_dict:
                return parent.pid
            parent = parent.parent()

        # 3. Быстрая проверка: идём ВНИЗ по потомкам
        for child in proc.children(recursive=True):
            if child.pid in data_dict:
                return child.pid

        # 4. Полный скан: от КАЖДОГО предка спускаемся по ВСЕМ веткам.
        #    Это находит сиблингов и кузенов — процессы в других
        #    ветках дерева, которые тоже имеют .exe.
        #
        #    Пример дерева Wine-игры:
        #      wine-preloader (1000)
        #      ├── AI.exe (1217897)        ← .exe, в data_dict
        #      ├── wine-server (2000)       ← предок xdotool PID
        #      │   ├── xdotool_PID (2500)   ← окно (мы тут)
        #      │   └── AI.exe (1217931)     ← .exe, СИБЛИНГ! в data_dict
        #      └── renderer (3000)
        #          └── AI.exe (1218004)     ← .exe, КУЗЕН! в data_dict
        #
        #    Шаги 2-3 не найдут 2500→2000→1217931 (сиблинг)
        #    Этот шаг найдёт: 2500↑2000, 2000↓все→1217931 ✓

        ancestors = []
        p = proc.parent()
        while p and p.pid > 1 and p.pid not in visited_up:
            ancestors.append(p)
            visited_up.add(p.pid)
            p = p.parent()

        visited_down = set()
        for ancestor in ancestors:
            try:
                for child in ancestor.children(recursive=True):
                    if child.pid not in visited_down:
                        visited_down.add(child.pid)
                        if child.pid in data_dict:
                            return child.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    return None


def check_current_active_window(games_checkmark_paths=None):
    """
    Получаем путь к исполняемому файлу процесса активного окна.
    Возвращает (file_path, game_pid) или (None, None).
    """
    data_dict = get_pid_and_path_window()
    if not data_dict:
        print("[!] Не найдено процессов с исполняемыми файлами")
        return None, None

    window_pid, method = get_active_window_pid()
    if not window_pid:
        print("[!] Не удалось определить PID активного окна")
        return None, None

    print(f"[i] PID окна ({method}): {window_pid}")

    game_pid = resolve_game_pid(window_pid, data_dict)
    if not game_pid:
        print(f"[!] PID {window_pid} не найден в словаре процессов ({len(data_dict)} записей)")
        from collections import Counter
        path_counts = Counter(data_dict.values())
        print(f"[i] Уникальные пути ({len(path_counts)}):")
        for path, cnt in path_counts.most_common(10):
            print(f"    [{cnt}x] {path}")
        exe_pids = [p for p, path in data_dict.items() if path.lower().endswith('.exe')]
        print(f"[i] PID с .exe ({len(exe_pids)} шт): {exe_pids}")
        return None, None

    file_path = data_dict[game_pid]
    print(f"[+] PID игры: {game_pid}")
    print(f"[+] Путь:    {file_path}")
    return file_path, game_pid


# ===================== Тестовый запуск =====================
if __name__ == "__main__":
    path, pid = check_current_active_window()
    if path:
        print(f"\nРезультат: PID={pid}, путь={path}")
    else:
        print("\nНе удалось определить активное игровое окно")
